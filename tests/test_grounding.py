"""Grounding prompt: third-person rules, project details and curated knowledge."""
from src.grounding import build_grounded_prompt
from src.models import Project

_PROJECT = Project.from_dict({
    "id": "x", "name": "ProjX", "role": "Dev", "status": "public", "stack": ["py"],
    "scope": {"es": "alcance", "en": "scope"},
    "participation": {"es": "hizo", "en": "did"},
    "summary": {"es": "resumen", "en": "summary"},
    "details": {"es": "detalle largo en español", "en": "long detail in english"},
})


def test_prompt_has_rules_projects_details_and_knowledge(tmp_path):
    prof = tmp_path / "p.md"
    prof.write_text("Bio de prueba.", encoding="utf-8")
    sp = build_grounded_prompt("Tester", str(prof), [_PROJECT], knowledge="- dato extra del dueño")
    assert "Never invent facts" in sp          # honesty guardrail preserved
    assert "THIRD PERSON" in sp                 # person fix present
    assert "Bio de prueba." in sp               # profile injected
    assert "ProjX" in sp                        # project injected
    assert "long detail in english" in sp       # optional details injected
    assert "dato extra del dueño" in sp         # curated knowledge injected


def test_no_knowledge_section_when_empty(tmp_path):
    prof = tmp_path / "p.md"
    prof.write_text("Bio.", encoding="utf-8")
    sp = build_grounded_prompt("Tester", str(prof), [_PROJECT], knowledge="")
    assert "ADDITIONAL KNOWLEDGE" not in sp
