"""TTS factory + voice selection (no network — does not synthesize)."""
from src.tts import EdgeTTS, PiperTTS, get_tts


def test_get_tts_factory():
    assert isinstance(get_tts("edge"), EdgeTTS)
    assert isinstance(get_tts("piper"), PiperTTS)
    assert isinstance(get_tts(None), EdgeTTS)


def test_edge_voice_selection():
    e = EdgeTTS()
    assert "es-ES" in e._voices["es"]
    assert "en-US" in e._voices["en"]
