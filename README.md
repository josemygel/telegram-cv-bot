# Telegram CV Bot

![CI](https://github.com/yourhandle/telegram-cv-bot/actions/workflows/ci.yml/badge.svg)

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
- Clean, tested architecture (pytest, CI).

---

## 1. Create your Telegram bot (@BotFather)
1. In Telegram, open **[@BotFather](https://t.me/BotFather)**.
2. Send `/newbot`, choose a **name** (display) and a **username** (must end in `bot`).
3. BotFather replies with an **HTTP API token** like `1234567890:AAH...`. Copy it.
4. (Optional) `/setdescription`, `/setabouttext`, `/setuserpic` to brand your bot.
5. You'll paste that token into `.env` as `TELEGRAM_TOKEN` (next step). Keep it secret.

## 2. Install
```bash
git clone https://github.com/yourhandle/telegram-cv-bot.git
cd telegram-cv-bot
pip install -r requirements.txt          # core (text mode)
# Optional voice mode (STT/TTS):  pip install -r requirements-voice.txt
```

## 3. Configure (`.env`)
```bash
cp .env.example .env
```
Open `.env` and fill it in. Key fields (full list with comments in `.env.example`):
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
  (send `/whoami` to the bot to get yours). Leave blank while testing.

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

## 6. Run
```bash
python -m src.bot          # starts the bot (text + voice)
python chat_cli.py         # quick test in the terminal, no Telegram
```
Talk to your bot in Telegram. Commands: `/start`, `/menu`, `/proyectos`, `/cv`, `/contacto`,
`/idioma`, `/voz`, `/help` — plus owner-only `/aprende`, `/reload`, `/whoami`.

---

## Voice mode
`pip install -r requirements-voice.txt`, set `BOT_MODE=voice`. STT is **faster-whisper**
(CPU by default; `WHISPER_DEVICE=cuda` + CUDA cuBLAS/cuDNN DLLs to use an NVIDIA GPU). TTS is
**edge-tts** (neural ES/EN voices). A bundled `ffmpeg` (imageio-ffmpeg) converts to the OGG/Opus
voice-note format. **Live voice calls are not possible via the Telegram Bot API** — voice *notes*
cover the use case.

## Hosting 24/7 (free)
On Groq the bot is lightweight (no GPU). Run it on your own VPS / an Oracle Cloud Always-Free VM
(systemd unit in `deploy/`) or a no-sleep container host (Koyeb, Fly.io). Full guide: **[DEPLOY.md](DEPLOY.md)**.
For a local always-on launch, `run_bot.ps1` (Windows) starts everything.

## MCP servers
`mcps/projects_mcp` and `mcps/cv_mcp` expose your projects/profile over the Model Context
Protocol for any MCP client. Each has its own README with a Claude Desktop config snippet.

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
- Secrets live in `.env` (git-ignored). `.env.example` ships placeholders only.
- Your personal data (`profile/profile.md`, `profile/projects.yaml`, `profile/knowledge.md`,
  `cv/*.pdf`) is git-ignored; the repo ships `*.example.*` templates.
- The bot never logs the token; avoid verbose HTTP logging (Telegram URLs embed the token).

## License
MIT — see [LICENSE](LICENSE).
