import json
import logging

from .logging_utils import truncate_for_log
from .llm_client import create_llm_client, get_llm_model, is_llm_configured, parse_json_content


logger = logging.getLogger("data_app.llm_answer")

ANSWER_RESPONSE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "answer": {
            "type": "string",
            "description": "Simple human-friendly answer based only on the SQL result.",
        },
        "data_missing": {
            "type": "boolean",
            "description": "True when the SQL result is empty or does not contain enough data.",
        },
    },
    "required": ["answer", "data_missing"],
}


def generate_final_answer(question, sql, data, sql_explanation=""):
    if not is_llm_configured():
        logger.warning("final answer generation skipped because no LLM provider is configured")
        return build_fallback_answer(data)

    try:
        client = create_llm_client()
        model = get_llm_model("gpt-4o-mini")
        logger.info(
            "final answer generation started model=%s sql=%r row_count=%s",
            model,
            sql,
            len(data or []),
        )

        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You explain database query results in simple language. "
                        "Use only the SQL result data. Do not invent values. "
                        "Return only raw JSON with keys answer and data_missing."
                    ),
                },
                {
                    "role": "user",
                    "content": build_answer_prompt(question, sql, data, sql_explanation),
                },
            ],
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content
        logger.info("final answer raw response=%s", truncate_for_log(content, 1000))
        result = parse_json_content(content)
        return result["answer"]
    except Exception:
        logger.exception("final answer generation failed; using deterministic fallback")
        return build_fallback_answer(data)


def build_answer_prompt(question, sql, data, sql_explanation=""):
    return f"""
User question:
{question}

Safe SQL that was executed:
{sql}

SQL explanation:
{sql_explanation}

SQL result as JSON:
{json.dumps(data, default=str)}

Rules:
- Answer only from the SQL result above.
- If the result is empty, say the data is missing.
- If a value is null, say the matching data is missing.
- Use simple language for a beginner.
- Do not mention internal implementation details.
- Do not invent causes, units, trends, or values that are not in the SQL result.
- If there are multiple rows, summarize what the rows show.
""".strip()


def build_fallback_answer(data):
    if not data:
        return "I ran the query, but no matching data was found."

    if len(data) == 1:
        first_row = data[0]
        if len(first_row) == 1:
            column, value = next(iter(first_row.items()))
            if value is None:
                return f"I ran the query, but {column} was missing in the matching data."
            return f"The result is {round(value, 4) if isinstance(value, float) else value}."

    return f"I found {len(data)} matching rows."
