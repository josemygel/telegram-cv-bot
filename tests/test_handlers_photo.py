"""Photo handler: declines gracefully when vision is off, calls the pipeline when on."""
import asyncio

from src.handlers.photo import make_photo_handler
from src.history_store import HistoryStore
from src.i18n import I18n
from src.lang_store import InMemoryLangStore


class _PhotoSize:
    def __init__(self, file_id):
        self.file_id = file_id


class _Message:
    def __init__(self, caption=None):
        self.caption = caption
        self.photo = [_PhotoSize("thumb"), _PhotoSize("full")]
        self.replies = []

    async def set_reaction(self, *a, **k):
        pass

    async def reply_text(self, text, **kw):
        self.replies.append(text)


class _User:
    def __init__(self, uid):
        self.id = uid
        self.username = "alice"
        self.first_name = "Alice"


class _Update:
    def __init__(self, uid, caption=None):
        self.message = _Message(caption)
        self.effective_user = _User(uid)
        self.effective_chat = type("C", (), {"id": uid})()


class _TgFile:
    async def download_to_drive(self, path):
        from pathlib import Path
        Path(path).write_bytes(b"\xff\xd8\xff")  # minimal fake jpeg bytes


class _Bot:
    async def get_file(self, file_id):
        return _TgFile()

    async def send_chat_action(self, *a, **k):
        pass


class _Ctx:
    def __init__(self):
        self.bot = _Bot()


class _FakeVisionPipeline:
    def __init__(self, reply="I see a cat."):
        self._reply = reply
        self.calls = []

    def process_image(self, chat_id, image_b64, caption, lang=None):
        self.calls.append((chat_id, caption, lang))
        return {"reply": self._reply}


def _deps(vision_enabled, pipeline=None, history_store=None):
    return {
        "pipeline": pipeline or _FakeVisionPipeline(),
        "lang_store": InMemoryLangStore(default="es"),
        "i18n": I18n("content/i18n", default="es"),
        "vision_enabled": vision_enabled,
        "history_store": history_store,
    }


def test_declines_and_logs_when_vision_disabled(tmp_path):
    store = HistoryStore(str(tmp_path / "h.db"))
    handlers_deps = _deps(vision_enabled=False, history_store=store)
    on_photo = make_photo_handler(handlers_deps)
    update = _Update(uid=1, caption="mira esto")
    asyncio.run(on_photo(update, _Ctx()))
    assert len(update.message.replies) == 1
    assert "imágenes" in update.message.replies[0] or "images" in update.message.replies[0]
    convo = store.conversation(1)
    assert [m.content for m in convo] == ["mira esto", update.message.replies[0]]


def test_calls_pipeline_and_replies_when_vision_enabled(tmp_path):
    store = HistoryStore(str(tmp_path / "h.db"))
    pipeline = _FakeVisionPipeline(reply="I see a cat.")
    on_photo = make_photo_handler(_deps(vision_enabled=True, pipeline=pipeline, history_store=store))
    update = _Update(uid=2, caption="what is this?")
    asyncio.run(on_photo(update, _Ctx()))
    assert update.message.replies == ["I see a cat."]
    assert pipeline.calls and pipeline.calls[0][1] == "what is this?"
    convo = store.conversation(2)
    assert [m.content for m in convo] == ["what is this?", "I see a cat."]
