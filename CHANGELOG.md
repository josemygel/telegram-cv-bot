# Changelog

Formato [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/).

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
