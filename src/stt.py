"""Speech-to-text with faster-whisper.

Resilient device handling:
- CPU by default (works everywhere; whisper-small transcribes a short note in ~2-3 s).
- GPU is wired and ready: set WHISPER_DEVICE=cuda. On Blackwell (RTX 50xx, sm_120) INT8
  is unsupported so CUDA forces float16, and the pip CUDA DLL dirs are added to the
  Windows search path. If GPU INFERENCE then fails (e.g. cuBLAS/cuDNN DLLs missing — the
  pip nvidia-*-cu12 wheels don't ship Windows DLLs), we transparently rebuild on CPU and
  retry, so voice never breaks.
faster-whisper reads OGG/Opus directly via PyAV, so no external ffmpeg is needed here.
"""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path

from faster_whisper import WhisperModel

from .config import WHISPER_COMPUTE, WHISPER_DEVICE, WHISPER_MODEL

_CUDA_MARKERS = ("cublas", "cudnn", "cuda", "gpu", "libcu", "cubla")


def _add_cuda_dll_dirs() -> None:
    """Add pip-installed CUDA lib dirs to the Windows DLL search path (best effort)."""
    if not hasattr(os, "add_dll_directory"):
        return
    for pkg in ("nvidia.cudnn", "nvidia.cublas"):
        spec = importlib.util.find_spec(pkg)
        if not spec or not spec.submodule_search_locations:
            continue
        root = Path(list(spec.submodule_search_locations)[0])
        for sub in ("bin", "lib"):
            d = root / sub
            if d.is_dir():
                try:
                    os.add_dll_directory(str(d))
                except (OSError, ValueError):
                    pass


class _ModelHolder:
    """Lazily builds the WhisperModel and remembers if we had to drop to CPU."""

    def __init__(self):
        self._model: WhisperModel | None = None
        self._cpu_only = False

    def _build(self) -> WhisperModel:
        if self._cpu_only or (WHISPER_DEVICE or "").lower() == "cpu":
            return WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")
        _add_cuda_dll_dirs()
        compute = WHISPER_COMPUTE or "float16"
        if "int8" in compute:  # INT8 is disabled on Blackwell sm_120
            compute = "float16"
        return WhisperModel(WHISPER_MODEL, device=WHISPER_DEVICE, compute_type=compute)

    def get(self) -> WhisperModel:
        if self._model is None:
            try:
                self._model = self._build()
            except Exception:
                self._cpu_only = True
                self._model = self._build()
        return self._model

    def force_cpu(self) -> WhisperModel:
        self._cpu_only = True
        self._model = None
        return self.get()

    @property
    def cpu_only(self) -> bool:
        return self._cpu_only


_holder = _ModelHolder()


def _looks_like_cuda_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(marker in msg for marker in _CUDA_MARKERS)


class WhisperSTT:
    def transcribe(self, audio_path: str) -> str:
        return self.transcribe_detailed(audio_path)[0]

    def transcribe_detailed(self, audio_path: str) -> tuple[str, str]:
        """Return (transcript, detected_lang in {'es','en'}). vad_filter trims silence
        for lower latency; beam_size=1 keeps decoding fast."""
        try:
            return self._run(_holder.get(), audio_path)
        except RuntimeError as exc:
            # GPU inference failed (missing cuBLAS/cuDNN DLLs) -> CPU fallback, retry once.
            if _holder.cpu_only or not _looks_like_cuda_error(exc):
                raise
            return self._run(_holder.force_cpu(), audio_path)

    @staticmethod
    def _run(model: WhisperModel, audio_path: str) -> tuple[str, str]:
        segments, info = model.transcribe(audio_path, beam_size=1, vad_filter=True)
        text = " ".join(seg.text.strip() for seg in segments).strip()
        lang = "es" if getattr(info, "language", "en") == "es" else "en"
        return text, lang
