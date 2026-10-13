"""Callbacks de los botones del dueno: Responder / Resumir / Traducir.

Seguridad: se verifica from_user.id == OWNER en CADA callback (callback_data es forjable por
un cliente modificado y el mensaje podria reenviarse). El texto fuente sale de SQLite por id
corto, no del callback_data (limite de 64 bytes).
"""
from __future__ import annotations

import asyncio

from telegram.constants import ParseMode

from ..formatting import escape_html, markdown_to_telegram_html, split_message
from ..llm import BackendError
from ..token_ledger import call_context
from .actions_ui import TARGET_LANGS, language_keyboard, source_lang_name
from .guard import after_call
from .util import safe_edit

LIMIT = 4096

SUMMARY_PROMPT = ("Resume el texto del usuario en 3 líneas como máximo. Si contiene tareas o acciones "
                  "pendientes, añade al final 'Acciones:' con viñetas. Responde en el idioma del texto "
                  "y no añadas nada más.")


def translate_prompt(target: str) -> str:
    return (f"Translate the user's text into {target}. Output ONLY the translation, with no comments, "
            "quotes or explanations. Keep names, numbers and technical terms intact.")


def make_action_handler(deps):
    pipeline, store, t = deps["pipeline"], deps["action_store"], deps["i18n"].t
    owner_id = deps.get("owner_id")

    async def _append(query, base: str, addition: str) -> None:
        """Anade `addition` (HTML) bajo el mensaje; si no cabe, el mensaje queda como esta y el
        resultado sale en mensajes nuevos."""
        if len(base) + 2 + len(addition) <= LIMIT:
            await safe_edit(query, base + "\n\n" + addition, parse_mode=ParseMode.HTML)
            return
        await safe_edit(query, base, parse_mode=ParseMode.HTML)
        for chunk in split_message(addition):
            await query.message.reply_text(chunk, parse_mode=ParseMode.HTML)

    async def _call(update, context, feature: str, fn, *args):
        call_context.set((update.effective_user.id, feature))
        try:
            out = await asyncio.to_thread(fn, *args)
        except BackendError:
            return None
        await after_call(deps, context, update.effective_user)
        return out

    async def on_action(update, context):
        query = update.callback_query
        if query.from_user.id != owner_id:
            await query.answer(t("action_forbidden", "es"), show_alert=True)
            return
        parts = query.data.split(":")  # act:r:<id> | act:s:<id> | act:t:<id> | act:l:<code>:<id>
        kind, action_id = parts[1], parts[-1]
        item = store.get(action_id)
        if item is None:
            await query.answer(t("action_expired", "es"), show_alert=True)
            return
        await query.answer()
        base = item.base_html
        if kind == "t":  # paso intermedio: elegir idioma destino
            await safe_edit(query, f"{base}\n\n🌐 Idioma de origen: {escape_html(source_lang_name(item.lang))}",
                            reply_markup=language_keyboard(action_id), parse_mode=ParseMode.HTML)
            return
        await safe_edit(query, base + "\n\n💭 Pensando…", parse_mode=ParseMode.HTML)
        if kind == "r":
            out = await _call(update, context, "answer", pipeline.process_text,
                              update.effective_chat.id, item.source_text)
            text = None if out is None else (out.get("reply") or "").strip()
            add = markdown_to_telegram_html(text) if text else None
        elif kind == "s":
            text = await _call(update, context, "summary", pipeline.run_task, SUMMARY_PROMPT, item.source_text)
            add = markdown_to_telegram_html(text) if text else None
        elif kind == "l":
            label, target = TARGET_LANGS[parts[2]]
            text = await _call(update, context, "translate", pipeline.run_task,
                               translate_prompt(target), item.source_text)
            add = f"🌐 {label}:\n{escape_html(text)}" if text else None
        else:
            return
        await _append(query, base, add or t("error_generic", "es"))

    return on_action
