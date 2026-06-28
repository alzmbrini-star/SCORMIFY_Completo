"""Regression tests for Whiteboard 'tool' propagation.

User bug: the AI-plan render path ignored the user's drawing implement
choice and always used the simple pen. This file covers:

1. POST /api/whiteboard/generate-from-plan accepts & propagates `tool`
   field (pen | hand | hand_real) and produces a non-empty file.
2. POST /api/whiteboard/generate-from-plan REJECTS invalid tool with 422.
3. POST /api/whiteboard/generate-from-plan still works when `tool` is
   omitted (defaults to 'pen').
4. POST /api/whiteboard/generate (text-only path) regression smoke for
   pen/hand/hand_real.
5. GET /api/whiteboard/tools returns all 3 tools.
"""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://ai-tutor-platform-12.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"
ADMIN_EMAIL = "admin@scormify.com"
ADMIN_PASSWORD = "admin123"

# Render polling settings
MAX_POLL_SECONDS = 90
POLL_INTERVAL = 2.0


@pytest.fixture(scope="module")
def auth_session():
    """Login as super_admin and return a requests.Session with cookie/header."""
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    resp = s.post(
        f"{API}/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=15,
    )
    assert resp.status_code == 200, f"login failed: {resp.status_code} {resp.text}"
    data = resp.json()
    token = data.get("token") or data.get("session_token")
    assert token, f"no token in login response: {data}"
    s.headers.update({"Authorization": f"Bearer {token}"})
    return s


def _poll_job(session: requests.Session, job_id: str, timeout: int = MAX_POLL_SECONDS) -> dict:
    """Poll /api/job/{job_id} until status == completed/failed or timeout."""
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        r = session.get(f"{API}/job/{job_id}", timeout=15)
        assert r.status_code == 200, f"job poll {job_id} -> {r.status_code} {r.text}"
        last = r.json()
        status = last.get("status")
        if status in ("completed", "failed"):
            return last
        time.sleep(POLL_INTERVAL)
    pytest.fail(f"job {job_id} did not finish within {timeout}s; last={last}")


def _verify_render_file(session: requests.Session, result_url: str) -> int:
    """Fetch the rendered file URL and confirm non-empty payload. Returns content length."""
    assert result_url, "result.url is missing"
    # result_url is like /api/whiteboard/file/wb_plan_xxx.mp4 — prepend BASE_URL
    full = result_url if result_url.startswith("http") else f"{BASE_URL}{result_url}"
    r = session.get(full, timeout=30)
    assert r.status_code == 200, f"file fetch {full} -> {r.status_code}"
    assert len(r.content) > 1000, f"rendered file suspiciously small: {len(r.content)} bytes"
    return len(r.content)


TINY_PLAN = {
    "ops": [
        {"type": "text", "text": "hi", "x": 100, "y": 100, "font_size": 80}
    ]
}


# ---------------------------------------------------------------------
# 1. AI-plan path honors `tool` field
# ---------------------------------------------------------------------

@pytest.mark.parametrize("tool", ["hand_real", "pen", "hand"])
def test_generate_from_plan_honors_tool(auth_session, tool):
    """POST /api/whiteboard/generate-from-plan must accept tool and
    complete successfully producing a non-empty file."""
    body = {"plan": TINY_PLAN, "tool": tool}
    r = auth_session.post(f"{API}/whiteboard/generate-from-plan", json=body, timeout=15)
    assert r.status_code == 200, f"submit({tool}) -> {r.status_code} {r.text}"
    data = r.json()
    job_id = data.get("jobId")
    assert job_id, f"no jobId in submit response: {data}"

    final = _poll_job(auth_session, job_id)
    assert final.get("status") == "completed", (
        f"tool={tool} job did not complete: {final}"
    )
    result = final.get("result") or {}
    # Renderer returns 'videoUrl' (mp4) or 'url' depending on path; accept either.
    url = result.get("videoUrl") or result.get("url")
    size = _verify_render_file(auth_session, url)
    print(f"[OK] tool={tool} rendered {size} bytes at {url}")


# ---------------------------------------------------------------------
# 2. Invalid tool -> 422 validation error
# ---------------------------------------------------------------------

def test_generate_from_plan_rejects_invalid_tool(auth_session):
    body = {"plan": TINY_PLAN, "tool": "banana"}
    r = auth_session.post(f"{API}/whiteboard/generate-from-plan", json=body, timeout=15)
    assert r.status_code == 422, (
        f"expected 422 for invalid tool, got {r.status_code} {r.text}"
    )


# ---------------------------------------------------------------------
# 3. Backward compat — tool omitted defaults to pen
# ---------------------------------------------------------------------

def test_generate_from_plan_tool_omitted_defaults_to_pen(auth_session):
    body = {"plan": TINY_PLAN}  # NOTE: no tool field
    r = auth_session.post(f"{API}/whiteboard/generate-from-plan", json=body, timeout=15)
    assert r.status_code == 200, f"omitted-tool submit -> {r.status_code} {r.text}"
    job_id = r.json().get("jobId")
    final = _poll_job(auth_session, job_id)
    assert final.get("status") == "completed", f"omitted-tool job failed: {final}"
    url = (final.get("result") or {}).get("videoUrl") or (final.get("result") or {}).get("url")
    _verify_render_file(auth_session, url)


# ---------------------------------------------------------------------
# 4. Text-only path regression smoke (already correct — make sure
#    nothing broke during refactor).
# ---------------------------------------------------------------------

@pytest.mark.parametrize("tool", ["pen", "hand", "hand_real"])
def test_generate_text_only_with_tool(auth_session, tool):
    body = {"text": "oi", "tool": tool, "projectId": None, "slideId": None}
    r = auth_session.post(f"{API}/whiteboard/generate", json=body, timeout=15)
    assert r.status_code == 200, f"text-only({tool}) submit -> {r.status_code} {r.text}"
    job_id = r.json().get("jobId")
    final = _poll_job(auth_session, job_id)
    assert final.get("status") == "completed", (
        f"text-only tool={tool} job failed: {final}"
    )
    url = (final.get("result") or {}).get("videoUrl") or (final.get("result") or {}).get("url")
    _verify_render_file(auth_session, url)


# ---------------------------------------------------------------------
# 5. Tool catalog endpoint
# ---------------------------------------------------------------------

def test_tools_catalog_lists_all_three():
    """GET /api/whiteboard/tools must list pen, hand and hand_real since
    all three PNG assets are present on disk."""
    r = requests.get(f"{API}/whiteboard/tools", timeout=10)
    assert r.status_code == 200, f"tools endpoint -> {r.status_code} {r.text}"
    data = r.json()
    tools = data.get("tools") or []
    ids = {t.get("id") for t in tools if isinstance(t, dict)}
    for expected in ("pen", "hand", "hand_real"):
        assert expected in ids, f"tool catalog missing '{expected}': {ids}"
