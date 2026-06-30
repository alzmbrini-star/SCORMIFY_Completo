"""
Iteration 130 — Verify export.py stamps projectId + companyId into tutorConfig
so feedback POSTs from exported courses can be joined back to the project
in /api/admin/tutor-dashboard.

Bug RCA: Before the fix, tutor_settings dict in routes/export.py was built
WITHOUT projectId/companyId. The exporter then propagated empty strings into
the HTML/SCORM, so /api/tutor/feedback received projectId='' and could never
be joined back to a course by the admin dashboard.
"""
import os
import re
import time
import zipfile
import io
import json
import requests
import pytest

def _load_base_url():
    val = os.environ.get("REACT_APP_BACKEND_URL", "").strip()
    if not val:
        try:
            with open("/app/frontend/.env") as f:
                for line in f:
                    if line.startswith("REACT_APP_BACKEND_URL="):
                        val = line.split("=", 1)[1].strip().strip('"').strip("'")
                        break
        except Exception:
            pass
    return val.rstrip("/")

BASE_URL = _load_base_url()
ADMIN_EMAIL = "admin@scormify.com"
ADMIN_PASS = "admin123"
PROJECT_ID = "d550fe43-f65a-40dc-b101-adf77befd7b3"
EXPECTED_COMPANY = "company_didaxis001"


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASS},
        timeout=30,
    )
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text[:200]}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def auth_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


def _poll_job(job_id, headers, timeout=300):
    """Poll a job until completed or failed; returns the result dict."""
    deadline = time.time() + timeout
    last_status = None
    while time.time() < deadline:
        r = requests.get(f"{BASE_URL}/api/job/{job_id}", headers=headers, timeout=30)
        if r.status_code != 200:
            time.sleep(2)
            continue
        data = r.json()
        last_status = data
        if data.get("status") == "completed":
            return data
        if data.get("status") == "failed":
            pytest.fail(f"Job failed: {data.get('message')}")
        time.sleep(3)
    pytest.fail(f"Job timeout. Last status: {last_status}")


# --- Tutor settings enabled check
def test_tutor_settings_enabled(auth_headers):
    """Ensure tutor is enabled in admin settings so exports embed tutorConfig."""
    r = requests.get(f"{BASE_URL}/api/admin/settings/tutor", headers=auth_headers, timeout=30)
    # 404 acceptable if no settings doc exists yet; in that case we cannot
    # verify embedded tutorConfig (it won't be embedded by exporter).
    if r.status_code == 200:
        data = r.json()
        if not data.get("enabled"):
            pytest.skip("Tutor settings disabled — exporter will skip tutorConfig block.")
    else:
        pytest.skip(f"Tutor settings endpoint returned {r.status_code}; cannot determine state.")


# --- HTML export carries projectId + companyId
def test_html_export_stamps_project_and_company_ids(auth_headers):
    r = requests.post(
        f"{BASE_URL}/api/course/{PROJECT_ID}/export-html",
        headers=auth_headers,
        json={"singlePage": False},
        timeout=60,
    )
    assert r.status_code == 200, f"Export init failed: {r.status_code} {r.text[:300]}"
    job_id = r.json()["jobId"]

    job = _poll_job(job_id, auth_headers, timeout=420)
    result = job.get("result") or {}
    download_url = result.get("downloadUrl") or result.get("url")
    assert download_url, f"No downloadUrl in result: {result}"

    full_url = download_url if download_url.startswith("http") else f"{BASE_URL}{download_url}"
    dl = requests.get(full_url, headers=auth_headers, timeout=180)
    assert dl.status_code == 200, f"Download failed: {dl.status_code}"
    html = dl.text

    # Validate by searching the full HTML for both fields — the inlined
    # tutorConfig JSON contains course HTML content (with braces), so a
    # naive non-greedy regex truncates the block. Simple substring check
    # is enough to confirm the stamping (the only place these fields appear
    # in the export is the tutorConfig JSON literal).
    assert f'"projectId": "{PROJECT_ID}"' in html, \
        f"projectId not stamped in exported HTML. Project={PROJECT_ID}"
    assert f'"companyId": "{EXPECTED_COMPANY}"' in html, \
        f"companyId not stamped in exported HTML. Expected={EXPECTED_COMPANY}"

    # Find a tutorConfig block (var tutorConfig = {...};)
    m = re.search(r"var\s+tutorConfig\s*=\s*(\{.*?\})\s*;", html, re.DOTALL)
    if not m:
        # tutor may be disabled — graceful skip
        if "AiTutor.init" not in html:
            pytest.skip("Tutor not embedded in exported HTML (tutor settings disabled).")
        pytest.fail("AiTutor.init present but tutorConfig var not found")

    cfg_text = m.group(1)
    # Validate apiUrl non-empty (within first ~1KB of tutorConfig)
    api_match = re.search(r'"apiUrl"\s*:\s*"([^"]*)"', cfg_text)
    assert api_match and api_match.group(1).startswith("http"), \
        f"apiUrl missing or empty: {api_match.group(1) if api_match else 'NONE'}"


# --- SCORM export carries projectId + companyId
def test_scorm_export_stamps_project_and_company_ids(auth_headers):
    r = requests.post(
        f"{BASE_URL}/api/course/{PROJECT_ID}/export-scorm",
        headers=auth_headers,
        json={"singlePage": False},
        timeout=60,
    )
    assert r.status_code == 200, f"SCORM init failed: {r.status_code} {r.text[:300]}"
    job_id = r.json()["jobId"]
    job = _poll_job(job_id, auth_headers, timeout=480)
    result = job.get("result") or {}
    download_url = result.get("downloadUrl") or result.get("url")
    assert download_url, f"No downloadUrl: {result}"

    full_url = download_url if download_url.startswith("http") else f"{BASE_URL}{download_url}"
    dl = requests.get(full_url, headers=auth_headers, timeout=300, stream=True)
    assert dl.status_code == 200, f"Download failed: {dl.status_code}"

    buf = io.BytesIO(dl.content)
    with zipfile.ZipFile(buf) as zf:
        all_names = zf.namelist()
        # Search for player.js or index.html or any js carrying tutorConfig
        candidates = [n for n in all_names if n.endswith((".html", ".js"))]
        found_pid = False
        found_cid = False
        for name in candidates:
            try:
                content = zf.read(name).decode("utf-8", errors="ignore")
            except Exception:
                continue
            if PROJECT_ID in content and "tutorConfig" in content:
                found_pid = True
            if EXPECTED_COMPANY in content and "tutorConfig" in content:
                found_cid = True
            if found_pid and found_cid:
                break
        # If tutor not embedded at all, skip
        if not any("AiTutor" in zf.read(n).decode("utf-8", errors="ignore")
                   for n in candidates if n.endswith(".js"))[:1] if False else True:
            pass  # tolerate; just assert what we found
        assert found_pid, f"projectId '{PROJECT_ID}' not in any js/html with tutorConfig. Files: {candidates[:10]}"
        assert found_cid, f"companyId '{EXPECTED_COMPANY}' not in any js/html with tutorConfig."


# --- /api/tutor/feedback validation regression
def test_feedback_validation_missing_fields():
    r = requests.post(
        f"{BASE_URL}/api/tutor/feedback",
        json={},
        timeout=15,
    )
    assert r.status_code in (400, 422), f"Expected 4xx on empty body, got {r.status_code}: {r.text[:200]}"


# --- End-to-end: POST feedback with real projectId, then verify admin dashboard join
def test_e2e_feedback_to_admin_dashboard_join(auth_headers):
    msg_id = f"e2e-test-{int(time.time())}"
    sess_id = f"ftest-{int(time.time())}"
    payload = {
        "projectId": PROJECT_ID,
        "companyId": EXPECTED_COMPANY,
        "sessionId": sess_id,
        "messageId": msg_id,
        "rating": "up",
        "messageText": "Test message for iter130",
        "userQuestion": "Test question",
    }
    r = requests.post(f"{BASE_URL}/api/tutor/feedback", json=payload, timeout=20)
    assert r.status_code == 200, f"Feedback POST failed: {r.status_code} {r.text[:300]}"

    # Hit admin dashboard
    time.sleep(2)
    r2 = requests.get(f"{BASE_URL}/api/admin/tutor-dashboard", headers=auth_headers, timeout=30)
    assert r2.status_code == 200, f"Admin dashboard failed: {r2.status_code}"
    data = r2.json()

    # Walk response to find the matching project
    matched = None
    candidates = []
    if isinstance(data, dict):
        for key in ("courses", "projects", "items", "data"):
            v = data.get(key)
            if isinstance(v, list):
                candidates = v
                break
        if not candidates and "feedbackByProject" in data:
            candidates = data["feedbackByProject"]
    elif isinstance(data, list):
        candidates = data

    for c in candidates:
        if isinstance(c, dict) and (c.get("projectId") == PROJECT_ID or c.get("id") == PROJECT_ID):
            matched = c
            break

    assert matched is not None, f"No entry for projectId={PROJECT_ID} in dashboard response. Keys: {list(data.keys()) if isinstance(data, dict) else 'list'}"

    summary = matched.get("feedbackSummary") or matched.get("summary") or matched
    up_total = summary.get("upTotal") or summary.get("up") or summary.get("up_count") or 0
    assert int(up_total) > 0, f"upTotal not incremented after feedback POST. Summary={summary}"
