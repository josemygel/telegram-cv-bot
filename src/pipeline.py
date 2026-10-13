"""Core orchestration (dependency-injected, testable).

Part of the josembot project, original work by Jose Miguel Gómez Lozano
(github.com/josemygel/telegram-cv-bot) — see AUTHORS.md and LICENSE.

Two paths share the same conversation memory:
- process_text:  text in  -> text reply
- process_voice: audio in -> {transcript, reply, synthesized audio}

Resilience: if the LLM returns an empty reply (reasoning models can do this when
the token budget is tight), we DON'T append an empty assistant turn (it would
corrupt the context) and return '' so the caller can show an honest fallback.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


class STT(Protocol):
    def transcribe(self, audio_path: str) -> str: ...


class LLM(Protocol):
    def reply(self, messages: list[dict]) -> str: ...


class TTS(Protocol):
    def synthesize(self, text: str, out_path: str) -> str: ...


@dataclass
class Pipeline:
    llm: LLM
    stt: STT | None = None  # required only for voice mode
    tts: TTS | None = None  # required only for voice mode
    system_prompt: str = "You are a concise, friendly voice assistant."
    max_turns: int = 8
    max_chats: int = 500  # cap in-memory history entries (public bot = untrusted chat_id churn)
    _histories: dict[int, list[dict]] = field(default_factory=dict)

    def _history(self, chat_id: int) -> list[dict]:
        if chat_id not in self._histories:
            if len(self._histories) >= self.max_chats:
                # Evict the oldest chat (insertion order) so memory can't grow unbounded
                # under bot/scraper traffic to a public instance.
                self._histories.pop(next(iter(self._histories)))
            self._histories[chat_id] = [{"role": "system", "content": self.system_prompt}]
        return self._histories[chat_id]

    def _trim(self, history: list[dict]) -> None:
        if len(history) > self.max_turns + 1:
            history[:] = [history[0]] + history[-self.max_turns:]

    def _generate(self, history: list[dict], lang: str | None, nudge: bool = False) -> str:
        # Ephemeral directives (not stored): a language hint, and on retry a nudge that
        # pushes reasoning models to emit a final answer instead of only their CoT.
        outbound = list(history)
        if lang:
            outbound.insert(1, {"role": "system", "content": f"Always answer in {lang}."})
        if nudge:
            outbound.append({
                "role": "system",
                "content": "Reply now with the final answer for the user, in plain text. "
                           "Do not think out loud; just answer.",
            })
        return self.llm.reply(outbound).strip()

    def _chat(self, chat_id: int, user_text: str, lang: str | None = None) -> str:
        history = self._history(chat_id)
        history.append({"role": "user", "content": user_text})
        reply = self._generate(history, lang)
        if not reply:
            # Reasoning models sometimes emit only their reasoning channel -> retry once.
            reply = self._generate(history, lang, nudge=True)
        if not reply:
            return ""  # don't persist an empty assistant turn; caller shows a fallback
        history.append({"role": "assistant", "content": reply})
        self._trim(history)
        return reply

    def set_system_prompt(self, prompt: str) -> None:
        """Hot-reload the grounding prompt and reset histories so it takes effect
        on the next message (used by the owner's /aprende and /reload commands)."""
        self.system_prompt = prompt
        self._histories.clear()

    def process_text(self, chat_id: int, text: str, lang: str | None = None) -> dict:
        return {"reply": self._chat(chat_id, text.strip(), lang)}

    def process_voice(self, chat_id: int, audio_path: str, out_path: str, lang: str | None = None) -> dict:
        if self.stt is None or self.tts is None:
            raise RuntimeError("Voice mode requires stt and tts components.")
        transcript = self.stt.transcribe(audio_path).strip()
        reply = self._chat(chat_id, transcript, lang)
        audio_out = self.tts.synthesize(reply, out_path)
        return {"transcript": transcript, "reply": reply, "audio": audio_out}

    def process_image(self, chat_id: int, image_b64: str, caption: str, lang: str | None = None) -> dict:
        """Vision turn: caller (handlers/photo.py) already checked the backend supports
        it. Uses the OpenAI-compatible vision content-part format -- image_url with a
        data: URI -- which OpenAICompatLLM forwards verbatim (it doesn't inspect
        message shape), so no backend-specific code lives here."""
        history = self._history(chat_id)
        prompt_text = caption or ("Describe esta imagen." if lang == "Spanish" else "Describe this image.")
        history.append({
            "role": "user",
            "content": [
                {"type": "text", "text": prompt_text},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
            ],
        })
        reply = self._generate(history, lang)
        if not reply:
            reply = self._generate(history, lang, nudge=True)
        if not reply:
            return {"reply": ""}
        history.append({"role": "assistant", "content": reply})
        self._trim(history)
        return {"reply": reply}

    def process_pdf(self, chat_id: int, pdf_b64: str, caption: str, lang: str | None = None) -> dict:
        """PDF nativo. El documento NO se guarda en el historial: reenviar el base64 en cada
        turno posterior multiplicaria el coste. Solo se apunta una nota de texto."""
        history = self._history(chat_id)
        prompt = caption or ("Resume este documento." if lang == "Spanish" else "Summarize this document.")
        turn = {"role": "user", "content": [
            {"type": "text", "text": prompt},
            {"type": "pdf", "data": pdf_b64},
        ]}
        reply = self._generate(history + [turn], lang)
        if not reply:
            return {"reply": ""}
        history.append({"role": "user", "content": f"[PDF] {prompt}"})
        history.append({"role": "assistant", "content": reply})
        self._trim(history)
        return {"reply": reply}

    # Para el DUENO, fotos y PDF se analizan como asistente personal: el prompt publico del CV
    # (pensado para reclutadores) hacia que se negara a leer sus propias facturas o desviara la
    # charla hacia su experiencia. Sin perfil ni historial: mas barato y sin contexto que estorbe.
    OWNER_MEDIA_PROMPT = (
        "Eres el asistente personal de tu dueno. Analiza el documento o la imagen que te envia "
        "y responde exactamente a lo que pide, de forma clara y concisa, en el idioma de su "
        "mensaje (espanol por defecto). Puedes leer y citar cualquier dato del contenido: es suyo."
    )

    def analyze_media_for_owner(self, media_part: dict, caption: str, kind: str) -> dict:
        default = "Resume este documento." if kind == "pdf" else "Describe esta imagen."
        reply = self.llm.reply([
            {"role": "system", "content": self.OWNER_MEDIA_PROMPT},
            {"role": "user", "content": [{"type": "text", "text": caption or default}, media_part]},
        ]).strip()
        return {"reply": reply}

    def run_task(self, instruction: str, text: str) -> str:
        """Tarea de una sola vez (resumir, traducir) sin perfil ni historial: es mas barata y
        el perfil del dueno no tiene nada que aportar a traducir un texto."""
        return self.llm.reply([
            {"role": "system", "content": instruction},
            {"role": "user", "content": text},
        ]).strip()
