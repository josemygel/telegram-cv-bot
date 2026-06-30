"""Deterministic project rendering from structured data (HTML, max precision).

Project facets (envergadura / participación / stack) are rendered straight from
the YAML — NOT through the LLM — so the figures and wording are exact and never
embellished. All dynamic text is HTML-escaped.
"""
from __future__ import annotations

from ..formatting import escape_html


def project_overview(t, lang, project) -> str:
    return (
        f"<b>{escape_html(project.name)}</b> — {escape_html(project.role)}\n\n"
        f"{escape_html(project.summary_text(lang))}"
    )


def project_facet(t, lang, project, facet: str) -> str:
    header = f"<b>{escape_html(project.name)}</b>\n"
    if facet == "scope":
        return header + f"<b>{escape_html(t('label_scope', lang))}:</b> {escape_html(project.scope_text(lang))}"
    if facet == "role":
        return header + (f"<b>{escape_html(t('label_participation', lang))}:</b> "
                         f"{escape_html(project.participation_text(lang))}")
    if facet == "tech":
        return header + f"<b>{escape_html(t('label_stack', lang))}:</b> {escape_html(', '.join(project.stack))}"
    return header
