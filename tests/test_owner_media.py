"""Fotos/PDF del dueno: se analizan como asistente personal, sin el prompt publico del CV."""
from src.pipeline import Pipeline


class _RecordingLLM:
    def __init__(self):
        self.calls = []

    def reply(self, messages):
        self.calls.append(messages)
        return " Factura de 12,04 € "


def test_owner_media_uses_owner_prompt_not_profile_history():
    llm = _RecordingLLM()
    p = Pipeline(llm=llm, system_prompt="PERFIL PUBLICO DEL CV")
    out = p.analyze_media_for_owner({"type": "pdf", "data": "ZmFrZQ=="}, "", "pdf")
    assert out == {"reply": "Factura de 12,04 €"}
    sent = llm.calls[0]
    # El prompt del CV (que hacia negarse a leer sus facturas) no viaja.
    assert all("PERFIL PUBLICO" not in str(m.get("content")) for m in sent)
    assert sent[0] == {"role": "system", "content": Pipeline.OWNER_MEDIA_PROMPT}
    user_parts = sent[1]["content"]
    assert user_parts[0] == {"type": "text", "text": "Resume este documento."}
    assert user_parts[1]["type"] == "pdf"


def test_owner_media_keeps_caption_and_does_not_touch_history():
    llm = _RecordingLLM()
    p = Pipeline(llm=llm)
    part = {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,eA=="}}
    p.analyze_media_for_owner(part, "¿Qué pone aquí?", "image")
    assert llm.calls[0][1]["content"][0]["text"] == "¿Qué pone aquí?"
    # El historial publico del chat no se contamina con el contenido privado del dueno.
    assert p._histories == {}
