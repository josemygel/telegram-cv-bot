"""Project model validation rules (TDD specs)."""
import pytest

from src.models import Project

_VALID = {
    "id": "x", "name": "X", "role": "Dev", "status": "public", "stack": ["py"],
    "scope": {"es": "alcance", "en": "scope"},
    "participation": {"es": "hice", "en": "did"},
    "summary": {"es": "resumen", "en": "summary"},
}


def test_from_dict_valid():
    p = Project.from_dict(_VALID)
    assert p.id == "x"
    assert p.scope_text("es") == "alcance"
    assert p.scope_text("en") == "scope"
    assert p.stack == ("py",)


def test_missing_id_raises():
    bad = {k: v for k, v in _VALID.items() if k != "id"}
    with pytest.raises(ValueError):
        Project.from_dict(bad)


def test_missing_translation_raises():
    bad = dict(_VALID, scope={"es": "solo es"})
    with pytest.raises(ValueError):
        Project.from_dict(bad)


def test_language_fallback_to_en():
    p = Project.from_dict(_VALID)
    assert p._pick({"en": "only-en"}, "es") == "only-en"
