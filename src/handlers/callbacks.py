"""CallbackQuery handlers for inline-button navigation.

Stateless: all navigation state lives in the callback_data (see keyboards.py),
so 'Back' needs no ConversationHandler and survives restarts. Every handler calls
query.answer() first (Telegram requires it to stop the client spinner).
"""
from __future__ import annotations

from telegram.constants import ChatAction, ParseMode

from .. import keyboards
from ..i18n import resolve_lang
from . import render
from .util import safe_edit


def make_callback_handlers(deps):
    i18n = deps["i18n"]
    projects_repo = deps["projects"]
    cv_service = deps["cv"]
    lang_store = deps["lang_store"]
    name = deps["name"]
    contact = deps.get("contact") or {}
    t = i18n.t

    def _lang(update) -> str:
        uid = update.effective_user.id
        if not lang_store.is_set(uid):
            lang_store.set(uid, resolve_lang(update.effective_user.language_code))
        return lang_store.get(uid)

    async def on_cv(update, context):
        query = update.callback_query
        await query.answer()
        lang = _lang(update)
        if query.data == "cv:ask":
            await safe_edit(query, t("cv_choose", lang),
                            reply_markup=keyboards.cv_menu(t, lang, cv_service.available_languages()))
            return
        cv_lang = "es" if query.data == "cv:es" else "en"
        path = cv_service.path_for(cv_lang)
        if path is None:
            await query.answer(t("cv_unavailable", lang), show_alert=True)
            return
        chat_id = update.effective_chat.id
        await context.bot.send_chat_action(chat_id, ChatAction.UPLOAD_DOCUMENT)
        with open(path, "rb") as fh:
            await context.bot.send_document(
                chat_id,
                document=fh,
                filename=f"{name.replace(' ', '_')}_CV_{cv_lang.upper()}.pdf",
                caption=t("cv_caption", lang, name=name),
            )

    async def on_projects(update, context):
        query = update.callback_query
        await query.answer()
        lang = _lang(update)
        parts = query.data.split(":")  # proj:<action>[:<arg>]
        action = parts[1]
        arg = parts[2] if len(parts) > 2 else ""
        if action == "list":
            page = int(arg) if arg.isdigit() else 0
            await safe_edit(query, t("projects_title", lang),
                            reply_markup=keyboards.projects_menu(t, lang, projects_repo.list_projects(), page))
            return
        project = projects_repo.get(arg)
        if project is None:
            await query.answer(t("project_not_found", lang), show_alert=True)
            return
        if action == "open":
            await safe_edit(query, render.project_overview(t, lang, project),
                            reply_markup=keyboards.project_detail_menu(t, lang, project), parse_mode=ParseMode.HTML)
        else:  # scope | role | tech
            await safe_edit(query, render.project_facet(t, lang, project, action),
                            reply_markup=keyboards.project_detail_menu(t, lang, project), parse_mode=ParseMode.HTML)

    async def on_lang(update, context):
        query = update.callback_query
        await query.answer()
        uid = update.effective_user.id
        if query.data == "lang:ask":
            await safe_edit(query, t("lang_choose", lang_store.get(uid)),
                            reply_markup=keyboards.language_menu(t, lang_store.get(uid)))
            return
        new_lang = "es" if query.data == "lang:es" else "en"
        lang_store.set(uid, new_lang)
        await safe_edit(query, t("lang_set", new_lang) + "\n\n" + t("menu_title", new_lang),
                        reply_markup=keyboards.main_menu(t, new_lang))

    async def on_nav(update, context):
        query = update.callback_query
        await query.answer()
        lang = _lang(update)
        data = query.data  # nav:back:home | nav:back:proj | nav:back:proj:<id>
        if data == "nav:back:home":
            await safe_edit(query, t("menu_title", lang), reply_markup=keyboards.main_menu(t, lang))
            return
        if data == "nav:back:proj":
            await safe_edit(query, t("projects_title", lang),
                            reply_markup=keyboards.projects_menu(t, lang, projects_repo.list_projects(), 0))
            return
        parts = data.split(":")
        project = projects_repo.get(parts[3]) if len(parts) > 3 else None
        if project is not None:
            await safe_edit(query, render.project_overview(t, lang, project),
                            reply_markup=keyboards.project_detail_menu(t, lang, project), parse_mode=ParseMode.HTML)

    async def on_contact(update, context):
        query = update.callback_query
        await query.answer()
        lang = _lang(update)
        await safe_edit(query, t("contact_title", lang), reply_markup=keyboards.contact_menu(t, lang, contact))

    async def on_noop(update, context):
        await update.callback_query.answer()

    return {"cv": on_cv, "projects": on_projects, "lang": on_lang, "nav": on_nav,
            "contact": on_contact, "noop": on_noop}
