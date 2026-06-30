"""Owner-curated knowledge file, injected into the grounding prompt.

This is the bot's 'training' surface for FACTS: edit profile/knowledge.md directly,
or append lines from Telegram with /aprende. (Fine-tuning is only for tone/persona,
never for facts — grounding from a file is accurate and instantly updatable.)
"""
from __future__ import annotations

from pathlib import Path

from .config import KNOWLEDGE_PATH


def load_knowledge(path: str | None = None) -> str:
    p = Path(path or KNOWLEDGE_PATH)
    return p.read_text(encoding="utf-8") if p.exists() else ""


def append_fact(text: str, path: str | None = None) -> None:
    p = Path(path or KNOWLEDGE_PATH)
    p.parent.mkdir(parents=True, exist_ok=True)
    fact = text.strip().replace("\n", " ")
    with p.open("a", encoding="utf-8") as fh:
        fh.write(f"- {fact}\n")
