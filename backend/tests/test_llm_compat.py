import base64

import pytest

from emergentintegrations.llm.chat import FileContent, LlmChat, UserMessage


def test_provider_model_mapping():
    assert (
        LlmChat("key", "test")
        .with_model("openai", "gpt-4o")
        ._litellm_model()
        == "openai/gpt-4o"
    )
    assert (
        LlmChat("key", "test")
        .with_model("gemini", "gemini-2.5-flash")
        ._litellm_model()
        == "gemini/gemini-2.5-flash"
    )
    assert (
        LlmChat("key", "test")
        .with_model("anthropic", "claude-sonnet")
        ._litellm_model()
        == "anthropic/claude-sonnet"
    )


def test_message_with_image_is_converted_to_data_url():
    encoded = base64.b64encode(b"image-data").decode("ascii")
    message = UserMessage(
        text="Describe the image",
        file_contents=[
            FileContent(content_type="image/png", file_content_base64=encoded)
        ],
    )

    content = LlmChat("key", "test")._user_content(message)

    assert content[0] == {"type": "text", "text": "Describe the image"}
    assert content[1]["image_url"]["url"] == f"data:image/png;base64,{encoded}"


def test_provider_specific_key_has_priority(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "project-key")
    chat = LlmChat("legacy-key", "test").with_model("openai", "gpt-4o")

    assert chat._provider_api_key() == "project-key"


@pytest.mark.asyncio
async def test_missing_key_fails_before_network_call(monkeypatch):
    for variable in ("OPENAI_API_KEY", "GEMINI_API_KEY", "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(variable, raising=False)
    chat = LlmChat("", "test").with_model("openai", "gpt-4o")

    with pytest.raises(RuntimeError, match="LLM API key is not configured"):
        await chat.send_message(UserMessage(text="Hello"))
