"""Regression tests for Scenario Creator polling and OpenAI configuration."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from emergentintegrations.llm import chat as llm_chat  # noqa: E402
from routes import scenarios as scenario_routes  # noqa: E402
from services import scenario_service  # noqa: E402


SCENARIO_RESPONSE = {
    "title": "Gestão de conflitos",
    "description": "Uma simulação de mediação.",
    "context": "Equipe de tecnologia.",
    "characters": [],
    "learning_objectives": ["Praticar mediação"],
    "competencies_evaluated": ["Comunicação"],
    "nodes": [
        {
            "id": "node_1",
            "title": "Início",
            "narrative": "Duas pessoas discordam.",
            "choices": [],
        }
    ],
}


class FakeLlmChat:
    captured: dict = {}

    def __init__(self, api_key, session_id, system_message=""):
        self.captured.update(api_key=api_key, session_id=session_id)

    def with_model(self, provider, model):
        self.captured.update(provider=provider, model=model)
        return self

    def with_params(self, **params):
        self.captured["params"] = params
        return self

    async def send_message(self, message):
        self.captured["prompt"] = message.text
        return json.dumps(SCENARIO_RESPONSE, ensure_ascii=False)


@pytest.mark.asyncio
async def test_scenario_generation_uses_configured_openai_key(monkeypatch):
    FakeLlmChat.captured = {}
    monkeypatch.setattr(llm_chat, "LlmChat", FakeLlmChat)
    monkeypatch.setenv("OPENAI_API_KEY", "scenario-openai-key")
    monkeypatch.setenv("OPENAI_SCENARIO_MODEL", "scenario-test-model")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("EMERGENT_LLM_KEY", raising=False)

    result = await scenario_service.generate_scenario_with_ai(
        {
            "theme": "Gestão de conflitos",
            "objectives": "Praticar mediação",
            "audience": "Gestores",
            "industry": "Tecnologia",
            "complexity": "intermediate",
            "duration_minutes": 15,
            "language": "pt-BR",
        }
    )

    assert result["title"] == "Gestão de conflitos"
    assert result["nodes"][0]["id"] == "node_1"
    assert FakeLlmChat.captured["api_key"] == "scenario-openai-key"
    assert FakeLlmChat.captured["provider"] == "openai"
    assert FakeLlmChat.captured["model"] == "scenario-test-model"
    assert FakeLlmChat.captured["params"]["response_format"] == {
        "type": "json_object"
    }


class FakeCollection:
    def __init__(self, document):
        self.document = document

    async def find_one(self, _query, _projection=None):
        return dict(self.document) if self.document else None


class FakeDatabase:
    def __init__(self, task, scenario):
        self.generation_tasks = FakeCollection(task)
        self.scenarios = FakeCollection(scenario)


@pytest.mark.asyncio
async def test_completed_task_can_be_polled_repeatedly(monkeypatch):
    task = {
        "task_id": "task-1",
        "status": "completed",
        "scenario_id": "scenario-1",
        "user_id": "author-1",
    }
    scenario = {"id": "scenario-1", "title": "Cenário pronto", "nodes": []}
    monkeypatch.setattr(
        scenario_routes,
        "db",
        FakeDatabase(task=task, scenario=scenario),
    )
    user = {"user_id": "author-1", "role": "author"}

    first = await scenario_routes.get_generation_status("task-1", user=user)
    second = await scenario_routes.get_generation_status("task-1", user=user)

    assert first["status"] == "completed"
    assert first["scenario"]["id"] == "scenario-1"
    assert second == first


@pytest.mark.asyncio
async def test_failed_task_returns_real_actionable_error(monkeypatch):
    task = {
        "task_id": "task-2",
        "status": "failed",
        "scenario_id": None,
        "user_id": "author-1",
        "error": "EMERGENT_LLM_KEY not configured",
    }
    monkeypatch.setattr(
        scenario_routes,
        "db",
        FakeDatabase(task=task, scenario=None),
    )

    result = await scenario_routes.get_generation_status(
        "task-2",
        user={"user_id": "author-1", "role": "author"},
    )

    assert result["status"] == "failed"
    assert "chave OpenAI" in result["error"]
    assert "EMERGENT_LLM_KEY" not in result["error"]
