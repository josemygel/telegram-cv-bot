"""Per-user reply-language store. In-memory behind a Protocol for DI/testability.

Why a Protocol: handlers depend on the interface, so tests inject a fake and a
future persistent backend (e.g. PicklePersistence) needs no handler changes.
"""
from __future__ import annotations

from typing import Protocol

from .config import BOT_LANG

_VALID = ("es", "en")


class LangStore(Protocol):
    def get(self, user_id: int) -> str: ...
    def set(self, user_id: int, lang: str) -> None: ...
    def is_set(self, user_id: int) -> bool: ...


class InMemoryLangStore:
    def __init__(self, default: str | None = None):
        self._default = (default or BOT_LANG or "es") if (default or BOT_LANG) in _VALID else "es"
        self._by_user: dict[int, str] = {}

    def get(self, user_id: int) -> str:
        return self._by_user.get(user_id, self._default)

    def set(self, user_id: int, lang: str) -> None:
        if lang in _VALID:
            self._by_user[user_id] = lang

    def is_set(self, user_id: int) -> bool:
        return user_id in self._by_user
