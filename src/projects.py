"""ProjectsRepository: loads and validates projects.yaml.

Single responsibility = project data access. Cached in memory because the file
is tiny and static. Inject a path in tests; defaults to config.PROJECTS_PATH.
"""
from __future__ import annotations

from pathlib import Path

import yaml

from .config import PROJECTS_PATH
from .models import Project


class ProjectsRepository:
    def __init__(self, path: str | None = None):
        self._path = Path(path or PROJECTS_PATH)
        self._cache: list[Project] | None = None

    def _load(self) -> list[Project]:
        if self._cache is None:
            if not self._path.exists():
                self._cache = []  # degrade gracefully: no projects, not a crash
            else:
                raw = yaml.safe_load(self._path.read_text(encoding="utf-8")) or {}
                items = raw.get("projects", []) if isinstance(raw, dict) else (raw or [])
                projects = [Project.from_dict(item) for item in items]
                self._cache = sorted(projects, key=lambda p: (p.order, p.name))
        return self._cache

    def list_projects(self) -> list[Project]:
        return list(self._load())

    def get(self, project_id: str) -> Project | None:
        return next((p for p in self._load() if p.id == project_id), None)

    def reload(self) -> None:
        """Drop the cache so the next access re-reads the YAML from disk (used by /reload)."""
        self._cache = None
