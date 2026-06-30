"""UI string lookup (bot chrome, NOT the LLM's answers). Bilingual es/en.

Kept separate from the grounding/profile data on purpose: the model answers in
the user's language, while menu labels must be deterministic for precision.
"""
from __future__ import annotations

from pathlib import Path

import yaml

from .config import BOT_LANG, I18N_DIR

_LANGS = ("es", "en")


def resolve_lang(code: str | None) -> str:
    """Map a Telegram language_code (e.g. 'es-ES') to one of our two languages."""
    return "es" if (code or "").lower().startswith("es") else "en"


class I18n:
    def __init__(self, directory: str | None = None, default: str | None = None):
        self._dir = Path(directory or I18N_DIR)
        self._default = default or BOT_LANG or "es"
        self._tables: dict[str, dict] = {}
        for lang in _LANGS:
            f = self._dir / f"{lang}.yaml"
            self._tables[lang] = (yaml.safe_load(f.read_text(encoding="utf-8")) if f.exists() else {}) or {}

    def t(self, key: str, lang: str | None = None, **fmt) -> str:
        """Look up a string, falling back default -> en -> the key itself."""
        lang = lang if lang in self._tables else self._default
        value = self._tables.get(lang, {}).get(key)
        if value is None:
            value = self._tables.get(self._default, {}).get(key)
        if value is None:
            value = self._tables.get("en", {}).get(key, key)
        text = str(value)
        if fmt:
            try:
                return text.format(**fmt)
            except (KeyError, IndexError):
                return text
        return text
