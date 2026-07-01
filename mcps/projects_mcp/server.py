"""MCP server exposing Jose Miguel's structured projects (reusable by any MCP client).

Part of the josembot project, original work by Jose Miguel Gómez Lozano
(github.com/josemygel/telegram-cv-bot) — see AUTHORS.md and LICENSE.

Reuses src.projects.ProjectsRepository as the SINGLE SOURCE OF TRUTH, so this server,
the Telegram bot and the LLM grounding all read identical data. Runs as a stdio MCP
server (the standard transport for desktop clients):

    python mcps/projects_mcp/server.py

Register it in any MCP client (e.g. Claude Desktop) — see README.md.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Make the project root importable so we reuse src/ as the single source of truth.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from mcp.server.fastmcp import FastMCP  # noqa: E402

from src.projects import ProjectsRepository  # noqa: E402

mcp = FastMCP("josembot-projects")
_repo = ProjectsRepository()


def _overview(p) -> dict:
    return {"id": p.id, "name": p.name, "role": p.role, "status": p.status}


@mcp.tool()
def list_projects() -> list[dict]:
    """List all of Jose Miguel's projects (id, name, role, status)."""
    return [_overview(p) for p in _repo.list_projects()]


@mcp.tool()
def get_project(project_id: str, lang: str = "es") -> dict:
    """Get one project's full detail in the given language ('es' or 'en')."""
    p = _repo.get(project_id)
    if p is None:
        return {"error": f"unknown project '{project_id}'"}
    return {
        "id": p.id, "name": p.name, "role": p.role, "status": p.status, "url": p.url,
        "stack": list(p.stack), "scope": p.scope_text(lang),
        "participation": p.participation_text(lang), "summary": p.summary_text(lang),
    }


@mcp.tool()
def get_project_field(project_id: str, field: str, lang: str = "es") -> str:
    """Get one field of a project: 'scope' (envergadura), 'participation', 'summary' or 'stack'."""
    p = _repo.get(project_id)
    if p is None:
        return f"unknown project '{project_id}'"
    if field == "scope":
        return p.scope_text(lang)
    if field == "participation":
        return p.participation_text(lang)
    if field == "summary":
        return p.summary_text(lang)
    if field == "stack":
        return ", ".join(p.stack)
    return f"unknown field '{field}' (use scope|participation|summary|stack)"


@mcp.tool()
def search_projects(query: str) -> list[dict]:
    """Search projects by name, summary or stack (case-insensitive substring match)."""
    q = (query or "").lower()
    matches = []
    for p in _repo.list_projects():
        haystack = " ".join([p.name, p.summary_text("es"), p.summary_text("en"), " ".join(p.stack)]).lower()
        if q in haystack:
            matches.append(_overview(p))
    return matches


if __name__ == "__main__":
    mcp.run()
