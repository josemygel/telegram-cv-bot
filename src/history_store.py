"""Durable conversation log, for the owner's /history command only.

Separate from Pipeline._histories (the in-memory LLM context window: capped,
trimmed, and reset on /reload by design). This is a plain append-only SQLite log of
every text exchange, kept so the owner can review who talked to the bot and what was
said — it is never read back into the LLM's context.

Part of the josembot project, original work by Jose Miguel Gómez Lozano
(github.com/josemygel/telegram-cv-bot) — see AUTHORS.md and LICENSE.
"""
from __future__ import annotations

import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class Message:
    role: str  # "user" | "assistant"
    content: str
    created_at: str  # ISO 8601 UTC, microsecond precision


@dataclass
class UserSummary:
    user_id: int
    chat_id: int
    username: str | None
    first_name: str | None
    last_message_at: str


class HistoryStore:
    def __init__(self, db_path: str):
        self._db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as con:
            con.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    username TEXT,
                    first_name TEXT,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            con.execute("CREATE INDEX IF NOT EXISTS idx_messages_user ON messages(user_id, created_at)")
            con.commit()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path)

    def record(self, chat_id: int, user_id: int, username: str | None, first_name: str | None,
               role: str, content: str) -> None:
        with closing(self._connect()) as con:
            con.execute(
                "INSERT INTO messages (chat_id, user_id, username, first_name, role, content, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (chat_id, user_id, username, first_name, role, content,
                 datetime.now(timezone.utc).isoformat()),
            )
            con.commit()

    def list_users(self) -> list[UserSummary]:
        """One row per user who has ever messaged, most recently active first."""
        with closing(self._connect()) as con:
            rows = con.execute("""
                SELECT user_id, chat_id, username, first_name, MAX(created_at) AS last_at, MAX(id)
                FROM messages GROUP BY user_id ORDER BY last_at DESC, MAX(id) DESC
            """).fetchall()
        return [UserSummary(user_id=r[0], chat_id=r[1], username=r[2], first_name=r[3], last_message_at=r[4])
                for r in rows]

    def conversation(self, user_id: int) -> list[Message]:
        """Full conversation for one user, oldest first."""
        with closing(self._connect()) as con:
            rows = con.execute(
                "SELECT role, content, created_at FROM messages WHERE user_id = ? ORDER BY id ASC",
                (user_id,),
            ).fetchall()
        return [Message(role=r[0], content=r[1], created_at=r[2]) for r in rows]
