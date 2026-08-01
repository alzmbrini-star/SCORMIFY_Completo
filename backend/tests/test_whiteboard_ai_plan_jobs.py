"""Regression tests for timeout-safe Whiteboard AI plan generation."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from routes import whiteboard as whiteboard_routes  # noqa: E402
from services import whiteboard_ai_plan  # noqa: E402


@pytest.mark.asyncio
async def test_ai_plan_background_job_completes(monkeypatch):
    plan = {
        "summary": "Plano pronto",
        "ops": [{"id": "title", "type": "text", "text": "Olá", "x": 200, "y": 200}],
    }

    async def fake_generate(*args, **kwargs):
        return plan

    updates = []

    async def fake_update(job_id, values):
        updates.append((job_id, values))

    monkeypatch.setattr(whiteboard_ai_plan, "generate_render_plan", fake_generate)
    monkeypatch.setattr(whiteboard_routes, "update_job", fake_update)

    payload = whiteboard_routes.WhiteboardPlanRequest(description="Escreva Olá")
    await whiteboard_routes._run_whiteboard_plan_generation_job("job-1", payload)

    assert updates[-1][0] == "job-1"
    assert updates[-1][1]["status"] == "completed"
    assert updates[-1][1]["result"] == plan


@pytest.mark.asyncio
async def test_ai_plan_background_job_surfaces_timeout(monkeypatch):
    async def fake_generate(*args, **kwargs):
        raise RuntimeError("tempo limite da IA excedido (90s)")

    updates = []

    async def fake_update(job_id, values):
        updates.append(values)

    monkeypatch.setattr(whiteboard_ai_plan, "generate_render_plan", fake_generate)
    monkeypatch.setattr(whiteboard_routes, "update_job", fake_update)

    payload = whiteboard_routes.WhiteboardPlanRequest(description="Desenhe um fluxo")
    await whiteboard_routes._run_whiteboard_plan_generation_job("job-2", payload)

    assert updates[-1]["status"] == "failed"
    assert "Tempo limite" in updates[-1]["message"]


def test_ai_plan_timeout_configuration_is_bounded(monkeypatch):
    monkeypatch.setenv("WHITEBOARD_AI_PLAN_TIMEOUT_SECONDS", "9999")
    assert whiteboard_ai_plan._ai_plan_timeout_seconds() == 240.0

    monkeypatch.setenv("WHITEBOARD_AI_PLAN_TIMEOUT_SECONDS", "invalid")
    assert whiteboard_ai_plan._ai_plan_timeout_seconds() == 90.0
