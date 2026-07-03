import json
import logging

from .logging_utils import truncate_for_log
from .llm_client import create_llm_client, get_llm_model, is_llm_configured, parse_json_content
from .semantic_layer import build_semantic_layer_prompt
from .sql_security import ALLOWED_COLUMNS, ALLOWED_TABLES, ensure_limit, validate_select_sql


logger = logging.getLogger("data_app.llm_sql")


SQL_RESPONSE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "sql": {
            "type": "string",
            "description": "A safe SQLite SELECT query, or an empty string when clarification is needed.",
        },
        "explanation": {
            "type": "string",
            "description": "Short explanation of what the SQL does.",
        },
        "clarification_question": {
            "type": "string",
            "description": "Question to ask the user if the original request is unclear.",
        },
    },
    "required": ["sql", "explanation", "clarification_question"],
}


def generate_sql_from_question(question):
    if not is_llm_configured():
        logger.warning("llm sql generation skipped because no provider is configured")
        return {
            "sql": "",
            "explanation": "No LLM provider is configured, so the local fallback chatbot was used.",
            "clarification_question": "",
            "used_llm": False,
        }

    try:
        client = create_llm_client()
        model = get_llm_model("gpt-4o-mini")
        prompt = build_sql_prompt(question)
        logger.info("llm sql generation started model=%s question=%r", model, question)
        logger.debug("llm sql prompt=%s", truncate_for_log(prompt, 1500))

        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "You convert user questions about process data into safe SQLite SELECT queries. Return only raw JSON with keys sql, explanation, clarification_question.",
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content
        logger.info("llm sql raw response=%s", truncate_for_log(content, 1500))
        result = parse_json_content(content)
        # Some local models may omit optional keys; normalize shape for downstream nodes.
        result = {
            "sql": str(result.get("sql", "") or "").strip(),
            "explanation": str(result.get("explanation", "") or "").strip(),
            "clarification_question": str(result.get("clarification_question", "") or "").strip(),
        }
        sql = result["sql"]

        if sql:
            sql = ensure_limit(sql)
            is_safe, message = validate_select_sql(sql)
            if not is_safe:
                logger.warning("llm generated unsafe sql reason=%s sql=%r", message, sql)
                return {
                    "sql": "",
                    "explanation": f"The generated SQL was blocked: {message}",
                    "clarification_question": "Please ask a simpler question about the allowed process data columns.",
                    "used_llm": True,
                }
            result["sql"] = sql

        logger.info("llm sql generation completed has_sql=%s sql=%r", bool(result.get("sql")), result.get("sql", ""))
        result["used_llm"] = True
        return result
    except Exception as exc:
        message = str(exc)
        if "insufficient_quota" in message or "Error code: 429" in message:
            message = "The configured LLM provider rejected the request because the API quota is unavailable."
        logger.exception("llm sql generation failed question=%r", question)
        return {
            "sql": "",
            "explanation": f"LLM SQL generation failed, so the local fallback was used: {message}",
            "clarification_question": "",
            "used_llm": False,
        }


def build_sql_prompt(question):
    allowed_columns = "\n".join(f"- {column}" for column in sorted(ALLOWED_COLUMNS))
    allowed_tables = "\n".join(f"- {table}" for table in sorted(ALLOWED_TABLES))
    semantic_layer = build_semantic_layer_prompt()

    return f"""
User question:
{question}

Semantic layer:
{semantic_layer}

Database:
Table name:
{allowed_tables}

Allowed columns:
{allowed_columns}

Rules:
- Return only valid JSON with keys sql, explanation, clarification_question.
- Generate PostgreSQL-compatible SELECT SQL.
- Only generate SELECT queries.
- Use only the allowed table and allowed columns.
- Never use DELETE, UPDATE, DROP, INSERT, ALTER, CREATE, PRAGMA, VACUUM, or TRUNCATE.
- Prefer LIMIT 100 for row-list queries.
- If the user provides an explicit date or year, use it exactly in the SQL.
- Do not question or override the user's year just because the dataset may or may not contain rows for that year.
- If the user omits the year, you may infer a reasonable year from the data context, but do not do that when the year is already explicit.
- It is acceptable to generate SQL that returns zero rows when the requested date has no data.
- If the question is unclear, return an empty sql string and put a helpful question in clarification_question.

Return:
sql: the SELECT query
explanation: one short sentence explaining the query
clarification_question: empty string if SQL is clear, otherwise a question for the user
""".strip()
