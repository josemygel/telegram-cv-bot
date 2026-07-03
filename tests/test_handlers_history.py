"""Owner-only /history: admin gating, pagination, and export rendering."""
import asyncio

from src.handlers.history import _label, make_history_handlers, render_html, users_menu
from src.history_store import HistoryStore, Message, UserSummary
from src.i18n import I18n
from src.lang_store import InMemoryLangStore


def _datas(markup):
    return [b.callback_data for row in markup.inline_keyboard for b in row]


def test_label_with_username_and_name():
    u = UserSummary(user_id=1, chat_id=1, username="alice", first_name="Alice",
                     last_message_at="2026-07-02T14:30:00")
    assert _label(u) == "@alice (Alice) 2026-07-02 14:30:00"


def test_label_without_username_or_name():
    u = UserSummary(user_id=42, chat_id=42, username=None, first_name=None,
                     last_message_at="2026-07-02T14:30:00")
    assert _label(u) == "id:42 2026-07-02 14:30:00"


def test_users_menu_pagination():
    users = [UserSummary(user_id=i, chat_id=i, username=f"u{i}", first_name=None,
                          last_message_at="2026-07-02T00:00:00") for i in range(10)]
    page0 = users_menu(users, page=0, page_size=8)
    datas0 = _datas(page0)
    assert "hist:open:0" in datas0
    assert "hist:list:1" in datas0
    page1 = users_menu(users, page=1, page_size=8)
    datas1 = _datas(page1)
    assert "hist:open:8" in datas1
    assert "hist:list:0" in datas1


def test_render_html_includes_roles_and_content():
    messages = [Message(role="user", content="hi <there>", created_at="2026-07-02T00:00:00")]
    out = render_html("@alice", messages)
    assert "hi &lt;there&gt;" in out  # HTML-escaped, not raw
    assert "user" in out


class _User:
    def __init__(self, uid):
        self.id = uid
        self.username = None
        self.first_name = None


class _Message:
    def __init__(self):
        self.replies = []
        self.markups = []

    async def reply_text(self, text, reply_markup=None, **kw):
        self.replies.append(text)
        self.markups.append(reply_markup)


class _Update:
    def __init__(self, uid):
        self.effective_user = _User(uid)
        self.message = _Message()


def _deps(history_store, admin_ids):
    from src.handlers import training
    training.ADMIN_USER_IDS = admin_ids  # _is_admin reads this module-level name at call time
    return {
        "history_store": history_store,
        "lang_store": InMemoryLangStore(default="es"),
        "i18n": I18n("content/i18n", default="es"),
    }


def test_non_admin_gets_not_admin_reply(tmp_path):
    store = HistoryStore(str(tmp_path / "h.db"))
    handlers = make_history_handlers(_deps(store, {1}))
    update = _Update(uid=2)  # not in admin set
    asyncio.run(handlers["history"](update, None))
    assert len(update.message.replies) == 1
    assert not update.message.markups[0]  # no user list handed out


def test_admin_with_no_conversations_yet(tmp_path):
    store = HistoryStore(str(tmp_path / "h.db"))
    handlers = make_history_handlers(_deps(store, {1}))
    update = _Update(uid=1)
    asyncio.run(handlers["history"](update, None))
    assert len(update.message.replies) == 1


def test_admin_sees_user_list(tmp_path):
    store = HistoryStore(str(tmp_path / "h.db"))
    store.record(chat_id=5, user_id=5, username="bob", first_name="Bob", role="user", content="hola")
    handlers = make_history_handlers(_deps(store, {1}))
    update = _Update(uid=1)
    asyncio.run(handlers["history"](update, None))
    assert update.message.markups[0] is not None
    assert "hist:open:5" in _datas(update.message.markups[0])
