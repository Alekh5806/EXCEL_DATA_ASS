from __future__ import annotations

from typing import Any, TypedDict

from .llm_answer import generate_final_answer
from .llm_sql import generate_sql_from_question
from .sql_runner import run_safe_select_sql


class ChatState(TypedDict, total=False):
    question: str
    llm_result: dict[str, Any]
    sql_result: dict[str, Any]
    response: dict[str, Any]


def run_langgraph_chat(question):
    graph = build_chat_graph()
    state = graph.invoke({"question": question})
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
    llm_result = generate_sql_from_question(state["question"])
    return {"llm_result": llm_result}


def run_sql_node(state: ChatState):
    llm_result = state.get("llm_result", {})
    sql = llm_result.get("sql", "").strip()
    if not llm_result.get("used_llm") or not sql:
        return {"sql_result": {"ok": False, "error": "", "sql": sql, "data": [], "columns": []}}
    return {"sql_result": run_safe_select_sql(sql)}


def finalize_node(state: ChatState):
    llm_result = state.get("llm_result", {})
    sql_result = state.get("sql_result", {})
    question = state["question"]

    if not llm_result.get("used_llm"):
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
        return {
            "response": {
                "answer": llm_result.get("clarification_question") or llm_result.get("explanation", ""),
                "sql": "",
                "data": [],
                "chart": None,
                "explanation": llm_result.get("explanation", ""),
            }
        }

    if not sql_result.get("ok"):
        return {
            "response": {
                "answer": f"I could not run the generated SQL because it was not safe: {sql_result.get('error', '')}",
                "sql": sql_result.get("sql", ""),
                "data": [],
                "chart": None,
                "explanation": llm_result.get("explanation", ""),
            }
        }

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