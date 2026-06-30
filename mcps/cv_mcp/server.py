"""MCP server exposing Jose Miguel's profile, contact and CV / cover-letter documents.

Reuses src.profile + src.cv_service so it stays in sync with the bot. Stdio MCP server:

    python mcps/cv_mcp/server.py

Register it in any MCP client (e.g. Claude Desktop) — see README.md.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from mcp.server.fastmcp import FastMCP  # noqa: E402

from src.config import (  # noqa: E402
    ASSISTANT_NAME, CONTACT_EMAIL, CONTACT_GITHUB, CONTACT_LINKEDIN, CONTACT_PHONE, CV_DIR,
)
from src.profile import load_profile  # noqa: E402

mcp = FastMCP("josembot-cv")

# Contact comes from config/.env (real values stay out of the committed code).
CONTACT = {
    "name": ASSISTANT_NAME,
    "email": CONTACT_EMAIL,
    "phone": CONTACT_PHONE,
    "linkedin": CONTACT_LINKEDIN,
    "github": CONTACT_GITHUB,
}
_KINDS = ("cv", "cover_letter")


@mcp.tool()
def get_profile() -> str:
    """Return Jose Miguel's full profile text (the grounding document)."""
    return load_profile()


@mcp.tool()
def get_contact() -> dict:
    """Return Jose Miguel's contact details (name, email, phone, location, LinkedIn, GitHub)."""
    return dict(CONTACT)


@mcp.tool()
def list_documents() -> dict:
    """List which CV and cover-letter PDFs are available, by language ('es'/'en')."""
    base = Path(CV_DIR)
    return {kind: [lang for lang in ("es", "en") if (base / f"{kind}_{lang}.pdf").exists()] for kind in _KINDS}


@mcp.tool()
def get_document_path(kind: str = "cv", lang: str = "es") -> str:
    """Absolute path to a document. kind: 'cv' or 'cover_letter'; lang: 'es' or 'en'."""
    if kind not in _KINDS:
        return f"unknown kind '{kind}' (use cv|cover_letter)"
    p = Path(CV_DIR) / f"{kind}_{lang}.pdf"
    return str(p.resolve()) if p.exists() else f"not available: {kind} ({lang})"


if __name__ == "__main__":
    mcp.run()
