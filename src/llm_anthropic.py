"""Backend nativo de Anthropic (Claude) con el SDK oficial.

POR QUE no basta con apuntar OPENAI_BASE_URL a Anthropic:
1. OpenAICompatLLM siempre manda `temperature`; Haiku 5.5 devuelve 400 con cualquier
   valor de muestreo no por defecto, asi que CADA mensaje fallaria. Aqui nunca se envia
   `temperature` ni `thinking` (omitir thinking = adaptativo; `budget_tokens` da 400).
2. El razonamiento adaptativo se factura como salida: para QA sobre un CV basta
   `effort: "low"` (ANTHROPIC_EFFORT).
3. La vision usa bloques `image` base64, no `image_url`.

Misma regla que llm.py: solo se devuelven bloques `text`; los `thinking` son borrador
interno y jamas se muestran.
"""
from __future__ import annotations

import logging
import threading
from typing import Callable

import anthropic

from .config import (
    ANTHROPIC_API_KEY, ANTHROPIC_EFFORT, ANTHROPIC_MAX_TOKENS, ANTHROPIC_MODEL, BOT_LANG,
)
from .i18n import I18n
from .llm import BackendError
from .token_ledger import TokenUsage, estimate_cost_usd

log = logging.getLogger("josembot.anthropic")


def _split_data_url(url: str) -> tuple[str, str] | None:
    """'data:image/png;base64,XXXX' -> ('image/png', 'XXXX'). Cualquier otra URL -> None:
    el bot nunca descarga URLs remotas (superficie de abuso/SSRF)."""
    if not url.startswith("data:") or ";base64," not in url:
        return None
    head, data = url[5:].split(";base64,", 1)
    return (head or "image/jpeg"), data


def _convert_parts(content) -> str | list[dict]:
    """Contenido estilo OpenAI (str | lista de partes) -> contenido de la Messages API."""
    if isinstance(content, str):
        return content
    blocks: list[dict] = []
    for part in content or []:
        if part.get("type") == "text" and part.get("text"):
            blocks.append({"type": "text", "text": part["text"]})
        elif part.get("type") == "image_url":
            parsed = _split_data_url((part.get("image_url") or {}).get("url", ""))
            if parsed:
                media, data = parsed
                blocks.append({"type": "image", "source": {"type": "base64", "media_type": media, "data": data}})
    return blocks


def convert_messages(messages: list[dict]) -> tuple[list[dict], list[dict]]:
    """Mensajes estilo OpenAI -> (system, messages) de Anthropic.

    - Los `system` van al parametro de nivel superior; `cache_control` solo en el
      ULTIMO bloque: el perfil es el prefijo grande y estable, y la cache cubre todo
      lo anterior al marcador (nada volatil debe ir antes).
    - La API exige que el primer mensaje sea `user`: se descartan turnos `assistant`
      iniciales.
    """
    system = [{"type": "text", "text": m["content"]}
              for m in messages if m.get("role") == "system" and m.get("content")]
    if system:
        system[-1]["cache_control"] = {"type": "ephemeral"}
    turns: list[dict] = []
    for m in messages:
        if m.get("role") not in ("user", "assistant"):
            continue
        content = _convert_parts(m.get("content"))
        if not content:  # la API rechaza texto/bloques vacios
            continue
        if not turns and m["role"] == "assistant":
            continue
        turns.append({"role": m["role"], "content": content})
    return system, turns


def _usage_of(resp) -> TokenUsage:
    u = getattr(resp, "usage", None)
    return TokenUsage(
        input_tokens=getattr(u, "input_tokens", 0) or 0,
        output_tokens=getattr(u, "output_tokens", 0) or 0,
        cache_read_tokens=getattr(u, "cache_read_input_tokens", 0) or 0,
        cache_creation_tokens=getattr(u, "cache_creation_input_tokens", 0) or 0,
    )


def _translate(exc: Exception) -> BackendError:
    """Excepciones del SDK -> BackendError. Lo MAS especifico primero: APITimeoutError
    hereda de APIConnectionError, y todas de APIError. Nunca se vuelca la clave."""
    if isinstance(exc, anthropic.APITimeoutError):
        return BackendError("El modelo tardó demasiado en responder (timeout).", retriable=True)
    if isinstance(exc, anthropic.APIConnectionError):
        return BackendError("No se puede conectar con la API de Anthropic.", retriable=True)
    if isinstance(exc, anthropic.RateLimitError):
        return BackendError("La API de Anthropic está saturada (límite de peticiones).", retriable=True)
    if isinstance(exc, (anthropic.AuthenticationError, anthropic.PermissionDeniedError)):
        return BackendError("Anthropic rechazó las credenciales (revisa ANTHROPIC_API_KEY).", retriable=False)
    if isinstance(exc, (anthropic.BadRequestError, anthropic.NotFoundError)):
        return BackendError("Anthropic rechazó la petición (revisa ANTHROPIC_MODEL y los parámetros).",
                            retriable=False)
    status = getattr(exc, "status_code", 0) or 0
    if isinstance(exc, anthropic.APIStatusError):
        return BackendError(f"La API de Anthropic devolvió un error HTTP {status}.", retriable=status >= 500)
    return BackendError("Error inesperado con la API de Anthropic.", retriable=False)


class AnthropicLLM:
    """LLMBackend sobre la Messages API de Claude."""

    def __init__(self, client=None, on_usage: Callable[[TokenUsage], None] | None = None):
        self._client = client  # perezoso: sin clave el bot arranca y falla solo al usarse
        self.on_usage = on_usage
        self._local = threading.local()  # pipeline.process_* corre en hilos distintos

    @property
    def last_usage(self) -> TokenUsage | None:
        return getattr(self._local, "usage", None)

    def _get_client(self):
        if self._client is None:
            self._client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY, max_retries=3, timeout=60)
        return self._client

    def reply(self, messages: list[dict]) -> str:
        system, turns = convert_messages(messages)
        if not turns:
            return ""
        try:
            resp = self._get_client().messages.create(
                model=ANTHROPIC_MODEL,
                max_tokens=ANTHROPIC_MAX_TOKENS,
                system=system,
                messages=turns,
                output_config={"effort": ANTHROPIC_EFFORT},
            )
        except Exception as exc:  # noqa: BLE001 - traducimos todo a BackendError
            raise _translate(exc) from exc

        usage = _usage_of(resp)
        self._local.usage = usage
        log.info("claude model=%s in=%d out=%d cache_read=%d cache_write=%d est_usd=%.6f",
                 ANTHROPIC_MODEL, usage.input_tokens, usage.output_tokens,
                 usage.cache_read_tokens, usage.cache_creation_tokens, estimate_cost_usd(usage))
        if self.on_usage:
            self.on_usage(usage)

        stop = getattr(resp, "stop_reason", None)
        if stop == "refusal":
            return I18n().t("llm_refusal", BOT_LANG)
        if stop == "max_tokens":
            log.warning("Respuesta cortada por max_tokens=%d", ANTHROPIC_MAX_TOKENS)
        text = "".join(b.text for b in (resp.content or []) if getattr(b, "type", None) == "text")
        return text.strip()
