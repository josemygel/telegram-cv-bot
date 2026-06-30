"""Telegram-safe formatting helpers: HTML escaping + 4096-char splitting.

We use parse_mode=HTML (not MarkdownV2) on purpose: MarkdownV2 requires escaping
~15 characters and the model emits free text (dashes, dots, parentheses) that
breaks that parser constantly. HTML only needs < > & escaped.
"""
from __future__ import annotations

import html
import re

TELEGRAM_LIMIT = 4096


def escape_html(text: str) -> str:
    # quote=False keeps quotes readable; Telegram HTML only needs < > & escaped.
    return html.escape(text or "", quote=False)


# LLMs emit Markdown, but Telegram parse_mode=HTML ignores it (so "**x**" shows
# literally). We render the common Markdown into Telegram's HTML subset instead.
_CODE_RE = re.compile(r"`([^`\n]+)`")
_BOLD_RE = re.compile(r"\*\*([^*\n]+?)\*\*")
_BOLD_US_RE = re.compile(r"__([^_\n]+?)__")
_HEADING_RE = re.compile(r"(?m)^[ \t]{0,3}#{1,6}[ \t]*(.+?)[ \t]*#*$")
_ITALIC_STAR_RE = re.compile(r"(?<!\*)\*(?!\s)([^*\n]+?)(?<!\s)\*(?!\*)")
_ITALIC_US_RE = re.compile(r"(?<![\w*])_(?!\s)([^_\n]+?)(?<!\s)_(?![\w*])")
_BULLET_RE = re.compile(r"(?m)^[ \t]*[-*+][ \t]+")


def markdown_to_telegram_html(text: str) -> str:
    """Render the common Markdown an LLM emits into Telegram's HTML subset.

    Supports **bold**/__bold__, *italic*/_italic_ (word-boundary safe so snake_case
    identifiers are untouched), `inline code`, '#'-headings (-> bold line) and
    '-'/'*' bullets (-> •). HTML metacharacters are escaped first.
    """
    s = html.escape(text or "", quote=False)   # < > &  -> entities; leaves * _ # `
    s = _CODE_RE.sub(r"<code>\1</code>", s)
    s = _BOLD_RE.sub(r"<b>\1</b>", s)
    s = _BOLD_US_RE.sub(r"<b>\1</b>", s)
    s = _HEADING_RE.sub(r"<b>\1</b>", s)
    s = _ITALIC_STAR_RE.sub(r"<i>\1</i>", s)
    s = _ITALIC_US_RE.sub(r"<i>\1</i>", s)
    s = _BULLET_RE.sub("• ", s)
    return s


def split_message(text: str, limit: int = TELEGRAM_LIMIT) -> list[str]:
    """Split text into <=limit chunks without cutting words mid-token where
    avoidable. Telegram rejects messages longer than 4096 chars."""
    text = text or ""
    if len(text) <= limit:
        return [text]
    chunks: list[str] = []
    current = ""
    for line in text.split("\n"):
        candidate = f"{current}\n{line}" if current else line
        if len(candidate) <= limit:
            current = candidate
            continue
        if current:
            chunks.append(current)
            current = ""
        # A single line longer than the limit: hard-split by words.
        while len(line) > limit:
            cut = line.rfind(" ", 0, limit)
            cut = cut if cut > 0 else limit
            chunks.append(line[:cut])
            line = line[cut:].lstrip()
        current = line
    if current:
        chunks.append(current)
    return chunks
