from pathlib import Path
from os import unlink
from tempfile import NamedTemporaryFile
import logging

from django.db.models import Avg, Count, Max, Min, Q
from django.utils.dateparse import parse_date
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .chatbot import answer_chat_message
from .importers import import_excel_workbook
from .models import ProcessData
from .serializers import ProcessDataSerializer


logger = logging.getLogger("data_app.views")


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

QUERYABLE_FIELDS = [
    field_name for field_name in ProcessDataSerializer.Meta.fields if field_name != "id"
]
TEXT_FIELDS = {"stage", "notes"}
AUDIT_FIELDS = {"source_file"}
COLUMN_DISTRIBUTION = [
    {"name": "Numeric", "value": len(MEASUREMENT_COLUMNS), "color": "#7c4dff"},
    {"name": "Text", "value": len(TEXT_FIELDS), "color": "#06b6d4"},
    {"name": "Date/Time", "value": 4, "color": "#3b82f6"},
    {"name": "Audit", "value": len(AUDIT_FIELDS), "color": "#8b5cf6"},
]


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

    overview = build_overview_payload(queryset, summary)

    return Response(
        {
            "date": date_value or "all",
            "summary": summary,
            "overview": overview,
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

    logger.info("chat request received question=%r", message)
    response_payload = answer_chat_message(message)
    logger.info(
        "chat response generated has_sql=%s row_count=%s answer_preview=%r",
        bool(response_payload.get("sql")),
        len(response_payload.get("data", [])),
        str(response_payload.get("answer", ""))[:200],
    )
    return Response(response_payload)


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

    with NamedTemporaryFile(suffix=".xlsx", delete=False) as temporary_file:
        for chunk in excel_file.chunks():
            temporary_file.write(chunk)
        temporary_file.flush()
        temp_file_path = temporary_file.name

    try:
        result = import_excel_workbook(temp_file_path, source_file=source_file)
    finally:
        try:
            unlink(temp_file_path)
        except FileNotFoundError:
            pass

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


def build_overview_payload(queryset, summary):
    date_bounds = queryset.aggregate(start=Min("date"), end=Max("date"))
    latest_row = queryset.order_by("-imported_at", "-id").first()
    source_files = [
        source_file
        for source_file in queryset.order_by().values_list("source_file", flat=True).distinct()
        if source_file
    ]
    distinct_stage_count = queryset.exclude(stage="").values("stage").distinct().count()

    completeness_aggregates = {}
    for field_name in QUERYABLE_FIELDS:
        aggregate_name = f"{field_name}_count"
        if field_name in TEXT_FIELDS or field_name in AUDIT_FIELDS:
            completeness_aggregates[aggregate_name] = Count(
                field_name,
                filter=~Q(**{field_name: ""}),
            )
        else:
            completeness_aggregates[aggregate_name] = Count(field_name)

    completeness_counts = queryset.aggregate(**completeness_aggregates)
    filled_values = sum(completeness_counts.values())
    total_values = summary["row_count"] * len(QUERYABLE_FIELDS)
    quality_score = round((filled_values / total_values) * 100, 1) if total_values else 0.0

    return {
        "total_rows": summary["row_count"],
        "total_columns": len(QUERYABLE_FIELDS),
        "date_range": {
            "start": date_bounds["start"].isoformat() if date_bounds["start"] else None,
            "end": date_bounds["end"].isoformat() if date_bounds["end"] else None,
            "label": format_date_range_label(date_bounds["start"], date_bounds["end"]),
        },
        "latest_source_file": latest_row.source_file if latest_row else "",
        "source_file_count": len(source_files),
        "source_files": source_files,
        "latest_imported_at": latest_row.imported_at.isoformat() if latest_row and latest_row.imported_at else None,
        "column_distribution": COLUMN_DISTRIBUTION,
        "insights": {
            "highest_biomass_temperature": summary["biomass_temperature"]["maximum"],
            "avg_reactor_flow": summary["reactor_gas_flow_rate"]["average"],
            "distinct_stages": distinct_stage_count,
            "data_quality_score": quality_score,
        },
    }


def format_date_range_label(start_date, end_date):
    if not start_date or not end_date:
        return "No dates available"
    return f"{format_month_day(start_date)} - {format_month_day(end_date)}, {end_date.year}"


def format_month_day(value):
    return value.strftime("%b %d").replace(" 0", " ")
