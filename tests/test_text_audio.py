"""Detection of explicit 'reply in audio' requests in free-text messages."""
from src.handlers.text import _is_content_free, _is_greeting, _wants_audio, _wants_contact


def test_content_free_detects_lone_emoji():
    assert _is_content_free("👍")
    assert _is_content_free("🥲")
    assert _is_content_free("😂😂😂")
    assert _is_content_free("...")
    assert _is_content_free("")


def test_content_free_false_for_real_text():
    assert not _is_content_free("hola")
    assert not _is_content_free("👍 gracias")  # emoji + real text -> still a real message
    assert not _is_content_free("123")  # digits count as content


def test_detects_contact_requests():
    assert _wants_contact("contactar con el")
    assert _wants_contact("¿cuáles son sus datos de contacto?")
    assert _wants_contact("how can I contact him?")


def test_non_contact_not_triggered():
    assert not _wants_contact("¿con quién ha contactado en GDFitness?")
    assert not _wants_contact("háblame de sus proyectos")


def test_detects_pure_greetings():
    assert _is_greeting("hola")
    assert _is_greeting("Hola!")
    assert _is_greeting("buenos días")
    assert _is_greeting("hello there 🙂")


def test_greeting_with_question_goes_to_llm():
    assert not _is_greeting("hola, cuéntame de GDFitness")
    assert not _is_greeting("¿qué proyectos tiene?")


def test_detects_audio_request():
    assert _wants_audio("respóndeme en audio por favor")
    assert _wants_audio("can you send it by voice?")
    assert _wants_audio("mándame un audio")


def test_plain_question_does_not_trigger_audio():
    assert not _wants_audio("¿Qué proyectos tiene Jose Miguel?")
    assert not _wants_audio("What is his experience with RAG?")
