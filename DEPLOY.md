# Hosting josembot 24/7 (free)

Because the bot now uses **Groq** (a hosted LLM), the bot process is **lightweight** — just an
async polling loop + HTTP calls. **No GPU needed.** It fits any tiny always-on host.

Two rules that apply to every option:
- **Run in TEXT mode** in the cloud (`BOT_MODE=text`, `LLM_BACKEND=openai` → Groq). Voice
  (faster-whisper) is heavy; keep voice for your local/GPU machine.
- **Only ONE poller may run at a time** (Telegram returns 409 with two). If you move to the
  cloud, **delete the local auto-start** `…\Start Menu\Programs\Startup\josembot.vbs`.

Provide secrets as the host's **env vars / secrets** (never commit `.env`):
`TELEGRAM_TOKEN`, `OPENAI_BASE_URL=https://api.groq.com/openai/v1`, `OPENAI_API_KEY`,
`OPENAI_MODEL=llama-3.3-70b-versatile`, `BOT_MODE=text`, `LLM_BACKEND=openai`.

---

## Option A — Your own VPS  ⭐ (recommended for you)
You already run a high-availability VPS (GDFitness backend, Sugo.es, Tradian). Adding a tiny
Python service there is trivial and free (you already pay for it):

```bash
git clone <repo> /opt/telegram-voice-bot && cd /opt/telegram-voice-bot
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill TELEGRAM_TOKEN + Groq OPENAI_* + BOT_MODE=text
# Run as a service (edit paths/user in the unit first):
sudo cp deploy/josembot.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now josembot
journalctl -u josembot -f
```
(If the unit uses a venv, point `ExecStart` at `/opt/telegram-voice-bot/.venv/bin/python`.)

## Option B — Free container host (no VPS): **Koyeb** ⭐ or Fly.io
- **Koyeb** — free tier with **no sleep mode**, so the polling bot stays up 24/7 (ideal).
  Connect the repo or push the image (a `Dockerfile` is included), set the env secrets, deploy.
- **Fly.io** — free allowance of 3 shared-cpu micro VMs (256 MB each); enough for this bot.
- ❌ **Avoid Render / Railway free tiers**: they **spin down after ~15 min idle**, which kills
  the polling loop. (They only work with a webhook + keep-alive — more hassle.)

## Option C — Oracle Cloud **Always Free** VM (free "real server")
A genuinely free-forever Linux VM (ARM Ampere A1, ~2 OCPU/12 GB as of mid-2026, or an AMD micro).
Create the instance, then follow **Option A** (clone + systemd). Caveats: ARM capacity is often
"out of capacity" in some regions, and idle always-free instances can be reclaimed.

---

### Polling vs webhook
This bot uses **polling** (`run_polling`), which is simplest and works on any always-on host
(VPS, Koyeb, Fly, Oracle). You only need a webhook if you go fully serverless (Cloudflare
Workers / Vercel / Deno Deploy) — that would require restructuring the bot as a webhook handler.
