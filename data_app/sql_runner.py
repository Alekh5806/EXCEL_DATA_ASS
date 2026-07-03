import logging

from django.db import DatabaseError, connection

from .sql_security import ensure_limit, validate_select_sql


logger = logging.getLogger("data_app.sql_runner")


def run_safe_select_sql(sql):
    logger.info("sql validation started sql=%r", sql)
    is_safe, message = validate_select_sql(sql)
    if not is_safe:
        logger.warning("sql rejected before execution reason=%s sql=%r", message, sql)
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
        logger.warning("sql rejected after limit normalization reason=%s sql=%r", message, limited_sql)
        return {
            "ok": False,
            "error": message,
            "sql": limited_sql,
            "data": [],
            "columns": [],
        }

    try:
        logger.info("sql execution started sql=%r", limited_sql)
        with connection.cursor() as cursor:
            cursor.execute(limited_sql)
            columns = [column[0] for column in cursor.description]
            rows = cursor.fetchall()
    except DatabaseError as exc:
        logger.exception("sql execution failed sql=%r", limited_sql)
        return {
            "ok": False,
            "error": f"Database error: {exc}",
            "sql": limited_sql,
            "data": [],
            "columns": [],
        }

    logger.info("sql execution completed row_count=%s columns=%s", len(rows), columns)
    return {
        "ok": True,
        "error": "",
        "sql": limited_sql,
        "data": [dict(zip(columns, row)) for row in rows],
        "columns": columns,
    }
