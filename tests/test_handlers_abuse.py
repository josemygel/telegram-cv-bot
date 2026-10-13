"""Topes de entrada, bloqueo, medios ignorados, /coste, /desbloquear y salida de grupos."""
import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace as NS

import src.handlers.guard as guard_mod
from src.handlers.cost import make_cost_handlers
from src.handlers.guard import make_group_guard, make_ignored_media_handler
from src.handlers.photo import make_photo_handler
from src.handlers.text import make_text_handler
from src.i18n import I18n
from src.lang_store import InMemoryLangStore
from src.token_ledger import TokenLedger, TokenUsage

OWNER = 999
NOW = datetime(2026, 10, 13, 12, 0, tzinfo=timezone.utc)


class _Msg:
    def __init__(self, text=None, photo=None, caption=None):
        self.text, self.photo, self.caption, self.replies = text, photo or [], caption, []

    async def set_reaction(self, *a, **k):
        pass

    async def reply_text(self, text, **kw):
        self.replies.append(text)


def _update(uid, **kw):
    return NS(message=_Msg(**kw), effective_user=NS(id=uid, username="u", first_name="U", language_code="es"),
              effective_chat=NS(id=uid))


class _Bot:
    def __init__(self):
        self.sent, self.left, self.downloads = [], [], 0

    async def send_chat_action(self, *a, **k):
        pass

    async def send_message(self, chat_id, text, **kw):
        self.sent.append((chat_id, text))

    async def leave_chat(self, chat_id):
        self.left.append(chat_id)

    async def get_file(self, fid):
        self.downloads += 1
        raise AssertionError("no debe descargarse")


def _ctx(args=None):
    return NS(bot=_Bot(), args=args or [])


class _Pipe:
    def __init__(self):
        self.calls = 0

    def process_text(self, chat_id, text, lang=None):
        self.calls += 1
        return {"reply": "ok"}

    def process_image(self, *a, **k):
        self.calls += 1
        return {"reply": "ok"}


def _deps(tmp_path, pipe=None, vision=True):
    led = TokenLedger(str(tmp_path / "u.db"), owner_id=OWNER, clock=lambda: NOW)
    return {"pipeline": pipe or _Pipe(), "lang_store": InMemoryLangStore(default="es"),
            "i18n": I18n("content/i18n", default="es"), "name": "Jose", "ledger": led,
            "owner_id": OWNER, "admin_ids": {OWNER}, "vision_enabled": vision}


def _block(d, uid):
    d["ledger"].record(uid, TokenUsage(300_000, 0, 0, 0), "m", "text")
    d["ledger"].evaluate(uid)


def test_text_over_2000_refused_without_llm(tmp_path):
    d = _deps(tmp_path)
    u = _update(1, text="a" * 2001)
    asyncio.run(make_text_handler(d)(u, _ctx()))
    assert d["pipeline"].calls == 0 and "2000" in u.message.replies[0]


def test_text_at_2000_accepted(tmp_path):
    d = _deps(tmp_path)
    asyncio.run(make_text_handler(d)(_update(1, text="a" * 2000), _ctx()))
    assert d["pipeline"].calls == 1


def test_blocked_user_gets_friendly_message_and_no_llm(tmp_path):
    d = _deps(tmp_path)
    _block(d, 5)
    u = _update(5, text="hola que tal")
    asyncio.run(make_text_handler(d)(u, _ctx()))
    assert d["pipeline"].calls == 0
    assert "24" in u.message.replies[0]


def test_blocked_photo_does_not_download(tmp_path):
    d = _deps(tmp_path)
    _block(d, 5)
    ctx = _ctx()
    asyncio.run(make_photo_handler(d)(_update(5, photo=[NS(file_id="f", file_size=100)]), ctx))
    assert ctx.bot.downloads == 0 and d["pipeline"].calls == 0


def test_after_call_blocks_and_notifies_admins_once(tmp_path):
    d = _deps(tmp_path)
    ctx = _ctx()
    d["ledger"].record(6, TokenUsage(300_000, 0, 0, 0), "m", "text")
    asyncio.run(guard_mod.after_call(d, ctx, _update(6).effective_user))
    asyncio.run(guard_mod.after_call(d, ctx, _update(6).effective_user))
    assert len(ctx.bot.sent) == 1 and ctx.bot.sent[0][0] == OWNER


def test_photo_over_5mb_refused_without_download(tmp_path):
    d = _deps(tmp_path)
    ctx = _ctx()
    u = _update(1, photo=[NS(file_id="f", file_size=5 * 1024 * 1024 + 1)])
    asyncio.run(make_photo_handler(d)(u, ctx))
    assert ctx.bot.downloads == 0 and d["pipeline"].calls == 0 and len(u.message.replies) == 1


def test_ignored_media_replies_and_never_downloads(tmp_path):
    d = _deps(tmp_path)
    ctx = _ctx()
    u = _update(1)
    asyncio.run(make_ignored_media_handler(d)(u, ctx))
    assert ctx.bot.downloads == 0 and len(u.message.replies) == 1


def test_coste_owner_only(tmp_path):
    d = _deps(tmp_path)
    d["ledger"].record(1, TokenUsage(1000, 100, 0, 0), "m", "text")
    h = make_cost_handlers(d)
    u, c = _update(1), _ctx([])
    asyncio.run(h["coste"](u, c))
    assert "dueño" in u.message.replies[0]
    u, c = _update(OWNER), _ctx([])
    asyncio.run(h["coste"](u, c))
    out = u.message.replies[0]
    assert "1100" in out and "$" in out


def test_desbloquear_owner_only_and_works(tmp_path):
    d = _deps(tmp_path)
    _block(d, 7)
    h = make_cost_handlers(d)
    asyncio.run(h["unblock"](_update(1), _ctx(["7"])))
    assert d["ledger"].is_blocked(7)
    asyncio.run(h["unblock"](_update(OWNER), _ctx(["7"])))
    assert not d["ledger"].is_blocked(7)
    u = _update(OWNER)
    asyncio.run(h["unblock"](u, _ctx(["abc"])))
    assert "/desbloquear" in u.message.replies[0]


def _member_update(adder_id, chat_type, status):
    return NS(my_chat_member=NS(chat=NS(id=-5, type=chat_type), from_user=NS(id=adder_id),
                                new_chat_member=NS(status=status)))


def test_leaves_group_unless_added_by_owner(tmp_path):
    h = make_group_guard(_deps(tmp_path))
    for adder, kind, status, leaves in [
        (123, "supergroup", "member", True),
        (OWNER, "group", "member", False),
        (123, "private", "member", False),
        (123, "group", "left", False),
    ]:
        ctx = _ctx()
        asyncio.run(h(_member_update(adder, kind, status), ctx))
        assert (ctx.bot.left == [-5]) is leaves, (adder, kind, status)
