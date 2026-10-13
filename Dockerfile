# josembot — Telegram assistant. LLM backend = Anthropic (Claude), OpenAI-compatible or Ollama.
# STT (faster-whisper) and PDF page counting (pypdf) are in requirements.txt. No ffmpeg needed:
# faster-whisper decodes audio with PyAV, which bundles its own libav.
#
# Build:  docker build -t josembot .
# Run:    docker run -d --env-file .env --name josembot --restart unless-stopped josembot
FROM python:3.12-slim
# Etiqueta propia en CADA etapa: permite limpiar imagenes huerfanas de este proyecto sin tocar otras.
LABEL com.josembot.image=bot

WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONUTF8=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY profile/ ./profile/
COPY content/ ./content/
COPY cv/ ./cv/
COPY chat_cli.py .

# Usuario sin privilegios (uid fijo para que los volumenes montados se puedan preparar con chown).
# /models guarda el modelo de Whisper (~1.6 GB) para no re-descargarlo en cada despliegue; es un
# volumen porque el sistema de ficheros del contenedor va de solo lectura.
RUN useradd --uid 61001 --no-create-home --shell /usr/sbin/nologin bot     && mkdir -p /models /app/data /app/cv && chown -R bot /models /app/data /app/cv
ENV HF_HOME=/models HOME=/tmp
USER bot

# Secrets (TELEGRAM_TOKEN, OPENAI_BASE_URL/KEY/MODEL, BOT_MODE=text...) come from the host's
# env / secrets manager or --env-file .env — never baked into the image (see .dockerignore).
CMD ["python", "-m", "src.bot"]
