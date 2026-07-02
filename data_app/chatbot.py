import re
from datetime import date
from math import sqrt

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
    selected_dates = extract_dates(lower_question)
    wants_chart = extract_chart_request(lower_question)
    wants_summary = extract_summary_request(lower_question)
    wants_compare = extract_compare_request(lower_question)
    wants_abnormal = extract_abnormal_request(lower_question)
    operation = extract_operation(lower_question)
    column = extract_column(lower_question)

    if wants_compare:
        if len(selected_dates) < 2:
            return clarification_response("Please mention two dates to compare, such as April 8 and April 9.")
        if column is None:
            return clarification_response("Please mention what to compare, such as temperature or biomass flow rate.")
        return build_compare_response(column, selected_dates[0], selected_dates[1])

    if wants_summary:
        if selected_date is None:
            return clarification_response("Please mention the day to summarize, such as April 8.")
        return build_summary_response(selected_date)

    if wants_abnormal:
        if column is None:
            column = "product_gas_temperature"
        return build_abnormal_response(column, selected_date)

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
            "chart": None,
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
        "chart": None,
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


def extract_summary_request(question):
    return any(word in question for word in ["summary", "summarize", "summarise", "overview"])


def extract_compare_request(question):
    return any(word in question for word in ["compare", "comparison", "versus", " vs "])


def extract_abnormal_request(question):
    return any(word in question for word in ["abnormal", "outlier", "outliers", "unusual", "anomaly"])


def build_summary_response(selected_date):
    queryset = ProcessData.objects.filter(date=selected_date)
    data = []

    for column in COLUMN_KEYWORDS:
        values = queryset.aggregate(
            minimum=Min(column),
            maximum=Max(column),
            average=Avg(column),
        )
        data.append(
            {
                "measurement": column,
                "minimum": values["minimum"],
                "maximum": values["maximum"],
                "average": round(values["average"], 4) if values["average"] is not None else None,
            }
        )

    row_count = queryset.count()
    return {
        "answer": f"Summary for {selected_date.isoformat()}: {row_count} rows were found.",
        "sql": f"SELECT MIN(...), MAX(...), AVG(...) FROM data_app_processdata WHERE date = '{selected_date.isoformat()}';",
        "data": data,
        "chart": None,
    }


def build_compare_response(column, first_date, second_date):
    data = []
    for selected_date in [first_date, second_date]:
        queryset = ProcessData.objects.filter(date=selected_date)
        values = queryset.aggregate(
            minimum=Min(column),
            maximum=Max(column),
            average=Avg(column),
            row_count=Count("id"),
        )
        data.append(
            {
                "date": selected_date.isoformat(),
                "minimum": values["minimum"],
                "maximum": values["maximum"],
                "average": round(values["average"], 4) if values["average"] is not None else None,
                "row_count": values["row_count"],
            }
        )

    first_average = data[0]["average"]
    second_average = data[1]["average"]
    if first_average is None or second_average is None:
        answer = f"I could not compare {humanize_column(column)} because one date is missing data."
    else:
        difference = round(second_average - first_average, 4)
        direction = "higher" if difference > 0 else "lower" if difference < 0 else "the same"
        answer = (
            f"The average {humanize_column(column)} on {second_date.isoformat()} was "
            f"{abs(difference)} {direction} than on {first_date.isoformat()}."
        )

    return {
        "answer": answer,
        "sql": (
            f"SELECT date, MIN({column}), MAX({column}), AVG({column}), COUNT(*) "
            f"FROM data_app_processdata WHERE date IN ('{first_date.isoformat()}', "
            f"'{second_date.isoformat()}') GROUP BY date;"
        ),
        "data": data,
        "chart": {
            "type": "line",
            "title": f"Average {humanize_column(column).title()} Comparison",
            "xKey": "date",
            "yKey": "average",
            "data": data,
        },
    }


def build_abnormal_response(column, selected_date):
    queryset = ProcessData.objects.exclude(**{column: None}).order_by("timestamp")
    if selected_date:
        queryset = queryset.filter(date=selected_date)

    rows = list(queryset.values("time", column))
    values = [row[column] for row in rows]
    if len(values) < 2:
        return {
            "answer": f"I could not detect abnormal {humanize_column(column)} values because there is not enough data.",
            "sql": build_abnormal_sql(column, selected_date),
            "data": [],
            "chart": None,
        }

    average = sum(values) / len(values)
    std_dev = sqrt(sum((value - average) ** 2 for value in values) / len(values))
    high_limit = average + (2 * std_dev)
    low_limit = average - (2 * std_dev)

    abnormal_rows = []
    for row in rows:
        value = row[column]
        if value > high_limit or value < low_limit:
            abnormal_rows.append(
                {
                    "time": row["time"].strftime("%H:%M") if row["time"] else "",
                    column: value,
                    "reason": "above expected range" if value > high_limit else "below expected range",
                }
            )

    data = abnormal_rows[:25]
    date_text = format_date_text(selected_date)
    answer = (
        f"I found {len(abnormal_rows)} abnormal {humanize_column(column)} values{date_text}. "
        f"The expected range is about {round(low_limit, 4)} to {round(high_limit, 4)}."
    )

    return {
        "answer": answer,
        "sql": build_abnormal_sql(column, selected_date),
        "data": data,
        "chart": {
            "type": "line",
            "title": f"Abnormal {humanize_column(column).title()} Values",
            "xKey": "time",
            "yKey": column,
            "data": data,
        }
        if data
        else None,
    }


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
    dates = extract_dates(question)
    return dates[0] if dates else None


def extract_dates(question):
    dates = []
    iso_match = re.search(r"\b\d{4}-\d{2}-\d{2}\b", question)
    for iso_match in re.finditer(r"\b\d{4}-\d{2}-\d{2}\b", question):
        parsed = parse_date(iso_match.group(0))
        if parsed:
            dates.append(parsed)

    month_pattern = (
        r"\b("
        + "|".join(MONTHS.keys())
        + r")\s+(\d{1,2})(?:,\s*(\d{4}))?\b"
    )
    for month_match in re.finditer(month_pattern, question):
        month = MONTHS[month_match.group(1)]
        day = int(month_match.group(2))
        year = int(month_match.group(3) or 2025)
        try:
            dates.append(date(year, month, day))
        except ValueError:
            continue

    return dates


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


def build_abnormal_sql(column, selected_date):
    sql = f"SELECT time, {column} FROM data_app_processdata WHERE {column} IS NOT NULL"
    if selected_date:
        sql += f" AND date = '{selected_date.isoformat()}'"
    return sql + " ORDER BY timestamp;"


def humanize_column(column):
    return column.replace("_", " ")


def format_date_text(selected_date):
    if selected_date is None:
        return ""
    return f" on {selected_date.isoformat()}"
