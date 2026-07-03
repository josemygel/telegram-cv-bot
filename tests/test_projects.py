"""ProjectsRepository over the committed profile/projects.example.yaml (validates the
schema without depending on profile/projects.yaml, which is git-ignored personal data
and won't exist in CI or a fresh clone)."""
from src.projects import ProjectsRepository

REPO = ProjectsRepository("profile/projects.example.yaml")


def test_lists_all_projects():
    projects = REPO.list_projects()
    assert len(projects) >= 2
    ids = {p.id for p in projects}
    assert {"example-product", "example-research"} <= ids


def test_get_known_project():
    proj = REPO.get("example-product")
    assert proj is not None
    assert "CTO" in proj.role
    assert proj.scope_text("es") and proj.scope_text("en")
    assert proj.participation_text("es") and proj.participation_text("en")


def test_get_unknown_returns_none():
    assert REPO.get("does-not-exist") is None


def test_missing_file_degrades_to_empty():
    assert ProjectsRepository("profile/__nope__.yaml").list_projects() == []
