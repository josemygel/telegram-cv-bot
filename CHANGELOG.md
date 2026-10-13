# Changelog

Formato [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/).

## [1.3.2] - 2026-10-13

### 🐛 Corregido
- **Fotos y PDF del dueño se analizan como asistente personal.** Con el prompt público del CV,
  Haiku se negaba a leer los datos de una factura del propio dueño («no voy a detallar los datos
  bancarios…») y desviaba la conversación hacia su experiencia. Ahora, si quien envía es
  `OWNER_USER_ID`, se usa un prompt de asistente personal, sin perfil ni historial (más barato,
  y el contenido privado no entra en el historial público). Para el resto no cambia nada.
- **La respuesta a una foto salía con `**asteriscos**` literales**: no pasaba por la conversión de
  Markdown a HTML que ya usan el texto y los PDF.
- **Los fallos de audio, foto y PDF ahora dejan traza en el log.** El manejador se tragaba la
  excepción y en producción solo se veía «Ups, algo ha fallado», sin forma de saber la causa.

## [1.3.1] - 2026-10-13

### 🐛 Corregido
- **El log ya dice POR QUÉ Anthropic rechaza una petición.** En producción solo aparecía
  `POST /v1/messages "HTTP/1.1 400 Bad Request"`: imposible distinguir saldo agotado
  («credit balance is too low»), un modelo inexistente o un parámetro no admitido. Ahora cada
  error del SDK se registra con su tipo y el mensaje de la API (nunca contiene la clave, que viaja
  en la cabecera).

## [1.3.0] - 2026-10-13

### ✨ Añadido
- **Transcripción local con faster-whisper `large-v3-turbo`** (int8, 6 hilos, `vad_filter`) y un
  `initial_prompt` con el vocabulario técnico del perfil (`profile/projects.yaml`; lista por
  defecto si no existe) para que acierte siglas y nombres propios. El modelo se carga una vez y
  la transcripción corre en un hilo detrás de una **cola de un solo trabajador**: quien espera ve
  `⏳ En cola (N.º)…` y el bot sigue respondiendo. Elegimos turbo por calidad aun sabiendo que en
  el VPS (2 CPUs) un clip de 11 s tarda ~39 s frente a ~11 s con `small`: el dueño lo acepta.
- **Burbuja de estado única**: se responde al audio y ese mensaje se edita (`🎙️ Transcribiendo…
  m:ss / m:ss` con ediciones de ≥ 2 s para no chocar con los límites de Telegram → `💭 Pensando…`
  → resultado). Cualquier fallo la deja en un mensaje de error corto, nunca en silencio. Las
  transcripciones largas se parten por texto (cada trozo con su propio `<pre>`), porque partir
  HTML ya renderizado rompería las etiquetas.
- **Topes antes de descargar** con lo que informa Telegram: audio ≤ 60 s (≤ 5 min el dueño) y
  ≤ 20 MB. El dueño puede enviar o reenviar archivos de audio; el resto, solo notas de voz.
- **Botones del dueño** `💬 Responder` · `📝 Resumir` · `🌐 Traducir` bajo cada transcripción (sin
  llamada al LLM hasta que pulsa uno, así reenviar audios no gasta tokens). Se verifica
  `from_user.id` en cada callback y el texto fuente vive en SQLite 48 h (`callback_data` admite
  64 bytes). Traducir a Español, Català (también valenciano), English UK/US, Deutsch y Français.
  Cada llamada se apunta en el ledger con su etiqueta (`answer`/`summary`/`translate`/`pdf`/`inline`).
- **PDF** para todos (≤ 5 MB y ≤ 5 páginas con pypdf), enviado nativo a Claude como bloque
  `document`. No se guarda en el historial: reenviar el base64 en cada turno multiplicaría el coste.
- **Modo inline solo del dueño** (`@bot texto `): seis traducciones, con antirrebote (solo si acaba
  en espacio o ≥ 3 palabras), caché de 10 min y tope de 500 caracteres. Activar con
  `/setinline` en @BotFather.
- **Endurecimiento Docker**: usuario sin privilegios, raíz de solo lectura con `tmpfs` en `/tmp`,
  `cap_drop: ALL`, `no-new-privileges`, `cpus: 6`, `cpu_shares: 256`, `mem_limit: 5g`, sin puertos,
  volúmenes para `data/`, `cv/` y la caché del modelo, y `LABEL com.josembot.image=bot`.
  No hace falta ffmpeg: faster-whisper decodifica con PyAV.
- DEPLOY.md documenta el flujo real de producción (repo público → repo privado → Plesk).

### 🔒 Seguridad
- Del contenido de audios de terceros solo se guarda en `/history` la duración; los ficheros
  descargados se borran justo después de procesarse.

### 💥 Cambios incompatibles
- Se retira el flujo «voz entra → voz sale» (`handlers/voice.py`): las notas de voz ahora devuelven
  la transcripción (TTS queda fuera de esta fase). `WHISPER_MODEL` pasa de `base` a `large-v3-turbo`
  y `WHISPER_DEVICE` de `auto` a `cpu`. `faster-whisper` y `pypdf` entran en `requirements.txt`.

### Pendiente
- `🌐 Traducir` bajo las respuestas automáticas a mensajes de texto del dueño: se omite (traduciría
  la respuesta del bot, no un texto suyo, y complica el flujo).

## [1.2.0] - 2026-10-13

### ✨ Añadido
- **Backend nativo de Anthropic** (`LLM_BACKEND=anthropic`, `src/llm_anthropic.py`) con el SDK
  oficial, modelo por defecto `claude-haiku-5-5`. El perfil se envía como `system` con
  `cache_control` en el último bloque (es el prefijo grande y estable, así se reutiliza).
  Las fotos viajan como bloques `image` base64 nativos; la visión queda activa siempre con
  este backend.
- **Contabilidad de tokens por usuario** (`src/token_ledger.py`, SQLite en `USAGE_DB_PATH`):
  entrada, salida y caché (lectura/escritura) de cada llamada, con coste estimado a tarifas de
  Haiku 5.5 (0,10 / 0,50 USD por MTok; lectura de caché 0,1x y escritura 1,25x de la entrada).
- **Regla anti-abuso**: más de 200k tokens en 1 h o 1M en 24 h bloquea al usuario 24 h, avisa
  una sola vez a los admins y le responde con un mensaje amable (es/en). El dueño cuenta pero
  nunca se bloquea. Comandos solo del dueño: `/coste` (hoy y mes, por usuario) y
  `/desbloquear <id>`.
- **Topes de entrada antes de llamar o descargar**: texto > 2000 caracteres se rechaza (no se
  trunca); foto > 5 MB se rechaza mirando el `file_size` que informa Telegram, sin descargarla;
  vídeo, notas de vídeo, documentos, animaciones y audio se ignoran sin descargar (el PDF
  llegará en la fase B). Salida limitada con `ANTHROPIC_MAX_TOKENS` (800).
- El bot abandona cualquier grupo al que no lo haya añadido el dueño (`my_chat_member`).
- Nuevas variables: `ANTHROPIC_*`, `OWNER_USER_ID` (por defecto, el primer `ADMIN_USER_IDS`),
  `TOKEN_LIMIT_HOUR/DAY`, `MAX_INPUT_CHARS`, `MAX_PHOTO_BYTES`, `USAGE_DB_PATH`.

### 🐛 Corregido
- El tope de texto pasa de 1500 a 2000 caracteres y ahora es configurable.

### 📝 Por qué un backend propio y no apuntar `OPENAI_BASE_URL` a Anthropic
- `OpenAICompatLLM` envía siempre `temperature`, y **Haiku 5.5 devuelve 400 ante cualquier
  valor de muestreo distinto del de por defecto**: con el shim cada mensaje habría fallado.
  El backend nuevo nunca envía `temperature` ni `thinking` (omitir `thinking` = adaptativo;
  `budget_tokens` también da 400).
- El razonamiento adaptativo se factura como salida; para preguntas sobre un CV basta
  `effort: "low"`.
- La visión usa bloques `image` base64, no `image_url`.
- No verificado sin clave real: que `claude-haiku-5-5` acepte imágenes y `output_config.effort`
  en la cuenta de Sugo Labs. Las pruebas usan un SDK simulado (sin red).
