"""HTML escaping + Telegram 4096-char splitting."""
from src.formatting import TELEGRAM_LIMIT, escape_html, markdown_to_telegram_html, split_message


def test_md_bold_italic_code():
    assert markdown_to_telegram_html("**Engram**") == "<b>Engram</b>"
    assert markdown_to_telegram_html("*RAG*") == "<i>RAG</i>"
    assert markdown_to_telegram_html("`code()`") == "<code>code()</code>"


def test_md_heading_becomes_bold():
    assert markdown_to_telegram_html("### Detalles clave") == "<b>Detalles clave</b>"


def test_md_bullets_become_dots():
    assert markdown_to_telegram_html("- uno") == "• uno"
    assert markdown_to_telegram_html("* dos") == "• dos"


def test_md_preserves_snake_case_and_escapes_html():
    assert markdown_to_telegram_html("usa file_name y out_of_time") == "usa file_name y out_of_time"
    assert "&lt;tag&gt;" in markdown_to_telegram_html("a <tag> b")


def test_escape_html():
    assert escape_html("<b> & </b>") == "&lt;b&gt; &amp; &lt;/b&gt;"


def test_short_text_single_chunk():
    assert split_message("hola") == ["hola"]


def test_long_text_split_under_limit():
    text = "palabra " * 1500  # ~12000 chars
    chunks = split_message(text)
    assert len(chunks) > 1
    assert all(len(c) <= TELEGRAM_LIMIT for c in chunks)


def test_long_single_line_hard_split():
    text = "x" * (TELEGRAM_LIMIT * 2 + 50)  # no spaces -> must hard-split
    chunks = split_message(text)
    assert all(len(c) <= TELEGRAM_LIMIT for c in chunks)
    assert "".join(chunks) == text
