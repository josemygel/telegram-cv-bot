"""Free-text handler: the only path that calls the LLM.

Bundles resilience for slow/uncertain local models in one place:
- 👀 seen-receipt + typing indicator,
- per-chat busy lock so message bursts don't fire parallel LLM calls,
- per-user rate limit (cooldown) so a public bot can't be spammed into racking up
  paid-backend costs or hammering the local STT/TTS/LLM,
- input length cap so one message can't blow up the LLM context/cost,
- BackendError -> clear localized message; empty reply -> honest fallback,
- HTML-escaped, 4096-split output,
- optional AUDIO reply: persistent /voz preference, or an explicit in-message request.
"""
from __future__ import annotations

import asyncio
import re
import tempfile
import time
import unicodedata
from pathlib import Path

from telegram.constants import ParseMode

from .. import keyboards
from ..formatting import markdown_to_telegram_html, split_message
from ..i18n import resolve_lang
from ..llm import BackendError
from .util import mark_seen, typing_action

_LANG_NAME = {"es": "Spanish", "en": "English"}

MAX_MESSAGE_CHARS = 1500  # generous for a real question; blocks copy-pasted walls of text
RATE_LIMIT_SECONDS = 3  # minimum gap between LLM calls per user, on a public bot

# Pure greetings get a fixed, formatted reply (no LLM) so the welcome is consistent
# and instant. A greeting WITH a question ("hola, cuéntame de X") still goes to the LLM.
_GREETINGS = {
    "hola", "holaa", "holaaa", "ola", "buenas", "buenos dias", "buenas tardes", "buenas noches",
    "hola buenas", "saludos", "que tal", "hello", "helo", "hi", "hii", "hey", "ey",
    "hello there", "hey there", "good morning", "good afternoon", "good evening",
}


def _is_greeting(text: str) -> bool:
    norm = unicodedata.normalize("NFD", (text or "").lower())
    norm = "".join(c for c in norm if unicodedata.category(c) != "Mn")  # drop accents
    norm = re.sub(r"[^a-z ]+", "", norm).strip()
    norm = re.sub(r"\s+", " ", norm)
    return bool(norm) and norm in _GREETINGS

# Explicit one-off requests to also get the answer as a voice note.
_AUDIO_REQUESTS = (
    "en audio", "en voz", "respondeme en audio", "respóndeme en audio", "manda un audio",
    "mandame un audio", "mándame un audio", "en un audio", "contesta en audio",
    "in audio", "by voice", "as audio", "read it aloud", "say it aloud", "voice reply",
)


def _wants_audio(text: str) -> bool:
    low = (text or "").lower()
    return any(phrase in low for phrase in _AUDIO_REQUESTS)


# Clear contact requests get the buttons (no LLM). "contactado" etc. don't match.
_CONTACT_INTENTS = (
    "contacto", "contactar", "contactarle", "contactarlo", "contactarte", "ponerme en contacto",
    "datos de contacto", "get in touch", "contact him", "contact you", "contact details",
    "contact info", "how to contact", "how can i contact", "reach out", "reach him",
)


def _wants_contact(text: str) -> bool:
    low = (text or "").lower()
    return any(phrase in low for phrase in _CONTACT_INTENTS)


def make_text_handler(deps):
    pipeline = deps["pipeline"]
    lang_store = deps["lang_store"]
    i18n = deps["i18n"]
    tts = deps.get("tts")
    voice_enabled = deps.get("voice_enabled", False)
    voice_pref = deps.get("voice_pref")
    if voice_pref is None:
        voice_pref = set()
    contact = deps.get("contact") or {}
    name = deps["name"]
    t = i18n.t
    busy: set[int] = set()
    last_call: dict[int, float] = {}

    async def _send_voice(update, reply: str, lang: str) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ogg = str(Path(tmp) / "out.ogg")
            await asyncio.to_thread(tts.synthesize, reply, ogg, lang)
            with open(ogg, "rb") as fh:
                await update.message.reply_voice(voice=fh)

    async def on_text(update, context):
        uid = update.effective_user.id
        chat_id = update.effective_chat.id
        if not lang_store.is_set(uid):
            lang_store.set(uid, resolve_lang(update.effective_user.language_code))
        lang = lang_store.get(uid)
        text = update.message.text or ""

        await mark_seen(update.message)
        if _is_greeting(text):
            # Fixed, formatted welcome — no LLM, so it's instant and always consistent.
            await update.message.reply_text(
                markdown_to_telegram_html(t("greeting", lang)), parse_mode=ParseMode.HTML
            )
            return
        if _wants_contact(text):
            # Show the contact buttons instead of an LLM text dump.
            await update.message.reply_text(
                t("contact_title", lang, name=name), reply_markup=keyboards.contact_menu(t, lang, contact)
            )
            return
        if len(text) > MAX_MESSAGE_CHARS:
            await update.message.reply_text(t("message_too_long", lang, max=MAX_MESSAGE_CHARS))
            return
        now = time.monotonic()
        if now - last_call.get(uid, 0.0) < RATE_LIMIT_SECONDS:
            await update.message.reply_text(t("rate_limited", lang))
            return
        if chat_id in busy:
            await update.message.reply_text(t("busy", lang))
            return
        busy.add(chat_id)
        last_call[uid] = now
        try:
            async with typing_action(context.bot, chat_id):
                try:
                    out = await asyncio.to_thread(
                        pipeline.process_text, chat_id, text, _LANG_NAME.get(lang, "Spanish")
                    )
                except BackendError:
                    await update.message.reply_text(t("error_backend", lang))
                    return
                except Exception:
                    await update.message.reply_text(t("error_generic", lang))
                    return
            reply = (out.get("reply") or "").strip()
            if not reply:
                await update.message.reply_text(t("empty_reply", lang))
                return
            for chunk in split_message(markdown_to_telegram_html(reply)):
                await update.message.reply_text(chunk, parse_mode=ParseMode.HTML)
            # Bonus audio reply (text already delivered, so failures are swallowed).
            if voice_enabled and tts and (uid in voice_pref or _wants_audio(text)):
                try:
                    await _send_voice(update, reply, lang)
                except Exception:
                    pass
        finally:
            busy.discard(chat_id)

    return on_text
