"""PDF (todos los usuarios, solo con backend Anthropic): se envia nativo a Claude.

Topes en orden barato->caro: peso informado por Telegram (sin descargar) -> descarga -> paginas
(pypdf). El fichero vive en un directorio temporal que se borra siempre.
"""
from __future__ import annotations

import logging

import asyncio
import base64
import tempfile
import time
from pathlib import Path

from ..bubble import StatusBubble
from ..config import MAX_PDF_PAGES
from ..formatting import markdown_to_telegram_html, split_message
from ..llm import BackendError
from ..media_caps import pdf_size_refusal
from ..token_ledger import call_context
from .guard import after_call, refuse_if_blocked
from .util import mark_seen

_LANG_NAME = {"es": "Spanish", "en": "English"}
RATE_LIMIT_SECONDS = 10


def count_pages(path: str) -> int:
    from pypdf import PdfReader  # import perezoso: solo se necesita con PDFs

    reader = PdfReader(path)
    if reader.is_encrypted:
        raise ValueError("encrypted")
    return len(reader.pages)


def make_pdf_handler(deps):
    pipeline, lang_store, t = deps["pipeline"], deps["lang_store"], deps["i18n"].t
    enabled = deps.get("pdf_enabled", False)
    busy: set[int] = set()
    last_call: dict[int, float] = {}

    async def on_pdf(update, context):
        msg, uid, chat_id = update.message, update.effective_user.id, update.effective_chat.id
        lang = lang_store.get(uid)
        if not enabled:
            await msg.reply_text(t("pdf_unavailable", lang))
            return
        await mark_seen(msg)
        if await refuse_if_blocked(deps, update, lang):
            return
        refusal = pdf_size_refusal(getattr(msg.document, "file_size", None))
        if refusal:
            await msg.reply_text(t(refusal[0], lang, **refusal[1]))
            return
        now = time.monotonic()
        if now - last_call.get(uid, 0.0) < RATE_LIMIT_SECONDS:
            await msg.reply_text(t("rate_limited", lang))
            return
        if chat_id in busy:
            await msg.reply_text(t("busy", lang))
            return
        busy.add(chat_id)
        last_call[uid] = now
        bubble = StatusBubble(msg)
        try:
            await bubble.start("💭 Pensando…")
            with tempfile.TemporaryDirectory() as tmp:
                path = str(Path(tmp) / "doc.pdf")
                tg_file = await context.bot.get_file(msg.document.file_id)
                await tg_file.download_to_drive(path)
                try:
                    pages = await asyncio.to_thread(count_pages, path)
                except Exception:  # noqa: BLE001 - corrupto o cifrado
                    await bubble.edit(t("pdf_unreadable", lang))
                    return
                if pages > MAX_PDF_PAGES:
                    await bubble.edit(t("pdf_too_many_pages", lang, max=MAX_PDF_PAGES))
                    return
                pdf_b64 = base64.b64encode(Path(path).read_bytes()).decode("ascii")
            call_context.set((uid, "pdf"))
            try:
                if uid == deps.get("owner_id"):
                    part = {"type": "pdf", "data": pdf_b64}
                    out = await asyncio.to_thread(pipeline.analyze_media_for_owner, part,
                                                  (msg.caption or "").strip(), "pdf")
                else:
                    out = await asyncio.to_thread(pipeline.process_pdf, chat_id, pdf_b64,
                                                  (msg.caption or "").strip(), _LANG_NAME.get(lang, "Spanish"))
            except BackendError:
                await bubble.edit(t("error_backend", lang))
                return
            await after_call(deps, context, update.effective_user)
            reply = (out.get("reply") or "").strip() or t("empty_reply", lang)
            await bubble.show(split_message(markdown_to_telegram_html(reply)))
        except Exception:  # noqa: BLE001
            logging.getLogger("josembot.pdf").exception("Fallo procesando un PDF")
            try:
                await bubble.edit(t("error_generic", lang))
            except Exception:  # noqa: BLE001
                pass
        finally:
            busy.discard(chat_id)

    return on_pdf
