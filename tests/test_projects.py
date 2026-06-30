"""ProjectsRepository over the real profile/projects.yaml (validates the data too)."""
from src.projects import ProjectsRepository

REPO = ProjectsRepository("profile/projects.yaml")


def test_lists_all_projects():
    projects = REPO.list_projects()
    assert len(projects) >= 4
    ids = {p.id for p in projects}
    assert {"gdfitness", "engram-colmena", "quant-ml"} <= ids


def test_get_known_project():
    gdf = REPO.get("gdfitness")
    assert gdf is not None
    assert "CTO" in gdf.role
    assert gdf.scope_text("es") and gdf.scope_text("en")
    assert gdf.participation_text("es") and gdf.participation_text("en")


def test_get_unknown_returns_none():
    assert REPO.get("does-not-exist") is None


def test_missing_file_degrades_to_empty():
    assert ProjectsRepository("profile/__nope__.yaml").list_projects() == []
