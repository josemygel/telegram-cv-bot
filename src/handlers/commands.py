"""Command handlers: /start, /menu, /proyectos, /cv, /idioma, /help.

Built via make_command_handlers(deps) so dependencies are injected, not global.
"""
from __future__ import annotations

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
    t = i18n.t

    def _lang(update) -> str:
        uid = update.effective_user.id
        if not lang_store.is_set(uid):
            # Seed from the user's Telegram client language on first contact.
            lang_store.set(uid, resolve_lang(update.effective_user.language_code))
        return lang_store.get(uid)

    async def start(update, context):
        lang = _lang(update)
        text = t("start_greeting", lang, name=name) + "\n\n" + t("start_hint", lang)
        await update.message.reply_text(text, reply_markup=keyboards.main_menu(t, lang), parse_mode=ParseMode.HTML)

    async def menu(update, context):
        lang = _lang(update)
        await update.message.reply_text(t("menu_title", lang), reply_markup=keyboards.main_menu(t, lang))

    async def projects(update, context):
        lang = _lang(update)
        await update.message.reply_text(
            t("projects_title", lang),
            reply_markup=keyboards.projects_menu(t, lang, projects_repo.list_projects(), 0),
        )

    async def cv(update, context):
        lang = _lang(update)
        await update.message.reply_text(
            t("cv_choose", lang),
            reply_markup=keyboards.cv_menu(t, lang, cv_service.available_languages()),
        )

    async def language(update, context):
        lang = _lang(update)
        await update.message.reply_text(t("lang_choose", lang), reply_markup=keyboards.language_menu(t, lang))

    async def contact_(update, context):
        lang = _lang(update)
        await update.message.reply_text(t("contact_title", lang), reply_markup=keyboards.contact_menu(t, lang, contact))

    async def help_(update, context):
        lang = _lang(update)
        await update.message.reply_text(t("help_text", lang), parse_mode=ParseMode.HTML)

    async def voice_toggle(update, context):
        lang = _lang(update)
        uid = update.effective_user.id
        if not voice_enabled:
            await update.message.reply_text(t("voice_unavailable", lang))
            return
        if uid in voice_pref:
            voice_pref.discard(uid)
            await update.message.reply_text(t("voice_off", lang))
        else:
            voice_pref.add(uid)
            await update.message.reply_text(t("voice_on", lang))

    return {"start": start, "menu": menu, "projects": projects, "cv": cv,
            "language": language, "contact": contact_, "help": help_, "voice": voice_toggle}
