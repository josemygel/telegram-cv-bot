"""Regresion: faster-whisper decodifica con av.open(..., metadata_errors="ignore").

PyAV 19 elimino ese argumento y cada nota de voz fallaba en produccion con
TypeError: open() got an unexpected keyword argument 'metadata_errors'.
"""
import wave

import pytest

av = pytest.importorskip("av")


def test_pyav_accepts_metadata_errors(tmp_path):
    path = tmp_path / "silence.wav"
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(bytes(3200))
    with av.open(str(path), mode="r", metadata_errors="ignore") as container:
        assert container.streams.audio
