"""Regression: PUT /api/projects/{id} must return a lightweight ack, NOT
the full project document.

Bug context (2026-04-29 user report): toggling `singlePageMode` in production
returned 502 Bad Gateway. Root cause: the endpoint returned the full project
via `get_project_by_id(...)` — for projects with many slides + inlined media
the response JSON could exceed several MB, hitting the proxy/timeout limits.
The frontend already re-fetches the project via GET after toggle, so the
fat response is wasted bandwidth too.
"""
import asyncio
from fastapi.testclient import TestClient


def test_put_project_returns_lightweight_ack(monkeypatch):
    """The PUT endpoint must return only `{success, id, updated}` — never
    the full project document.

    We import the route directly and inspect the function signature/body.
    """
    from routes import projects_crud
    src = open(projects_crud.__file__).read()
    # The implementation should return the lightweight ack
    assert 'return {"success": True, "id": project_id, "updated": list(update_data.keys())}' in src
    # And must NOT call get_project_by_id at the end of update_project_endpoint
    # (we do the substring check on the body of the function specifically)
    func_source = src.split("async def update_project_endpoint(")[1].split("@router")[0]
    assert "get_project_by_id" not in func_source


def test_put_project_endpoint_runs_quickly(monkeypatch):
    """End-to-end smoke: simulate a PUT call and ensure response is small.
    Uses a TestClient with FastAPI app + mocked db.
    """
    # Stub deps so we don't need MongoDB
    async def _fake_load(pid, user):
        return {"id": pid, "name": "x", "companyId": "c1", "course": {"slides": []}}

    async def _fake_update(pid, data):
        return None

    from routes import projects_crud
    monkeypatch.setattr(projects_crud, "load_authorized_project", _fake_load)
    monkeypatch.setattr(projects_crud, "update_project", _fake_update)
    monkeypatch.setattr(projects_crud, "require_auth",
                          lambda: {"id": "u1", "email": "x@x.com"})

    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(projects_crud.router, prefix="/api")
    # Bypass auth for this test
    from routes.auth import require_auth as real_auth
    app.dependency_overrides[real_auth] = lambda: {"id": "u1", "email": "x@x.com", "companyId": "c1"}

    client = TestClient(app)
    resp = client.put("/api/projects/test-id", json={"singlePageMode": True})
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"success": True, "id": "test-id", "updated": ["singlePageMode"]}
    # Lightweight: response payload must be tiny (< 200 bytes)
    assert len(resp.content) < 200
