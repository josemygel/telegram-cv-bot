"""Owner-only 'training' commands — teach the bot at runtime, no restart needed.

  /whoami           -> your Telegram id (to lock down access via ADMIN_USER_IDS).
  /aprende <texto>  -> append a fact to profile/knowledge.md and hot-reload grounding.
  /reload           -> re-read profile/projects/knowledge from disk (after editing files).

Gated by config.ADMIN_USER_IDS; if it's empty, allowed (convenient while you set it up).
This is grounding-based 'training': accurate, versionable and instant — no fine-tuning.
"""
from __future__ import annotations

from ..config import ADMIN_USER_IDS, ASSISTANT_NAME, PROFILE_PATH
from ..grounding import build_grounded_prompt
from ..knowledge import append_fact


def _is_admin(user_id: int) -> bool:
    return (not ADMIN_USER_IDS) or (user_id in ADMIN_USER_IDS)


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

    return {"whoami": whoami, "aprende": aprende, "reload": reload_}
