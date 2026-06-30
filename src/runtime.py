"""Runtime selection: bot mode (voice/text) and LLM backend."""
from __future__ import annotations

import shutil
import subprocess

from .llm import OllamaLLM, OpenAICompatLLM


def gpu_available() -> bool:
    """True if an NVIDIA GPU is visible (used to auto-enable voice mode)."""
    if shutil.which("nvidia-smi") is None:
        return False
    try:
        out = subprocess.run(["nvidia-smi", "-L"], capture_output=True, text=True, timeout=5)
        return out.returncode == 0 and "GPU" in out.stdout
    except Exception:
        return False


def resolve_mode(bot_mode: str, gpu: bool) -> str:
    bot_mode = (bot_mode or "auto").lower()
    if bot_mode in {"voice", "text"}:
        return bot_mode
    return "voice" if gpu else "text"  # "auto"


def get_llm(backend: str):
    backend = (backend or "ollama").lower()
    if backend == "ollama":
        return OllamaLLM()
    if backend == "openai":
        return OpenAICompatLLM()
    raise ValueError(f"Unknown LLM_BACKEND: {backend!r} (use 'ollama' or 'openai')")
