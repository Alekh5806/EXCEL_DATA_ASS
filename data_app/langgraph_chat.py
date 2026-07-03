from __future__ import annotations

import logging
from typing import Any, TypedDict

from .logging_utils import truncate_for_log
from .llm_answer import generate_final_answer
from .llm_sql import generate_sql_from_question
from .sql_runner import run_safe_select_sql


logger = logging.getLogger("data_app.langgraph_chat")


class ChatState(TypedDict, total=False):
    question: str
    llm_result: dict[str, Any]
    sql_result: dict[str, Any]
    response: dict[str, Any]


def run_langgraph_chat(question):
    logger.info("langgraph chat started question=%r", question)
    graph = build_chat_graph()
    state = graph.invoke({"question": question})
    logger.info(
        "langgraph chat finished has_sql=%s answer_preview=%r",
        bool(state["response"].get("sql")),
        truncate_for_log(state["response"].get("answer", ""), 200),
    )
    return state["response"]


def build_chat_graph():
    from langgraph.graph import END, StateGraph

    graph = StateGraph(ChatState)
    graph.add_node("generate_sql", generate_sql_node)
    graph.add_node("run_sql", run_sql_node)
    graph.add_node("finalize", finalize_node)
    graph.set_entry_point("generate_sql")
    graph.add_edge("generate_sql", "run_sql")
    graph.add_edge("run_sql", "finalize")
    graph.add_edge("finalize", END)
    return graph.compile()


def generate_sql_node(state: ChatState):
    logger.info("generate_sql node started question=%r", state["question"])
    llm_result = generate_sql_from_question(state["question"])
    logger.info(
        "generate_sql node completed used_llm=%s has_sql=%s explanation=%r clarification=%r",
        llm_result.get("used_llm"),
        bool(llm_result.get("sql")),
        truncate_for_log(llm_result.get("explanation", ""), 200),
        truncate_for_log(llm_result.get("clarification_question", ""), 200),
    )
    return {"llm_result": llm_result}


def run_sql_node(state: ChatState):
    llm_result = state.get("llm_result", {})
    sql = llm_result.get("sql", "").strip()
    if not llm_result.get("used_llm") or not sql:
        logger.info(
            "run_sql node skipped used_llm=%s has_sql=%s explanation=%r",
            llm_result.get("used_llm"),
            bool(sql),
            truncate_for_log(llm_result.get("explanation", ""), 200),
        )
        return {"sql_result": {"ok": False, "error": "", "sql": sql, "data": [], "columns": []}}
    logger.info("run_sql node executing sql=%r", sql)
    return {"sql_result": run_safe_select_sql(sql)}


def finalize_node(state: ChatState):
    llm_result = state.get("llm_result", {})
    sql_result = state.get("sql_result", {})
    question = state["question"]
    logger.info(
        "finalize node started used_llm=%s has_sql=%s sql_ok=%s row_count=%s",
        llm_result.get("used_llm"),
        bool(llm_result.get("sql")),
        sql_result.get("ok"),
        len(sql_result.get("data", [])),
    )

    if not llm_result.get("used_llm"):
        logger.warning("finalize node returning llm unavailable explanation=%r", llm_result.get("explanation", ""))
        return {
            "response": {
                "answer": llm_result.get(
                    "explanation",
                    "The LLM path is unavailable. Check OPENAI_API_KEY and restart the server after updating .env.",
                ),
                "sql": "",
                "data": [],
                "chart": None,
                "explanation": llm_result.get("explanation", ""),
            }
        }

    if not llm_result.get("sql"):
        logger.info("finalize node returning clarification no sql generated")
        fallback_answer = (
            llm_result.get("clarification_question")
            or llm_result.get("explanation")
            or "I could not generate SQL for that request. Please rephrase with a metric and date, for example: 'What was the highest product_gas_temperature on 2025-04-08?'"
        )
        return {
            "response": {
                "answer": fallback_answer,
                "sql": "",
                "data": [],
                "chart": None,
                "explanation": llm_result.get("explanation", ""),
            }
        }

    if not sql_result.get("ok"):
        logger.warning("finalize node returning sql execution failure error=%r", sql_result.get("error", ""))
        return {
            "response": {
                "answer": f"I could not run the generated SQL because it was not safe: {sql_result.get('error', '')}",
                "sql": sql_result.get("sql", ""),
                "data": [],
                "chart": None,
                "explanation": llm_result.get("explanation", ""),
            }
        }

    logger.info("finalize node generating natural language answer from sql result")
    return {
        "response": {
            "answer": generate_final_answer(
                question,
                sql_result["sql"],
                sql_result["data"],
                llm_result.get("explanation", ""),
            ),
            "sql": sql_result["sql"],
            "data": sql_result["data"],
            "chart": None,
            "explanation": llm_result.get("explanation", ""),
        }
    }