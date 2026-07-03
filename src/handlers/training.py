"""Owner-only 'training' commands — teach the bot at runtime, no restart needed.

  /whoami           -> your Telegram id (to lock down access via ADMIN_USER_IDS).
  /aprende <texto>  -> append a fact to profile/knowledge.md and hot-reload grounding.
  /reload           -> re-read profile/projects/knowledge from disk (after editing files).
  /claim <code>     -> one-time bootstrap: become the first admin (see below).

Gated by config.ADMIN_USER_IDS; if it's empty, allowed (convenient while you set it up).
This is grounding-based 'training': accurate, versionable and instant — no fine-tuning.
"""
from __future__ import annotations

import secrets
from pathlib import Path

from ..config import ADMIN_CLAIM_CODE, ADMIN_USER_IDS, ASSISTANT_NAME, PROFILE_PATH
from ..grounding import build_grounded_prompt
from ..knowledge import append_fact

ENV_PATH = ".env"


def _is_admin(user_id: int) -> bool:
    return (not ADMIN_USER_IDS) or (user_id in ADMIN_USER_IDS)


def _persist_admin_id(user_id: int, env_path: str | None = None) -> bool:
    """Best-effort: add user_id to ADMIN_USER_IDS= in .env so /claim survives a
    restart. In-memory admin status is granted either way (see ADMIN_USER_IDS.add()
    in claim() below) -- this just makes it stick. env_path defaults to the module-level
    ENV_PATH, looked up at CALL time (not as a bound default) so tests can monkeypatch it."""
    try:
        path = Path(env_path if env_path is not None else ENV_PATH)
        lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
        for i, line in enumerate(lines):
            if line.startswith("ADMIN_USER_IDS="):
                current = line[len("ADMIN_USER_IDS="):].strip()
                ids = [x for x in current.split(",") if x.strip()]
                if str(user_id) not in ids:
                    ids.append(str(user_id))
                lines[i] = "ADMIN_USER_IDS=" + ",".join(ids)
                break
        else:
            lines.append(f"ADMIN_USER_IDS={user_id}")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return True
    except OSError:
        return False


def make_training_handlers(deps):
    i18n = deps["i18n"]
    projects_repo = deps["projects"]
    pipeline = deps["pipeline"]
    lang_store = deps["lang_store"]
    t = i18n.t

    def _rebuild() -> None:
        prompt = build_grounded_prompt(ASSISTANT_NAME, PROFILE_PATH, projects_repo.list_projects())
        pipeline.set_system_prompt(prompt)

    async def whoami(update, context):
        uid = update.effective_user.id
        await update.message.reply_text(t("whoami", lang_store.get(uid), id=uid))

    async def aprende(update, context):
        uid = update.effective_user.id
        lang = lang_store.get(uid)
        if not _is_admin(uid):
            await update.message.reply_text(t("not_admin", lang))
            return
        fact = " ".join(context.args).strip() if context.args else ""
        if not fact:
            await update.message.reply_text(t("aprende_usage", lang))
            return
        append_fact(fact)
        _rebuild()
        await update.message.reply_text(t("learned", lang))

    async def reload_(update, context):
        uid = update.effective_user.id
        lang = lang_store.get(uid)
        if not _is_admin(uid):
            await update.message.reply_text(t("not_admin", lang))
            return
        projects_repo.reload()
        _rebuild()
        await update.message.reply_text(t("reloaded", lang))

    async def claim(update, context):
        uid = update.effective_user.id
        lang = lang_store.get(uid)
        if ADMIN_USER_IDS or not ADMIN_CLAIM_CODE:
            # Bootstrap window already closed (an admin exists) or never configured.
            # Silent -- don't confirm/deny that this command does anything.
            return
        code = " ".join(context.args).strip() if context.args else ""
        if not code or not secrets.compare_digest(code, ADMIN_CLAIM_CODE):
            await update.message.reply_text(t("claim_usage", lang))
            return
        ADMIN_USER_IDS.add(uid)  # mutate the shared set in place -> _is_admin sees it instantly
        _persist_admin_id(uid)
        await update.message.reply_text(t("claim_success", lang, id=uid))

    return {"whoami": whoami, "aprende": aprende, "reload": reload_, "claim": claim}
