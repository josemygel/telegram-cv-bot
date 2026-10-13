"""Contabilidad de tokens por usuario + bloqueo anti-abuso para el backend de pago.

POR QUE existe: el backend Anthropic se paga con un credito mensual fijo. Un solo
usuario malintencionado (o un bucle) podria quemarlo, asi que CADA llamada se apunta
en SQLite (mismo estilo que history_store.py) y, si un usuario pasa de 200k tokens en
una hora o de 1M en 24 h, se le bloquea 24 h. El dueno queda exento del bloqueo pero
sigue contando (para que /coste sea la cifra real).

Part of the josembot project, original work by Jose Miguel Gómez Lozano
(github.com/josemygel/telegram-cv-bot) — see AUTHORS.md and LICENSE.
"""
from __future__ import annotations

import sqlite3
from contextlib import closing
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

# Tarifas Haiku 5.5 en USD por millon de tokens. La lectura de cache cuesta 0.1x la
# entrada y la escritura de cache 1.25x (prompt caching de 5 min).
RATE_INPUT = 0.10
RATE_OUTPUT = 0.50
CACHE_READ_FACTOR = 0.10
CACHE_WRITE_FACTOR = 1.25

BLOCK_HOURS = 24
_FMT = "%Y-%m-%dT%H:%M:%S.%fZ"  # ancho fijo: comparar strings == comparar fechas

# Quien hace la llamada y para que. El handler lo fija antes de `asyncio.to_thread`
# (que copia el contexto), asi el LLM -que no sabe nada de usuarios- puede apuntar el
# gasto al usuario correcto sin cambiar la firma LLMBackend.reply(messages).
call_context: ContextVar[tuple[int, str] | None] = ContextVar("call_context", default=None)


@dataclass(frozen=True)
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0

    @property
    def total(self) -> int:
        return (self.input_tokens + self.output_tokens
                + self.cache_read_tokens + self.cache_creation_tokens)


@dataclass
class UserReport:
    user_id: int
    total_tokens: int
    cost_usd: float
    calls: int


def estimate_cost_usd(u: TokenUsage) -> float:
    per_m = (u.input_tokens * RATE_INPUT
             + u.output_tokens * RATE_OUTPUT
             + u.cache_read_tokens * RATE_INPUT * CACHE_READ_FACTOR
             + u.cache_creation_tokens * RATE_INPUT * CACHE_WRITE_FACTOR)
    return per_m / 1_000_000


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TokenLedger:
    def __init__(self, db_path: str, owner_id: int = 0, hour_limit: int = 200_000,
                 day_limit: int = 1_000_000, clock: Callable[[], datetime] = _utcnow):
        self._db_path, self._owner = db_path, owner_id
        self._hour_limit, self._day_limit, self._clock = hour_limit, day_limit, clock
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as con:
            con.execute("""
                CREATE TABLE IF NOT EXISTS token_usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    feature TEXT NOT NULL,
                    model TEXT NOT NULL,
                    input_tokens INTEGER NOT NULL,
                    output_tokens INTEGER NOT NULL,
                    cache_read_tokens INTEGER NOT NULL,
                    cache_creation_tokens INTEGER NOT NULL,
                    total_tokens INTEGER NOT NULL,
                    cost_usd REAL NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            con.execute("CREATE INDEX IF NOT EXISTS idx_usage_user ON token_usage(user_id, created_at)")
            con.execute("""
                CREATE TABLE IF NOT EXISTS token_blocks (
                    user_id INTEGER PRIMARY KEY,
                    blocked_until TEXT NOT NULL
                )
            """)
            con.commit()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path)

    def _now(self) -> datetime:
        return self._clock()

    def _stamp(self, dt: datetime) -> str:
        return dt.astimezone(timezone.utc).strftime(_FMT)

    def is_owner(self, user_id: int) -> bool:
        return bool(self._owner) and user_id == self._owner

    def record(self, user_id: int, usage: TokenUsage, model: str, feature: str = "text") -> None:
        with closing(self._connect()) as con:
            con.execute(
                "INSERT INTO token_usage (user_id, feature, model, input_tokens, output_tokens, "
                "cache_read_tokens, cache_creation_tokens, total_tokens, cost_usd, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (user_id, feature, model, usage.input_tokens, usage.output_tokens,
                 usage.cache_read_tokens, usage.cache_creation_tokens, usage.total,
                 estimate_cost_usd(usage), self._stamp(self._now())),
            )
            con.commit()

    def _tokens_since(self, user_id: int, since: datetime) -> int:
        with closing(self._connect()) as con:
            row = con.execute(
                "SELECT COALESCE(SUM(total_tokens), 0) FROM token_usage WHERE user_id = ? AND created_at >= ?",
                (user_id, self._stamp(since)),
            ).fetchone()
        return int(row[0])

    def evaluate(self, user_id: int) -> bool:
        """Mira el consumo reciente y bloquea si pasa un limite.

        Devuelve True SOLO la vez que el usuario pasa de libre a bloqueado, para que
        el aviso a los admins salga una unica vez (no una por cada mensaje posterior).
        """
        if self.is_owner(user_id) or self.is_blocked(user_id):
            return False
        now = self._now()
        over = (self._tokens_since(user_id, now - timedelta(hours=1)) > self._hour_limit
                or self._tokens_since(user_id, now - timedelta(hours=24)) > self._day_limit)
        if not over:
            return False
        with closing(self._connect()) as con:
            con.execute("INSERT OR REPLACE INTO token_blocks (user_id, blocked_until) VALUES (?, ?)",
                        (user_id, self._stamp(now + timedelta(hours=BLOCK_HOURS))))
            con.commit()
        return True

    def is_blocked(self, user_id: int) -> bool:
        if self.is_owner(user_id):
            return False
        with closing(self._connect()) as con:
            row = con.execute("SELECT blocked_until FROM token_blocks WHERE user_id = ?", (user_id,)).fetchone()
        return bool(row) and row[0] > self._stamp(self._now())

    def unblock(self, user_id: int) -> bool:
        """Quita el bloqueo (si lo habia). Devuelve si habia algo que quitar."""
        was = self.is_blocked(user_id)
        with closing(self._connect()) as con:
            con.execute("DELETE FROM token_blocks WHERE user_id = ?", (user_id,))
            con.commit()
        return was

    def report(self, period: str) -> list[UserReport]:
        """Gasto por usuario, el mayor primero. period: 'day' (UTC) | 'month' (UTC)."""
        now = self._now().astimezone(timezone.utc)
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        if period == "month":
            start = start.replace(day=1)
        with closing(self._connect()) as con:
            rows = con.execute(
                "SELECT user_id, SUM(total_tokens), SUM(cost_usd), COUNT(*) FROM token_usage "
                "WHERE created_at >= ? GROUP BY user_id ORDER BY SUM(cost_usd) DESC",
                (self._stamp(start),),
            ).fetchall()
        return [UserReport(r[0], int(r[1]), float(r[2]), int(r[3])) for r in rows]
