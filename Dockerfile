# josembot — Telegram assistant (text mode). LLM backend = OpenAI-compatible (Groq) or Ollama.
# Voice (faster-whisper/edge-tts) is NOT installed here on purpose: keep the image light for
# free/tiny 24/7 hosts. If BOT_MODE=voice is set without those deps, the bot degrades to text.
#
# Build:  docker build -t josembot .
# Run:    docker run -d --env-file .env --name josembot --restart unless-stopped josembot
FROM python:3.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONUTF8=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY profile/ ./profile/
COPY content/ ./content/
COPY cv/ ./cv/
COPY chat_cli.py .

# Secrets (TELEGRAM_TOKEN, OPENAI_BASE_URL/KEY/MODEL, BOT_MODE=text...) come from the host's
# env / secrets manager or --env-file .env — never baked into the image (see .dockerignore).
CMD ["python", "-m", "src.bot"]
