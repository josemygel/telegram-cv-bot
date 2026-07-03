"""Callback handler: CV button degrades gracefully when the PDF is missing.

Async handlers are exercised with lightweight fakes (no Telegram network) via
asyncio.run, matching the dependency-injected design.
"""
import asyncio

from src.cv_service import CvService
from src.handlers.callbacks import make_callback_handlers
from src.i18n import I18n
from src.lang_store import InMemoryLangStore
from src.projects import ProjectsRepository


class _User:
    id = 1
    language_code = "es"


class _Query:
    def __init__(self, data):
        self.data = data
        self.answers = []
        self.edits = []

    async def answer(self, text=None, show_alert=False):
        self.answers.append({"text": text, "show_alert": show_alert})

    async def edit_message_text(self, text, reply_markup=None, parse_mode=None):
        self.edits.append(text)


class _Update:
    def __init__(self, query):
        self.callback_query = query
        self.effective_user = _User()
        self.effective_chat = type("C", (), {"id": 1})()


class _Bot:
    def __init__(self):
        self.documents = 0

    async def send_chat_action(self, *a, **k):
        pass

    async def send_document(self, *a, **k):
        self.documents += 1


class _Ctx:
    def __init__(self):
        self.bot = _Bot()


def _deps(cv_dir):
    return {
        "i18n": I18n("content/i18n", default="es"),
        "projects": ProjectsRepository("profile/projects.example.yaml"),
        "cv": CvService(str(cv_dir)),
        "lang_store": InMemoryLangStore(default="es"),
        "name": "Jose Miguel",
    }


def test_cv_missing_shows_alert_and_sends_nothing(tmp_path):
    handlers = make_callback_handlers(_deps(tmp_path))  # empty dir -> no PDFs
    q = _Query("cv:es")
    ctx = _Ctx()
    asyncio.run(handlers["cv"](_Update(q), ctx))
    assert any(a["show_alert"] for a in q.answers)  # alerted the user
    assert ctx.bot.documents == 0  # never tried to send a missing file


def test_project_open_renders_overview(tmp_path):
    handlers = make_callback_handlers(_deps(tmp_path))
    q = _Query("proj:open:example-product")
    asyncio.run(handlers["projects"](_Update(q), _Ctx()))
    assert q.edits and "Example Product" in q.edits[0]
