"""Text handler: reacts 👀 (seen) and replies. Async handler exercised with fakes."""
import asyncio

from src.handlers.text import make_text_handler
from src.i18n import I18n
from src.lang_store import InMemoryLangStore
from src.pipeline import Pipeline


class _FakeLLM:
    def reply(self, messages):
        return "Hola, soy el asistente."


class _Msg:
    def __init__(self, text):
        self.text = text
        self.reactions = []
        self.replies = []

    async def set_reaction(self, reaction=None, **kw):
        self.reactions.append(reaction)

    async def reply_text(self, text, parse_mode=None, **kw):
        self.replies.append(text)


class _Update:
    def __init__(self, msg):
        self.message = msg
        self.effective_user = type("U", (), {"id": 7, "language_code": "es"})()
        self.effective_chat = type("C", (), {"id": 7})()


class _Ctx:
    def __init__(self):
        self.bot = type("B", (), {"send_chat_action": staticmethod(lambda *a, **k: _noop())})()


async def _noop():
    return None


def _deps():
    return {
        "pipeline": Pipeline(llm=_FakeLLM()),
        "lang_store": InMemoryLangStore(default="es"),
        "i18n": I18n("content/i18n", default="es"),
    }


def test_marks_seen_with_eyes_and_replies():
    on_text = make_text_handler(_deps())
    msg = _Msg("¿Quién eres?")
    asyncio.run(on_text(_Update(msg), _Ctx()))
    assert len(msg.reactions) == 1
    assert getattr(msg.reactions[0], "emoji", "") == "\U0001F440"  # 👀
    assert msg.replies and "Hola" in msg.replies[0]
