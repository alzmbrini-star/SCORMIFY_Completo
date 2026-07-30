"""Editor AI text generation must use the OpenAI key configured for Tutor IA."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from emergentintegrations.llm import chat as llm_chat  # noqa: E402
from routes import ai_gen  # noqa: E402


class FakeLlmChat:
    captured: dict = {}
    response = "```html\n<h2>SCORMIFY</h2><p>Conteúdo gerado.</p>\n```"
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

    async def send_message(self, message):
        self.captured["prompt"] = message.text
        if self.error:
            raise self.error
        return self.response


@pytest.fixture(autouse=True)
def reset_fake(monkeypatch):
    FakeLlmChat.captured = {}
    FakeLlmChat.response = "```html\n<h2>SCORMIFY</h2><p>Conteúdo gerado.</p>\n```"
    FakeLlmChat.error = None
    monkeypatch.setattr(llm_chat, "LlmChat", FakeLlmChat)
    monkeypatch.delenv("EMERGENT_LLM_KEY", raising=False)
    monkeypatch.delenv("OPENAI_TEXT_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_TUTOR_MODEL", raising=False)


@pytest.mark.asyncio
async def test_editor_text_uses_openai_key_and_returns_clean_html(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    monkeypatch.setenv("OPENAI_TEXT_MODEL", "gpt-test-model")

    result = await ai_gen.generate_text_with_ai(
        ai_gen.AITextGenerateRequest(
            prompt="Explique o SCORMIFY",
            context="Curso de integração SCORM",
        ),
        _user={"user_id": "author-1"},
    )

    assert result["success"] is True
    assert result["content"] == "<h2>SCORMIFY</h2><p>Conteúdo gerado.</p>"
    assert FakeLlmChat.captured["api_key"] == "test-openai-key"
    assert FakeLlmChat.captured["provider"] == "openai"
    assert FakeLlmChat.captured["model"] == "gpt-test-model"
    assert "Curso de integração SCORM" in FakeLlmChat.captured["prompt"]


@pytest.mark.asyncio
async def test_editor_text_reports_missing_openai_configuration(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(HTTPException) as exc_info:
        await ai_gen.generate_text_with_ai(
            ai_gen.AITextGenerateRequest(prompt="Crie um texto educacional"),
            _user={"user_id": "author-1"},
        )

    assert exc_info.value.status_code == 503
    assert "OPENAI_API_KEY" in exc_info.value.detail


@pytest.mark.asyncio
async def test_editor_text_maps_openai_quota_error(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    FakeLlmChat.error = RuntimeError("insufficient_quota: billing limit")

    with pytest.raises(HTTPException) as exc_info:
        await ai_gen.generate_text_with_ai(
            ai_gen.AITextGenerateRequest(prompt="Crie um texto educacional"),
            _user={"user_id": "author-1"},
        )

    assert exc_info.value.status_code == 503
    assert "saldo ou limite" in exc_info.value.detail
