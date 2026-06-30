"""Telegram bot: a personal assistant grounded on a profile + structured projects.

This module is thin WIRING only: build dependencies, build the Application and
register handlers (which live in src/handlers/). Modes (set BOT_MODE):
- voice: voice in -> voice out (faster-whisper -> LLM -> Piper)
- text:  text chat only (LLM)              [no GPU / voice runtime needed]
- auto:  voice if a GPU is detected, else text

Run:  python -m src.bot
"""
from __future__ import annotations

import logging

from telegram import BotCommand
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from .config import (
    ASSISTANT_NAME, BOT_MODE, LLM_BACKEND, PROFILE_PATH, TELEGRAM_TOKEN, TTS_BACKEND,
    CONTACT_EMAIL, CONTACT_GITHUB, CONTACT_LINKEDIN, CONTACT_PHONE, CONTACT_TELEGRAM, CONTACT_WHATSAPP,
)
from .cv_service import CvService
from .grounding import build_grounded_prompt
from .handlers.callbacks import make_callback_handlers
from .handlers.commands import make_command_handlers
from .handlers.errors import make_error_handler
from .handlers.text import make_text_handler
from .handlers.training import make_training_handlers
from .handlers.voice import make_voice_handler
from .i18n import I18n
from .lang_store import InMemoryLangStore
from .pipeline import Pipeline
from .projects import ProjectsRepository
from .runtime import get_llm, gpu_available, resolve_mode

log = logging.getLogger("josembot")

MODE = resolve_mode(BOT_MODE, gpu_available())

# (telegram command, i18n key suffix) — both /proyectos and /projects map here.
_COMMANDS = [
    ("start", "start"), ("menu", "menu"), ("proyectos", "projects"), ("cv", "cv"),
    ("contacto", "contact"), ("idioma", "language"), ("voz", "voice"), ("help", "help"),
]


def build_dependencies() -> dict:
    """Instantiate repositories, services and the pipeline once, for injection."""
    projects = ProjectsRepository()
    i18n = I18n()
    cv = CvService()
    lang_store = InMemoryLangStore()
    llm = get_llm(LLM_BACKEND)
    system_prompt = build_grounded_prompt(ASSISTANT_NAME, PROFILE_PATH, projects.list_projects())
    pipeline = Pipeline(llm=llm, system_prompt=system_prompt)

    # Voice (STT/TTS) is enabled unless BOT_MODE=text. Built lazily and guarded so a
    # missing dependency degrades to text-only instead of crashing the bot.
    stt = tts = None
    voice_enabled = MODE == "voice"
    if voice_enabled:
        try:
            from .stt import WhisperSTT
            from .tts import get_tts

            stt, tts = WhisperSTT(), get_tts(TTS_BACKEND)
        except Exception as exc:  # noqa: BLE001
            log.warning("Voice disabled (deps unavailable): %s", exc)
            voice_enabled = False

    contact = {
        "email": CONTACT_EMAIL, "phone": CONTACT_PHONE, "whatsapp": CONTACT_WHATSAPP,
        "linkedin": CONTACT_LINKEDIN, "github": CONTACT_GITHUB, "telegram": CONTACT_TELEGRAM,
    }
    return {
        "i18n": i18n, "projects": projects, "cv": cv, "lang_store": lang_store,
        "name": ASSISTANT_NAME, "pipeline": pipeline, "contact": contact,
        "stt": stt, "tts": tts, "voice_enabled": voice_enabled, "voice_pref": set(),
    }


def _register_handlers(app: Application, deps: dict) -> None:
    cmd = make_command_handlers(deps)
    cb = make_callback_handlers(deps)
    app.add_handler(CommandHandler("start", cmd["start"]))
    app.add_handler(CommandHandler("menu", cmd["menu"]))
    app.add_handler(CommandHandler(["proyectos", "projects"], cmd["projects"]))
    app.add_handler(CommandHandler(["cv", "resume"], cmd["cv"]))
    app.add_handler(CommandHandler(["contacto", "contact"], cmd["contact"]))
    app.add_handler(CommandHandler(["idioma", "language"], cmd["language"]))
    app.add_handler(CommandHandler("help", cmd["help"]))
    app.add_handler(CommandHandler(["voz", "voice"], cmd["voice"]))
    # Owner 'training' commands (not in the public menu).
    tr = make_training_handlers(deps)
    app.add_handler(CommandHandler("whoami", tr["whoami"]))
    app.add_handler(CommandHandler(["aprende", "learn"], tr["aprende"]))
    app.add_handler(CommandHandler(["reload", "recargar"], tr["reload"]))
    app.add_handler(CallbackQueryHandler(cb["cv"], pattern=r"^cv:"))
    app.add_handler(CallbackQueryHandler(cb["contact"], pattern=r"^contact:"))
    app.add_handler(CallbackQueryHandler(cb["projects"], pattern=r"^proj:"))
    app.add_handler(CallbackQueryHandler(cb["lang"], pattern=r"^lang:"))
    app.add_handler(CallbackQueryHandler(cb["nav"], pattern=r"^nav:"))
    app.add_handler(CallbackQueryHandler(cb["noop"], pattern=r"^noop$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, make_text_handler(deps)))
    app.add_handler(MessageHandler(filters.VOICE, make_voice_handler(deps)))
    app.add_error_handler(make_error_handler(deps))


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    # Don't log Telegram request URLs (they embed the bot token) — keep httpx quiet.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    if not TELEGRAM_TOKEN:
        raise SystemExit("Set TELEGRAM_TOKEN (see .env.example).")
    deps = build_dependencies()
    t = deps["i18n"].t

    async def post_init(app: Application) -> None:
        # Localized persistent command menus (run once at startup, no per-message cost).
        for lang in ("es", "en"):
            await app.bot.set_my_commands(
                [BotCommand(c, t(f"cmd_{key}", lang)) for c, key in _COMMANDS], language_code=lang
            )
        await app.bot.set_my_commands([BotCommand(c, t(f"cmd_{key}", "es")) for c, key in _COMMANDS])

    app = Application.builder().token(TELEGRAM_TOKEN).post_init(post_init).build()
    _register_handlers(app, deps)
    print(f"Bot running in {MODE.upper()} mode. Press Ctrl+C to stop.")
    app.run_polling()


if __name__ == "__main__":
    main()
