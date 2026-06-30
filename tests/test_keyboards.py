"""Inline keyboard builders: structure, callback_data and pagination."""
from dataclasses import dataclass

from src import keyboards


def _t(key, lang, **fmt):
    return key.format(**fmt) if fmt else key


@dataclass
class _P:
    id: str
    name: str
    url: str | None = None


def _datas(markup):
    return [b.callback_data for row in markup.inline_keyboard for b in row]


def test_main_menu_callbacks():
    datas = _datas(keyboards.main_menu(_t, "es"))
    assert "proj:list:0" in datas
    assert "cv:ask" in datas
    assert "lang:ask" in datas


def test_cv_menu_only_available_languages():
    datas = _datas(keyboards.cv_menu(_t, "es", ["es"]))
    assert "cv:es" in datas
    assert "cv:en" not in datas
    assert "nav:back:home" in datas


def test_projects_menu_pagination():
    projects = [_P(f"p{i}", f"Project {i}") for i in range(8)]
    page0 = keyboards.projects_menu(_t, "es", projects, page=0, page_size=6)
    datas0 = _datas(page0)
    assert "proj:open:p0" in datas0
    assert "proj:list:1" in datas0  # 'next' to page 1
    page1 = keyboards.projects_menu(_t, "es", projects, page=1, page_size=6)
    datas1 = _datas(page1)
    assert "proj:open:p6" in datas1
    assert "proj:list:0" in datas1  # 'prev' back to page 0


def test_contact_menu_links_and_copy_buttons():
    contact = {"email": "a@b.com", "phone": "+34 1", "whatsapp": "341",
               "linkedin": "https://li", "github": "https://gh", "telegram": "user"}
    flat = [b for row in keyboards.contact_menu(_t, "es", contact).inline_keyboard for b in row]
    urls = [b.url for b in flat if b.url]
    assert any("wa.me/341" in u for u in urls)
    assert "https://li" in urls and "https://gh" in urls
    assert any("t.me/user" in u for u in urls)
    copies = [b.copy_text.text for b in flat if getattr(b, "copy_text", None)]
    assert "a@b.com" in copies and "+34 1" in copies
    assert "nav:back:home" in [b.callback_data for b in flat if b.callback_data]


def test_main_menu_has_contact():
    assert "contact:show" in _datas(keyboards.main_menu(_t, "es"))


def test_project_detail_includes_facets_and_link():
    datas = _datas(keyboards.project_detail_menu(_t, "es", _P("gdf", "GDF", url="https://x")))
    assert "proj:scope:gdf" in datas
    assert "proj:role:gdf" in datas
    assert "proj:tech:gdf" in datas
    assert "nav:back:proj" in datas
