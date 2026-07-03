"""Command handlers: /start, /menu, /proyectos, /cv, /idioma, /help.

Built via make_command_handlers(deps) so dependencies are injected, not global.

Every command is also recorded to the history store (when enabled): menu taps are
often a visitor's ONLY interaction, and without this the owner's /history would
show nobody was ever here. The stored "assistant" row is the reply's title text —
keyboards themselves aren't serialized.
"""
from __future__ import annotations

import asyncio

from telegram.constants import ParseMode

from .. import keyboards
from ..i18n import resolve_lang


def make_command_handlers(deps):
    i18n = deps["i18n"]
    projects_repo = deps["projects"]
    cv_service = deps["cv"]
    lang_store = deps["lang_store"]
    name = deps["name"]
    contact = deps.get("contact") or {}
    voice_enabled = deps.get("voice_enabled", False)
    voice_pref = deps.get("voice_pref")
    if voice_pref is None:
        voice_pref = set()
    history_store = deps.get("history_store")
    t = i18n.t

    def _lang(update) -> str:
        uid = update.effective_user.id
        if not lang_store.is_set(uid):
            # Seed from the user's Telegram client language on first contact.
            lang_store.set(uid, resolve_lang(update.effective_user.language_code))
        return lang_store.get(uid)

    async def _log(update, reply: str) -> None:
        if history_store is None:
            return
        u = update.effective_user
        chat_id = update.effective_chat.id
        user_text = update.message.text or ""
        await asyncio.to_thread(history_store.record, chat_id, u.id, u.username, u.first_name, "user", user_text)
        await asyncio.to_thread(history_store.record, chat_id, u.id, u.username, u.first_name, "assistant", reply)

    async def start(update, context):
        lang = _lang(update)
        text = t("start_greeting", lang, name=name) + "\n\n" + t("start_hint", lang)
        await update.message.reply_text(text, reply_markup=keyboards.main_menu(t, lang), parse_mode=ParseMode.HTML)
        await _log(update, text)

    async def menu(update, context):
        lang = _lang(update)
        reply = t("menu_title", lang)
        await update.message.reply_text(reply, reply_markup=keyboards.main_menu(t, lang))
        await _log(update, reply)

    async def projects(update, context):
        lang = _lang(update)
        reply = t("projects_title", lang)
        await update.message.reply_text(
            reply,
            reply_markup=keyboards.projects_menu(t, lang, projects_repo.list_projects(), 0),
        )
        await _log(update, reply)

    async def cv(update, context):
        lang = _lang(update)
        reply = t("cv_choose", lang)
        await update.message.reply_text(
            reply,
            reply_markup=keyboards.cv_menu(t, lang, cv_service.available_languages()),
        )
        await _log(update, reply)

    async def language(update, context):
        lang = _lang(update)
        reply = t("lang_choose", lang)
        await update.message.reply_text(reply, reply_markup=keyboards.language_menu(t, lang))
        await _log(update, reply)

    async def contact_(update, context):
        lang = _lang(update)
        reply = t("contact_title", lang, name=name)
        await update.message.reply_text(reply, reply_markup=keyboards.contact_menu(t, lang, contact))
        await _log(update, reply)

    async def help_(update, context):
        lang = _lang(update)
        reply = t("help_text", lang, name=name)
        await update.message.reply_text(reply, parse_mode=ParseMode.HTML)
        await _log(update, reply)

    async def voice_toggle(update, context):
        lang = _lang(update)
        uid = update.effective_user.id
        if not voice_enabled:
            reply = t("voice_unavailable", lang)
        elif uid in voice_pref:
            voice_pref.discard(uid)
            reply = t("voice_off", lang)
        else:
            voice_pref.add(uid)
            reply = t("voice_on", lang)
        await update.message.reply_text(reply)
        await _log(update, reply)

    return {"start": start, "menu": menu, "projects": projects, "cv": cv,
            "language": language, "contact": contact_, "help": help_, "voice": voice_toggle}
