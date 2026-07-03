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

**No DNS, subdomain or reverse proxy is needed for any of this.** The bot uses *polling*
(`getUpdates`): it always connects out to Telegram, Telegram never connects in to your host. A
subdomain/Caddy/Nginx setup is only needed for *webhooks* (Telegram calling *you*), which this
bot doesn't use — see [Polling vs webhook](#polling-vs-webhook) below.

---

## Option A — Your own VPS ⭐ (if you already have one)

### A1 — Docker (recommended if you're already comfortable with Docker)
```bash
# One-time, on the VPS:
git clone <your-private-repo-url> ~/apps/telegram-voice-bot
cd ~/apps/telegram-voice-bot
cp .env.example .env   # fill TELEGRAM_TOKEN + Groq OPENAI_* + BOT_MODE=text + ADMIN_USER_IDS
docker compose up -d --build
docker compose logs -f   # confirm it connected to Telegram cleanly, then Ctrl+C
```
`docker-compose.yml` already sets `restart: unless-stopped` (survives crashes and VPS reboots,
as long as Docker itself is enabled on boot — check with `systemctl is-enabled docker`; the
official `apt` install enables it automatically on Ubuntu/Debian) and mounts `./data` and `./cv`
as volumes so `/history`'s log and your generated CVs **survive rebuilds** — without that
volume, every redeploy would wipe them.

**To deploy an update**, from the VPS:
```bash
git pull
docker compose up -d --build
```
(A fancier `git push`-to-deploy setup — a bare repo + a `post-receive` hook that rebuilds
automatically — is overkill for a solo-maintainer, low-traffic bot: one more moving part to
maintain for a convenience you won't feel deploying occasionally. Ask if you ever want it.)

### A2 — Plain Python + systemd (no Docker)
```bash
git clone <your-private-repo-url> /opt/telegram-voice-bot && cd /opt/telegram-voice-bot
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill TELEGRAM_TOKEN + Groq OPENAI_* + BOT_MODE=text
# Run as a service (edit paths/user in the unit first):
sudo cp deploy/josembot.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now josembot
journalctl -u josembot -f
```
(If the unit uses a venv, point `ExecStart` at `/opt/telegram-voice-bot/.venv/bin/python`.)

## Option B — Free container hosts: mostly dead as of mid-2026 ❌
- **Koyeb**: its free Instance now scales to zero after **1 hour without traffic** (a polling
  bot generates no inbound "traffic", so it would sleep and never wake) — and since Koyeb's
  acquisition by Mistral AI (Feb 2026), **new users can no longer sign up for the free tier**
  at all. Not usable for this.
- **Fly.io**: no longer has a permanent free tier for new accounts (only a 2-hour trial); a
  minimal always-on app now costs a few dollars a month.
- ❌ **Render / Railway free tiers**: unchanged and still bad — spin down after ~15 min idle,
  which kills the polling loop.

If you don't have your own VPS, **Option C (Oracle)** is the real free always-on alternative.

## Option C — Oracle Cloud **Always Free** VM (genuinely free, genuinely 24/7)
A free-forever Linux VM: ARM Ampere A1 (2 OCPU / 12 GB as of mid-2026 — reduced from 4/24 in
June 2026, still far more than this bot needs) or an AMD micro instance. Create the instance,
then follow **Option A** (Docker or systemd). Real caveats: Ampere capacity is often "out of
capacity" in popular regions (may need a few retries), sign-up requires a credit card for
verification (not charged if you stay in the free tier), and the cloud-level firewall (Security
List) is closed by default — but note **this bot needs zero inbound ports open**, since it only
polls outward.

---

## Security note for this project specifically
Your **real** data (`profile/profile.md`, `profile/projects.yaml`, `profile/knowledge.md`,
`.env`, and now `data/` if `/history` is enabled) must live in a **private** repository or be
copied to the VPS out-of-band — never in the public `telegram-cv-bot` template repo. Clone the
public template for the code, keep your real config/data in a separate private git repo (or
just `scp` them once) on top of it.

### Polling vs webhook
This bot uses **polling** (`run_polling`), which needs no inbound network path at all and works
on any host that can make outbound HTTPS calls (VPS, Oracle, your laptop). You'd only need a
webhook (and therefore a domain + TLS + reverse proxy) if you went fully serverless (Cloudflare
Workers / Vercel / Deno Deploy) — that would require restructuring the bot as a webhook handler,
which is not necessary for a personal, low-traffic bot like this one.
