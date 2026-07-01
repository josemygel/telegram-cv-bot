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

    def thumbnail_for(self, lang: str) -> Path | None:
        """Optional cv_{lang}_thumb.jpg shown as an inline preview next to the PDF in
        Telegram (see Bot API sendDocument 'thumbnail'). Entirely optional — bring
        your own JPEG (<200 kB, longest side <=320px) or skip it."""
        p = self._dir / f"cv_{lang}_thumb.jpg"
        return p if p.exists() else None

    def exists(self, lang: str) -> bool:
        return self.path_for(lang) is not None

    def available_languages(self) -> list[str]:
        return [lang for lang in _LANGS if self.exists(lang)]
