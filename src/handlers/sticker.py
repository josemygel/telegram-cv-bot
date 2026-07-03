"""Sticker handler: a light acknowledgment instead of silence (no LLM call --
there's no text to ground an answer on).

Part of the josembot project, original work by Jose Miguel Gómez Lozano
(github.com/josemygel/telegram-cv-bot) — see AUTHORS.md and LICENSE.
"""
from __future__ import annotations

import asyncio

from .util import mark_seen


def make_sticker_handler(deps):
    lang_store = deps["lang_store"]
    i18n = deps["i18n"]
    name = deps["name"]
    history_store = deps.get("history_store")
    t = i18n.t

    async def on_sticker(update, context):
        uid = update.effective_user.id
        chat_id = update.effective_chat.id
        lang = lang_store.get(uid)
        await mark_seen(update.message)
        reply = t("content_free_reply", lang, name=name)
        await update.message.reply_text(reply)
        if history_store is not None:
            u = update.effective_user
            emoji = getattr(update.message.sticker, "emoji", None) or "[sticker]"
            await asyncio.to_thread(history_store.record, chat_id, u.id, u.username, u.first_name,
                                     "user", emoji)
            await asyncio.to_thread(history_store.record, chat_id, u.id, u.username, u.first_name,
                                     "assistant", reply)

    return on_sticker
