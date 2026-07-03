"""/claim: one-time admin bootstrap while ADMIN_USER_IDS is empty."""
import asyncio

from src.handlers import training


class _User:
    def __init__(self, uid):
        self.id = uid


class _Message:
    def __init__(self, args):
        self.args_sent = args
        self.replies = []

    async def reply_text(self, text, **kw):
        self.replies.append(text)


class _Update:
    def __init__(self, uid):
        self.effective_user = _User(uid)
        self.message = _Message(None)


class _Ctx:
    def __init__(self, args):
        self.args = args


def _deps():
    from src.i18n import I18n
    from src.lang_store import InMemoryLangStore
    from src.pipeline import Pipeline
    from src.projects import ProjectsRepository

    class _FakeLLM:
        def reply(self, messages):
            return "ok"

    return {
        "i18n": I18n("content/i18n", default="es"),
        "projects": ProjectsRepository("profile/projects.yaml"),
        "pipeline": Pipeline(llm=_FakeLLM()),
        "lang_store": InMemoryLangStore(default="es"),
    }


def test_wrong_code_does_not_grant_admin(tmp_path, monkeypatch):
    monkeypatch.setattr(training, "ADMIN_USER_IDS", set())
    monkeypatch.setattr(training, "ADMIN_CLAIM_CODE", "correct-code")
    monkeypatch.setattr(training, "ENV_PATH", str(tmp_path / ".env"))
    handlers = training.make_training_handlers(_deps())
    update = _Update(uid=99)
    asyncio.run(handlers["claim"](update, _Ctx(["wrong-code"])))
    assert 99 not in training.ADMIN_USER_IDS
    assert update.message.replies  # told them it was wrong


def test_correct_code_grants_admin_and_persists(tmp_path, monkeypatch):
    env_path = tmp_path / ".env"
    env_path.write_text("TELEGRAM_TOKEN=x\nADMIN_USER_IDS=\n", encoding="utf-8")
    monkeypatch.setattr(training, "ADMIN_USER_IDS", set())
    monkeypatch.setattr(training, "ADMIN_CLAIM_CODE", "correct-code")
    monkeypatch.setattr(training, "ENV_PATH", str(env_path))
    handlers = training.make_training_handlers(_deps())
    update = _Update(uid=99)
    asyncio.run(handlers["claim"](update, _Ctx(["correct-code"])))
    assert 99 in training.ADMIN_USER_IDS
    assert "ADMIN_USER_IDS=99" in env_path.read_text(encoding="utf-8")


def test_claim_disabled_once_an_admin_already_exists(tmp_path, monkeypatch):
    monkeypatch.setattr(training, "ADMIN_USER_IDS", {1})
    monkeypatch.setattr(training, "ADMIN_CLAIM_CODE", "correct-code")
    monkeypatch.setattr(training, "ENV_PATH", str(tmp_path / ".env"))
    handlers = training.make_training_handlers(_deps())
    update = _Update(uid=99)
    asyncio.run(handlers["claim"](update, _Ctx(["correct-code"])))
    assert 99 not in training.ADMIN_USER_IDS  # bootstrap window already closed
    assert not update.message.replies  # silent, doesn't confirm the command exists
