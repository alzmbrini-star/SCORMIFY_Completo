"""Tests for the storyboard-chat op application logic.

The conversational Storyboard editor receives free-form text, asks the LLM
to produce structured ops, then applies them atomically. These tests
validate the APPLICATION layer (not the LLM parsing) — i.e. given a list
of ops, does the endpoint mutate the session storyboard correctly?
"""
import pytest
import asyncio
from httpx import AsyncClient, ASGITransport
import os
import uuid as _uuid

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "scormify_test_storyboard_chat")
os.environ.setdefault("REACT_APP_BACKEND_URL", "http://localhost")
os.environ.setdefault("EMERGENT_LLM_KEY", "test-key")


async def _mock_llm_response(ops_to_emit):
    """Build a fake LLM JSON response producing the given ops."""
    import json as _json
    return "```json\n" + _json.dumps({
        "reply": f"Aplicando {len(ops_to_emit)} alteracoes.",
        "ops": ops_to_emit,
    }) + "\n```"


@pytest.mark.asyncio
async def test_chat_edit_narration_applies_atomically(monkeypatch):
    """User says 'mude a narracao do slide 2' → ops emit edit_narration →
    backend persists the change in db.agent_sessions."""
    from server import app as _wrapped
    app = getattr(_wrapped, 'inner', _wrapped)
    from routes.deps import db
    from routes.auth import require_auth

    # Mock auth
    async def _mock_auth():
        return {"user_id": "u1", "role": "super_admin"}
    app.dependency_overrides[require_auth] = _mock_auth

    # Mock the LLM call (LlmChat.send_message) to return a predictable JSON
    from emergentintegrations.llm import chat as llm_chat
    original_send = llm_chat.LlmChat.send_message

    async def _fake_send(self, msg):
        return await _mock_llm_response([
            {"type": "edit_narration", "index": 1, "narrationScript": "Nova narracao do slide 2"},
            {"type": "edit_title", "index": 0, "title": "Titulo Atualizado"},
        ])
    monkeypatch.setattr(llm_chat.LlmChat, "send_message", _fake_send)

    # Seed a session with a storyboard
    sid = f"test-chat-{_uuid.uuid4().hex[:8]}"
    await db.agent_sessions.delete_one({"id": sid})
    await db.agent_sessions.insert_one({
        "id": sid,
        "userId": "u1",
        "storyboard": {
            "slides": [
                {"id": "s0", "title": "Slide 1", "narrationScript": "narr1", "elements": []},
                {"id": "s1", "title": "Slide 2", "narrationScript": "narr2", "elements": []},
                {"id": "s2", "title": "Slide 3", "narrationScript": "narr3", "elements": []},
            ]
        },
    })

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.post(
                f"/api/agent/sessions/{sid}/storyboard-chat",
                json={"message": "mude o titulo do 1 e a narracao do 2", "history": []},
            )
            assert r.status_code == 200, r.text
            data = r.json()
            assert data["opsProposed"] == 2
            assert len(data["ops"]) == 2
            assert data["storyboard"]["slides"][0]["title"] == "Titulo Atualizado"
            assert data["storyboard"]["slides"][1]["narrationScript"] == "Nova narracao do slide 2"
            # Slide 3 untouched
            assert data["storyboard"]["slides"][2]["narrationScript"] == "narr3"

        # Verify persistence
        fresh = await db.agent_sessions.find_one({"id": sid})
        assert fresh["storyboard"]["slides"][1]["narrationScript"] == "Nova narracao do slide 2"
    finally:
        app.dependency_overrides.pop(require_auth, None)
        monkeypatch.setattr(llm_chat.LlmChat, "send_message", original_send)
        await db.agent_sessions.delete_one({"id": sid})


@pytest.mark.asyncio
async def test_chat_add_and_delete_slide(monkeypatch):
    from server import app as _wrapped
    app = getattr(_wrapped, 'inner', _wrapped)
    from routes.deps import db
    from routes.auth import require_auth

    async def _mock_auth():
        return {"user_id": "u1", "role": "super_admin"}
    app.dependency_overrides[require_auth] = _mock_auth

    from emergentintegrations.llm import chat as llm_chat

    async def _fake_send(self, msg):
        return await _mock_llm_response([
            {"type": "add_slide", "insertAfter": 0, "title": "Inserido", "narrationScript": "nova", "elements": []},
            {"type": "delete_slide", "index": 3},  # slide 3 becomes 3 after insert → we target original last
        ])
    monkeypatch.setattr(llm_chat.LlmChat, "send_message", _fake_send)

    sid = f"test-chat-{_uuid.uuid4().hex[:8]}"
    await db.agent_sessions.delete_one({"id": sid})
    await db.agent_sessions.insert_one({
        "id": sid,
        "userId": "u1",
        "storyboard": {
            "slides": [
                {"id": "s0", "title": "A", "elements": []},
                {"id": "s1", "title": "B", "elements": []},
                {"id": "s2", "title": "C", "elements": []},
            ]
        },
    })

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.post(
                f"/api/agent/sessions/{sid}/storyboard-chat",
                json={"message": "adicione um slide e remova o ultimo", "history": []},
            )
            assert r.status_code == 200, r.text
            data = r.json()
            slides = data["storyboard"]["slides"]
            # Started with 3, +1 added, -1 deleted = 3
            assert len(slides) == 3
            # Order: A, Inserido, B (C was deleted)
            assert slides[0]["title"] == "A"
            assert slides[1]["title"] == "Inserido"
            assert slides[2]["title"] == "B"
    finally:
        app.dependency_overrides.pop(require_auth, None)
        await db.agent_sessions.delete_one({"id": sid})


@pytest.mark.asyncio
async def test_chat_rejects_empty_message(monkeypatch):
    from server import app as _wrapped
    app = getattr(_wrapped, 'inner', _wrapped)
    from routes.auth import require_auth

    async def _mock_auth():
        return {"user_id": "u1", "role": "super_admin"}
    app.dependency_overrides[require_auth] = _mock_auth

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.post(
                "/api/agent/sessions/nonexistent/storyboard-chat",
                json={"message": "", "history": []},
            )
            assert r.status_code == 400
    finally:
        app.dependency_overrides.pop(require_auth, None)
