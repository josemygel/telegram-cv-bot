import pytest

from src.pipeline import Pipeline


class FakeSTT:
    def __init__(self, text: str):
        self.text = text

    def transcribe(self, audio_path: str) -> str:
        return self.text


class FakeLLM:
    def reply(self, messages: list[dict]) -> str:
        return "reply to: " + messages[-1]["content"]


class FakeTTS:
    def synthesize(self, text: str, out_path: str) -> str:
        self.spoken = text
        return out_path


def test_process_text_flow():
    p = Pipeline(llm=FakeLLM())
    out = p.process_text(1, "  hola  ")
    assert out["reply"] == "reply to: hola"  # input trimmed, reply grounded on last msg


def test_process_voice_flow():
    tts = FakeTTS()
    p = Pipeline(llm=FakeLLM(), stt=FakeSTT("  hello there  "), tts=tts)
    out = p.process_voice(chat_id=1, audio_path="in.ogg", out_path="out.wav")
    assert out["transcript"] == "hello there"
    assert out["reply"] == "reply to: hello there"
    assert out["audio"] == "out.wav"
    assert tts.spoken == "reply to: hello there"


def test_process_voice_requires_components():
    p = Pipeline(llm=FakeLLM())  # no stt/tts
    with pytest.raises(RuntimeError):
        p.process_voice(1, "a.ogg", "o.wav")


def test_history_persists_per_chat():
    p = Pipeline(llm=FakeLLM())
    p.process_text(1, "a")
    p.process_text(1, "a")
    hist = p._history(1)
    assert hist[0]["role"] == "system"
    assert sum(m["role"] == "user" for m in hist) == 2
    assert sum(m["role"] == "assistant" for m in hist) == 2


def test_history_is_trimmed():
    p = Pipeline(llm=FakeLLM(), max_turns=4)
    for _ in range(10):
        p.process_text(7, "a")
    hist = p._history(7)
    assert hist[0]["role"] == "system"
    assert len(hist) <= 4 + 1
