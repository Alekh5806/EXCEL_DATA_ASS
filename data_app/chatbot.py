import re
from datetime import date

from django.db.models import Avg, Count, Max, Min
from django.utils.dateparse import parse_date

from .llm_answer import generate_final_answer
from .llm_sql import generate_sql_from_question
from .models import ProcessData
from .sql_runner import run_safe_select_sql


MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}

COLUMN_KEYWORDS = {
    "product_gas_temperature": ["product gas temperature", "product temperature", "temperature"],
    "reactor_gas_temperature": ["reactor gas temperature", "reactor temperature"],
    "biomass_temperature": ["biomass temperature"],
    "heat_carrier_temperature": ["heat carrier temperature"],
    "heat_carrier_return_temperature": ["heat carrier return temperature", "return temperature"],
    "pygas_flow_rate": ["pygas flow rate", "pygas flow"],
    "biomass_flow_rate": ["biomass flow rate", "biomass flow"],
    "reactor_gas_flow_rate": ["reactor gas flow rate", "reactor gas flow"],
    "heat_carrier_flow_rate": ["heat carrier flow rate", "heat carrier flow"],
}

OPERATIONS = {
    "max": {
        "keywords": ["highest", "maximum", "max", "peak"],
        "aggregate": Max,
        "sql_function": "MAX",
        "label": "highest",
    },
    "min": {
        "keywords": ["lowest", "minimum", "min"],
        "aggregate": Min,
        "sql_function": "MIN",
        "label": "lowest",
    },
    "avg": {
        "keywords": ["average", "avg", "mean"],
        "aggregate": Avg,
        "sql_function": "AVG",
        "label": "average",
    },
    "count": {
        "keywords": ["how many", "count", "number of rows"],
        "aggregate": Count,
        "sql_function": "COUNT",
        "label": "row count",
    },
}


def answer_chat_message(message):
    question = (message or "").strip()
    if not question:
        return clarification_response("Please ask a question about the process data.")

    llm_result = generate_sql_from_question(question)
    if llm_result["used_llm"]:
        if llm_result["sql"]:
            sql_result = run_safe_select_sql(llm_result["sql"])
            if not sql_result["ok"]:
                return {
                    "answer": f"I could not run the generated SQL because it was not safe: {sql_result['error']}",
                    "sql": sql_result["sql"],
                    "data": [],
                    "explanation": llm_result["explanation"],
                }
            return {
                "answer": generate_final_answer(
                    question,
                    sql_result["sql"],
                    sql_result["data"],
                    llm_result["explanation"],
                ),
                "sql": sql_result["sql"],
                "data": sql_result["data"],
                "explanation": llm_result["explanation"],
            }
        return {
            "answer": llm_result["clarification_question"] or llm_result["explanation"],
            "sql": "",
            "data": [],
            "explanation": llm_result["explanation"],
        }

    lower_question = question.lower()
    selected_date = extract_date(lower_question)
    wants_chart = extract_chart_request(lower_question)
    operation = extract_operation(lower_question)
    column = extract_column(lower_question)

    if wants_chart:
        if column is None:
            return clarification_response(
                "Please mention what to chart, such as product gas temperature or biomass flow rate."
            )
        return build_trend_response(column, selected_date)

    if operation is None:
        return clarification_response(
            "Please ask for a max, min, average, count, or trend. For example: Show temperature trend on April 8."
        )

    if operation != "count" and column is None:
        return clarification_response(
            "Please mention a measurement column, such as product gas temperature or biomass flow rate."
        )

    queryset = ProcessData.objects.all()
    if selected_date:
        queryset = queryset.filter(date=selected_date)

    if operation == "count":
        value = queryset.count()
        sql = build_count_sql(selected_date)
        data = [{"count": value}]
        date_text = format_date_text(selected_date)
        return {
            "answer": f"There are {value} rows{date_text}.",
            "sql": sql,
            "data": data,
        }

    aggregate_name = "value"
    result = queryset.aggregate(**{aggregate_name: OPERATIONS[operation]["aggregate"](column)})
    value = result[aggregate_name]
    sql = build_stat_sql(operation, column, selected_date)
    data = [{aggregate_name: value}]

    if value is None:
        answer = f"I could not find data for {humanize_column(column)}{format_date_text(selected_date)}."
    else:
        answer = (
            f"The {OPERATIONS[operation]['label']} {humanize_column(column)}"
            f"{format_date_text(selected_date)} was {round(value, 4)}."
        )

    return {
        "answer": answer,
        "sql": sql,
        "data": data,
    }


def clarification_response(answer):
    return {
        "answer": answer,
        "sql": "",
        "data": [],
        "chart": None,
    }


def extract_chart_request(question):
    chart_words = ["chart", "graph", "plot", "trend", "show"]
    return any(word in question for word in chart_words)


def build_trend_response(column, selected_date):
    queryset = ProcessData.objects.exclude(**{column: None}).order_by("timestamp")
    if selected_date:
        queryset = queryset.filter(date=selected_date)

    rows = list(queryset.values("time", column)[:300])
    data = [
        {
            "time": row["time"].strftime("%H:%M") if row["time"] else "",
            column: row[column],
        }
        for row in rows
    ]
    sql = build_trend_sql(column, selected_date)
    date_text = format_date_text(selected_date)

    if not data:
        answer = f"I could not find chart data for {humanize_column(column)}{date_text}."
    else:
        answer = (
            f"Here is the {humanize_column(column)} trend{date_text}. "
            f"I returned {len(data)} chart points."
        )

    return {
        "answer": answer,
        "sql": sql,
        "data": data,
        "chart": {
            "type": "line",
            "title": f"{humanize_column(column).title()} Trend",
            "xKey": "time",
            "yKey": column,
            "data": data,
        },
    }


def extract_operation(question):
    for operation, config in OPERATIONS.items():
        if any(keyword in question for keyword in config["keywords"]):
            return operation
    return None


def extract_column(question):
    for column, keywords in COLUMN_KEYWORDS.items():
        if any(keyword in question for keyword in keywords):
            return column
    return None


def extract_date(question):
    iso_match = re.search(r"\b\d{4}-\d{2}-\d{2}\b", question)
    if iso_match:
        return parse_date(iso_match.group(0))

    month_match = re.search(
        r"\b("
        + "|".join(MONTHS.keys())
        + r")\s+(\d{1,2})(?:,\s*(\d{4}))?\b",
        question,
    )
    if month_match:
        month = MONTHS[month_match.group(1)]
        day = int(month_match.group(2))
        year = int(month_match.group(3) or 2025)
        try:
            return date(year, month, day)
        except ValueError:
            return None

    return None


def build_stat_sql(operation, column, selected_date):
    sql_function = OPERATIONS[operation]["sql_function"]
    sql = f"SELECT {sql_function}({column}) AS value FROM data_app_processdata"
    if selected_date:
        sql += f" WHERE date = '{selected_date.isoformat()}'"
    return sql + ";"


def build_count_sql(selected_date):
    sql = "SELECT COUNT(*) AS count FROM data_app_processdata"
    if selected_date:
        sql += f" WHERE date = '{selected_date.isoformat()}'"
    return sql + ";"


def build_trend_sql(column, selected_date):
    sql = f"SELECT time, {column} FROM data_app_processdata WHERE {column} IS NOT NULL"
    if selected_date:
        sql += f" AND date = '{selected_date.isoformat()}'"
    return sql + " ORDER BY timestamp LIMIT 300;"


def humanize_column(column):
    return column.replace("_", " ")


def format_date_text(selected_date):
    if selected_date is None:
        return ""
    return f" on {selected_date.isoformat()}"
