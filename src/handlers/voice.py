"""Voice-note handler: voice in -> voice out.

Flow (all async, off the event loop for the blocking parts):
  voice note -> download OGG -> faster-whisper STT (+ language detect) -> echo transcript
  -> grounded LLM (same pipeline as text) -> edge-TTS -> reply with an OGG/Opus voice note.

A live voice CALL is NOT possible via the Telegram Bot API (it would need an MTProto
userbot + pytgcalls), so voice notes are the supported real-time-ish channel. Every
blocking step is guarded so a failure degrades to a clear message or to a text answer.
"""
from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from telegram.constants import ChatAction, ParseMode

from ..formatting import markdown_to_telegram_html, split_message
from ..llm import BackendError
from .util import mark_seen, typing_action

_LANG_NAME = {"es": "Spanish", "en": "English"}


def make_voice_handler(deps):
    pipeline = deps["pipeline"]
    lang_store = deps["lang_store"]
    i18n = deps["i18n"]
    stt = deps.get("stt")
    tts = deps.get("tts")
    voice_enabled = deps.get("voice_enabled", False)
    t = i18n.t
    busy: set[int] = set()

    async def on_voice(update, context):
        uid = update.effective_user.id
        chat_id = update.effective_chat.id
        await mark_seen(update.message)
        if not (voice_enabled and stt and tts):
            await update.message.reply_text(t("voice_disabled", lang_store.get(uid)))
            return
        if chat_id in busy:
            await update.message.reply_text(t("busy", lang_store.get(uid)))
            return
        busy.add(chat_id)
        try:
            async with typing_action(context.bot, chat_id, action=ChatAction.RECORD_VOICE):
                with tempfile.TemporaryDirectory() as tmp:
                    ogg_in = str(Path(tmp) / "in.ogg")
                    tg_file = await context.bot.get_file(update.message.voice.file_id)
                    await tg_file.download_to_drive(ogg_in)

                    try:
                        transcript, detected = await asyncio.to_thread(stt.transcribe_detailed, ogg_in)
                    except Exception:
                        await update.message.reply_text(t("error_generic", lang_store.get(uid)))
                        return
                    if not transcript:
                        await update.message.reply_text(t("voice_unintelligible", lang_store.get(uid)))
                        return

                    lang_store.set(uid, detected)  # reply in the language the user spoke
                    lang = detected
                    await update.message.reply_text(f"\U0001F5E3 {transcript}")  # echo what was heard

                    try:
                        out = await asyncio.to_thread(
                            pipeline.process_text, chat_id, transcript, _LANG_NAME.get(lang, "Spanish")
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

                    # Speak the answer back as a voice note; if TTS/network fails, send text.
                    ogg_out = str(Path(tmp) / "out.ogg")
                    try:
                        await asyncio.to_thread(tts.synthesize, reply, ogg_out, lang)
                        with open(ogg_out, "rb") as fh:
                            await update.message.reply_voice(voice=fh)
                    except Exception:
                        for chunk in split_message(markdown_to_telegram_html(reply)):
                            await update.message.reply_text(chunk, parse_mode=ParseMode.HTML)
        finally:
            busy.discard(chat_id)

    return on_voice
