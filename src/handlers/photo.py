"""Photo handler: vision reply when the configured model supports it, a graceful
decline otherwise. Telegram sends several PhotoSize thumbnails per photo — we always
use the largest (update.message.photo[-1]).

Part of the josembot project, original work by Jose Miguel Gómez Lozano
(github.com/josemygel/telegram-cv-bot) — see AUTHORS.md and LICENSE.
"""
from __future__ import annotations

import asyncio
import base64
import tempfile
import time
from pathlib import Path

from ..llm import BackendError
from .util import mark_seen, typing_action

_LANG_NAME = {"es": "Spanish", "en": "English"}
RATE_LIMIT_SECONDS = 5  # vision calls are heavier than plain text


def make_photo_handler(deps):
    pipeline = deps["pipeline"]
    lang_store = deps["lang_store"]
    i18n = deps["i18n"]
    vision_enabled = deps.get("vision_enabled", False)
    history_store = deps.get("history_store")
    t = i18n.t
    busy: set[int] = set()
    last_call: dict[int, float] = {}

    async def _log(update, chat_id: int, user_text: str, reply: str) -> None:
        if history_store is None:
            return
        u = update.effective_user
        await asyncio.to_thread(history_store.record, chat_id, u.id, u.username, u.first_name, "user", user_text)
        await asyncio.to_thread(history_store.record, chat_id, u.id, u.username, u.first_name, "assistant", reply)

    async def on_photo(update, context):
        uid = update.effective_user.id
        chat_id = update.effective_chat.id
        lang = lang_store.get(uid)
        await mark_seen(update.message)
        caption = (update.message.caption or "").strip()

        if not vision_enabled:
            decline = t("vision_unavailable", lang)
            await update.message.reply_text(decline)
            await _log(update, chat_id, caption or "[image]", decline)
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
                with tempfile.TemporaryDirectory() as tmp:
                    photo_path = str(Path(tmp) / "photo.jpg")
                    tg_file = await context.bot.get_file(update.message.photo[-1].file_id)
                    await tg_file.download_to_drive(photo_path)
                    image_b64 = base64.b64encode(Path(photo_path).read_bytes()).decode("ascii")
                try:
                    out = await asyncio.to_thread(
                        pipeline.process_image, chat_id, image_b64, caption, _LANG_NAME.get(lang, "Spanish")
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
            await _log(update, chat_id, caption or "[image]", reply)
            await update.message.reply_text(reply)
        finally:
            busy.discard(chat_id)

    return on_photo
