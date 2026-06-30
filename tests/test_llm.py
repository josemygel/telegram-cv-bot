"""LLM backend resilience: defensive content extraction + transport-error wrapping.

The key regression here is the reasoning-model empty-content bug: content may be
empty/None while a separate reasoning_content holds the chain-of-thought — we must
return '' and NEVER surface reasoning_content as the answer.
"""
import pytest
import requests

import src.llm as llm
from src.llm import BackendError, OpenAICompatLLM, _content_of


def test_content_normal():
    assert _content_of({"content": "  hi  "}) == "hi"


def test_content_empty_with_reasoning_returns_empty():
    # Reasoning model: answer empty, CoT in reasoning_content. Must NOT leak the CoT.
    msg = {"content": "", "reasoning_content": "step 1... step 2..."}
    assert _content_of(msg) == ""


def test_content_none_is_empty_not_error():
    assert _content_of({"content": None}) == ""
    assert _content_of({}) == ""
    assert _content_of(None) == ""


class _Resp:
    def __init__(self, payload, raise_exc=None):
        self._payload = payload
        self._raise = raise_exc

    def raise_for_status(self):
        if self._raise:
            raise self._raise

    def json(self):
        return self._payload


def test_openai_reply_reads_content(monkeypatch):
    payload = {"choices": [{"message": {"content": "hola", "reasoning_content": "pensando"}}]}
    monkeypatch.setattr(llm.requests, "post", lambda *a, **k: _Resp(payload))
    assert OpenAICompatLLM().reply([{"role": "user", "content": "hi"}]) == "hola"


def test_openai_reply_empty_choices(monkeypatch):
    monkeypatch.setattr(llm.requests, "post", lambda *a, **k: _Resp({"choices": []}))
    assert OpenAICompatLLM().reply([]) == ""


def test_connection_error_becomes_retriable_backenderror(monkeypatch):
    def boom(*a, **k):
        raise requests.ConnectionError("refused")
    monkeypatch.setattr(llm.requests, "post", boom)
    with pytest.raises(BackendError) as exc:
        OpenAICompatLLM().reply([])
    assert exc.value.retriable is True


def test_http_error_becomes_nonretriable_backenderror(monkeypatch):
    err = requests.HTTPError("500")
    err.response = type("R", (), {"status_code": 500})()
    monkeypatch.setattr(llm.requests, "post", lambda *a, **k: _Resp({}, raise_exc=err))
    with pytest.raises(BackendError) as exc:
        OpenAICompatLLM().reply([])
    assert exc.value.retriable is False
