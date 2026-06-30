from pathlib import Path

from src.profile import build_system_prompt


def test_grounding_includes_rules_name_and_profile(tmp_path: Path):
    prof = tmp_path / "profile.md"
    prof.write_text("Jose builds RAG systems and fine-tunes models.", encoding="utf-8")
    sp = build_system_prompt(name="Tester", path=str(prof))
    assert "Tester" in sp
    assert "Never invent facts" in sp                       # honesty guardrail present
    assert "Jose builds RAG systems and fine-tunes models." in sp  # profile injected


def test_missing_profile_is_empty_not_error(tmp_path: Path):
    sp = build_system_prompt(name="X", path=str(tmp_path / "nope.md"))
    assert "X" in sp  # still builds; profile section just empty
