"""Knowledge file: append facts and load them back."""
from src.knowledge import append_fact, load_knowledge


def test_append_and_load(tmp_path):
    p = str(tmp_path / "k.md")
    append_fact("Le gusta enseñar en charlas técnicas", p)
    append_fact("Disponible para remoto", p)
    txt = load_knowledge(p)
    assert "- Le gusta enseñar en charlas técnicas" in txt
    assert "- Disponible para remoto" in txt


def test_append_flattens_newlines(tmp_path):
    p = str(tmp_path / "k.md")
    append_fact("línea 1\nlínea 2", p)
    assert "línea 1 línea 2" in load_knowledge(p)


def test_load_missing_is_empty(tmp_path):
    assert load_knowledge(str(tmp_path / "nope.md")) == ""
