"""Precision regressions for AI + Shapes semantic geometry."""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from emergentintegrations.llm import chat as llm_chat  # noqa: E402
from services import whiteboard_ai_plan  # noqa: E402
from services.whiteboard_ai_plan import (  # noqa: E402
    ARROW_GAP,
    _point_in_shape,
    _text_aabb,
    generate_render_plan,
    prepare_render_plan,
)


def _semantic_plan():
    return {
        "summary": "Fluxo preciso",
        "ops": [
            {
                "id": "texto_origem",
                "type": "text",
                "text": "Diagnóstico",
                "x": 170,
                "y": 300,
                "font_size": 64,
                "container_id": "caixa_origem",
            },
            {
                "id": "caixa_origem",
                "type": "rectangle",
                "x": 140,
                "y": 250,
                "w": 440,
                "h": 160,
                "width": 6,
            },
            {
                "id": "texto_destino",
                "type": "text",
                "text": "Ação",
                "x": 1340,
                "y": 300,
                "font_size": 64,
                "container_id": "caixa_destino",
            },
            {
                "id": "caixa_destino",
                "type": "rectangle",
                "x": 1300,
                "y": 250,
                "w": 440,
                "h": 160,
                "width": 6,
            },
            {
                "id": "seta_fluxo",
                "type": "arrow",
                "x1": 0,
                "y1": 0,
                "x2": 1,
                "y2": 1,
                "from_id": "caixa_origem",
                "to_id": "caixa_destino",
                "width": 7,
            },
            {
                "id": "sublinhado_destino",
                "type": "underline",
                "x1": 0,
                "y1": 0,
                "x2": 1,
                "target_id": "texto_destino",
                "width": 5,
            },
        ],
    }


def test_semantic_links_drive_exact_geometry():
    result = prepare_render_plan(_semantic_plan())
    by_id = {op["id"]: op for op in result["ops"]}

    origin = by_id["caixa_origem"]
    destination = by_id["caixa_destino"]
    arrow = by_id["seta_fluxo"]
    underline = by_id["sublinhado_destino"]
    destination_text = by_id["texto_destino"]

    assert arrow["x1"] < arrow["x2"]
    assert not _point_in_shape(
        (arrow["x1"], arrow["y1"]), origin, ARROW_GAP - 2
    )
    assert not _point_in_shape(
        (arrow["x2"], arrow["y2"]), destination, ARROW_GAP - 2
    )

    text_x0, _, text_x1, text_y1 = _text_aabb(destination_text)
    assert abs(underline["x1"] - text_x0) <= 2
    assert abs(underline["x2"] - text_x1) <= 2
    assert 8 <= underline["y1"] - text_y1 <= 12
    assert result["quality"]["score"] >= 88


def test_linked_text_uses_named_container_even_when_initially_far_away():
    plan = _semantic_plan()
    plan["ops"][0]["x"] = 900
    plan["ops"][0]["y"] = 800
    result = prepare_render_plan(plan)
    by_id = {op["id"]: op for op in result["ops"]}
    text = by_id["texto_origem"]
    shape = by_id["caixa_origem"]
    x0, y0, x1, y1 = _text_aabb(text)

    assert shape["x"] <= x0 <= x1 <= shape["x"] + shape["w"]
    assert shape["y"] <= y0 <= y1 <= shape["y"] + shape["h"]


class FakeLlmChat:
    captured: dict = {}

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
        import json

        return json.dumps(_semantic_plan())


@pytest.mark.asyncio
async def test_ai_plan_prefers_openai_and_requests_json(monkeypatch):
    captured = {}

    async def fake_openai_plan(**kwargs):
        captured.update(kwargs)
        import json
        return json.dumps(_semantic_plan())

    monkeypatch.setattr(
        whiteboard_ai_plan,
        "_request_openai_plan",
        fake_openai_plan,
    )
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    monkeypatch.setenv("OPENAI_WHITEBOARD_MODEL", "gpt-test-whiteboard")
    monkeypatch.delenv("EMERGENT_LLM_KEY", raising=False)

    result = await generate_render_plan("Conecte diagnóstico a ação")

    assert captured["api_key"] == "test-openai-key"
    assert captured["model"] == "gpt-test-whiteboard"
    assert "Conecte diagn" in captured["user_message"]
    assert result["quality"]["score"] >= 88


@pytest.mark.asyncio
async def test_openai_plan_uses_bounded_official_json_request(monkeypatch):
    import openai

    captured = {}

    class FakeCompletions:
        async def create(self, **kwargs):
            captured["request"] = kwargs
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content='{"ops": []}'))]
            )

    class FakeAsyncOpenAI:
        def __init__(self, **kwargs):
            captured["client"] = kwargs
            self.chat = SimpleNamespace(completions=FakeCompletions())

    monkeypatch.setattr(openai, "AsyncOpenAI", FakeAsyncOpenAI)
    result = await whiteboard_ai_plan._request_openai_plan(
        api_key="secret-test-key",
        model="gpt-test-whiteboard",
        user_message="Crie um fluxo",
        timeout_seconds=30,
    )

    assert result == '{"ops": []}'
    assert captured["client"]["timeout"] == 30
    assert captured["client"]["max_retries"] == 2
    assert captured["request"]["response_format"] == {"type": "json_object"}
    assert captured["request"]["messages"][1]["content"] == "Crie um fluxo"
