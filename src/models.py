"""Domain data models. Pure data + light validation, no I/O.

Single place that defines the shape the rest of the code relies on, so that
the projects feature (buttons) and the grounding layer (LLM) read identical
fields and can never drift apart.
"""
from __future__ import annotations

from dataclasses import dataclass, field

_LANGS = ("es", "en")


def _bilingual(value: object, field_name: str, pid: str) -> dict[str, str]:
    """Validate that a field has non-empty es/en text. Why: the bot answers in
    either language, so a missing translation would surface as an empty reply."""
    if not isinstance(value, dict):
        raise ValueError(f"Project '{pid}': field '{field_name}' must be a map with es/en keys")
    out: dict[str, str] = {}
    for lang in _LANGS:
        text = value.get(lang)
        if not text or not str(text).strip():
            raise ValueError(f"Project '{pid}': missing '{field_name}.{lang}'")
        out[lang] = str(text).strip()
    return out


def _bilingual_optional(value: object) -> dict[str, str]:
    """Parse an OPTIONAL bilingual field (e.g. long-form details): keep whatever
    languages are present, tolerate absence."""
    if not isinstance(value, dict):
        return {}
    return {lang: str(value[lang]).strip() for lang in _LANGS if value.get(lang)}


@dataclass(frozen=True)
class Project:
    """One project, with bilingual scope/participation/summary and optional details."""

    id: str
    name: str
    role: str
    status: str
    stack: tuple[str, ...]
    url: str | None
    scope: dict[str, str]
    participation: dict[str, str]
    summary: dict[str, str]
    details: dict[str, str] = field(default_factory=dict)
    order: int = 0

    def _pick(self, field_value: dict[str, str], lang: str) -> str:
        # Fall back to English, then to whatever exists, so a view never breaks.
        return field_value.get(lang) or field_value.get("en") or next(iter(field_value.values()), "")

    def scope_text(self, lang: str) -> str:
        return self._pick(self.scope, lang)

    def participation_text(self, lang: str) -> str:
        return self._pick(self.participation, lang)

    def summary_text(self, lang: str) -> str:
        return self._pick(self.summary, lang)

    def details_text(self, lang: str) -> str:
        return self._pick(self.details, lang) if self.details else ""

    @classmethod
    def from_dict(cls, data: dict) -> "Project":
        pid = str(data.get("id") or "").strip()
        if not pid:
            raise ValueError("Project is missing a required 'id'")
        return cls(
            id=pid,
            name=str(data.get("name") or pid).strip(),
            role=str(data.get("role") or "").strip(),
            status=str(data.get("status") or "private").strip(),
            stack=tuple(str(s).strip() for s in (data.get("stack") or [])),
            url=(str(data["url"]).strip() if data.get("url") else None),
            scope=_bilingual(data.get("scope") or {}, "scope", pid),
            participation=_bilingual(data.get("participation") or {}, "participation", pid),
            summary=_bilingual(data.get("summary") or {}, "summary", pid),
            details=_bilingual_optional(data.get("details")),
            order=int(data.get("order") or 0),
        )
