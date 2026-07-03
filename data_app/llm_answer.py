import json
import os

from openai import OpenAI


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
    if not os.environ.get("OPENAI_API_KEY"):
        return build_fallback_answer(data)

    try:
        client = OpenAI()
        model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

        response = client.responses.create(
            model=model,
            input=[
                {
                    "role": "developer",
                    "content": (
                        "You explain database query results in simple language. "
                        "Use only the SQL result data. Do not invent values."
                    ),
                },
                {
                    "role": "user",
                    "content": build_answer_prompt(question, sql, data, sql_explanation),
                },
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "final_answer_response",
                    "strict": True,
                    "schema": ANSWER_RESPONSE_SCHEMA,
                }
            },
        )

        result = json.loads(response.output_text)
        return result["answer"]
    except Exception:
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
