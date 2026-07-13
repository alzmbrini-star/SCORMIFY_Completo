"""
Tests for the "Reopen course from AI Agent" feature.

Validates:
  - POST /agent/sessions/{id}/analyze cache vs ?force=1
  - POST /agent/sessions/{id}/generate-structure cache vs body {force:true}
  - POST /agent/sessions/{id}/generate-storyboard cache vs ?force=1
  - POST /agent/sessions/{id}/generate-course cache vs body {mode:'new'|'replace'}
  - GET  /agent/sessions/by-project/{project_id}

We create a synthetic agent_session in Mongo with step='generated' plus all
required cached fields, so the endpoints return cached payloads immediately
without touching the LLM. When we send `force` we only validate the initial
contract switch (status: processing / no already_done). Background threads may
fail afterwards, but that is fine — we roll the step back at teardown so no
real generation happens.
"""

import os
import uuid
import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # Fallback to frontend env file for direct pytest runs
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL"):
                    BASE_URL = line.split("=", 1)[1].strip().strip('"').rstrip("/")
                    break
    except Exception:
        pass

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def db():
    client = MongoClient(MONGO_URL)
    yield client[DB_NAME]
    client.close()


@pytest.fixture()
def fake_session(db):
    """Insert a synthetic fully-generated session, remove it at teardown."""
    sid = f"TEST_sess_{uuid.uuid4().hex[:8]}"
    pid = f"TEST_proj_{uuid.uuid4().hex[:8]}"
    doc = {
        "id": sid,
        "step": "generated",
        "contentText": "Conteudo de teste sintetico para reopen wizard.",
        "fileName": "test.txt",
        "analysis": {
            "title": "Curso Teste Reopen",
            "summary": "Resumo teste",
            "objectives": ["Obj 1"],
            "topics": ["Topico A"],
        },
        "config": {"title": "Curso Teste Reopen", "description": "d", "duration": 30},
        "structure": {"modules": [{"title": "M1", "slides": []}]},
        "storyboard": {"slides": [{"title": "S1", "content": "c"}]},
        "mediaConfig": {},
        "bgConfig": {},
        "projectId": pid,
        "createdAt": "2026-01-01T00:00:00+00:00",
        "updatedAt": "2026-01-01T00:00:00+00:00",
    }
    db.agent_sessions.insert_one(doc)

    # Also insert a fake project so by-project lookup can be verified
    project_doc = {
        "id": pid,
        "name": "Curso Teste Reopen",
        "createdByAgent": True,
        "agentSessionId": sid,
        "status": "ready",
    }
    db.projects.insert_one(project_doc)

    yield {"session_id": sid, "project_id": pid}

    # Cleanup — also revert step in case a force test flipped it into processing
    db.agent_sessions.delete_one({"id": sid})
    db.projects.delete_one({"id": pid})


def _reset_step_to_generated(db, sid):
    """Force-tests flip step to *ing (analyzing/structuring/...). Roll back
    so the session remains fully cached for the subsequent assertions.
    """
    db.agent_sessions.update_one(
        {"id": sid},
        {"$set": {"step": "generated"}},
    )


# ---------------------------------------------------------------------------
# analyze
# ---------------------------------------------------------------------------

class TestAgentAnalyzeCacheForce:

    def test_analyze_cache_returns_analysis(self, fake_session):
        sid = fake_session["session_id"]
        r = requests.post(f"{BASE_URL}/api/agent/sessions/{sid}/analyze", timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        # Cached: analysis object returned (title = "Curso Teste Reopen")
        assert data.get("title") == "Curso Teste Reopen"
        # NOT a processing/error shell
        assert data.get("status") != "processing"

    def test_analyze_force_returns_processing(self, fake_session, db):
        sid = fake_session["session_id"]
        r = requests.post(
            f"{BASE_URL}/api/agent/sessions/{sid}/analyze?force=1", timeout=15
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("status") == "processing", data
        _reset_step_to_generated(db, sid)


# ---------------------------------------------------------------------------
# generate-structure
# ---------------------------------------------------------------------------

class TestAgentGenerateStructureCacheForce:

    def test_structure_cache(self, fake_session):
        sid = fake_session["session_id"]
        r = requests.post(
            f"{BASE_URL}/api/agent/sessions/{sid}/generate-structure",
            json={},
            timeout=15,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        # Cache = structure returned (has 'modules' key)
        assert "modules" in data, data
        assert data.get("status") != "processing"

    def test_structure_force(self, fake_session, db):
        sid = fake_session["session_id"]
        r = requests.post(
            f"{BASE_URL}/api/agent/sessions/{sid}/generate-structure",
            json={"force": True},
            timeout=15,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("status") == "processing", data
        _reset_step_to_generated(db, sid)


# ---------------------------------------------------------------------------
# generate-storyboard
# ---------------------------------------------------------------------------

class TestAgentGenerateStoryboardCacheForce:

    def test_storyboard_cache_already_done(self, fake_session):
        sid = fake_session["session_id"]
        r = requests.post(
            f"{BASE_URL}/api/agent/sessions/{sid}/generate-storyboard", timeout=15
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("status") == "already_done", data

    def test_storyboard_force(self, fake_session, db):
        sid = fake_session["session_id"]
        r = requests.post(
            f"{BASE_URL}/api/agent/sessions/{sid}/generate-storyboard?force=1",
            timeout=15,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("status") == "processing", data
        _reset_step_to_generated(db, sid)


# ---------------------------------------------------------------------------
# generate-course
# ---------------------------------------------------------------------------

class TestAgentGenerateCourseModes:

    def test_course_cache_already_done(self, fake_session):
        sid = fake_session["session_id"]
        pid = fake_session["project_id"]
        # No body/mode: session already generated → already_done
        r = requests.post(
            f"{BASE_URL}/api/agent/sessions/{sid}/generate-course", timeout=15
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("status") == "already_done", data
        assert data.get("projectId") == pid

    def test_course_mode_new_starts_processing(self, fake_session, db):
        sid = fake_session["session_id"]
        r = requests.post(
            f"{BASE_URL}/api/agent/sessions/{sid}/generate-course",
            json={"mode": "new"},
            timeout=15,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        # Must NOT be already_done (a new generation was started/queued)
        assert data.get("status") != "already_done", data
        # Should indicate processing has started (background thread kicked off)
        # Even if it errors later in background, the initial contract is what
        # we're validating here.
        assert data.get("status") in ("processing", None) or "message" in data, data
        _reset_step_to_generated(db, sid)


# ---------------------------------------------------------------------------
# GET /agent/sessions/by-project/{project_id}
# ---------------------------------------------------------------------------

class TestAgentSessionByProject:

    def test_by_project_returns_session(self, fake_session):
        pid = fake_session["project_id"]
        sid = fake_session["session_id"]
        r = requests.get(
            f"{BASE_URL}/api/agent/sessions/by-project/{pid}", timeout=15
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("id") == sid
        assert data.get("projectId") == pid
        assert data.get("step") == "generated"
        # contentText is intentionally excluded from this endpoint for size
        assert "contentText" not in data

    def test_by_project_404_when_missing(self):
        r = requests.get(
            f"{BASE_URL}/api/agent/sessions/by-project/nonexistent_TEST_xxxx",
            timeout=15,
        )
        assert r.status_code == 404
