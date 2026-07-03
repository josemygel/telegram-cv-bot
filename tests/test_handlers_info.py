"""Owner-only /info: admin gate + build/instance fields in the reply."""
import asyncio
from datetime import datetime, timedelta, timezone

import src.handlers.training as training
from src.handlers.info import make_info_handler
from src.i18n import I18n
from src.lang_store import InMemoryLangStore


class _Msg:
    def __init__(self):
        self.replies = []

    async def reply_text(self, text, **kw):
        self.replies.append(text)


class _Update:
    def __init__(self, uid):
        self.message = _Msg()
        self.effective_user = type("U", (), {"id": uid, "language_code": "es"})()
        self.effective_chat = type("C", (), {"id": uid})()


def _deps():
    return {
        "i18n": I18n("content/i18n", default="es"),
        "lang_store": InMemoryLangStore(default="es"),
        "vision_enabled": False,
        "history_store": None,
        "runtime_info": {
            "version": "9.9.9-test",
            "mode": "text",
            "llm_backend": "openai",
            "llm_model": "test-model",
            "started_at": datetime.now(timezone.utc) - timedelta(minutes=5),
        },
    }


def test_admin_sees_version_host_and_uptime(monkeypatch):
    monkeypatch.setattr(training, "ADMIN_USER_IDS", {42})
    handler = make_info_handler(_deps())
    update = _Update(uid=42)
    asyncio.run(handler(update, None))
    reply = update.message.replies[0]
    assert "9.9.9-test" in reply
    assert "host:" in reply          # container id / machine name present
    assert "openai / test-model" in reply
    assert "uptime:" in reply
    assert "history: <code>off</code>" in reply


def test_non_admin_is_rejected(monkeypatch):
    monkeypatch.setattr(training, "ADMIN_USER_IDS", {42})
    handler = make_info_handler(_deps())
    update = _Update(uid=7)
    asyncio.run(handler(update, None))
    assert "9.9.9-test" not in update.message.replies[0]
