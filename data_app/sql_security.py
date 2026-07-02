import re

import sqlparse


ALLOWED_TABLES = {"data_app_processdata"}

ALLOWED_COLUMNS = {
    "id",
    "timestamp",
    "date",
    "time",
    "pygas_flow_rate",
    "biomass_flow_rate",
    "biomass_temperature",
    "reactor_gas_flow_rate",
    "reactor_gas_temperature",
    "heat_carrier_flow_rate",
    "heat_carrier_temperature",
    "product_gas_temperature",
    "heat_carrier_return_temperature",
    "stage",
    "notes",
    "source_file",
    "imported_at",
}

ALLOWED_FUNCTIONS = {"max", "min", "avg", "count", "sum", "date", "time"}

ALLOWED_OUTPUT_ALIASES = {
    "average",
    "count",
    "maximum",
    "minimum",
    "total",
    "value",
}

FORBIDDEN_KEYWORDS = {
    "alter",
    "attach",
    "create",
    "delete",
    "detach",
    "drop",
    "insert",
    "pragma",
    "replace",
    "truncate",
    "update",
    "vacuum",
}


def validate_select_sql(sql):
    if not sql or not isinstance(sql, str):
        return False, "SQL is empty."

    clean_sql = sql.strip()
    parsed = sqlparse.parse(clean_sql)

    if len(parsed) != 1:
        return False, "Only one SQL statement is allowed."

    statement = parsed[0]
    if statement.get_type() != "SELECT":
        return False, "Only SELECT queries are allowed."

    lowered = clean_sql.lower()
    if any(re.search(rf"\b{keyword}\b", lowered) for keyword in FORBIDDEN_KEYWORDS):
        return False, "Dangerous SQL keyword detected."

    if ";" in clean_sql[:-1]:
        return False, "Multiple SQL statements are not allowed."

    table_names = extract_table_names(lowered)
    if not table_names:
        return False, "Query must include an allowed table."

    if not table_names.issubset(ALLOWED_TABLES):
        return False, "Query uses a table that is not allowed."

    identifiers = extract_identifiers(lowered)
    unknown_identifiers = (
        identifiers
        - ALLOWED_COLUMNS
        - ALLOWED_TABLES
        - ALLOWED_FUNCTIONS
        - ALLOWED_OUTPUT_ALIASES
    )
    if unknown_identifiers:
        return False, f"Unknown column or function: {', '.join(sorted(unknown_identifiers))}."

    return True, "SQL is safe."


def ensure_limit(sql, limit=100):
    lowered = sql.lower()
    if re.search(r"\blimit\s+\d+\b", lowered):
        return sql

    sql_without_semicolon = sql.rstrip().rstrip(";")
    return f"{sql_without_semicolon} LIMIT {limit};"


def extract_table_names(lowered_sql):
    tables = set()
    matches = re.findall(r"\bfrom\s+([a-zA-Z_][a-zA-Z0-9_]*)", lowered_sql)
    matches += re.findall(r"\bjoin\s+([a-zA-Z_][a-zA-Z0-9_]*)", lowered_sql)
    for match in matches:
        tables.add(match)
    return tables


def extract_identifiers(lowered_sql):
    without_strings = re.sub(r"'[^']*'|\"[^\"]*\"", " ", lowered_sql)
    words = set(re.findall(r"\b[a-zA-Z_][a-zA-Z0-9_]*\b", without_strings))
    sql_words = {
        "as",
        "asc",
        "and",
        "between",
        "by",
        "desc",
        "from",
        "group",
        "having",
        "in",
        "is",
        "limit",
        "not",
        "null",
        "or",
        "order",
        "select",
        "where",
    }
    return words - sql_words
