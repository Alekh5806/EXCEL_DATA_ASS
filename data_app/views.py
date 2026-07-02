from pathlib import Path
from tempfile import NamedTemporaryFile

from django.db.models import Avg, Max, Min
from django.utils.dateparse import parse_date
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .chatbot import answer_chat_message
from .importers import import_excel_workbook
from .models import ProcessData
from .serializers import ProcessDataSerializer


MEASUREMENT_COLUMNS = {
    "pygas_flow_rate",
    "biomass_flow_rate",
    "biomass_temperature",
    "reactor_gas_flow_rate",
    "reactor_gas_temperature",
    "heat_carrier_flow_rate",
    "heat_carrier_temperature",
    "product_gas_temperature",
    "heat_carrier_return_temperature",
}

COLUMN_ALIASES = {
    "temperature": "product_gas_temperature",
    "flow_rate": "pygas_flow_rate",
    "product_temperature": "product_gas_temperature",
    "product_gas_temp": "product_gas_temperature",
    "reactor_temperature": "reactor_gas_temperature",
    "reactor_gas_temp": "reactor_gas_temperature",
    "biomass_temp": "biomass_temperature",
    "heat_carrier_temp": "heat_carrier_temperature",
}

OPERATIONS = {
    "max": Max,
    "min": Min,
    "avg": Avg,
    "average": Avg,
}


@api_view(["GET"])
def health_check(request):
    return Response(
        {
            "status": "ok",
            "message": "Excel Data Intelligence Chatbot backend is running.",
        }
    )


@api_view(["GET"])
def data_list(request):
    queryset = ProcessData.objects.all()

    date_value = request.query_params.get("date")
    if date_value:
        parsed_date = parse_date(date_value)
        if parsed_date is None:
            return Response(
                {"error": "Invalid date. Use YYYY-MM-DD format."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        queryset = queryset.filter(date=parsed_date)

    limit = parse_positive_int(request.query_params.get("limit"), default=100, maximum=1000)
    serializer = ProcessDataSerializer(queryset[:limit], many=True)

    return Response(
        {
            "count": queryset.count(),
            "limit": limit,
            "results": serializer.data,
        }
    )


@api_view(["GET"])
def data_summary(request):
    queryset = ProcessData.objects.all()

    date_value = request.query_params.get("date")
    if date_value:
        parsed_date = parse_date(date_value)
        if parsed_date is None:
            return Response(
                {"error": "Invalid date. Use YYYY-MM-DD format."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        queryset = queryset.filter(date=parsed_date)

    summary = {"row_count": queryset.count()}
    for column in MEASUREMENT_COLUMNS:
        values = queryset.aggregate(
            minimum=Min(column),
            maximum=Max(column),
            average=Avg(column),
        )
        summary[column] = values

    return Response(
        {
            "date": date_value or "all",
            "summary": summary,
        }
    )


@api_view(["GET"])
def data_stats(request):
    column = normalize_column(request.query_params.get("column"))
    operation = request.query_params.get("operation", "").lower()
    date_value = request.query_params.get("date")

    if column not in MEASUREMENT_COLUMNS:
        return Response(
            {
                "error": "Invalid column.",
                "allowed_columns": sorted(MEASUREMENT_COLUMNS),
                "aliases": COLUMN_ALIASES,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    if operation not in OPERATIONS:
        return Response(
            {
                "error": "Invalid operation.",
                "allowed_operations": sorted(OPERATIONS.keys()),
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    queryset = ProcessData.objects.all()
    if date_value:
        parsed_date = parse_date(date_value)
        if parsed_date is None:
            return Response(
                {"error": "Invalid date. Use YYYY-MM-DD format."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        queryset = queryset.filter(date=parsed_date)

    aggregate_name = f"{operation}_{column}"
    result = queryset.aggregate(**{aggregate_name: OPERATIONS[operation](column)})

    return Response(
        {
            "column": column,
            "operation": operation,
            "date": date_value or "all",
            "value": result[aggregate_name],
            "row_count": queryset.count(),
        }
    )


@api_view(["POST"])
def chat(request):
    message = request.data.get("message", "")
    if not isinstance(message, str):
        return Response(
            {"error": "message must be a string."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return Response(answer_chat_message(message))


@api_view(["POST"])
def upload_excel(request):
    excel_file = request.FILES.get("file")
    replace_source = str(request.data.get("replace_source", "")).lower() in {"1", "true", "yes", "on"}
    source_file = Path(excel_file.name).name if excel_file else ""

    if excel_file is None:
        return Response(
            {"error": "Please upload an Excel file using the 'file' field."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not excel_file.name.lower().endswith(".xlsx"):
        return Response(
            {"error": "Only .xlsx files are supported right now."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if replace_source:
        ProcessData.objects.filter(source_file=source_file).delete()

    with NamedTemporaryFile(suffix=".xlsx") as temporary_file:
        for chunk in excel_file.chunks():
            temporary_file.write(chunk)
        temporary_file.flush()
        result = import_excel_workbook(temporary_file.name, source_file=source_file)

    return Response(
        {
            "message": f"Imported {result['rows_created']} rows from {result['source_file']}.",
            **result,
            "total_rows": ProcessData.objects.count(),
        },
        status=status.HTTP_201_CREATED,
    )


def normalize_column(column):
    if not column:
        return ""
    normalized = column.strip().lower()
    return COLUMN_ALIASES.get(normalized, normalized)


def parse_positive_int(value, default, maximum):
    if value is None:
        return default
    try:
        number = int(value)
    except ValueError:
        return default
    if number < 1:
        return default
    return min(number, maximum)
