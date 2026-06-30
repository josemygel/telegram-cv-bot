"""Empty-reply guard: a model returning '' must not corrupt the history with an
empty assistant turn, and process_text must surface '' for the caller's fallback."""
from src.pipeline import Pipeline


class EmptyLLM:
    def reply(self, messages):
        return "   "  # whitespace -> effectively empty


class OkLLM:
    def reply(self, messages):
        return "ok"


def test_empty_reply_not_stored_and_returned_empty():
    p = Pipeline(llm=EmptyLLM())
    out = p.process_text(1, "hola")
    assert out["reply"] == ""
    hist = p._history(1)
    assert sum(m["role"] == "assistant" for m in hist) == 0  # no empty assistant turn
    assert sum(m["role"] == "user" for m in hist) == 1


def test_lang_directive_does_not_break_normal_reply():
    p = Pipeline(llm=OkLLM())
    assert p.process_text(1, "hi", lang="Spanish")["reply"] == "ok"
