"""Owner-only /history: lists everyone who has talked to the bot, tap a user to get
their full conversation exported as an HTML file, sent only to the admin who asked.

Hidden from the public command menu (see bot.py's per-admin BotCommandScopeChat), but
that's UX polish only — the real gate is the same ADMIN_USER_IDS check used by
/aprende and /reload (a command menu entry doesn't stop anyone from typing the
command by hand; Telegram does not enforce menu scopes server-side).

Part of the josembot project, original work by Jose Miguel Gómez Lozano
(github.com/josemygel/telegram-cv-bot) — see AUTHORS.md and LICENSE.
"""
from __future__ import annotations

import asyncio
import html
import tempfile
from pathlib import Path

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from .training import _is_admin

PAGE_SIZE = 8


def _label(u) -> str:
    handle = f"@{u.username}" if u.username else f"id:{u.user_id}"
    name = f" ({u.first_name})" if u.first_name else ""
    when = u.last_message_at.replace("T", " ")[:19]  # trim to yyyy-mm-dd HH:MM:SS
    return f"{handle}{name} {when}"


def users_menu(users, page: int = 0, page_size: int = PAGE_SIZE) -> InlineKeyboardMarkup:
    total_pages = max(1, (len(users) + page_size - 1) // page_size)
    page = max(0, min(page, total_pages - 1))
    start = page * page_size
    rows = [[InlineKeyboardButton(_label(u), callback_data=f"hist:open:{u.user_id}")]
            for u in users[start:start + page_size]]
    if total_pages > 1:
        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton("‹", callback_data=f"hist:list:{page - 1}"))
        nav.append(InlineKeyboardButton(f"{page + 1}/{total_pages}", callback_data="noop"))
        if page < total_pages - 1:
            nav.append(InlineKeyboardButton("›", callback_data=f"hist:list:{page + 1}"))
        rows.append(nav)
    return InlineKeyboardMarkup(rows)


def render_html(label: str, messages) -> str:
    esc = html.escape
    rows = "\n".join(
        f'<div class="msg {esc(m.role)}"><div class="meta">{esc(m.role)} · {esc(m.created_at)}</div>'
        f'<div class="content">{esc(m.content)}</div></div>'
        for m in messages
    )
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>{esc(label)}</title>
<style>
body {{ font-family: system-ui, sans-serif; max-width: 700px; margin: 2rem auto; padding: 0 1rem;
        background: #0d1117; color: #e6edf3; }}
.msg {{ padding: .75rem 1rem; margin-bottom: .5rem; border-radius: 8px; white-space: pre-wrap; }}
.msg.user {{ background: #1f6feb33; }}
.msg.assistant {{ background: #23863633; }}
.meta {{ font-size: .75rem; opacity: .6; margin-bottom: .25rem; }}
</style></head>
<body>
<h2>{esc(label)}</h2>
{rows}
</body></html>"""


def make_history_handlers(deps):
    history_store = deps.get("history_store")
    lang_store = deps["lang_store"]
    i18n = deps["i18n"]
    t = i18n.t

    async def history_cmd(update, context):
        uid = update.effective_user.id
        lang = lang_store.get(uid)
        if not _is_admin(uid):
            await update.message.reply_text(t("not_admin", lang))
            return
        if history_store is None:
            await update.message.reply_text(t("history_disabled", lang))
            return
        users = await asyncio.to_thread(history_store.list_users)
        if not users:
            await update.message.reply_text(t("history_empty", lang))
            return
        await update.message.reply_text(t("history_title", lang), reply_markup=users_menu(users))

    async def on_history_callback(update, context):
        query = update.callback_query
        await query.answer()
        uid = update.effective_user.id
        if not (_is_admin(uid) and history_store is not None):
            return
        parts = query.data.split(":")  # hist:list:<page> | hist:open:<user_id>
        action, arg = parts[1], parts[2]
        users = await asyncio.to_thread(history_store.list_users)
        if action == "list":
            await query.edit_message_reply_markup(reply_markup=users_menu(users, page=int(arg)))
            return
        target_id = int(arg)
        target = next((u for u in users if u.user_id == target_id), None)
        if target is None:
            return
        messages = await asyncio.to_thread(history_store.conversation, target_id)
        label = _label(target)
        export = render_html(label, messages)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / f"history_{target_id}.html"
            path.write_text(export, encoding="utf-8")
            with open(path, "rb") as fh:
                await context.bot.send_document(update.effective_chat.id, document=fh,
                                                 filename=path.name, caption=label)

    return {"history": history_cmd, "history_callback": on_history_callback}
