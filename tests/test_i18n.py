"""i18n lookup over the real content/i18n tables (also catches missing keys)."""
from src.i18n import I18n, resolve_lang

I = I18n("content/i18n", default="es")


def test_resolve_lang():
    assert resolve_lang("es-ES") == "es"
    assert resolve_lang("en-US") == "en"
    assert resolve_lang(None) == "en"


def test_known_keys_localized_and_nonempty():
    for lang in ("es", "en"):
        for key in ("btn_cv", "btn_projects", "menu_title", "cv_unavailable", "error_backend"):
            assert I.t(key, lang).strip()


def test_format_args():
    assert "Ada" in I.t("start_greeting", "en", name="Ada")


def test_unknown_key_falls_back_to_key():
    assert I.t("totally_missing_key", "es") == "totally_missing_key"
