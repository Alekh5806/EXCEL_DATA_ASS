from .langgraph_chat import run_langgraph_chat


def answer_chat_message(message):
    question = (message or "").strip()
    if not question:
        return {
            "answer": "Please ask a question about the process data.",
            "sql": "",
            "data": [],
            "chart": None,
        }

    return run_langgraph_chat(question)