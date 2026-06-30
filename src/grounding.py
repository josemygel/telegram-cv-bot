"""Compose the full grounded system prompt: profile bio + structured projects +
owner-curated knowledge.

Both the project BUTTONS and the LLM read the SAME Project objects, so free-text
answers and the button drill-downs can never contradict each other. The project
block (and optional per-project details) is included in both languages; the model
answers in the user's language.
"""
from __future__ import annotations

from . import profile as profile_mod
from .knowledge import load_knowledge
from .models import Project


def _serialize_projects(projects: list[Project], lang: str = "en") -> str:
    # Single language keeps the prompt small (the model translates for the other
    # language, exactly as it already does for the English profile.md).
    blocks = []
    for p in projects:
        block = (
            f"### {p.name} ({p.role}, {p.status})\n"
            f"Scope: {p.scope_text(lang)}\n"
            f"Participation: {p.participation_text(lang)}\n"
            f"Stack: {', '.join(p.stack)}\n"
            f"Summary: {p.summary_text(lang)}"
        )
        if p.details:
            block += f"\nDetails: {p.details_text(lang)}"
        blocks.append(block)
    return "\n\n".join(blocks)


def build_grounded_prompt(
    name: str = "Your Name",
    profile_path: str | None = None,
    projects: list[Project] | None = None,
    knowledge: str | None = None,
    grounding_lang: str = "en",
) -> str:
    prompt = profile_mod.build_system_prompt(name, profile_path)
    if projects:
        prompt += (
            "\n\n--- PROJECTS (structured, authoritative — quote faithfully) ---\n"
            + _serialize_projects(projects, grounding_lang)
        )
    if knowledge is None:
        knowledge = load_knowledge()
    if knowledge and knowledge.strip():
        prompt += "\n\n--- ADDITIONAL KNOWLEDGE (curated by the owner — authoritative) ---\n" + knowledge.strip()
    return prompt
