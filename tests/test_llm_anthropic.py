"""AnthropicLLM: conversion OpenAI-style -> Messages API, request shape, errors.

El SDK se simula entero (sin red). Lo que se vigila aqui son las trampas conocidas:
`temperature` o `thinking` en la peticion dan 400 con Haiku 5.5, y los bloques
`thinking` de la respuesta nunca deben llegar al usuario.
"""
from types import SimpleNamespace as NS

import anthropic
import httpx
import pytest

import src.llm_anthropic as mod
from src.llm import BackendError
from src.llm_anthropic import AnthropicLLM

_REQ = httpx.Request("POST", "https://api.anthropic.com/v1/messages")


def _resp(content, stop_reason="end_turn", usage=None):
    usage = usage or NS(input_tokens=10, output_tokens=5,
                        cache_read_input_tokens=3, cache_creation_input_tokens=2)
    return NS(content=content, stop_reason=stop_reason, usage=usage)


def _text(t):
    return NS(type="text", text=t)


class _Client:
    def __init__(self, resp=None, exc=None):
        self.calls = []
        self._resp, self._exc = resp, exc
        self.messages = NS(create=self._create)

    def _create(self, **kw):
        self.calls.append(kw)
        if self._exc:
            raise self._exc
        return self._resp


def _llm(resp=None, exc=None, on_usage=None):
    c = _Client(resp or _resp([_text("hola")]), exc)
    return AnthropicLLM(client=c, on_usage=on_usage), c


MSGS = [
    {"role": "system", "content": "perfil"},
    {"role": "system", "content": "Always answer in Spanish."},
    {"role": "user", "content": "hola"},
]


def test_system_extracted_with_cache_control_on_last_block():
    llm, c = _llm()
    assert llm.reply(MSGS) == "hola"
    kw = c.calls[0]
    assert kw["system"][0] == {"type": "text", "text": "perfil"}
    assert kw["system"][-1]["cache_control"] == {"type": "ephemeral"}
    assert "cache_control" not in kw["system"][0]
    assert kw["messages"] == [{"role": "user", "content": "hola"}]


def test_request_has_no_temperature_nor_thinking_and_sets_effort(monkeypatch):
    monkeypatch.setattr(mod, "ANTHROPIC_EFFORT", "low")
    llm, c = _llm()
    llm.reply(MSGS)
    kw = c.calls[0]
    assert "temperature" not in kw and "thinking" not in kw
    assert kw["output_config"] == {"effort": "low"}
    assert kw["model"] == mod.ANTHROPIC_MODEL
    assert kw["max_tokens"] == mod.ANTHROPIC_MAX_TOKENS


def test_image_data_url_becomes_native_block():
    llm, c = _llm()
    llm.reply([{"role": "user", "content": [
        {"type": "text", "text": "que es?"},
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,QUJD"}},
        {"type": "image_url", "image_url": {"url": "https://evil.example/x.png"}},  # nunca se sigue
    ]}])
    parts = c.calls[0]["messages"][0]["content"]
    assert parts[0] == {"type": "text", "text": "que es?"}
    assert parts[1] == {"type": "image",
                        "source": {"type": "base64", "media_type": "image/png", "data": "QUJD"}}
    assert len(parts) == 2


def test_leading_assistant_turn_is_dropped():
    llm, c = _llm()
    llm.reply([{"role": "assistant", "content": "x"}, {"role": "user", "content": "q"}])
    assert c.calls[0]["messages"] == [{"role": "user", "content": "q"}]


def test_only_text_blocks_are_joined_thinking_ignored():
    llm, _ = _llm(_resp([NS(type="thinking", thinking="secreto"), _text("a"), _text("b")]))
    assert llm.reply(MSGS) == "ab"


def test_empty_content_returns_empty_string():
    llm, _ = _llm(_resp([]))
    assert llm.reply(MSGS) == ""


def test_refusal_returns_friendly_message():
    llm, _ = _llm(_resp([], stop_reason="refusal"))
    out = llm.reply(MSGS)
    assert out and out != "llm_refusal"  # clave i18n resuelta


def test_max_tokens_returns_partial_text(caplog):
    llm, _ = _llm(_resp([_text("cortado")], stop_reason="max_tokens"))
    with caplog.at_level("WARNING"):
        assert llm.reply(MSGS) == "cortado"
    assert "max_tokens" in caplog.text


def test_usage_exposed_and_callback_called():
    seen = []
    llm, _ = _llm(on_usage=seen.append)
    llm.reply(MSGS)
    u = llm.last_usage
    assert (u.input_tokens, u.output_tokens, u.cache_read_tokens, u.cache_creation_tokens) == (10, 5, 3, 2)
    assert seen == [u]


def test_usage_with_none_cache_fields():
    llm, _ = _llm(_resp([_text("x")], usage=NS(input_tokens=4, output_tokens=1,
                                              cache_read_input_tokens=None,
                                              cache_creation_input_tokens=None)))
    llm.reply(MSGS)
    assert llm.last_usage.cache_read_tokens == 0


def _status(cls, code):
    return cls("boom", response=httpx.Response(code, request=_REQ), body=None)


@pytest.mark.parametrize("exc,retriable", [
    (anthropic.APITimeoutError(request=_REQ), True),
    (anthropic.APIConnectionError(request=_REQ), True),
    (_status(anthropic.RateLimitError, 429), True),
    (_status(anthropic.InternalServerError, 500), True),
    (_status(anthropic.InternalServerError, 529), True),
    (_status(anthropic.AuthenticationError, 401), False),
    (_status(anthropic.PermissionDeniedError, 403), False),
    (_status(anthropic.BadRequestError, 400), False),
    (_status(anthropic.NotFoundError, 404), False),
])
def test_sdk_errors_map_to_backend_error(exc, retriable):
    llm, _ = _llm(exc=exc)
    with pytest.raises(BackendError) as ei:
        llm.reply(MSGS)
    assert ei.value.retriable is retriable


def test_api_key_never_in_error(monkeypatch):
    monkeypatch.setattr(mod, "ANTHROPIC_API_KEY", "sk-ant-SECRET")
    llm, _ = _llm(exc=_status(anthropic.AuthenticationError, 401))
    with pytest.raises(BackendError) as ei:
        llm.reply(MSGS)
    assert "SECRET" not in str(ei.value)
