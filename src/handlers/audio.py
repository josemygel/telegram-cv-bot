"""Notas de voz y audios: transcripcion local con burbuja de estado.

Flujo: topes (con lo que informa Telegram, sin descargar) -> burbuja -> descarga a un
directorio temporal que se borra SIEMPRE -> cola de un trabajador (Whisper en un hilo) ->
transcripcion en <pre>.
- Otros usuarios: debajo de la transcripcion Claude responde en la misma burbuja.
- Dueno: solo transcripcion + botones (Responder/Resumir/Traducir); sin llamada al LLM,
  asi reenviar un audio largo no cuesta tokens salvo que pulse un boton.
Privacidad: del contenido de terceros solo se guarda en /history el marcador con la duracion.
"""
from __future__ import annotations

import asyncio
import logging
import tempfile
import time
from pathlib import Path

from telegram.constants import ParseMode

from ..bubble import StatusBubble, fmt_clock
from ..formatting import markdown_to_telegram_html, split_message
from ..llm import BackendError
from ..media_caps import audio_refusal
from ..token_ledger import call_context
from ..transcript import transcript_chunks
from .actions_ui import owner_audio_keyboard
from .guard import after_call, refuse_if_blocked
from .util import mark_seen

_LANG_NAME = {"es": "Spanish", "en": "English"}
RATE_LIMIT_SECONDS = 5
TICK_SECONDS = 2.0  # cadencia con la que se refresca el progreso


def make_audio_handler(deps):
    pipeline, lang_store, i18n = deps["pipeline"], deps["lang_store"], deps["i18n"]
    stt, queue, store = deps.get("stt"), deps.get("queue"), deps.get("action_store")
    owner_id, history_store, t = deps.get("owner_id"), deps.get("history_store"), i18n.t
    busy: set[int] = set()
    last_call: dict[int, float] = {}

    async def _progress_ticker(bubble, state, total_label):
        """Refresca la burbuja con el progreso que el hilo de Whisper va apuntando en `state`."""
        while True:
            await asyncio.sleep(TICK_SECONDS)
            done = state.get("done")
            if done is not None:
                await bubble.edit(f"🎙️ Transcribiendo… {fmt_clock(done)} / {total_label}", throttle=True)

    async def on_audio(update, context):
        msg, user = update.message, update.effective_user
        uid, chat_id = user.id, update.effective_chat.id
        is_owner = uid == owner_id
        lang = lang_store.get(uid)
        media = msg.voice or msg.audio or msg.document  # voz, audio de Telegram o archivo de audio
        # Solo notas de voz para el resto; audios/archivos de audio son cosa del dueno.
        if msg.voice is None and not is_owner:
            await msg.reply_text(t("unsupported_media", lang))
            return
        if stt is None or queue is None:
            await msg.reply_text(t("voice_disabled", lang))
            return
        await mark_seen(msg)
        if await refuse_if_blocked(deps, update, lang):
            return
        duration = getattr(media, "duration", None)
        refusal = audio_refusal(duration, getattr(media, "file_size", None), is_owner)
        if refusal:
            await msg.reply_text(t(refusal[0], lang, **refusal[1]))
            return
        if not is_owner:  # el dueno puede reenviar varios seguidos: la cola los ordena
            now = time.monotonic()
            if now - last_call.get(uid, 0.0) < RATE_LIMIT_SECONDS:
                await msg.reply_text(t("rate_limited", lang))
                return
            if chat_id in busy:
                await msg.reply_text(t("busy", lang))
                return
            busy.add(chat_id)
            last_call[uid] = now
        total_label = fmt_clock(float(duration or 0))
        bubble = StatusBubble(msg)
        state: dict = {}
        ticker = None
        try:
            await bubble.start(f"🎙️ Transcribiendo… 0:00 / {total_label}")
            with tempfile.TemporaryDirectory() as tmp:  # el audio se borra aqui pase lo que pase
                path = str(Path(tmp) / "in.audio")
                tg_file = await context.bot.get_file(media.file_id)
                await tg_file.download_to_drive(path)

                async def on_wait(n):
                    await bubble.edit(f"⏳ En cola ({n}.º)…")

                ticker = asyncio.create_task(_progress_ticker(bubble, state, total_label))
                result = await queue.run(
                    stt.transcribe_progress, path, lambda done, tot: state.update(done=done), on_wait=on_wait)
            ticker.cancel()
            if not result.text:
                await bubble.edit(t("voice_unintelligible", lang))
                return
            dur = result.duration or float(duration or 0)
            chunks = transcript_chunks(dur, result.text)
            if is_owner:
                action_id = store.put(uid, result.text, chunks[-1], result.language)
                await bubble.show(chunks, owner_audio_keyboard(action_id))
                return
            await _answer_for_user(update, context, bubble, chunks, result, dur)
        except Exception:  # noqa: BLE001 - cualquier fallo -> mensaje corto, nunca silencio
            # Sin esta traza el fallo era invisible en produccion (solo «Ups, algo ha fallado»).
            logging.getLogger("josembot.audio").exception("Fallo procesando un audio")
            try:
                await bubble.edit(t("error_generic", lang))
            except Exception:  # noqa: BLE001
                pass
        finally:
            if ticker:
                ticker.cancel()
            busy.discard(chat_id)

    async def _answer_for_user(update, context, bubble, chunks, result, dur):
        uid, chat_id = update.effective_user.id, update.effective_chat.id
        det = "es" if result.language == "es" else "en"
        lang_store.set(uid, det)  # se contesta en el idioma en que hablo
        base = chunks[-1]
        await bubble.show(chunks[:-1] + [base + "\n\n💭 Pensando…"])
        call_context.set((uid, "answer"))
        try:
            out = await asyncio.to_thread(pipeline.process_text, chat_id, result.text, _LANG_NAME[det])
        except BackendError:
            await bubble.show(chunks[:-1] + [base + "\n\n" + t("error_backend", det)])
            return
        await after_call(deps, context, update.effective_user)
        reply = (out.get("reply") or "").strip() or t("empty_reply", det)
        answer = split_message(markdown_to_telegram_html(reply))
        if len(base) + 2 + len(answer[0]) <= 4096:
            await bubble.show(chunks[:-1] + [base + "\n\n" + answer[0]])
            extra = answer[1:]
        else:
            await bubble.show(chunks)  # quita "Pensando" y la respuesta va como mensajes nuevos
            extra = answer
        for chunk in extra:
            await update.message.reply_text(chunk, parse_mode=ParseMode.HTML)
        if history_store is not None:  # solo metadatos: nada del contenido del audio
            u = update.effective_user
            await asyncio.to_thread(history_store.record, chat_id, u.id, u.username, u.first_name,
                                    "user", f"[audio {int(dur)} s]")

    return on_audio
