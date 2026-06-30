"""Small async helpers shared by handlers."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from telegram import ReactionTypeEmoji
from telegram.constants import ChatAction
from telegram.error import BadRequest


@asynccontextmanager
async def typing_action(bot, chat_id, action=ChatAction.TYPING, interval=4.0):
    """Keep Telegram's 'typing…' status alive while a slow LLM call runs.

    The chat action expires after ~5s, so we re-send it on a loop and cancel
    the loop when the work finishes. Without this the user thinks the bot hung.
    """
    async def _loop():
        try:
            while True:
                await bot.send_chat_action(chat_id, action)
                await asyncio.sleep(interval)
        except asyncio.CancelledError:
            pass

    task = asyncio.create_task(_loop())
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


async def safe_edit(query, text, reply_markup=None, parse_mode=None):
    """Edit a message, tolerating Telegram's 'message is not modified' error
    (raised when a user taps a button that yields identical content)."""
    try:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
    except BadRequest as exc:
        if "not modified" in str(exc).lower():
            return
        raise


async def mark_seen(message, emoji: str = "\U0001F440") -> None:
    """React to an incoming message with an emoji (default 👀) as a 'seen' receipt.

    Guarded: reactions can be forbidden/disabled in some chats, and the emoji must
    be in Telegram's allowed reaction set — a failure must never block the reply.
    """
    try:
        await message.set_reaction(ReactionTypeEmoji(emoji=emoji))
    except Exception:
        pass
