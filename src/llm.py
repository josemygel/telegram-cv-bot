"""LLM backends: local Ollama, or any OpenAI-compatible API (LM Studio, Groq, vLLM...).

Strategy pattern: both backends implement LLMBackend.reply(messages) -> str and
share the SAME defensive response extraction. Two hard-won rules live here:

1. Reasoning models (e.g. Gemma-QAT, some Qwen variants) split their chain-of-thought
   into `reasoning_content` and the real answer into `content`. We read ONLY `content`
   and treat an empty/None content as a valid case to handle upstream — NEVER fall back
   to reasoning_content (it's internal scratch work, not a user-facing answer).
2. Transport failures (backend down, timeout) are translated to a domain BackendError
   so the Telegram layer can show a clear message instead of leaking a requests stack.
"""
from __future__ import annotations

from typing import Protocol

import requests

from .config import (
    LLM_MAX_TOKENS,
    LLM_MODEL,
    LLM_TEMPERATURE,
    OLLAMA_URL,
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
    OPENAI_MODEL,
)


class BackendError(RuntimeError):
    """Raised when the LLM backend is unreachable or returns an error.

    `retriable` lets the caller distinguish 'try again' (timeout / connection)
    from 'won't help to retry' (HTTP 4xx / malformed response).
    """

    def __init__(self, message: str, retriable: bool = True):
        super().__init__(message)
        self.retriable = retriable


class LLMBackend(Protocol):
    def reply(self, messages: list[dict]) -> str: ...


def _content_of(message: dict | None) -> str:
    """Extract the user-facing text from a chat message, defensively.

    `content` may be missing or None (reasoning models, truncated budgets); we
    normalize to '' so an empty turn is handled by the pipeline, not a KeyError.
    """
    return ((message or {}).get("content") or "").strip()


def _post_json(url: str, payload: dict, headers: dict | None = None, timeout: int = 120) -> dict:
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except requests.Timeout as exc:
        raise BackendError("El modelo tardó demasiado en responder (timeout).", retriable=True) from exc
    except requests.ConnectionError as exc:
        raise BackendError("No se puede conectar con el backend LLM (¿está LM Studio/Ollama encendido?).",
                           retriable=True) from exc
    except requests.HTTPError as exc:
        code = getattr(getattr(exc, "response", None), "status_code", "?")
        raise BackendError(f"El backend LLM devolvió un error HTTP {code}.", retriable=False) from exc
    except ValueError as exc:  # JSON decode failure
        raise BackendError("Respuesta no válida del backend LLM.", retriable=False) from exc


class OllamaLLM:
    """Local LLM via the Ollama chat API."""

    def reply(self, messages: list[dict]) -> str:
        data = _post_json(
            f"{OLLAMA_URL}/api/chat",
            {
                "model": LLM_MODEL,
                "messages": messages,
                "stream": False,
                "options": {"temperature": LLM_TEMPERATURE, "num_predict": LLM_MAX_TOKENS},
            },
        )
        return _content_of(data.get("message"))


class OpenAICompatLLM:
    """Any OpenAI-compatible endpoint — LM Studio (local), Groq, OpenRouter, vLLM.

    Sends max_tokens + temperature explicitly: max_tokens is generous so reasoning
    models don't starve the answer; temperature is low for grounded-QA fidelity.
    """

    def reply(self, messages: list[dict]) -> str:
        payload = {
            "model": OPENAI_MODEL,
            "messages": messages,
            "temperature": LLM_TEMPERATURE,
            "max_tokens": LLM_MAX_TOKENS,
            "stream": False,
        }
        headers = {
            "Authorization": f"Bearer {OPENAI_API_KEY or 'not-needed'}",
            "Content-Type": "application/json",
        }
        data = _post_json(f"{OPENAI_BASE_URL}/chat/completions", payload, headers)
        choices = data.get("choices") or []
        if not choices:
            return ""
        return _content_of(choices[0].get("message"))
