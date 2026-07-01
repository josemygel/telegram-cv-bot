"""Generate starter CV PDFs (cv/cv_es.pdf, cv/cv_en.pdf) from your data.

Part of the josembot project, original work by Jose Miguel Gómez Lozano
(github.com/josemygel/telegram-cv-bot) — see AUTHORS.md and LICENSE.

This is a simple, dependency-light generator (reportlab — no Word/LibreOffice needed). It pulls
your name + contact from config/.env and your projects from profile/projects.yaml; the bio text
below is a template you edit (or just bring your own designed PDFs into cv/). reportlab flows
content across pages automatically: it fits one page when it can and extends to a second only if
the content needs it. Run from the project root:  python scripts/build_cv.py
"""
from __future__ import annotations

import sys
from pathlib import Path
from xml.sax.saxutils import escape

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from reportlab.lib.enums import TA_CENTER  # noqa: E402
from reportlab.lib.pagesizes import A4  # noqa: E402
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet  # noqa: E402
from reportlab.lib.units import cm  # noqa: E402
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer  # noqa: E402

from src.config import (  # noqa: E402
    ASSISTANT_NAME, CONTACT_EMAIL, CONTACT_GITHUB, CONTACT_LINKEDIN, CONTACT_PHONE, CV_DIR,
)
from src.projects import ProjectsRepository  # noqa: E402

CONTACT = " · ".join(x for x in [CONTACT_EMAIL, CONTACT_PHONE, CONTACT_LINKEDIN, CONTACT_GITHUB] if x)

# Edit this bio template with your own headline / summary / strengths (es + en).
BIO = {
    "es": {
        "headline": "Tu titular profesional (p. ej. Machine Learning Engineer)",
        "sec_summary": "Resumen", "summary": "Tu resumen profesional: quién eres, tu foco y qué construyes.",
        "sec_strengths": "Fortalezas",
        "strengths": ["Fortaleza 1 con tecnologías concretas.", "Fortaleza 2.", "Fortaleza 3."],
        "sec_projects": "Proyectos", "lbl_scope": "Envergadura", "lbl_part": "Participación",
        "lbl_stack": "Stack", "sec_contact": "Contacto",
        "languages": "Idiomas: tu idioma nativo; otros y nivel honesto.",
    },
    "en": {
        "headline": "Your professional headline (e.g. Machine Learning Engineer)",
        "sec_summary": "Summary", "summary": "Your professional summary: who you are, your focus, what you build.",
        "sec_strengths": "Strengths",
        "strengths": ["Strength 1 with concrete technologies.", "Strength 2.", "Strength 3."],
        "sec_projects": "Projects", "lbl_scope": "Scope", "lbl_part": "Participation",
        "lbl_stack": "Stack", "sec_contact": "Contact",
        "languages": "Languages: your native language; others and an honest level.",
    },
}


def _styles():
    base = getSampleStyleSheet()
    return {
        "name": ParagraphStyle("Name", parent=base["Title"], fontSize=20, spaceAfter=2, alignment=TA_CENTER),
        "headline": ParagraphStyle("Headline", parent=base["Normal"], fontSize=11, textColor="#444444",
                                   alignment=TA_CENTER, spaceAfter=10),
        "section": ParagraphStyle("Section", parent=base["Heading2"], fontSize=13, spaceBefore=10, spaceAfter=4,
                                  textColor="#1a5276"),
        "body": ParagraphStyle("Body", parent=base["Normal"], fontSize=10, leading=14),
        "bullet": ParagraphStyle("Bullet", parent=base["Normal"], fontSize=10, leading=14, leftIndent=10),
        "small": ParagraphStyle("Small", parent=base["Normal"], fontSize=9, textColor="#444444", alignment=TA_CENTER),
    }


def _build(lang: str, projects, out_path: Path) -> None:
    c = BIO[lang]
    st = _styles()
    flow = [
        Paragraph(escape(ASSISTANT_NAME), st["name"]),
        Paragraph(escape(c["headline"]), st["headline"]),
        Paragraph(escape(c["sec_summary"]), st["section"]),
        Paragraph(escape(c["summary"]), st["body"]),
        Paragraph(escape(c["sec_strengths"]), st["section"]),
    ]
    flow += [Paragraph("• " + escape(s), st["bullet"]) for s in c["strengths"]]
    flow.append(Paragraph(escape(c["sec_projects"]), st["section"]))
    for p in projects:
        flow.append(Paragraph(f"<b>{escape(p.name)}</b> — {escape(p.role)}", st["body"]))
        flow.append(Paragraph(escape(p.summary_text(lang)), st["body"]))
        flow.append(Paragraph(f"<i>{escape(c['lbl_scope'])}:</i> {escape(p.scope_text(lang))}", st["bullet"]))
        flow.append(Paragraph(f"<i>{escape(c['lbl_part'])}:</i> {escape(p.participation_text(lang))}", st["bullet"]))
        flow.append(Paragraph(f"<i>{escape(c['lbl_stack'])}:</i> {escape(', '.join(p.stack))}", st["bullet"]))
        flow.append(Spacer(1, 4))
    if CONTACT:
        flow.append(Paragraph(escape(c["sec_contact"]), st["section"]))
        flow.append(Paragraph(escape(c["languages"]), st["body"]))
        flow.append(Spacer(1, 4))
        flow.append(Paragraph(escape(CONTACT), st["small"]))

    SimpleDocTemplate(
        str(out_path), pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm, topMargin=1.5 * cm, bottomMargin=1.5 * cm,
        title=f"{ASSISTANT_NAME} — CV ({lang.upper()})", author=ASSISTANT_NAME,
    ).build(flow)


def main() -> None:
    projects = ProjectsRepository().list_projects()
    out_dir = Path(CV_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    for lang in ("es", "en"):
        out = out_dir / f"cv_{lang}.pdf"
        if out.exists():
            print(f"Skip {out} (already present — delete it to regenerate)")
            continue
        _build(lang, projects, out)
        print(f"Wrote {out} ({out.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
