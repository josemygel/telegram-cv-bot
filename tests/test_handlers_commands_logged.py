"""Menu commands are recorded to the history store: a visitor whose only
interaction is tapping /cv or /proyectos must still show up in /history."""
import asyncio

from src.cv_service import CvService
from src.handlers.commands import make_command_handlers
from src.history_store import HistoryStore
from src.i18n import I18n
from src.lang_store import InMemoryLangStore
from src.projects import ProjectsRepository


class _Msg:
    def __init__(self, text):
        self.text = text
        self.replies = []

    async def reply_text(self, text, **kw):
        self.replies.append(text)


class _Update:
    def __init__(self, text, uid=5):
        self.message = _Msg(text)
        self.effective_user = type("U", (), {"id": uid, "username": "ana", "first_name": "Ana",
                                             "language_code": "es"})()
        self.effective_chat = type("C", (), {"id": uid})()


def _deps(store):
    return {
        "i18n": I18n("content/i18n", default="es"),
        "projects": ProjectsRepository(),
        "cv": CvService(),
        "lang_store": InMemoryLangStore(default="es"),
        "name": "Test Name",
        "history_store": store,
    }


def test_cv_command_is_recorded(tmp_path):
    store = HistoryStore(str(tmp_path / "h.db"))
    cmd = make_command_handlers(_deps(store))
    update = _Update("/cv")
    asyncio.run(cmd["cv"](update, None))
    convo = store.conversation(5)
    assert convo[0].role == "user" and convo[0].content == "/cv"
    assert convo[1].role == "assistant"


def test_commands_without_store_still_work(tmp_path):
    cmd = make_command_handlers(_deps(None))
    update = _Update("/menu")
    asyncio.run(cmd["menu"](update, None))
    assert update.message.replies  # replied fine, no store needed
