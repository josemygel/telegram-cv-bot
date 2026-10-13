"""Burbuja de estado: UN mensaje del bot que se edita en sitio.

POR QUE: transcribir tarda decenas de segundos; en vez de spamear mensajes, se responde al
audio del usuario y se edita esa respuesta (transcribiendo m:ss / m:ss -> pensando -> final).
Telegram limita las ediciones por chat, por eso el progreso se limita a 1 cada >=2 s, y el
error "message is not modified" (mismo texto) se ignora.
"""
from __future__ import annotations

import time
from typing import Callable

from telegram.constants import ParseMode
from telegram.error import BadRequest

MIN_EDIT_INTERVAL = 2.0


def fmt_clock(seconds: float) -> str:
    s = max(0, int(seconds))
    return f"{s // 60}:{s % 60:02d}"


class StatusBubble:
    def __init__(self, origin, clock: Callable[[], float] = time.monotonic):
        self._origin = origin  # mensaje del usuario al que se responde
        self._msg = None
        self._extra: list[tuple] = []  # (mensaje, ultimo texto) de los trozos 1..n
        self._last_text: str | None = None
        self._last_edit = float("-inf")
        self._clock = clock

    async def start(self, text: str) -> None:
        self._msg = await self._origin.reply_text(text)
        self._last_text, self._last_edit = text, self._clock()

    async def edit(self, text: str, parse_mode=None, markup=None, throttle: bool = False) -> None:
        if self._msg is None:
            await self.start(text)
            return
        now = self._clock()
        if throttle and now - self._last_edit < MIN_EDIT_INTERVAL:
            return
        if text == self._last_text and markup is None:
            return
        try:
            await self._msg.edit_text(text, parse_mode=parse_mode, reply_markup=markup)
        except BadRequest as exc:
            if "not modified" not in str(exc).lower():
                raise
        self._last_text, self._last_edit = text, now

    async def show(self, chunks: list[str], markup=None) -> None:
        """Texto final en HTML (limite 4096 por mensaje). El trozo 0 se edita en la burbuja;
        los demas son mensajes propios que se crean la primera vez y se EDITAN en llamadas
        posteriores (asi 'Pensando...' -> respuesta no duplica mensajes). El teclado va en el
        ultimo trozo."""
        last = len(chunks) - 1
        await self.edit(chunks[0], ParseMode.HTML, markup if last == 0 else None)
        for i, chunk in enumerate(chunks[1:], start=1):
            kb = markup if i == last else None
            if i - 1 < len(self._extra):
                msg, old = self._extra[i - 1]
                if old != chunk or kb is not None:
                    try:
                        await msg.edit_text(chunk, parse_mode=ParseMode.HTML, reply_markup=kb)
                    except BadRequest as exc:
                        if "not modified" not in str(exc).lower():
                            raise
                self._extra[i - 1] = (msg, chunk)
            else:
                msg = await self._origin.reply_text(chunk, parse_mode=ParseMode.HTML, reply_markup=kb)
                self._extra.append((msg, chunk))
