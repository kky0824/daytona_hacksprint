"""OpenAI-compatible client for the LLM served on Nosana."""
import json
import os
from pathlib import Path

from openai import OpenAI

_STATE = Path(__file__).resolve().parent.parent / "nosana_deployment.json"


def base_url() -> str:
    url = os.environ.get("LLM_BASE_URL")
    if not url and _STATE.exists():
        url = json.loads(_STATE.read_text()).get("llm_base_url")
    if not url:
        raise RuntimeError("LLM_BASE_URL not set; run `python -m core.nosana status` first")
    return url.rstrip("/") + ("" if url.rstrip("/").endswith("/v1") else "/v1")


def model() -> str:
    return os.environ.get("LLM_MODEL", "qwen3-14b")


def chat(messages, **kwargs) -> str:
    c = OpenAI(base_url=base_url(), api_key=os.environ.get("LLM_API_KEY", "none"))
    # Qwen3 thinks out loud by default; turn it off for faster, direct answers.
    extra_body = {"chat_template_kwargs": {"enable_thinking": False}, **kwargs.pop("extra_body", {})}
    r = c.chat.completions.create(model=model(), messages=messages, extra_body=extra_body, **kwargs)
    return r.choices[0].message.content
