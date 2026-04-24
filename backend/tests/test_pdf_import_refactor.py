"""Tests for the PDF import routes refactored from routes/agent.py to routes/pdf_import.py.

Validates:
  1) The refactored routes are still registered and respond with correct contracts.
  2) Non-moved agent endpoints still work (smoke test regression).
  3) Auth works; project listing works; agent session create/analyze still works.
"""
import io
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
SUPER_ADMIN_EMAIL = "admin@scormify.com"
SUPER_ADMIN_PASSWORD = "admin123"


# ---------- Fixtures ----------
@pytest.fixture(scope="module")
def api():
    s = requests.Session()
    return s


@pytest.fixture(scope="module")
def token(api):
    r = api.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": SUPER_ADMIN_EMAIL, "password": SUPER_ADMIN_PASSWORD},
        timeout=15,
    )
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:300]}"
    data = r.json()
    tok = data.get("access_token") or data.get("token") or (data.get("data") or {}).get("access_token")
    assert tok, f"no token in login response: {data}"
    return tok


@pytest.fixture(scope="module")
def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def agent_session(api, auth_headers):
    """Create a fresh agent session used by PDF-related tests."""
    # Try a couple of known payload shapes defensively
    payloads = [
        {"name": f"TEST_pdf_refactor_{uuid.uuid4().hex[:8]}"},
        {"title": f"TEST_pdf_refactor_{uuid.uuid4().hex[:8]}"},
        {},
    ]
    last = None
    for p in payloads:
        r = api.post(f"{BASE_URL}/api/agent/sessions", json=p, headers=auth_headers, timeout=15)
        last = r
        if r.status_code in (200, 201):
            d = r.json()
            sid = d.get("id") or d.get("sessionId") or (d.get("session") or {}).get("id")
            if sid:
                return {"id": sid, "raw": d}
    pytest.skip(f"Could not create agent session: {last.status_code} {last.text[:300]}")


# ---------- Smoke: auth ----------
def test_login_smoke(token):
    assert isinstance(token, str) and len(token) > 10


# ---------- Smoke: projects listing ----------
def test_projects_list(api, auth_headers):
    r = api.get(f"{BASE_URL}/api/projects", headers=auth_headers, timeout=15)
    assert r.status_code == 200, r.text[:300]
    body = r.json()
    # Should be a list or paginated object
    assert isinstance(body, (list, dict))


# ---------- Smoke: agent session create ----------
def test_agent_session_create(agent_session):
    assert agent_session["id"]


# ---------- Smoke: agent session analyze (not moved, stays in routes/agent.py) ----------
def test_agent_session_analyze_registered(api, auth_headers, agent_session):
    """analyze endpoint should be registered; we just check it doesn't 404 on route.
    An empty body may return 400/422, which is acceptable — means route exists.
    """
    sid = agent_session["id"]
    r = api.post(
        f"{BASE_URL}/api/agent/sessions/{sid}/analyze",
        json={},
        headers=auth_headers,
        timeout=30,
    )
    # Anything except 404 proves the route is still wired.
    assert r.status_code != 404, f"analyze route missing: {r.status_code} {r.text[:300]}"
    assert r.status_code != 405


# ---------- Refactored: pdf-preview GET on fresh session => hasPdf: false ----------
def test_pdf_preview_empty_session(api, auth_headers, agent_session):
    sid = agent_session["id"]
    r = api.get(
        f"{BASE_URL}/api/agent/sessions/{sid}/pdf-preview",
        headers=auth_headers,
        timeout=15,
    )
    assert r.status_code == 200, r.text[:300]
    body = r.json()
    # Fresh session has no PDF yet — contract says hasPdf: false
    assert body.get("hasPdf") is False, f"expected hasPdf=false, got {body}"


# ---------- Refactored: pdf-preview GET 404 on non-existent session ----------
def test_pdf_preview_unknown_session(api, auth_headers):
    sid = f"nonexistent-{uuid.uuid4().hex}"
    r = api.get(
        f"{BASE_URL}/api/agent/sessions/{sid}/pdf-preview",
        headers=auth_headers,
        timeout=15,
    )
    assert r.status_code == 404


# ---------- Refactored: generate-faithful-course => 400 without rawFileGridFS ----------
def test_generate_faithful_course_no_pdf(api, auth_headers, agent_session):
    sid = agent_session["id"]
    r = api.post(
        f"{BASE_URL}/api/agent/sessions/{sid}/generate-faithful-course",
        json={},
        headers=auth_headers,
        timeout=15,
    )
    # Must be 400 (PDF not available) — not 500, not NoneType errors
    assert r.status_code == 400, f"expected 400, got {r.status_code} {r.text[:400]}"
    body = r.json()
    detail = str(body.get("detail", "")).lower()
    assert "pdf" in detail or "reenvie" in detail or "disponivel" in detail or "disponível" in detail


# ---------- Refactored: generate-faithful-course 404 for unknown session ----------
def test_generate_faithful_course_unknown_session(api, auth_headers):
    sid = f"nonexistent-{uuid.uuid4().hex}"
    r = api.post(
        f"{BASE_URL}/api/agent/sessions/{sid}/generate-faithful-course",
        json={},
        headers=auth_headers,
        timeout=15,
    )
    assert r.status_code == 404


# ---------- Refactored: faithful-status 404 for non-existent project ----------
def test_faithful_status_unknown_project(api, auth_headers):
    pid = f"nonexistent-{uuid.uuid4().hex}"
    r = api.get(
        f"{BASE_URL}/api/projects/{pid}/faithful-status",
        headers=auth_headers,
        timeout=15,
    )
    assert r.status_code == 404, f"expected 404, got {r.status_code} {r.text[:300]}"


# ---------- Refactored: repair-pdf-images 404 for non-existent project ----------
def test_repair_pdf_images_unknown_project(api, auth_headers):
    pid = f"nonexistent-{uuid.uuid4().hex}"
    r = api.post(
        f"{BASE_URL}/api/projects/{pid}/repair-pdf-images",
        headers=auth_headers,
        timeout=15,
    )
    assert r.status_code == 404


# ---------- Refactored: upload-chunk — route registered, 404 on unknown session ----------
def test_upload_chunk_unknown_session(api, auth_headers):
    sid = f"nonexistent-{uuid.uuid4().hex}"
    upload_id = uuid.uuid4().hex
    # Minimal fake chunk (not a real PDF — we only need to hit the route)
    files = {"chunk": ("chunk_0", io.BytesIO(b"%PDF-1.4 fake"), "application/octet-stream")}
    form = {
        "uploadId": upload_id,
        "chunkIndex": "0",
        "totalChunks": "2",
        "fileName": "test.pdf",
    }
    r = api.post(
        f"{BASE_URL}/api/agent/sessions/{sid}/upload-chunk",
        files=files,
        data=form,
        headers=auth_headers,
        timeout=30,
    )
    # Must be 404 session-not-found — proves the route is registered and parses inputs
    assert r.status_code == 404, f"expected 404, got {r.status_code} {r.text[:400]}"


# ---------- Refactored: upload-chunk — single-chunk flow on valid session returns chunk_received ----------
def test_upload_chunk_first_chunk_valid_session(api, auth_headers, agent_session):
    sid = agent_session["id"]
    upload_id = uuid.uuid4().hex
    fake_pdf = b"%PDF-1.4\n%fake-content-for-route-test\n"
    files = {"chunk": ("chunk_0", io.BytesIO(fake_pdf), "application/octet-stream")}
    form = {
        "uploadId": upload_id,
        "chunkIndex": "0",
        "totalChunks": "2",  # 2 so the server returns "chunk_received" (not final assembly)
        "fileName": "TEST_refactor.pdf",
    }
    r = api.post(
        f"{BASE_URL}/api/agent/sessions/{sid}/upload-chunk",
        files=files,
        data=form,
        headers=auth_headers,
        timeout=30,
    )
    assert r.status_code == 200, f"expected 200, got {r.status_code} {r.text[:400]}"
    body = r.json()
    assert body.get("status") == "chunk_received"
    assert body.get("received") == 1
    assert body.get("total") == 2
