"""CV service: resolves existing PDFs, degrades to None when missing."""
from src.cv_service import CvService


def test_missing_dir_no_languages(tmp_path):
    svc = CvService(str(tmp_path))
    assert svc.available_languages() == []
    assert svc.path_for("es") is None
    assert svc.exists("en") is False


def test_resolves_existing_pdf(tmp_path):
    (tmp_path / "cv_es.pdf").write_bytes(b"%PDF-1.4 fake")
    svc = CvService(str(tmp_path))
    assert svc.exists("es") is True
    assert svc.exists("en") is False
    assert svc.available_languages() == ["es"]
    assert svc.path_for("es") is not None
