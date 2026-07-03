"""Sticker handler: light acknowledgment instead of silence, logged if enabled."""
import asyncio

from src.handlers.sticker import make_sticker_handler
from src.history_store import HistoryStore
from src.i18n import I18n
from src.lang_store import InMemoryLangStore


class _Sticker:
    def __init__(self, emoji=None):
        self.emoji = emoji


class _Message:
    def __init__(self, emoji=None):
        self.sticker = _Sticker(emoji)
        self.replies = []

    async def set_reaction(self, *a, **k):
        pass

    async def reply_text(self, text, **kw):
        self.replies.append(text)


class _Update:
    def __init__(self, uid, emoji=None):
        self.message = _Message(emoji)
        self.effective_user = type("U", (), {"id": uid, "username": "bob", "first_name": "Bob"})()
        self.effective_chat = type("C", (), {"id": uid})()


def _deps(history_store=None):
    return {
        "lang_store": InMemoryLangStore(default="es"),
        "i18n": I18n("content/i18n", default="es"),
        "name": "Test Name",
        "history_store": history_store,
    }


def test_sticker_gets_reply_instead_of_silence():
    on_sticker = make_sticker_handler(_deps())
    update = _Update(uid=1)
    asyncio.run(on_sticker(update, None))
    assert update.message.replies  # not silent anymore


def test_sticker_logged_with_its_emoji(tmp_path):
    store = HistoryStore(str(tmp_path / "h.db"))
    on_sticker = make_sticker_handler(_deps(history_store=store))
    update = _Update(uid=2, emoji="👍")
    asyncio.run(on_sticker(update, None))
    convo = store.conversation(2)
    assert convo[0].content == "👍"
