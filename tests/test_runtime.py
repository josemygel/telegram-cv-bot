import pytest

from src.llm import OllamaLLM, OpenAICompatLLM
from src.runtime import get_llm, resolve_mode


def test_resolve_mode_explicit():
    assert resolve_mode("voice", False) == "voice"
    assert resolve_mode("text", True) == "text"


def test_resolve_mode_auto():
    assert resolve_mode("auto", True) == "voice"
    assert resolve_mode("auto", False) == "text"


def test_get_llm_factory():
    assert isinstance(get_llm("ollama"), OllamaLLM)
    assert isinstance(get_llm("openai"), OpenAICompatLLM)
    with pytest.raises(ValueError):
        get_llm("nope")
