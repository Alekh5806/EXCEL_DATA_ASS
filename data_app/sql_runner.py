from django.db import DatabaseError, connection

from .sql_security import ensure_limit, validate_select_sql


def run_safe_select_sql(sql):
    is_safe, message = validate_select_sql(sql)
    if not is_safe:
        return {
            "ok": False,
            "error": message,
            "sql": sql,
            "data": [],
            "columns": [],
        }

    limited_sql = ensure_limit(sql)
    is_safe, message = validate_select_sql(limited_sql)
    if not is_safe:
        return {
            "ok": False,
            "error": message,
            "sql": limited_sql,
            "data": [],
            "columns": [],
        }

    try:
        with connection.cursor() as cursor:
            cursor.execute(limited_sql)
            columns = [column[0] for column in cursor.description]
            rows = cursor.fetchall()
    except DatabaseError as exc:
        return {
            "ok": False,
            "error": f"Database error: {exc}",
            "sql": limited_sql,
            "data": [],
            "columns": [],
        }

    return {
        "ok": True,
        "error": "",
        "sql": limited_sql,
        "data": [dict(zip(columns, row)) for row in rows],
        "columns": columns,
    }
