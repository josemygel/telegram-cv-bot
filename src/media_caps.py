"""Topes de audio/PDF contra lo que Telegram informa en el update, ANTES de descargar.

Funciones puras: devuelven (clave_i18n, parametros) con el motivo del rechazo, o None si pasa.
"""
from __future__ import annotations

from .config import (
    MAX_AUDIO_BYTES, MAX_AUDIO_SECONDS_OWNER, MAX_AUDIO_SECONDS_USER, MAX_PDF_BYTES,
)


def audio_refusal(duration: int | None, size: int | None, is_owner: bool):
    max_s = MAX_AUDIO_SECONDS_OWNER if is_owner else MAX_AUDIO_SECONDS_USER
    if duration is not None and duration > max_s:
        return "audio_too_long", {"max": max_s}
    if size is not None and size > MAX_AUDIO_BYTES:
        return "audio_too_large", {"max": MAX_AUDIO_BYTES // (1024 * 1024)}
    return None


def pdf_size_refusal(size: int | None):
    if size is not None and size > MAX_PDF_BYTES:
        return "pdf_too_large", {"max": MAX_PDF_BYTES // (1024 * 1024)}
    return None
