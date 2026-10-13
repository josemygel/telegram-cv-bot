"""Comandos SOLO del dueno: /coste (consumo) y /desbloquear <id>.

Gate real = comparar con OWNER_USER_ID (no ADMIN_USER_IDS): el dinero es del dueno.
Si OWNER_USER_ID no esta definido, nadie pasa (fallo cerrado).

Part of the josembot project, original work by Jose Miguel Gómez Lozano
(github.com/josemygel/telegram-cv-bot) — see AUTHORS.md and LICENSE.
"""
from __future__ import annotations

import asyncio


def _lines(rows) -> str:
    return "\n".join(f"{r.user_id}: {r.total_tokens} tok · ${r.cost_usd:.4f} · {r.calls} llamadas" for r in rows)


def make_cost_handlers(deps):
    ledger, lang_store, t = deps.get("ledger"), deps["lang_store"], deps["i18n"].t

    def _is_owner(uid: int) -> bool:
        return bool(deps.get("owner_id")) and uid == deps["owner_id"]

    async def coste(update, context):
        uid = update.effective_user.id
        lang = lang_store.get(uid)
        if not _is_owner(uid):
            await update.message.reply_text(t("not_admin", lang))
            return
        if ledger is None:
            await update.message.reply_text(t("cost_disabled", lang))
            return
        parts = []
        for period, key in (("day", "cost_today"), ("month", "cost_month")):
            rows = await asyncio.to_thread(ledger.report, period)
            total = sum(r.cost_usd for r in rows)
            body = _lines(rows) or t("cost_empty", lang)
            parts.append(f"{t(key, lang)} (${total:.4f})\n{body}")
        await update.message.reply_text("\n\n".join(parts))

    async def unblock(update, context):
        uid = update.effective_user.id
        lang = lang_store.get(uid)
        if not _is_owner(uid):
            await update.message.reply_text(t("not_admin", lang))
            return
        arg = (context.args[0] if context.args else "").strip()
        if ledger is None or not arg.lstrip("-").isdigit():
            await update.message.reply_text(t("unblock_usage", lang))
            return
        was = await asyncio.to_thread(ledger.unblock, int(arg))
        await update.message.reply_text(t("unblock_done" if was else "unblock_none", lang, uid=arg))

    return {"coste": coste, "unblock": unblock}
