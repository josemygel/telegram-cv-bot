# Telegram CV Bot (josembot)

<p align="center"><img src="logo.png" alt="josembot logo" width="360"></p>

![CI](https://github.com/josemygel/telegram-cv-bot/actions/workflows/ci.yml/badge.svg)
![License](https://img.shields.io/badge/license-personal--non--commercial-blue)

> **Original project by [Jose Miguel Gómez Lozano](https://github.com/josemygel)** — designed and
> written from scratch, **not a fork or derivative** of any other project. Personal,
> non-commercial license: you may run and modify your own copy, but **not** redistribute or
> republish it (as a fork, a "template" repo, or otherwise) or use it commercially. See
> [Author & License](#author--license), [AUTHORS.md](AUTHORS.md) and [LICENSE](LICENSE).

A **personal-assistant Telegram bot** that answers questions about **you** — your background,
skills and projects — **grounded on a profile you write** (no fine-tuning, no hallucinated
facts). It's aimed at recruiters: they chat with the bot, browse your projects, download your
CV, and get your contact — in **Spanish or English**, by **text or voice**.

```
text  ───────────────────────────────► LLM ─────────────────► text
voice ─► faster-whisper (STT) ────────► LLM ─► edge-tts (TTS) ─► voice note
                                         ▲
              grounded on profile/profile.md + profile/projects.yaml + knowledge.md
```

> The bot reads **only** what you put in your profile files. It answers in the **third person**
> ("She built…", not "I built…"), never invents facts, and cites contact details verbatim.

## Table of contents
- [Features](#features)
- [Requirements](#requirements)
- [1. Create your Telegram bot](#1-create-your-telegram-bot-botfather)
- [2. Install](#2-install)
- [3. Configure (.env)](#3-configure-env)
- [4. Fill in your data](#4-fill-in-your-data-the-part-that-makes-it-yours)
- [5. Generate your CV PDFs](#5-generate-your-cv-pdfs-served-by-cv)
- [6. Run](#6-run)
- [Environment variables reference](#environment-variables-reference)
- [Voice mode](#voice-mode)
- [Hosting 24/7 (free)](#hosting-247-free)
- [MCP servers](#mcp-servers)
- [CV best practices](#cv-best-practices-why-the-generated-cv-looks-the-way-it-does)
- [Architecture](#architecture)
- [Development](#development)
- [Security](#security)
- [Troubleshooting](#troubleshooting)
- [Limitations & roadmap](#limitations--roadmap)
- [Contributing](#contributing)
- [Author & License](#author--license)

## Features
- **Grounded Q&A** in ES/EN about your experience, skills, projects, strengths and limits.
- **Inline buttons**: `/proyectos` (projects → scope / your role / stack), `/cv` (download the
  CV PDF in 🇪🇸/🇬🇧), `/contacto` (email & phone *copy* buttons + WhatsApp/Telegram/LinkedIn/GitHub
  links), `/idioma`, `/voz`.
- **Voice notes**: send a voice message → it transcribes, answers, and replies with a voice note.
- **Owner "training"** from Telegram: `/aprende <fact>` adds knowledge live; `/reload` re-reads
  your data files — no restart.
- **Local or hosted LLM**: LM Studio / Ollama (private, on your GPU) **or** a free hosted API
  (Groq). One line in `.env`.
- **Reusable MCP servers** (`mcps/`) expose your profile/projects to any MCP client (Claude
  Desktop, etc.).
- **Abuse-resistant by default**: per-user rate limiting, input-length caps, a bounded
  in-memory chat-history cache, and prompt-injection guardrails in the grounding prompt (see
  [Security](#security)) — the defaults assume the bot may be reachable by strangers.
- Clean, tested architecture (pytest, CI).

## Requirements
- **Python**: developed and tested on 3.14; CI runs the test suite on **3.11**; the Docker image
  uses **3.12-slim**. Anything **3.11+** should work — the codebase doesn't use version-specific
  syntax beyond that floor.
- **OS**: cross-platform (Windows, Linux, macOS). Text mode has no OS-specific dependencies.
  Voice-mode GPU acceleration (`WHISPER_DEVICE=cuda`) has only been exercised on Windows +
  NVIDIA; CPU inference (the default) works everywhere.
- **Telegram account** to create a bot via [@BotFather](https://t.me/BotFather).
- An LLM you can reach: a local server ([LM Studio](https://lmstudio.ai) or
  [Ollama](https://ollama.com)) or a hosted OpenAI-compatible API key (e.g.
  [Groq](https://console.groq.com), free tier available).

---

## 1. Create your Telegram bot (@BotFather)
1. In Telegram, open **[@BotFather](https://t.me/BotFather)**.
2. Send `/newbot`, choose a **name** (display) and a **username** (must end in `bot`).
3. BotFather replies with an **HTTP API token** like `1234567890:AAH...`. Copy it.
4. (Optional) `/setdescription`, `/setabouttext`, `/setuserpic` to brand your bot.
5. You'll paste that token into `.env` as `TELEGRAM_TOKEN` (next step). Keep it secret — anyone
   with the token can control your bot (see [Security](#security) for what to do if it leaks).

## 2. Install
```bash
git clone https://github.com/josemygel/telegram-cv-bot.git
cd telegram-cv-bot
pip install -r requirements.txt          # core (text mode)
# Optional voice mode (STT/TTS):  pip install -r requirements-voice.txt
```

## 3. Configure (`.env`)
```bash
cp .env.example .env
```
Open `.env` and fill it in. Key fields (the full list, with every variable documented, is in
[Environment variables reference](#environment-variables-reference) and in `.env.example`):
- `TELEGRAM_TOKEN` — from BotFather (step 1).
- `BOT_MODE` — `text` (lightest), `voice`, or `auto`.
- `LLM_BACKEND=openai` + an OpenAI-compatible endpoint:
  - **Local** (private): [LM Studio](https://lmstudio.ai) → `OPENAI_BASE_URL=http://localhost:1234/v1`,
    `OPENAI_MODEL=<the model you loaded>`; or [Ollama](https://ollama.com) (`LLM_BACKEND=ollama`).
  - **Hosted free**: [Groq](https://console.groq.com) → `OPENAI_BASE_URL=https://api.groq.com/openai/v1`,
    `OPENAI_API_KEY=<key>`, `OPENAI_MODEL=llama-3.3-70b-versatile`.
- `ASSISTANT_NAME` — your full name.
- `CONTACT_*` — email, phone, WhatsApp digits, LinkedIn/GitHub URLs, Telegram handle (each blank = button hidden).
- `ADMIN_USER_IDS` — your numeric Telegram id(s) so only you can use `/aprende` and `/reload`
  (send `/whoami` to the bot to get yours). **Leave it empty only while testing** — the bot logs
  a loud warning at startup if it's still empty, because an empty value means *anyone* can use
  those commands.

`.env` is **git-ignored** — your secrets never get committed.

## 4. Fill in your data (the part that makes it *yours*)
Copy the example files and edit them with your information (the real ones are git-ignored, so
your data stays private):
```bash
cp profile/profile.example.md   profile/profile.md
cp profile/projects.example.yaml profile/projects.yaml
cp profile/knowledge.example.md profile/knowledge.md   # optional extra facts
```
- **`profile/profile.md`** — bio, experience, skills, education, languages, honest limitations.
  Write it in **English** (the model answers in the user's language). Keep the section headings.
- **`profile/projects.yaml`** — one entry per project. Each field is documented inline in the
  example; `scope` (envergadura), `participation` (your role) and `summary` are **bilingual**
  (es/en); `details` is optional long-form. This single file feeds the buttons, the MCP servers
  and the grounding — one source of truth.
- **`profile/knowledge.md`** — free-form extra facts / FAQ / how you want to be described. You can
  also add lines live with `/aprende`.

## 5. Generate your CV PDFs (served by `/cv`)
The bot serves `cv/cv_es.pdf` and `cv/cv_en.pdf`. Two ways to provide them:
- **Bring your own**: drop your designed PDFs into `cv/` as `cv_es.pdf` / `cv_en.pdf`.
- **Generate from your data**:
  ```bash
  pip install -r requirements-dev.txt   # reportlab
  python scripts/build_cv.py            # writes cv/cv_es.pdf and cv/cv_en.pdf
  ```
  Re-run it whenever your data changes. (`build_cv.py` skips files that already exist, so delete
  the old PDF first to regenerate.) CVs are git-ignored by default — commit them only if they're
  not confidential.
- **Optional inline preview**: drop a `cv_es_thumb.jpg` / `cv_en_thumb.jpg` (JPEG, <200 kB,
  longest side ≤320px — Telegram's own limits) into `cv/` and `/cv` sends it as the document's
  thumbnail, so recruiters see a preview next to the PDF in the **same message** instead of a
  bare file icon. Fully optional — if the file isn't there, `/cv` behaves exactly as before.
  Rendering is best-effort on Telegram's side (reliable on mobile/web; occasionally falls back
  to the generic icon on Desktop for some file types — a known, unresolved Telegram Desktop
  quirk, not a bug in this bot). A manually designed cover image is recommended over trying to
  auto-render page 1 of the PDF: at 320px a text-heavy CV page is illegible anyway, and it would
  add a heavy dependency (`pdf2image`/`poppler` or `pymupdf`) for little real benefit.

## 6. Run
```bash
python -m src.bot          # starts the bot (text + voice)
python chat_cli.py         # quick test in the terminal, no Telegram
```
Talk to your bot in Telegram. Commands: `/start`, `/menu`, `/proyectos`, `/cv`, `/contacto`,
`/idioma`, `/voz`, `/help` — plus owner-only `/aprende`, `/reload`, `/whoami`.

---

## Environment variables reference
All variables live in `.env` (copied from `.env.example`, git-ignored). "Default" is the value
`.env.example` ships with; `src/config.py` falls back to a slightly different value for a few
vars if a variable is missing entirely (noted below) — that only matters if you delete a line
instead of leaving it blank.

| Variable | Required | Default (`.env.example`) | Description |
|---|---|---|---|
| `TELEGRAM_TOKEN` | **Yes** | *(empty)* | Bot token from BotFather. |
| `BOT_MODE` | No | `text` | `text` \| `voice` \| `auto` (voice if an NVIDIA GPU is detected, else text). |
| `LLM_BACKEND` | No | `openai` | `openai` (any OpenAI-compatible API) \| `ollama`. |
| `OPENAI_BASE_URL` | If `LLM_BACKEND=openai` | `http://localhost:1234/v1` | LM Studio local server, or a hosted endpoint (Groq: `https://api.groq.com/openai/v1`). |
| `OPENAI_API_KEY` | If using a hosted API | `lm-studio` | LM Studio ignores the value; hosted APIs need a real key. |
| `OPENAI_MODEL` | If `LLM_BACKEND=openai` | `qwen/qwen3-vl-4b` | Model id/name as your endpoint expects it. |
| `LLM_MAX_TOKENS` | No | `1024` | Generous on purpose — reasoning models can burn the budget on hidden "thinking" before the visible answer. |
| `LLM_TEMPERATURE` | No | `0.3` | Kept low for grounded-QA fidelity (higher invites drifting from the profile). |
| `OLLAMA_URL` | If `LLM_BACKEND=ollama` | `http://localhost:11434` | Local Ollama daemon URL. |
| `LLM_MODEL` | If `LLM_BACKEND=ollama` | `llama3.2` | Ollama model tag. |
| `WHISPER_MODEL` | Voice mode only | `small` | faster-whisper model size (`tiny`…`large-v3`). |
| `WHISPER_DEVICE` | Voice mode only | `cpu` | `cpu` \| `cuda` (needs CUDA cuBLAS/cuDNN DLLs). |
| `WHISPER_COMPUTE` | Voice mode only | `int8` | Compute type; **use `float16` on Blackwell/RTX 50-series GPUs** (`int8` isn't supported there). |
| `TTS_BACKEND` | Voice mode only | `edge` | `edge` (edge-tts, online, neural) \| `piper` (offline). |
| `TTS_VOICE_ES` / `TTS_VOICE_EN` | Voice mode only | `es-ES-ElviraNeural` / `en-US-AriaNeural` | edge-tts voice names. |
| `PIPER_BIN` / `PIPER_VOICE` | Only if `TTS_BACKEND=piper` | `piper` / `voices/en_US-amy-medium.onnx` | Local Piper binary + voice model path. |
| `ASSISTANT_NAME` | Recommended | `Your Name` | Used throughout replies, the CV, and `/contacto`. |
| `PROFILE_PATH` | No | `profile/profile.md` | Grounding profile file. |
| `PROJECTS_PATH` | No | `profile/projects.yaml` | Structured project data. |
| `KNOWLEDGE_PATH` | No | `profile/knowledge.md` | Free-form extra facts, editable live via `/aprende`. |
| `CV_DIR` | No | `cv` | Where `/cv` looks for `cv_es.pdf` / `cv_en.pdf`. |
| `I18N_DIR` | No | `content/i18n` | Bot UI strings (`es.yaml` / `en.yaml`). |
| `BOT_LANG` | No | `en` | Fallback UI language if a user's Telegram client language can't be resolved. |
| `ADMIN_USER_IDS` | **Recommended** | *(empty)* | Comma-separated numeric Telegram ids allowed to use `/aprende` and `/reload`. **Empty = open to everyone** — the bot warns loudly at startup if so; get your id via `/whoami`. |
| `CONTACT_EMAIL` | No | `you@example.com` | Shown as a copy button; blank hides it. |
| `CONTACT_PHONE` | No | `+00 000 000 000` | Copy button (Telegram buttons can't be `tel:`). |
| `CONTACT_WHATSAPP` | No | *(digits only)* | Builds a `wa.me/<digits>` link. |
| `CONTACT_LINKEDIN` | No | *(empty)* | Full profile URL. |
| `CONTACT_GITHUB` | No | *(empty)* | Full profile URL. |
| `CONTACT_TELEGRAM` | No | *(empty)* | Handle only (no `@`), builds a `t.me/<handle>` link. |

## Voice mode
`pip install -r requirements-voice.txt`, set `BOT_MODE=voice`. STT is **faster-whisper**
(CPU by default; `WHISPER_DEVICE=cuda` + CUDA cuBLAS/cuDNN DLLs to use an NVIDIA GPU). TTS is
**edge-tts** (neural ES/EN voices). A bundled `ffmpeg` (imageio-ffmpeg) converts to the OGG/Opus
voice-note format. **Live voice calls are not possible via the Telegram Bot API** — voice *notes*
cover the use case. Voice messages longer than 120s and rapid-fire voice notes are rejected (see
[Security](#security)).

## Hosting 24/7 (free)
On Groq the bot is lightweight (no GPU). Run it on your own VPS / an Oracle Cloud Always-Free VM
(systemd unit in `deploy/`) or a no-sleep container host (Koyeb, Fly.io). Full guide: **[DEPLOY.md](DEPLOY.md)**.
For a local always-on launch, `run_bot.ps1` (Windows) starts everything.

## MCP servers
`mcps/projects_mcp` and `mcps/cv_mcp` expose your projects/profile over the Model Context
Protocol for any MCP client. Each has its own README with a Claude Desktop config snippet and a
note on running them safely if you ever expose them over a network transport instead of stdio.

---

## CV best practices (why the generated CV looks the way it does)
The CV layout follows what works for recruiters / ATS:
- **Lead with a tight summary** (2–4 lines): role + focus + what you build.
- **Reverse-chronological experience**, each bullet an **achievement** (action + result), with
  numbers and named technologies.
- **One page if you can.** Compact it (margins, concise bullets) before spilling to a second.
  Go to **2+ pages only if the content genuinely needs it** — never pad. The generator targets
  one page and auto-extends if the content overflows.
- **Honesty**: state real strengths and acknowledge gaps — it builds trust.
- **Avoid**: photos in regions where they bias ATS, dense walls of text, vague buzzwords without
  evidence, inconsistent formatting, and **typos in contact details** (double-check email/phone).
- **Match the role**: keep the profile broad, and tailor wording to each application.

## Architecture
| Area | Files |
|---|---|
| Config | `src/config.py` (env) |
| LLM | `src/llm.py` (Ollama / OpenAI-compatible, defensive extraction, `BackendError`) |
| Grounding | `src/profile.py`, `src/grounding.py`, `src/knowledge.py` |
| Data | `src/models.py`, `src/projects.py` (`profile/projects.yaml`), `src/cv_service.py` |
| UX | `src/keyboards.py`, `src/formatting.py`, `src/i18n.py`, `src/lang_store.py` |
| Voice | `src/stt.py`, `src/tts.py`, `src/audio.py` |
| Orchestration | `src/pipeline.py` |
| Handlers | `src/handlers/` (commands, callbacks, text, voice, training, errors) |
| Wiring | `src/bot.py` |
| MCP | `mcps/cv_mcp`, `mcps/projects_mcp` |

## Development
```bash
pip install -r requirements-dev.txt
pytest -q          # CI runs this on every push
```

## Security
This template assumes a public bot can be reached by anyone, including people who aren't
recruiters. Defaults are chosen accordingly:
- **Secrets** live in `.env` (git-ignored). `.env.example` ships placeholders only. The bot
  never logs the token, and `httpx`'s own logger is quieted (Telegram request URLs embed it).
- **Personal data** (`profile/profile.md`, `profile/projects.yaml`, `profile/knowledge.md`,
  `cv/*.pdf`) is excluded from **both** git (`.gitignore`) **and** Docker builds
  (`.dockerignore`) — the repo ships `*.example.*` templates instead. Docker's `COPY` ignores
  `.gitignore`, so both files matter if you build the image locally.
- **Owner-only commands** (`/aprende`, `/reload`) are gated by `ADMIN_USER_IDS`. If it's left
  empty, the bot logs a startup warning because that means anyone can use them — set it before
  exposing the bot publicly.
- **Rate limiting & input caps**: text messages are limited to one per 3s per user and capped at
  1500 characters; voice notes are limited to one per 5s per user and capped at 120s — this
  protects you from both cost abuse (hosted LLM APIs bill per token) and local resource abuse
  (STT/TTS/LLM inference).
- **Bounded memory**: in-memory chat histories are capped (`Pipeline.max_chats`, default 500)
  with LRU-style eviction, so a flood of distinct `chat_id`s can't grow memory unboundedly.
- **Prompt-injection guardrails**: the grounding system prompt instructs the model to never
  reveal or discuss its own instructions and to ignore attempts to change its role — mitigation,
  not a guarantee; don't put anything in `knowledge.md` you wouldn't want extracted with enough
  effort.
- **If a secret leaks** (token committed, `.env` shared, etc.), rotate it immediately:
  - Telegram: message [@BotFather](https://t.me/BotFather) → `/revoke` on your bot → get a new
    token → update `.env` / your host's secrets.
  - Groq (or any hosted LLM key): regenerate the key in the provider's console and update `.env`.

## Troubleshooting
- **`Unauthorized` / 401 from Telegram** — the token is wrong or was revoked. Recheck
  `TELEGRAM_TOKEN`, or get a fresh one from BotFather.
- **`Conflict: terminated by other getUpdates request` / 409** — two processes are polling the
  same bot at once (e.g. a local run *and* a cloud deployment). Stop one; only one poller may run
  at a time (see [DEPLOY.md](DEPLOY.md)).
- **`Connection refused` to `localhost:1234` / `localhost:11434`** — LM Studio or Ollama isn't
  running, or `OPENAI_BASE_URL` / `OLLAMA_URL` points at the wrong port. Start the local server
  and load a model first.
- **Empty or truncated replies from a reasoning model** — some models split output into a hidden
  "thinking" channel and a final answer; if `LLM_MAX_TOKENS` is too low, the budget can be
  consumed entirely by the hidden part. Raise `LLM_MAX_TOKENS`.
- **Voice mode won't start / falls back to text** — a missing voice dependency degrades the bot
  to text-only by design (see `src/bot.py`); check the startup log for which import failed and
  confirm `pip install -r requirements-voice.txt` succeeded.
- **`int8` unsupported on an NVIDIA RTX 50-series (Blackwell) GPU** — set
  `WHISPER_COMPUTE=float16` instead.
- **"anyone can use `/aprende` or `/reload`"** — `ADMIN_USER_IDS` is empty. Send `/whoami` to the
  bot to get your numeric id and set it in `.env`.
- **`/cv` thumbnail doesn't show (falls back to a plain PDF icon)** — this is best-effort on
  Telegram's side, not a bug here: it's reliable on mobile/web but Telegram Desktop has a known,
  unresolved bug where document thumbnails intermittently don't render for some file types.
  Double-check the file is a real JPEG under 200 kB with its longest side ≤320px if it never
  shows on any client.

## Limitations & roadmap
- **No persistent storage**: chat history and per-user language preference live in memory and
  reset on restart. Fine for a single always-on process; would need a real store (SQLite/Redis)
  for multi-instance or crash-resilient deployments.
- **Single-process polling only** — no horizontal scaling; `run_polling()` assumes exactly one
  instance talks to Telegram at a time.
- **No live voice calls** — Telegram's Bot API only supports voice *notes*, not real-time calls.
- **No automated credential rotation** — see [Security](#security) for the manual steps.
- Ideas for later: optional persistent storage, a webhook-based deployment path for serverless
  hosts, more UI languages.

## Contributing
This is a personal template shared under a **non-commercial, no-redistribution** license (see
below) — it isn't set up to accept pull requests or forks-for-republishing, since the license
doesn't permit redistributing modified copies. If you find a bug or have a suggestion, open an
issue or reach out to the author directly (see below); if you build your own copy for personal,
non-commercial use, that's exactly what the license is for.

## Author & License
Created by **Jose Miguel Gómez Lozano** ([github.com/josemygel](https://github.com/josemygel)) —
an **original work**, not a fork or derivative of any other project. See [AUTHORS.md](AUTHORS.md)
for the authorship statement.

**Personal, non-commercial license** (source-available — intentionally *not* an OSI "open-source"
license): you may **view, download and modify** it for your **own personal, non-commercial** use.
**Redistribution and commercial use are NOT allowed** without the author's written permission.
See [LICENSE](LICENSE). Third-party dependencies keep their own licenses.
