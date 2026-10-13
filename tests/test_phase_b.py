"""Fase B: STT/cola, topes, burbuja, transcripcion, botones del dueno, PDF e inline."""
import asyncio
from types import SimpleNamespace as NS

import pytest
from telegram.error import BadRequest

from src.action_store import ActionStore
from src.bubble import StatusBubble, fmt_clock
from src.handlers.actions import make_action_handler
from src.handlers.audio import make_audio_handler
from src.handlers.inline import make_inline_handler, ready_to_translate
from src.handlers.pdf import make_pdf_handler
from src.i18n import I18n
from src.job_queue import SingleWorkerQueue
from src.lang_store import InMemoryLangStore
from src.llm_anthropic import convert_messages
from src.media_caps import audio_refusal, pdf_size_refusal
from src.pipeline import Pipeline
from src.stt import TranscriptResult, WhisperSTT
from src.token_ledger import TokenLedger
from src.transcript import duration_label, transcript_chunks
from src.vocab import DEFAULT_TERMS, build_initial_prompt

OWNER, USER = 999, 5


# ---------- pequenas utilidades ----------
def test_vocab_default_and_from_projects():
    assert "Docker" in build_initial_prompt([])
    p = NS(name="Zone", stack=("PHP", "React"))
    out = build_initial_prompt([p, p])
    assert out.count("Zone") == 1 and "React" in out and "Docker" not in out
    assert len(build_initial_prompt([NS(name="x" * 50, stack=tuple(f"t{i}" * 5 for i in range(200)))])) <= 620
    assert DEFAULT_TERMS


def test_caps_owner_user_and_size():
    assert audio_refusal(300, 100, True) is None
    assert audio_refusal(301, 100, True)[0] == "audio_too_long"
    assert audio_refusal(61, 100, False)[0] == "audio_too_long"
    assert audio_refusal(60, 100, False) is None
    assert audio_refusal(10, 21 * 1024 * 1024, True)[0] == "audio_too_large"
    assert pdf_size_refusal(6 * 1024 * 1024)[0] == "pdf_too_large" and pdf_size_refusal(1) is None


def test_duration_label_and_html_escaped_chunks():
    assert duration_label(45) == "Audio de duración 45 s"
    assert duration_label(125) == "Audio de duración 2 min 5 s"
    assert transcript_chunks(5, "a<b & c")[0] == "Audio de duración 5 s\n<pre>a&lt;b &amp; c</pre>"
    chunks = transcript_chunks(200, "palabra " * 1500)
    assert len(chunks) > 1 and all(len(c) < 4096 and c.endswith("</pre>") for c in chunks)


def test_fmt_clock():
    assert fmt_clock(65) == "1:05" and fmt_clock(0) == "0:00"


def test_action_store_ttl_and_short_id():
    now = [1000.0]
    st = ActionStore(":memory:", ttl_hours=48, clock=lambda: now[0])
    aid = st.put(1, "hola", "<pre>hola</pre>", "es")
    assert len(f"act:l:ca:{aid}") <= 64 and st.get(aid).source_text == "hola"
    now[0] += 48 * 3600 + 1
    assert st.get(aid) is None


def test_queue_runs_one_at_a_time_and_reports_position():
    q, running, peak, waits = SingleWorkerQueue(), [0], [0], []

    def job(i):
        running[0] += 1
        peak[0] = max(peak[0], running[0])
        import time
        time.sleep(0.05)
        running[0] -= 1
        return i

    async def on_wait(n):
        waits.append(n)

    async def main():
        return await asyncio.gather(*(q.run(job, i, on_wait=on_wait) for i in range(3)))

    assert asyncio.run(main()) == [0, 1, 2]
    assert peak[0] == 1 and waits == [1, 2]


# ---------- STT con whisper falso ----------
class _Model:
    def transcribe(self, path, **kw):
        self.kw = kw
        segs = [NS(text=" hola ", end=2.0), NS(text="mundo", end=4.0)]
        return iter(segs), NS(language="ca", duration=4.0)


def test_whisper_progress_prompt_and_vad(monkeypatch):
    import src.stt as stt_mod
    model = _Model()
    monkeypatch.setattr(stt_mod._holder, "get", lambda: model)
    seen = []
    res = WhisperSTT(initial_prompt="Vocab").transcribe_progress("x", lambda d, t: seen.append((d, t)))
    assert res == TranscriptResult("hola mundo", "ca", 4.0)
    assert seen == [(2.0, 4.0), (4.0, 4.0)]
    assert model.kw["vad_filter"] is True and model.kw["initial_prompt"] == "Vocab"
    assert WhisperSTT().transcribe_detailed("x") == ("hola mundo", "en")


def test_defaults_large_v3_turbo_int8_6_threads():
    from src import config
    assert (config.WHISPER_MODEL, config.WHISPER_COMPUTE, config.WHISPER_CPU_THREADS) == ("large-v3-turbo", "int8", 6)


# ---------- burbuja ----------
class _Sent:
    def __init__(self, text, kw, log):
        self.text, self.kw, self.log, self.edits = text, kw, log, []

    async def edit_text(self, text, **kw):
        if self.edits and self.edits[-1][0] == text:
            raise BadRequest("Message is not modified")
        self.edits.append((text, kw))


class _Msg:
    def __init__(self, uid=USER, **attrs):
        self.replies, self.sent = [], []
        self.voice = self.audio = self.document = None
        self.caption = None
        self.__dict__.update(attrs)

    async def set_reaction(self, *a, **k):
        pass

    async def reply_text(self, text, **kw):
        s = _Sent(text, kw, self.replies)
        self.replies.append(text)
        self.sent.append(s)
        return s


def test_bubble_throttle_and_not_modified():
    now = [0.0]
    msg = _Msg()
    b = StatusBubble(msg, clock=lambda: now[0])

    async def main():
        await b.start("a")
        now[0] = 1.0
        await b.edit("b", throttle=True)  # <2 s: se ignora
        now[0] = 2.5
        await b.edit("b", throttle=True)
        await b.edit("c")
        b._msg.edits.append(("c", {}))
        await b.edit("c")  # igual: no edita
        await b.show(["x", "y"])
        await b.show(["x", "z"])  # el trozo 2 se edita, no se duplica

    asyncio.run(main())
    texts = [e[0] for e in msg.sent[0].edits]
    assert texts[:2] == ["b", "c"] and len(msg.sent) == 2
    assert [e[0] for e in msg.sent[1].edits] == ["z"]


# ---------- handler de audio ----------
class _Bot:
    def __init__(self):
        self.downloads, self.paths = 0, []

    async def send_chat_action(self, *a, **k):
        pass

    async def send_message(self, *a, **k):
        pass

    async def get_file(self, fid):
        self.downloads += 1
        bot = self

        class F:
            async def download_to_drive(self, path):
                import pathlib
                pathlib.Path(path).write_bytes(b"%PDF-1.4 data")
                bot.paths.append(path)
        return F()


class _STT:
    def __init__(self, text="hola qué tal"):
        self.text = text

    def transcribe_progress(self, path, cb=None):
        if cb:
            cb(3.0, 6.0)
        return TranscriptResult(self.text, "es", 6.0)


class _Pipe(Pipeline):
    def __init__(self):
        self.calls = []
        self.llm = None

    def process_text(self, chat_id, text, lang=None):
        self.calls.append(("text", text))
        return {"reply": "Respuesta"}

    def process_pdf(self, *a, **k):
        self.calls.append(("pdf",))
        return {"reply": "Resumen pdf"}

    def run_task(self, instruction, text):
        self.calls.append(("task", instruction, text))
        return "TRAD"


def _deps(tmp_path, stt=None, **extra):
    d = {"pipeline": _Pipe(), "lang_store": InMemoryLangStore(default="es"),
         "i18n": I18n("content/i18n", default="es"), "stt": stt or _STT(), "queue": SingleWorkerQueue(),
         "action_store": ActionStore(":memory:"), "owner_id": OWNER, "admin_ids": {OWNER},
         "ledger": TokenLedger(str(tmp_path / "u.db"), owner_id=OWNER), "history_store": None,
         "pdf_enabled": True}
    d.update(extra)
    return d


def _upd(uid, **msg):
    return NS(message=_Msg(**msg), effective_user=NS(id=uid, username="u", first_name="U"),
              effective_chat=NS(id=uid))


def _run(handler, upd, ctx=None):
    asyncio.run(handler(upd, ctx or NS(bot=_Bot())))


def test_non_owner_voice_gets_transcript_and_answer_in_same_bubble(tmp_path):
    d = _deps(tmp_path)
    ctx = NS(bot=_Bot())
    u = _upd(USER, voice=NS(duration=30, file_size=1000, file_id="f"))
    _run(make_audio_handler(d), u, ctx)
    bubble = u.message.sent[0]
    assert u.message.replies[0].startswith("🎙️ Transcribiendo… 0:00 / 0:30")
    final = bubble.edits[-1][0]
    assert final.startswith("Audio de duración 6 s\n<pre>hola qué tal</pre>") and final.endswith("Respuesta")
    assert any("💭 Pensando…" in e[0] for e in bubble.edits)
    assert d["pipeline"].calls == [("text", "hola qué tal")]
    assert not __import__("os").path.exists(ctx.bot.paths[0])  # audio borrado


def test_owner_voice_transcript_only_with_buttons_and_no_llm(tmp_path):
    d = _deps(tmp_path)
    u = _upd(OWNER, audio=NS(duration=290, file_size=1000, file_id="f"))
    _run(make_audio_handler(d), u)
    last = u.message.sent[0].edits[-1]
    assert d["pipeline"].calls == []
    labels = [b.text for b in last[1]["reply_markup"].inline_keyboard[0]]
    assert labels == ["💬 Responder", "📝 Resumir", "🌐 Traducir"]


def test_caps_refuse_without_download(tmp_path):
    d = _deps(tmp_path)
    ctx = NS(bot=_Bot())
    u = _upd(USER, voice=NS(duration=61, file_size=10, file_id="f"))
    _run(make_audio_handler(d), u, ctx)
    assert ctx.bot.downloads == 0 and "60" in u.message.replies[0]
    u = _upd(USER, audio=NS(duration=5, file_size=10, file_id="f"))  # audio no-voz: solo dueno
    _run(make_audio_handler(d), u, ctx)
    assert ctx.bot.downloads == 0
    u = _upd(OWNER, voice=NS(duration=301, file_size=10, file_id="f"))
    _run(make_audio_handler(d), u, ctx)
    assert ctx.bot.downloads == 0


def test_stt_failure_edits_bubble_with_friendly_error(tmp_path):
    class Boom:
        def transcribe_progress(self, *a, **k):
            raise RuntimeError("x")

    d = _deps(tmp_path, stt=Boom())
    u = _upd(USER, voice=NS(duration=5, file_size=10, file_id="f"))
    _run(make_audio_handler(d), u)
    assert "falla" in u.message.sent[0].edits[-1][0].lower() or "ups" in u.message.sent[0].edits[-1][0].lower()


# ---------- callbacks ----------
class _Q:
    def __init__(self, uid, data, text="x"):
        self.from_user, self.data = NS(id=uid), data
        self.message = _Msg()
        self.message.text_html = text
        self.answers, self.edits = [], []

    async def answer(self, text=None, show_alert=False):
        self.answers.append((text, show_alert))

    async def edit_message_text(self, text, reply_markup=None, parse_mode=None):
        self.edits.append((text, reply_markup))


def _cb(handler, uid, data, d=None):
    q = _Q(uid, data)
    asyncio.run(handler(NS(callback_query=q, effective_user=NS(id=uid, username="o", first_name="O"),
                           effective_chat=NS(id=uid)), NS(bot=_Bot())))
    return q


def test_callback_rejects_non_owner_and_expired(tmp_path):
    d = _deps(tmp_path)
    aid = d["action_store"].put(OWNER, "texto", "<pre>texto</pre>", "es")
    h = make_action_handler(d)
    q = _cb(h, USER, f"act:r:{aid}")
    assert q.answers[0][1] is True and q.edits == [] and d["pipeline"].calls == []
    q = _cb(h, OWNER, "act:r:nope")
    assert q.answers[0][1] is True and d["pipeline"].calls == []


def test_respond_summarize_translate_flow(tmp_path):
    d = _deps(tmp_path)
    aid = d["action_store"].put(OWNER, "texto", "<pre>texto</pre>", "ca")
    h = make_action_handler(d)
    q = _cb(h, OWNER, f"act:r:{aid}")
    assert q.edits[-1] == ("<pre>texto</pre>\n\nRespuesta", None)
    q = _cb(h, OWNER, f"act:s:{aid}")
    assert q.edits[-1][0].endswith("TRAD") and "3 líneas" in d["pipeline"].calls[-1][1]
    q = _cb(h, OWNER, f"act:t:{aid}")
    assert "Idioma de origen: Català" in q.edits[-1][0]
    assert [b.text for r in q.edits[-1][1].inline_keyboard for b in r] == [
        "Español", "Català", "English (UK)", "English (US)", "Deutsch", "Français"]
    q = _cb(h, OWNER, f"act:l:ca:{aid}")
    assert q.edits[-1][0].endswith("🌐 Català:\nTRAD") and "Catalan" in d["pipeline"].calls[-1][1]


def test_calls_are_booked_with_feature_label(tmp_path):
    seen = []
    from src.token_ledger import call_context

    class P(_Pipe):
        def run_task(self, i, t):
            seen.append(call_context.get())
            return "ok"

    d = _deps(tmp_path, pipeline=P())
    aid = d["action_store"].put(OWNER, "t", "<pre>t</pre>", "es")
    _cb(make_action_handler(d), OWNER, f"act:s:{aid}")
    assert seen == [(OWNER, "summary")]


# ---------- PDF ----------
def _pdf_bytes(pages):
    from pypdf import PdfWriter
    import io
    w = PdfWriter()
    for _ in range(pages):
        w.add_blank_page(100, 100)
    b = io.BytesIO()
    w.write(b)
    return b.getvalue()


class _PdfBot(_Bot):
    def __init__(self, data):
        super().__init__()
        self.data = data

    async def get_file(self, fid):
        self.downloads += 1
        data = self.data

        class F:
            async def download_to_drive(self, path):
                import pathlib
                pathlib.Path(path).write_bytes(data)
        return F()


def _pdf_update(size=1000):
    return _upd(USER, document=NS(file_size=size, file_id="f", mime_type="application/pdf"))


def test_pdf_ok_sent_and_too_many_pages_refused(tmp_path):
    d = _deps(tmp_path)
    u = _pdf_update()
    _run(make_pdf_handler(d), u, NS(bot=_PdfBot(_pdf_bytes(5))))
    assert u.message.sent[0].edits[-1][0] == "Resumen pdf" and d["pipeline"].calls == [("pdf",)]
    d = _deps(tmp_path)
    u = _pdf_update()
    _run(make_pdf_handler(d), u, NS(bot=_PdfBot(_pdf_bytes(6))))
    assert d["pipeline"].calls == [] and "5" in u.message.sent[0].edits[-1][0]


def test_pdf_size_and_disabled_and_corrupt(tmp_path):
    d = _deps(tmp_path)
    bot = _PdfBot(b"junk")
    u = _pdf_update(size=6 * 1024 * 1024)
    _run(make_pdf_handler(d), u, NS(bot=bot))
    assert bot.downloads == 0
    u = _pdf_update()
    _run(make_pdf_handler(d), u, NS(bot=bot))
    assert d["pipeline"].calls == [] and "PDF" in u.message.sent[0].edits[-1][0]
    d = _deps(tmp_path, pdf_enabled=False)
    u = _pdf_update()
    _run(make_pdf_handler(d), u, NS(bot=bot))
    assert bot.downloads == 1  # solo el del caso corrupto


def test_anthropic_converts_pdf_part_to_document_block():
    _, turns = convert_messages([{"role": "user", "content": [
        {"type": "text", "text": "q"}, {"type": "pdf", "data": "QUJD"}]}])
    assert turns[0]["content"][1] == {"type": "document", "source": {
        "type": "base64", "media_type": "application/pdf", "data": "QUJD"}}


def test_pipeline_pdf_not_persisted_in_history():
    class L:
        def reply(self, m):
            self.m = m
            return "ok"

    p = Pipeline(llm=L())
    assert p.process_pdf(1, "QUJD", "", "Spanish")["reply"] == "ok"
    assert "QUJD" not in str(p._histories[1]) and "[PDF]" in str(p._histories[1])


# ---------- inline ----------
class _IQ:
    def __init__(self, uid, query):
        self.from_user, self.query, self.results = NS(id=uid), query, None

    async def answer(self, results, **kw):
        self.results = results


def _inline(handler, uid, query):
    iq = _IQ(uid, query)
    asyncio.run(handler(NS(inline_query=iq), None))
    return iq.results


def test_inline_owner_only_debounce_cache_and_cap(tmp_path):
    d = _deps(tmp_path)
    h = make_inline_handler(d)
    assert _inline(h, USER, "hola mundo y más") == []
    assert _inline(h, OWNER, "hola") == []  # sin espacio final ni 3 palabras
    assert d["pipeline"].calls == []
    res = _inline(h, OWNER, "hola ")
    assert len(res) == 6 and len(d["pipeline"].calls) == 6
    _inline(h, OWNER, "hola ")
    assert len(d["pipeline"].calls) == 6  # cache
    assert _inline(h, OWNER, "a " * 300) == []
    assert ready_to_translate("uno dos tres") and not ready_to_translate("  ")
