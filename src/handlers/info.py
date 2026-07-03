"""Owner-only /info: which build is answering, from where, with what config.

Exists to answer one operational question fast: "is the instance replying to me the
one I think I deployed?". After a local↔VPS migration a forgotten auto-started copy
can steal polling (Telegram allows one getUpdates consumer per token) — /info makes
that visible: the hostname is the Docker container ID when running in a container,
so a reply from an unexpected host or an old version exposes the stray instance.

Same real gate as /history: ADMIN_USER_IDS (the hidden command menu is cosmetic).

Part of the josembot project, original work by Jose Miguel Gómez Lozano
(github.com/josemygel/telegram-cv-bot) — see AUTHORS.md and LICENSE.
"""
from __future__ import annotations

import platform
import socket
from datetime import datetime, timezone

from telegram.constants import ParseMode

from ..i18n import resolve_lang
from .training import _is_admin


def _fmt_uptime(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    d, h = divmod(h, 24)
    return f"{d}d {h}h {m}m" if d else f"{h}h {m}m {s}s"


def make_info_handler(deps):
    i18n = deps["i18n"]
    lang_store = deps["lang_store"]
    runtime = deps.get("runtime_info") or {}
    history_store = deps.get("history_store")
    t = i18n.t

    async def info(update, context):
        uid = update.effective_user.id
        if not lang_store.is_set(uid):
            lang_store.set(uid, resolve_lang(update.effective_user.language_code))
        lang = lang_store.get(uid)
        if not _is_admin(uid):
            await update.message.reply_text(t("not_admin", lang))
            return

        started_at: datetime | None = runtime.get("started_at")
        now = datetime.now(timezone.utc)
        uptime = _fmt_uptime((now - started_at).total_seconds()) if started_at else "?"
        started = started_at.strftime("%Y-%m-%d %H:%M:%S UTC") if started_at else "?"
        history = "on" if history_store is not None else "off"

        lines = [
            f"<b>{t('info_title', lang)}</b>",
            f"version: <code>{runtime.get('version', '?')}</code>",
            # Inside Docker the hostname IS the short container ID — compare it against
            # `docker ps` / the Plesk container panel to confirm which instance replied.
            f"host: <code>{socket.gethostname()}</code>",
            f"mode: <code>{runtime.get('mode', '?')}</code>",
            f"llm: <code>{runtime.get('llm_backend', '?')} / {runtime.get('llm_model', '?')}</code>",
            f"vision: <code>{'on' if deps.get('vision_enabled') else 'off'}</code>",
            f"history: <code>{history}</code>",
            f"python: <code>{platform.python_version()}</code>",
            f"started: <code>{started}</code>",
            f"uptime: <code>{uptime}</code>",
        ]
        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)

    return info
