"""Formato de la transcripcion (HTML de Telegram).

`Audio de duración 1 min 5 s` + transcripcion en <pre>. Una transcripcion de 5 min supera
los 4096 caracteres de un mensaje; partir HTML ya renderizado romperia las etiquetas, asi que
se parte el TEXTO plano y cada trozo se envuelve en su propio <pre> (HTML siempre valido).
"""
from __future__ import annotations

from .formatting import escape_html

CHUNK_CHARS = 3600  # margen bajo 4096 para cabecera, etiquetas y entidades escapadas (&amp;...)


def duration_label(seconds: float) -> str:
    s = int(round(seconds))
    m, sec = divmod(s, 60)
    return f"Audio de duración {m} min {sec} s" if m else f"Audio de duración {sec} s"


def _pieces(text: str, limit: int) -> list[str]:
    out: list[str] = []
    while len(text) > limit:
        cut = text.rfind(" ", 0, limit)
        cut = cut if cut > limit // 2 else limit
        out.append(text[:cut].rstrip())
        text = text[cut:].lstrip()
    out.append(text)
    return out


def transcript_chunks(duration: float, text: str) -> list[str]:
    parts = _pieces(text.strip(), CHUNK_CHARS)
    chunks = []
    for i, part in enumerate(parts):
        head = f"{duration_label(duration)}\n" if i == 0 else ""
        chunks.append(f"{head}<pre>{escape_html(part)}</pre>")
    return chunks
