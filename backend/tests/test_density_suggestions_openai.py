import json
from types import SimpleNamespace

import pytest

from services.density_suggester import generate_visual_suggestions
from services.text_density_analyzer import analyze_slide


def test_density_analyzer_reads_agent_html_elements():
    result = analyze_slide({
        "title": "Seguranca",
        "elements": [{
            "type": "html",
            "htmlContent": "<section><h2>Riscos principais</h2><p>" + ("Use protecao adequada. " * 40) + "</p><img src='x.png'></section>",
        }],
    })

    assert result["metrics"]["words"] > 40
    assert result["metrics"]["hasImage"] is True
    assert result["label"] in {"medium", "heavy"}


@pytest.mark.asyncio
async def test_density_suggester_uses_openai_and_normalizes(monkeypatch):
    payload = {"suggestions": [{
        "type": "bullets",
        "title": "Pontos essenciais",
        "description": "Facilita a leitura.",
        "transformedText": "",
        "transformedBullets": ["Primeiro ponto", "Segundo ponto"],
        "imagePrompt": "",
        "requiresImage": False,
    }]}
    captured = {}

    class FakeCompletions:
        async def create(self, **kwargs):
            captured.update(kwargs)
            message = SimpleNamespace(content=json.dumps(payload))
            return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    class FakeClient:
        def __init__(self, **kwargs):
            captured["client"] = kwargs
            self.chat = SimpleNamespace(completions=FakeCompletions())

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_DENSITY_MODEL", "gpt-test-density")
    monkeypatch.setattr("openai.AsyncOpenAI", FakeClient)

    result = await generate_visual_suggestions(
        title="Seguranca",
        text="Um texto extenso para transformar em uma leitura mais visual.",
        reasons=["muito texto"],
    )

    assert result[0]["type"] == "bullets"
    assert result[0]["transformedBullets"] == ["Primeiro ponto", "Segundo ponto"]
    assert captured["model"] == "gpt-test-density"
    assert captured["response_format"] == {"type": "json_object"}


@pytest.mark.asyncio
async def test_density_suggester_keeps_deterministic_fallback(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("EMERGENT_LLM_KEY", raising=False)

    result = await generate_visual_suggestions(
        text="Primeira frase com conteudo. Segunda frase importante. Terceira explicacao util.",
    )

    assert result
    assert {item["type"] for item in result} >= {"summarize", "bullets"}


@pytest.mark.asyncio
async def test_infographic_always_requires_image_and_gets_prompt(monkeypatch):
    payload = {"suggestions": [{
        "type": "infographic",
        "title": "Fluxo de seguranca",
        "description": "Representacao visual.",
        "transformedText": "Resumo",
        "transformedBullets": [],
        "imagePrompt": "",
        "requiresImage": False,
    }]}

    class FakeCompletions:
        async def create(self, **_kwargs):
            message = SimpleNamespace(content=json.dumps(payload))
            return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    class FakeClient:
        def __init__(self, **_kwargs):
            self.chat = SimpleNamespace(completions=FakeCompletions())

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr("openai.AsyncOpenAI", FakeClient)

    result = await generate_visual_suggestions(title="Seguranca", text="Conteudo")

    assert result[0]["type"] == "infographic"
    assert result[0]["requiresImage"] is True
    assert result[0]["imagePrompt"]
