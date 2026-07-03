"""Telegram bot: a personal assistant grounded on a profile + structured projects.

Original project by Jose Miguel Gómez Lozano (github.com/josemygel/telegram-cv-bot).
Not a fork or derivative of any other project — see AUTHORS.md and LICENSE.

This module is thin WIRING only: build dependencies, build the Application and
register handlers (which live in src/handlers/). Modes (set BOT_MODE):
- voice: voice in -> voice out (faster-whisper -> LLM -> Piper)
- text:  text chat only (LLM)              [no GPU / voice runtime needed]
- auto:  voice if a GPU is detected, else text

Run:  python -m src.bot
"""
from __future__ import annotations

import logging
import socket
from datetime import datetime, timezone

from telegram import BotCommand, BotCommandScopeChat
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from .config import (
    ADMIN_USER_IDS, ASSISTANT_NAME, BOT_MODE, HISTORY_DB_PATH, LLM_BACKEND, LLM_MODEL, LLM_VISION,
    OPENAI_MODEL, PROFILE_PATH, TELEGRAM_TOKEN, TTS_BACKEND, CONTACT_EMAIL, CONTACT_GITHUB,
    CONTACT_LINKEDIN, CONTACT_PHONE, CONTACT_TELEGRAM, CONTACT_WHATSAPP,
)
from .cv_service import CvService
from .grounding import build_grounded_prompt
from .handlers.callbacks import make_callback_handlers
from .handlers.commands import make_command_handlers
from .handlers.errors import make_error_handler
from .handlers.history import make_history_handlers
from .handlers.info import make_info_handler
from .handlers.photo import make_photo_handler
from .handlers.sticker import make_sticker_handler
from .handlers.text import make_text_handler
from .handlers.training import make_training_handlers
from .handlers.voice import make_voice_handler
from .history_store import HistoryStore
from .i18n import I18n
from .lang_store import InMemoryLangStore
from .pipeline import Pipeline
from .projects import ProjectsRepository
from .runtime import get_llm, gpu_available, resolve_mode
from .version import __version__

log = logging.getLogger("josembot")

MODE = resolve_mode(BOT_MODE, gpu_available())

# (telegram command, i18n key suffix) — both /proyectos and /projects map here.
_COMMANDS = [
    ("start", "start"), ("menu", "menu"), ("proyectos", "projects"), ("cv", "cv"),
    ("contacto", "contact"), ("idioma", "language"), ("voz", "voice"), ("help", "help"),
]
# Extra commands appended ONLY to the admin's own chat menu (cosmetic UX scoping via
# BotCommandScopeChat -- NOT a security boundary; see handlers/history.py docstring).
_ADMIN_COMMANDS = [("history", "history"), ("info", "info")]


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
    history_store = HistoryStore(HISTORY_DB_PATH) if HISTORY_DB_PATH else None
    # Vision only implemented for the OpenAI-compatible transport (image_url content
    # parts); Ollama's image format differs and isn't implemented -- fall back to the
    # graceful decline in handlers/photo.py rather than sending a request it can't use.
    vision_enabled = LLM_VISION and LLM_BACKEND.lower() == "openai"
    # Surfaced by the owner-only /info command to verify WHICH build is answering.
    runtime_info = {
        "version": __version__,
        "mode": MODE,
        "llm_backend": LLM_BACKEND,
        "llm_model": OPENAI_MODEL if LLM_BACKEND.lower() == "openai" else LLM_MODEL,
        "started_at": datetime.now(timezone.utc),
    }
    return {
        "i18n": i18n, "projects": projects, "cv": cv, "lang_store": lang_store,
        "name": ASSISTANT_NAME, "pipeline": pipeline, "contact": contact,
        "stt": stt, "tts": tts, "voice_enabled": voice_enabled, "voice_pref": set(),
        "history_store": history_store, "vision_enabled": vision_enabled,
        "runtime_info": runtime_info,
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
    # /claim: one-time admin bootstrap. Deliberately never added to ANY command menu
    # (public or admin-scoped) -- see handlers/training.py.
    app.add_handler(CommandHandler("claim", tr["claim"]))
    # Owner-only conversation history (not in the public menu; see handlers/history.py).
    hist = make_history_handlers(deps)
    app.add_handler(CommandHandler("history", hist["history"]))
    app.add_handler(CallbackQueryHandler(hist["history_callback"], pattern=r"^hist:"))
    # Owner-only build/instance info (version, host, uptime; see handlers/info.py).
    app.add_handler(CommandHandler("info", make_info_handler(deps)))
    app.add_handler(CallbackQueryHandler(cb["cv"], pattern=r"^cv:"))
    app.add_handler(CallbackQueryHandler(cb["contact"], pattern=r"^contact:"))
    app.add_handler(CallbackQueryHandler(cb["projects"], pattern=r"^proj:"))
    app.add_handler(CallbackQueryHandler(cb["lang"], pattern=r"^lang:"))
    app.add_handler(CallbackQueryHandler(cb["nav"], pattern=r"^nav:"))
    app.add_handler(CallbackQueryHandler(cb["noop"], pattern=r"^noop$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, make_text_handler(deps)))
    app.add_handler(MessageHandler(filters.VOICE, make_voice_handler(deps)))
    app.add_handler(MessageHandler(filters.PHOTO, make_photo_handler(deps)))
    app.add_handler(MessageHandler(filters.Sticker.ALL, make_sticker_handler(deps)))
    app.add_error_handler(make_error_handler(deps))


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    # Don't log Telegram request URLs (they embed the bot token) — keep httpx quiet.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    if not TELEGRAM_TOKEN:
        raise SystemExit("Set TELEGRAM_TOKEN (see .env.example).")
    if not ADMIN_USER_IDS:
        # /aprende, /reload and /history let a caller inject grounding text or read back
        # everyone's conversations. Empty ADMIN_USER_IDS means ANYONE can use them — fine
        # while testing, dangerous once the bot is reachable by strangers. Loud by design;
        # see README -> Security.
        log.warning(
            "ADMIN_USER_IDS is empty: /aprende, /reload and /history are open to ANY Telegram "
            "user (including reading back OTHER people's conversations via /history). "
            "Send /whoami to the bot and set ADMIN_USER_IDS in .env before going public."
        )
    deps = build_dependencies()
    t = deps["i18n"].t

    async def post_init(app: Application) -> None:
        # Localized persistent command menus (run once at startup, no per-message cost).
        for lang in ("es", "en"):
            await app.bot.set_my_commands(
                [BotCommand(c, t(f"cmd_{key}", lang)) for c, key in _COMMANDS], language_code=lang
            )
        await app.bot.set_my_commands([BotCommand(c, t(f"cmd_{key}", "es")) for c, key in _COMMANDS])
        # Admin-only extras (e.g. /history), visible ONLY in that admin's own chat menu.
        # Cosmetic scoping only -- see handlers/history.py for why this is not the real gate.
        for admin_id in ADMIN_USER_IDS:
            await app.bot.set_my_commands(
                [BotCommand(c, t(f"cmd_{key}", "es")) for c, key in _COMMANDS + _ADMIN_COMMANDS],
                scope=BotCommandScopeChat(chat_id=admin_id),
            )

    app = Application.builder().token(TELEGRAM_TOKEN).post_init(post_init).build()
    _register_handlers(app, deps)
    # Version + host in the startup log so `docker logs` (or the Plesk console) shows
    # at a glance WHICH build came up and where — pairs with the owner's /info command.
    log.info("josembot v%s starting (mode=%s, host=%s, llm=%s)",
             __version__, MODE, socket.gethostname(), LLM_BACKEND)
    print(f"josembot v{__version__} running in {MODE.upper()} mode. Press Ctrl+C to stop.")
    app.run_polling()


if __name__ == "__main__":
    main()
