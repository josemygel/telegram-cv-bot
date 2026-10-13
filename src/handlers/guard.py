"""Guardas anti-abuso compartidas por los handlers (backend de pago).

POR QUE un modulo aparte: texto y foto necesitan exactamente la misma comprobacion
de bloqueo y el mismo aviso a admins; duplicarla en cada handler garantiza que
acabarian divergiendo. Todo es no-op si no hay ledger (backends gratuitos/locales).

Part of the josembot project, original work by Jose Miguel Gómez Lozano
(github.com/josemygel/telegram-cv-bot) — see AUTHORS.md and LICENSE.
"""
from __future__ import annotations

import logging

log = logging.getLogger("josembot.guard")

_GROUP_TYPES = {"group", "supergroup", "channel"}
_PRESENT = {"member", "administrator"}


async def refuse_if_blocked(deps, update, lang: str) -> bool:
    """True (tras avisar con un mensaje amable) si el usuario esta bloqueado por consumo."""
    ledger = deps.get("ledger")
    if ledger is None or not ledger.is_blocked(update.effective_user.id):
        return False
    await update.message.reply_text(deps["i18n"].t("user_blocked", lang))
    return True


async def after_call(deps, context, user) -> None:
    """Tras una llamada de pago: evalua limites y, si el usuario acaba de pasarse,
    avisa UNA vez a los admins (evaluate() solo devuelve True en la transicion)."""
    ledger = deps.get("ledger")
    if ledger is None or not ledger.evaluate(user.id):
        return
    who = f"@{user.username}" if getattr(user, "username", None) else f"id:{user.id}"
    text = deps["i18n"].t("admin_user_blocked", "es", who=who, uid=user.id)
    for admin_id in deps.get("admin_ids") or ():
        try:
            await context.bot.send_message(admin_id, text)
        except Exception as exc:  # noqa: BLE001 - un admin que bloqueo al bot no debe romper el flujo
            log.warning("No se pudo avisar al admin %s: %s", admin_id, exc)


def make_ignored_media_handler(deps):
    """Video, notas de video, documentos, animaciones, audio: se ignoran con un aviso
    corto SIN descargar nada (el PDF llegara en la fase B)."""
    lang_store, t = deps["lang_store"], deps["i18n"].t

    async def on_ignored(update, context):
        await update.message.reply_text(t("unsupported_media", lang_store.get(update.effective_user.id)))

    return on_ignored


def make_group_guard(deps):
    """El bot abandona cualquier grupo al que lo anade alguien que no es el dueno:
    en un grupo cualquiera podria gastar credito sin control."""
    async def on_my_chat_member(update, context):
        ev = update.my_chat_member
        if ev.chat.type not in _GROUP_TYPES or ev.new_chat_member.status not in _PRESENT:
            return
        if ev.from_user.id == deps.get("owner_id"):
            return
        await context.bot.leave_chat(ev.chat.id)

    return on_my_chat_member
