"""Thin wrapper around the Groq client. Every agent talks to the LLM only through here.
If GROQ_API_KEY is missing, llm_available() is False and agents use rule-based fallbacks."""
import json
import re
from typing import Optional

import config

_client = None


def llm_available() -> bool:
    return bool(config.GROQ_API_KEY)


def _get_client():
    global _client
    if _client is None:
        from groq import Groq
        _client = Groq(api_key=config.GROQ_API_KEY)
    return _client


def chat(system: str, user: str, temperature: float = 0.4, json_mode: bool = False) -> str:
    kwargs = {"response_format": {"type": "json_object"}} if json_mode else {}
    resp = _get_client().chat.completions.create(
        model=config.LLM_MODEL,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=temperature,
        **kwargs,
    )
    return (resp.choices[0].message.content or "").strip()


def chat_json(system: str, user: str) -> Optional[dict]:
    """Ask for JSON and parse it defensively. Returns None on any failure."""
    for json_mode in (True, False):
        try:
            text = chat(system, user, temperature=0.1, json_mode=json_mode)
            m = re.search(r"\{.*\}", text, re.DOTALL)
            if m:
                return json.loads(m.group(0))
        except Exception as e:  # noqa: BLE001
            print(f"[llm] chat_json failed (json_mode={json_mode}): {e}")
    return None


def grounded_explain(task: str, data, language: str, fallback: str) -> str:
    """LLM only *explains* data that was already retrieved. It may not add facts."""
    if not llm_available():
        return fallback
    system = (
        f"You are Swar Setu, a friendly voice assistant for Indian skilling beneficiaries. "
        f"Reply in {language}, in very simple words, at most 4 short sentences, suitable to be read aloud. "
        "Use ONLY facts present in DATA. Never invent jobs, schemes, eligibility, numbers or links. "
        "If DATA is empty, say honestly that nothing was found."
    )
    try:
        out = chat(system, f"Task: {task}\nDATA:\n{json.dumps(data, ensure_ascii=False)}", temperature=0.3)
        return out or fallback
    except Exception as e:  # noqa: BLE001
        print(f"[llm] grounded_explain failed: {e}")
        return fallback
