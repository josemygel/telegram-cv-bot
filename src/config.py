"""Configuration via environment variables (see .env.example).

Part of the josembot project, original work by Jose Miguel Gómez Lozano
(github.com/josemygel/telegram-cv-bot) — see AUTHORS.md and LICENSE.
"""
from __future__ import annotations

import os

# Load a local .env if python-dotenv is installed (optional convenience).
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

# Telegram
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")

# Mode: voice (STT+LLM+TTS) | text (LLM only) | auto (voice if a GPU is detected)
BOT_MODE = os.environ.get("BOT_MODE", "auto")

# LLM backend: ollama (local) | openai (any OpenAI-compatible API, e.g. LM Studio / Groq) | anthropic (Claude)
LLM_BACKEND = os.environ.get("LLM_BACKEND", "ollama")

# Ollama (local LLM)
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
LLM_MODEL = os.environ.get("LLM_MODEL", "llama3.2")

# OpenAI-compatible API (LM Studio, Groq, OpenRouter, vLLM...) — for local or hosted use
OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL", "http://localhost:1234/v1")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "qwen/qwen3-vl-4b")

# Vision: send photos to the LLM as image content parts (OpenAI-compatible vision
# format only -- LM Studio/vLLM/OpenRouter with a vision model, e.g. qwen3-vl-4b, or
# Groq's vision-capable models). Off by default: most configured models (e.g. Groq's
# llama-3.3-70b-versatile) are text-only and would just ignore or error on an image.
# Only takes effect when LLM_BACKEND=openai -- Ollama's image format isn't implemented.
LLM_VISION = os.environ.get("LLM_VISION", "false").strip().lower() == "true"

# Anthropic (Claude) nativo. Haiku 5.5 da 400 con `temperature` y `budget_tokens`, asi que
# el backend NO los envia (ver src/llm_anthropic.py). `effort` low basta para QA sobre
# un CV y evita facturar razonamiento largo como salida.
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-5-5")
ANTHROPIC_EFFORT = os.environ.get("ANTHROPIC_EFFORT", "low")
# Tope de salida por respuesta: que una respuesta no pueda ser "eterna" (coste).
ANTHROPIC_MAX_TOKENS = int(os.environ.get("ANTHROPIC_MAX_TOKENS", "800"))

# Generation controls (shared by both backends).
# max_tokens GENEROSO: con modelos de razonamiento, un presupuesto pequeño hace que
# el "pensamiento" agote el cupo y la respuesta (content) llegue vacía.
# temperature BAJA para QA grounded: 0.7 invita a desviarse del perfil; 0.2-0.3 da fidelidad.
LLM_MAX_TOKENS = int(os.environ.get("LLM_MAX_TOKENS", "1024"))
LLM_TEMPERATURE = float(os.environ.get("LLM_TEMPERATURE", "0.3"))

# Speech-to-text (faster-whisper) — only used in voice mode
WHISPER_MODEL = os.environ.get("WHISPER_MODEL", "base")
WHISPER_DEVICE = os.environ.get("WHISPER_DEVICE", "auto")
WHISPER_COMPUTE = os.environ.get("WHISPER_COMPUTE", "int8")

# Text-to-speech — used in voice mode / for audio replies
TTS_BACKEND = os.environ.get("TTS_BACKEND", "edge")  # edge (online, ES/EN neural) | piper (local)
TTS_VOICE_ES = os.environ.get("TTS_VOICE_ES", "es-ES-ElviraNeural")
TTS_VOICE_EN = os.environ.get("TTS_VOICE_EN", "en-US-AriaNeural")
PIPER_BIN = os.environ.get("PIPER_BIN", "piper")
PIPER_VOICE = os.environ.get("PIPER_VOICE", "voices/en_US-amy-medium.onnx")

# Profile grounding
ASSISTANT_NAME = os.environ.get("ASSISTANT_NAME", "Your Name")
PROFILE_PATH = os.environ.get("PROFILE_PATH", "profile/profile.md")

# Structured data + UI
PROJECTS_PATH = os.environ.get("PROJECTS_PATH", "profile/projects.yaml")
CV_DIR = os.environ.get("CV_DIR", "cv")
I18N_DIR = os.environ.get("I18N_DIR", "content/i18n")
BOT_LANG = os.environ.get("BOT_LANG", "es")

# Owner "training": a free-form knowledge file injected into grounding, plus the
# Telegram user ids allowed to use /aprende and /reload (empty = allowed for setup).
KNOWLEDGE_PATH = os.environ.get("KNOWLEDGE_PATH", "profile/knowledge.md")
_ADMIN_LIST = [int(x) for x in os.environ.get("ADMIN_USER_IDS", "").replace(" ", "").split(",") if x.isdigit()]
ADMIN_USER_IDS = set(_ADMIN_LIST)

# Dueno del bot: unico exento del bloqueo por consumo, y quien puede anadirlo a grupos
# y usar /coste y /desbloquear. Si no se define, el primer id de ADMIN_USER_IDS.
OWNER_USER_ID = int(os.environ.get("OWNER_USER_ID") or (_ADMIN_LIST[0] if _ADMIN_LIST else 0))

# Topes anti-abuso (backend de pago). Se comprueban ANTES de llamar al LLM o descargar nada.
MAX_INPUT_CHARS = int(os.environ.get("MAX_INPUT_CHARS", "2000"))
MAX_PHOTO_BYTES = int(os.environ.get("MAX_PHOTO_BYTES", str(5 * 1024 * 1024)))
TOKEN_LIMIT_HOUR = int(os.environ.get("TOKEN_LIMIT_HOUR", "200000"))
TOKEN_LIMIT_DAY = int(os.environ.get("TOKEN_LIMIT_DAY", "1000000"))
# SQLite de consumo por usuario (solo se usa con LLM_BACKEND=anthropic).
USAGE_DB_PATH = os.environ.get("USAGE_DB_PATH", "data/usage.db")

# One-time bootstrap: while ADMIN_USER_IDS is empty, whoever sends "/claim <this code>"
# to the bot becomes the first admin (see handlers/training.py). Ignored once any admin
# exists -- there is no way to use it again after that, by design.
ADMIN_CLAIM_CODE = os.environ.get("ADMIN_CLAIM_CODE", "")

# Owner-only conversation log for /history (who talked to the bot, and what was said).
# Off by default (empty) -- a public template shouldn't silently log conversations
# unless the owner opts in. Only ADMIN_USER_IDS can read it back via /history.
HISTORY_DB_PATH = os.environ.get("HISTORY_DB_PATH", "")

# Contact (the /contacto buttons). Email/phone are copy-to-clipboard (Telegram url
# buttons can't be mailto:/tel:); the rest are link buttons. Override via env.
CONTACT_EMAIL = os.environ.get("CONTACT_EMAIL", "")
CONTACT_PHONE = os.environ.get("CONTACT_PHONE", "")
CONTACT_WHATSAPP = os.environ.get("CONTACT_WHATSAPP", "")  # digits only -> wa.me/<digits>
CONTACT_LINKEDIN = os.environ.get("CONTACT_LINKEDIN", "")
CONTACT_GITHUB = os.environ.get("CONTACT_GITHUB", "")
CONTACT_TELEGRAM = os.environ.get("CONTACT_TELEGRAM", "")  # t.me/<handle>; empty to hide
