"""Teclados y constantes de los botones del dueno (compartidos por audio y callbacks)."""
from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

# codigo corto (cabe en callback_data) -> (etiqueta, nombre para el prompt del LLM)
TARGET_LANGS = {
    "es": ("Español", "Spanish"),
    "ca": ("Català", "Catalan (use Valencian forms where they differ)"),
    "gb": ("English (UK)", "British English"),
    "us": ("English (US)", "American English"),
    "de": ("Deutsch", "German"),
    "fr": ("Français", "French"),
}
_SRC_NAMES = {"es": "Español", "ca": "Català", "en": "English", "de": "Deutsch", "fr": "Français",
              "pt": "Português", "it": "Italiano"}


def source_lang_name(code: str) -> str:
    return _SRC_NAMES.get(code, code.upper()) if code else "no detectado"


def owner_audio_keyboard(action_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("💬 Responder", callback_data=f"act:r:{action_id}"),
        InlineKeyboardButton("📝 Resumir", callback_data=f"act:s:{action_id}"),
        InlineKeyboardButton("🌐 Traducir", callback_data=f"act:t:{action_id}"),
    ]])


def language_keyboard(action_id: str) -> InlineKeyboardMarkup:
    btns = [InlineKeyboardButton(label, callback_data=f"act:l:{code}:{action_id}")
            for code, (label, _) in TARGET_LANGS.items()]
    return InlineKeyboardMarkup([btns[:3], btns[3:]])
