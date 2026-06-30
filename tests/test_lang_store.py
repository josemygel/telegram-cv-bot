"""Per-user language store behavior."""
from src.lang_store import InMemoryLangStore


def test_default_until_set():
    s = InMemoryLangStore(default="es")
    assert s.get(1) == "es"
    assert s.is_set(1) is False


def test_set_and_isolation():
    s = InMemoryLangStore(default="es")
    s.set(1, "en")
    assert s.get(1) == "en"
    assert s.is_set(1) is True
    assert s.get(2) == "es"  # other user unaffected


def test_invalid_lang_ignored():
    s = InMemoryLangStore(default="es")
    s.set(1, "fr")
    assert s.is_set(1) is False
    assert s.get(1) == "es"
