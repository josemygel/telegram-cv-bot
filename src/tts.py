"""Text-to-speech.

EdgeTTS (Microsoft neural voices, online) is the default: pure-Python, no GPU,
excellent low-latency ES/EN voices, and it installs cleanly on Python 3.14. Piper is
kept as a local/offline fallback. Output is written as OGG/Opus (via the bundled
ffmpeg) so Telegram renders a real voice note.
"""
from __future__ import annotations

import asyncio
import subprocess
import tempfile
from pathlib import Path

from .audio import to_opus_ogg
from .config import PIPER_BIN, PIPER_VOICE, TTS_VOICE_EN, TTS_VOICE_ES


class EdgeTTS:
    """Microsoft Edge neural voices (online). Picks an ES or EN voice per language."""

    def __init__(self):
        self._voices = {"es": TTS_VOICE_ES, "en": TTS_VOICE_EN}

    def synthesize(self, text: str, out_path: str, lang: str = "es") -> str:
        import edge_tts

        voice = self._voices.get(lang, TTS_VOICE_ES)
        with tempfile.TemporaryDirectory() as tmp:
            mp3 = str(Path(tmp) / "tts.mp3")
            # edge-tts is async; we run it in this worker thread's own event loop.
            asyncio.run(edge_tts.Communicate(text, voice).save(mp3))
            to_opus_ogg(mp3, out_path)  # -> Telegram voice-note format
        return out_path


class PiperTTS:
    """Local/offline TTS via the Piper binary (needs a .onnx voice file)."""

    def synthesize(self, text: str, out_path: str, lang: str = "es") -> str:
        subprocess.run(
            [PIPER_BIN, "--model", PIPER_VOICE, "--output_file", out_path],
            input=text.encode("utf-8"),
            check=True,
        )
        return out_path


def get_tts(backend: str = "edge"):
    """Factory: 'edge' (default, online ES/EN) or 'piper' (local)."""
    return PiperTTS() if (backend or "edge").lower() == "piper" else EdgeTTS()
