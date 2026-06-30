"""CV file delivery. Resolves cv_{lang}.pdf and degrades gracefully if missing.

The bot only ever CONSUMES the PDF files; generation (scripts/build_cv.py) is a
separate, optional step. If a language's PDF is absent, the button is omitted
and the callback shows a localized 'not available yet' alert instead of crashing.
"""
from __future__ import annotations

from pathlib import Path

from .config import CV_DIR

_LANGS = ("es", "en")


class CvService:
    def __init__(self, cv_dir: str | None = None):
        self._dir = Path(cv_dir or CV_DIR)

    def path_for(self, lang: str) -> Path | None:
        p = self._dir / f"cv_{lang}.pdf"
        return p if p.exists() else None

    def exists(self, lang: str) -> bool:
        return self.path_for(lang) is not None

    def available_languages(self) -> list[str]:
        return [lang for lang in _LANGS if self.exists(lang)]
