"""HistoryStore: durable conversation log used only by the owner's /history."""
from src.history_store import HistoryStore


def test_creates_parent_directory(tmp_path):
    db_path = tmp_path / "nested" / "history.db"
    HistoryStore(str(db_path))
    assert db_path.exists()


def test_conversation_ordered_oldest_first(tmp_path):
    store = HistoryStore(str(tmp_path / "history.db"))
    store.record(chat_id=1, user_id=10, username="alice", first_name="Alice", role="user", content="first")
    store.record(chat_id=1, user_id=10, username="alice", first_name="Alice", role="assistant", content="second")
    store.record(chat_id=1, user_id=10, username="alice", first_name="Alice", role="user", content="third")
    msgs = store.conversation(10)
    assert [m.content for m in msgs] == ["first", "second", "third"]
    assert [m.role for m in msgs] == ["user", "assistant", "user"]


def test_list_users_most_recent_first(tmp_path):
    store = HistoryStore(str(tmp_path / "history.db"))
    store.record(chat_id=1, user_id=10, username="alice", first_name="Alice", role="user", content="hi")
    store.record(chat_id=2, user_id=20, username=None, first_name=None, role="user", content="hey")
    store.record(chat_id=1, user_id=10, username="alice", first_name="Alice", role="assistant", content="hello")
    users = store.list_users()
    assert [u.user_id for u in users] == [10, 20]  # user 10's last message came after user 20's


def test_list_users_carries_username_and_name(tmp_path):
    store = HistoryStore(str(tmp_path / "history.db"))
    store.record(chat_id=1, user_id=10, username="alice", first_name="Alice", role="user", content="hi")
    store.record(chat_id=2, user_id=20, username=None, first_name=None, role="user", content="hey")
    users = {u.user_id: u for u in store.list_users()}
    assert users[10].username == "alice" and users[10].first_name == "Alice"
    assert users[20].username is None and users[20].first_name is None


def test_conversation_empty_for_unknown_user(tmp_path):
    store = HistoryStore(str(tmp_path / "history.db"))
    assert store.conversation(999) == []
