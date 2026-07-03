"""Pipeline.process_image: vision content-part shape, independent of any backend."""
from src.pipeline import Pipeline


class FakeVisionLLM:
    def __init__(self):
        self.last_messages = None

    def reply(self, messages: list[dict]) -> str:
        self.last_messages = messages
        return "I see a cat."


def test_process_image_sends_vision_content_parts():
    llm = FakeVisionLLM()
    p = Pipeline(llm=llm)
    out = p.process_image(1, image_b64="ZmFrZQ==", caption="What is this?")
    assert out["reply"] == "I see a cat."
    last_user_msg = [m for m in llm.last_messages if m["role"] == "user"][-1]
    assert isinstance(last_user_msg["content"], list)
    types = {part["type"] for part in last_user_msg["content"]}
    assert types == {"text", "image_url"}
    image_part = next(part for part in last_user_msg["content"] if part["type"] == "image_url")
    assert image_part["image_url"]["url"] == "data:image/jpeg;base64,ZmFrZQ=="


def test_process_image_without_caption_uses_default_prompt():
    llm = FakeVisionLLM()
    p = Pipeline(llm=llm)
    p.process_image(1, image_b64="ZmFrZQ==", caption="")
    last_user_msg = [m for m in llm.last_messages if m["role"] == "user"][-1]
    text_part = next(part for part in last_user_msg["content"] if part["type"] == "text")
    assert text_part["text"]  # some default prompt, non-empty


def test_process_image_persists_to_shared_history():
    llm = FakeVisionLLM()
    p = Pipeline(llm=llm)
    p.process_image(1, image_b64="ZmFrZQ==", caption="What is this?")
    hist = p._history(1)
    assert any(m["role"] == "assistant" and m["content"] == "I see a cat." for m in hist)
