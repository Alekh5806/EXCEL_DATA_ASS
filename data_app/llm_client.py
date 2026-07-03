import json
import os

from openai import OpenAI


def is_llm_configured():
    return bool(os.environ.get("OPENAI_API_KEY") or os.environ.get("LLM_BASE_URL"))


def get_llm_model(default_model="gpt-4o-mini"):
    return os.environ.get("OPENAI_MODEL") or os.environ.get("LLM_MODEL") or default_model


def create_llm_client():
    base_url = os.environ.get("LLM_BASE_URL", "").strip()
    api_key = (
        os.environ.get("OPENAI_API_KEY")
        or os.environ.get("LLM_API_KEY")
        or "ollama"
    )

    if base_url:
        return OpenAI(base_url=base_url.rstrip("/"), api_key=api_key)
    return OpenAI(api_key=api_key)


def parse_json_content(content):
    text = (content or "").strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    return json.loads(text)