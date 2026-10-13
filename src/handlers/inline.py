"""Modo inline SOLO para el dueno: `@bot texto` ofrece una traduccion por idioma.

Coste: cada consulta lanza 6 traducciones, asi que (1) solo se traduce cuando el texto termina
en espacio o tiene >= 3 palabras (Telegram envia una consulta por pulsacion), (2) se cachea por
(texto, idioma) 10 min y (3) se limita a INLINE_MAX_CHARS. Cualquier otro usuario recibe una
respuesta vacia (nunca se llama al LLM por el).
"""
from __future__ import annotations

import asyncio
import hashlib
import time

from telegram import InlineQueryResultArticle, InputTextMessageContent

from ..config import INLINE_MAX_CHARS
from ..llm import BackendError
from ..token_ledger import call_context
from .actions import translate_prompt
from .actions_ui import TARGET_LANGS

CACHE_TTL = 600
CACHE_MAX = 200


def ready_to_translate(raw: str) -> bool:
    return bool(raw.strip()) and (raw.endswith(" ") or len(raw.split()) >= 3)


def make_inline_handler(deps, clock=time.monotonic):
    pipeline, owner_id = deps["pipeline"], deps.get("owner_id")
    cache: dict[tuple[str, str], tuple[float, str]] = {}

    def _translate(text: str, code: str) -> str:
        key = (text, code)
        hit = cache.get(key)
        if hit and clock() - hit[0] < CACHE_TTL:
            return hit[1]
        out = pipeline.run_task(translate_prompt(TARGET_LANGS[code][1]), text)
        if len(cache) >= CACHE_MAX:
            cache.pop(next(iter(cache)))
        cache[key] = (clock(), out)
        return out

    async def on_inline(update, context):
        q = update.inline_query
        if q.from_user.id != owner_id:
            await q.answer([], cache_time=60)
            return
        raw = q.query or ""
        text = raw.strip()
        if not ready_to_translate(raw) or len(text) > INLINE_MAX_CHARS:
            await q.answer([], cache_time=0)
            return
        call_context.set((q.from_user.id, "inline"))
        try:
            outs = await asyncio.gather(*(asyncio.to_thread(_translate, text, c) for c in TARGET_LANGS))
        except BackendError:
            await q.answer([], cache_time=0)
            return
        results = [
            InlineQueryResultArticle(
                id=hashlib.sha1(f"{code}:{text}".encode()).hexdigest()[:32],
                title=label, description=out[:100], input_message_content=InputTextMessageContent(out))
            for (code, (label, _)), out in zip(TARGET_LANGS.items(), outs) if out
        ]
        await q.answer(results, cache_time=0, is_personal=True)

    return on_inline
