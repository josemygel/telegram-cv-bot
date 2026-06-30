"""Pure InlineKeyboardMarkup builders. No Telegram I/O -> trivially unit-testable.

callback_data scheme (namespaced, stateless, <=64 bytes — Telegram's hard limit):
  cv:ask | cv:es | cv:en
  proj:list:<page> | proj:open:<id> | proj:scope:<id> | proj:role:<id> | proj:tech:<id>
  lang:ask | lang:es | lang:en
  nav:back:home | nav:back:proj | nav:back:proj:<id>
  noop  (page-indicator button)
Language is NOT embedded in callback_data — it lives in the LangStore — so ids
stay short and language-agnostic.
"""
from __future__ import annotations

from telegram import CopyTextButton, InlineKeyboardButton, InlineKeyboardMarkup

PAGE_SIZE = 6


def main_menu(t, lang):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("btn_projects", lang), callback_data="proj:list:0"),
         InlineKeyboardButton(t("btn_cv", lang), callback_data="cv:ask")],
        [InlineKeyboardButton(t("btn_contact", lang), callback_data="contact:show"),
         InlineKeyboardButton(t("btn_language", lang), callback_data="lang:ask")],
    ])


def cv_menu(t, lang, available):
    row = []
    if "es" in available:
        row.append(InlineKeyboardButton(t("btn_cv_es", lang), callback_data="cv:es"))
    if "en" in available:
        row.append(InlineKeyboardButton(t("btn_cv_en", lang), callback_data="cv:en"))
    rows = [row] if row else []
    rows.append([InlineKeyboardButton(t("btn_back", lang), callback_data="nav:back:home")])
    return InlineKeyboardMarkup(rows)


def projects_menu(t, lang, projects, page=0, page_size=PAGE_SIZE):
    total_pages = max(1, (len(projects) + page_size - 1) // page_size)
    page = max(0, min(page, total_pages - 1))
    start = page * page_size
    rows = [[InlineKeyboardButton(p.name, callback_data=f"proj:open:{p.id}")]
            for p in projects[start:start + page_size]]
    if total_pages > 1:
        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton(t("btn_prev", lang), callback_data=f"proj:list:{page - 1}"))
        nav.append(InlineKeyboardButton(t("page_indicator", lang, cur=page + 1, total=total_pages),
                                        callback_data="noop"))
        if page < total_pages - 1:
            nav.append(InlineKeyboardButton(t("btn_next", lang), callback_data=f"proj:list:{page + 1}"))
        rows.append(nav)
    rows.append([InlineKeyboardButton(t("btn_back", lang), callback_data="nav:back:home")])
    return InlineKeyboardMarkup(rows)


def project_detail_menu(t, lang, project):
    rows = [
        [InlineKeyboardButton(t("btn_scope", lang), callback_data=f"proj:scope:{project.id}"),
         InlineKeyboardButton(t("btn_participation", lang), callback_data=f"proj:role:{project.id}")],
        [InlineKeyboardButton(t("btn_stack", lang), callback_data=f"proj:tech:{project.id}")],
    ]
    if project.url:
        rows.append([InlineKeyboardButton(t("btn_link", lang), url=project.url)])
    rows.append([InlineKeyboardButton(t("btn_back_projects", lang), callback_data="nav:back:proj")])
    return InlineKeyboardMarkup(rows)


def language_menu(t, lang):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("btn_lang_es", lang), callback_data="lang:es"),
         InlineKeyboardButton(t("btn_lang_en", lang), callback_data="lang:en")],
        [InlineKeyboardButton(t("btn_back", lang), callback_data="nav:back:home")],
    ])


def contact_menu(t, lang, contact):
    """Contact buttons. Email/phone use copy-to-clipboard (Telegram url buttons can't be
    mailto:/tel:); WhatsApp/Telegram/LinkedIn/GitHub are link buttons."""
    rows = []
    if contact.get("email"):
        rows.append([InlineKeyboardButton(f"📧 {contact['email']}",
                                          copy_text=CopyTextButton(text=contact["email"]))])
    if contact.get("phone"):
        rows.append([InlineKeyboardButton(f"📞 {contact['phone']}",
                                          copy_text=CopyTextButton(text=contact["phone"]))])
    msg_row = []
    if contact.get("whatsapp"):
        msg_row.append(InlineKeyboardButton(t("btn_whatsapp", lang), url=f"https://wa.me/{contact['whatsapp']}"))
    if contact.get("telegram"):
        msg_row.append(InlineKeyboardButton(t("btn_telegram", lang), url=f"https://t.me/{contact['telegram']}"))
    if msg_row:
        rows.append(msg_row)
    prof_row = []
    if contact.get("linkedin"):
        prof_row.append(InlineKeyboardButton(t("btn_linkedin", lang), url=contact["linkedin"]))
    if contact.get("github"):
        prof_row.append(InlineKeyboardButton(t("btn_github", lang), url=contact["github"]))
    if prof_row:
        rows.append(prof_row)
    rows.append([InlineKeyboardButton(t("btn_back", lang), callback_data="nav:back:home")])
    return InlineKeyboardMarkup(rows)
