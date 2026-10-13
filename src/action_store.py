"""Texto fuente de los botones del dueno (Responder / Resumir / Traducir).

POR QUE SQLite y no callback_data: Telegram limita callback_data a 64 bytes, asi que el boton
solo lleva un id corto y el texto se guarda aqui con caducidad (48 h por defecto): pasado
ese tiempo el contenido del dueno no se conserva.
"""
from __future__ import annotations

import secrets
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, NamedTuple


class StoredAction(NamedTuple):
    user_id: int
    source_text: str  # texto que se responde/resume/traduce
    base_html: str  # lo que muestra el mensaje con botones (se le anade debajo el resultado)
    lang: str  # idioma detectado por Whisper ('' si no se conoce)


class ActionStore:
    def __init__(self, db_path: str, ttl_hours: int = 48, clock: Callable[[], float] = time.time):
        self._path, self._ttl, self._clock = db_path, ttl_hours * 3600, clock
        if db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._mem = sqlite3.connect(":memory:") if db_path == ":memory:" else None
        with self._connect() as c:
            c.execute("CREATE TABLE IF NOT EXISTS actions (id TEXT PRIMARY KEY, user_id INTEGER, "
                      "source_text TEXT, base_html TEXT, lang TEXT, created REAL)")

    @contextmanager
    def _connect(self):
        """Conexion con commit; la de :memory: se reutiliza (cerrarla borraria la BD)."""
        if self._mem is not None:
            with self._mem as c:
                yield c
            return
        c = sqlite3.connect(self._path)
        try:
            with c:
                yield c
        finally:
            c.close()

    def put(self, user_id: int, source_text: str, base_html: str, lang: str = "") -> str:
        self.purge()
        action_id = secrets.token_hex(5)  # 10 caracteres: cabe de sobra en 64 bytes
        with self._connect() as c:
            c.execute("INSERT INTO actions VALUES (?,?,?,?,?,?)",
                      (action_id, user_id, source_text, base_html, lang, self._clock()))
        return action_id

    def get(self, action_id: str) -> StoredAction | None:
        with self._connect() as c:
            row = c.execute("SELECT user_id, source_text, base_html, lang, created FROM actions WHERE id=?",
                            (action_id,)).fetchone()
        if not row or self._clock() - row[4] > self._ttl:
            return None
        return StoredAction(*row[:4])

    def purge(self) -> None:
        with self._connect() as c:
            c.execute("DELETE FROM actions WHERE created < ?", (self._clock() - self._ttl,))
