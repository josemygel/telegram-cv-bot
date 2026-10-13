"""Vocabulario tecnico para el `initial_prompt` de Whisper.

POR QUE: Whisper transcribe peor siglas y nombres propios tecnicos (FastAPI, Kubernetes...)
si no los ha "visto" antes. Un prompt corto con el vocabulario del dueno sesga el decodificador
hacia esas grafias. Whisper solo admite ~224 tokens de prompt, asi que se limita por caracteres.
"""
from __future__ import annotations

DEFAULT_TERMS = [
    "Python", "TypeScript", "JavaScript", "Docker", "Kubernetes", "FastAPI", "PostgreSQL", "Redis",
    "GitHub", "GitHub Actions", "WordPress", "Flutter", "LLM", "RAG", "Claude", "Anthropic",
    "Whisper", "Telegram", "API", "SQLite", "CI/CD",
]
MAX_PROMPT_CHARS = 600


def build_initial_prompt(projects=(), extra=()) -> str:
    """Une nombres de proyecto + stacks (sin duplicados, orden estable); si no hay perfil
    usa una lista razonable por defecto."""
    seen: dict[str, None] = {}
    for p in projects or ():
        for term in (getattr(p, "name", ""), *getattr(p, "stack", ())):
            term = (term or "").strip()
            if term:
                seen.setdefault(term, None)
    for term in extra:
        seen.setdefault(term, None)
    terms = list(seen) or list(DEFAULT_TERMS)
    out = "Vocabulario técnico:"
    for term in terms:
        nxt = f"{out} {term},"
        if len(nxt) > MAX_PROMPT_CHARS:
            break
        out = nxt
    return out.rstrip(",") + "."
