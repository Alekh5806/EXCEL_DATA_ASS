import json
import os

from openai import OpenAI

from .sql_security import ALLOWED_COLUMNS, ALLOWED_TABLES, ensure_limit, validate_select_sql


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
    if not os.environ.get("OPENAI_API_KEY"):
        return {
            "sql": "",
            "explanation": "OPENAI_API_KEY is not set, so the local fallback chatbot was used.",
            "clarification_question": "",
            "used_llm": False,
        }

    client = OpenAI()
    model = os.environ.get("OPENAI_MODEL", "gpt-5.2")
    prompt = build_sql_prompt(question)

    response = client.responses.create(
        model=model,
        input=[
            {
                "role": "developer",
                "content": "You convert user questions about process data into safe SQLite SELECT queries.",
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": "sql_generation_response",
                "strict": True,
                "schema": SQL_RESPONSE_SCHEMA,
            }
        },
    )

    result = json.loads(response.output_text)
    sql = result.get("sql", "").strip()

    if sql:
        sql = ensure_limit(sql)
        is_safe, message = validate_select_sql(sql)
        if not is_safe:
            return {
                "sql": "",
                "explanation": f"The generated SQL was blocked: {message}",
                "clarification_question": "Please ask a simpler question about the allowed process data columns.",
                "used_llm": True,
            }
        result["sql"] = sql

    result["used_llm"] = True
    return result


def build_sql_prompt(question):
    allowed_columns = "\n".join(f"- {column}" for column in sorted(ALLOWED_COLUMNS))
    allowed_tables = "\n".join(f"- {table}" for table in sorted(ALLOWED_TABLES))

    return f"""
User question:
{question}

Database:
Table name:
{allowed_tables}

Allowed columns:
{allowed_columns}

Rules:
- Return only JSON that matches the schema.
- Generate SQLite SQL.
- Only generate SELECT queries.
- Use only the allowed table and allowed columns.
- Never use DELETE, UPDATE, DROP, INSERT, ALTER, CREATE, PRAGMA, VACUUM, or TRUNCATE.
- Prefer LIMIT 100 for row-list queries.
- For April 8 without a year, use 2025-04-08 because this dataset is from 2025.
- If the question is unclear, return an empty sql string and put a helpful question in clarification_question.

Return:
sql: the SELECT query
explanation: one short sentence explaining the query
clarification_question: empty string if SQL is clear, otherwise a question for the user
""".strip()
