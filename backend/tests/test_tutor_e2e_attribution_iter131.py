"""
Iteration 131 — End-to-End attribution: widget chat POST now sends
projectId+companyId so tutor_logs entries carry attribution. This unlocks
the admin dashboard aggregation for exported courses.

Critical flow under test:
  POST /api/tutor/chat (with projectId+companyId) ->
  Mongo tutor_logs has projectId=PROJECT_ID ->
  POST /api/tutor/feedback (rating up) ->
  GET /api/admin/tutor-dashboard -> courses[] AND companies[].courseList[]
  contain matching entry with feedbackSummary upTotal>=1.

Also covers:
- Legacy widget compat (no projectId in payload still returns 200).
- Validation regression for /api/tutor/feedback (missing fields -> 4xx).
- /api/admin/tutor/feedback-stats endpoint still returns structured payload.
- HTML/SCORM export still stamps projectId+companyId AND tutor.js inlined
  in the export contains the new `projectId: config.projectId` field
  (iter 131 widget code change).
"""
import os
import io
import re
import time
import zipfile
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
# Tag every doc we create so cleanup is easy & doesn't touch real data.
SESSION_PREFIX = "e2eflow131-"


# ---- Mongo helper (best-effort, used for direct verification + cleanup) ----
def _mongo():
    try:
        from pymongo import MongoClient
        url = os.environ.get("MONGO_URL")
        dbn = os.environ.get("DB_NAME")
        if not url or not dbn:
            # Read backend/.env
            try:
                with open("/app/backend/.env") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("MONGO_URL=") and not url:
                            url = line.split("=", 1)[1].strip().strip('"')
                        if line.startswith("DB_NAME=") and not dbn:
                            dbn = line.split("=", 1)[1].strip().strip('"')
            except Exception:
                pass
        if not url or not dbn:
            return None
        return MongoClient(url)[dbn]
    except Exception:
        return None


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


@pytest.fixture(scope="module", autouse=True)
def cleanup_seeded_data():
    """Remove test docs at module teardown."""
    yield
    db = _mongo()
    if db is None:
        return
    try:
        db.tutor_logs.delete_many({"sessionId": {"$regex": f"^{SESSION_PREFIX}"}})
        db.tutor_feedback.delete_many({"sessionId": {"$regex": f"^{SESSION_PREFIX}"}})
    except Exception:
        pass


# --- 1) END-TO-END CRITICAL FLOW (the user's reported bug)
def test_e2e_chat_with_projectid_persisted_and_joined_in_dashboard(auth_headers):
    """The big one. Simulates the new widget payload and asserts:
       - chat returns 200
       - tutor_logs gets a row with the real projectId (not empty)
       - feedback POST persists
       - admin dashboard reports the project under courses[] + companies[]
         with the right feedbackSummary numbers.
    """
    session_id = f"{SESSION_PREFIX}{int(time.time())}"
    message_text = "Pergunta de teste para validar atribuição projeto/empresa."
    chat_payload = {
        "message": message_text,
        "courseTopic": "Projeto SCORMIFY",
        "courseContext": "Conteúdo de teste para validar atribuição.",
        "history": [],
        "sessionId": session_id,
        "projectId": PROJECT_ID,
        "companyId": EXPECTED_COMPANY,
    }
    r = requests.post(f"{BASE_URL}/api/tutor/chat", json=chat_payload, timeout=90)
    assert r.status_code == 200, f"chat failed: {r.status_code} {r.text[:300]}"
    chat_data = r.json()
    assert "response" in chat_data and isinstance(chat_data["response"], str) and chat_data["response"], \
        f"chat returned no response field: {chat_data}"

    # Verify tutor_logs got the new doc with attribution (direct Mongo check)
    db = _mongo()
    if db is None:
        pytest.skip("Cannot reach Mongo directly to verify tutor_logs persistence.")

    # Allow a brief moment for the insert
    log_doc = None
    for _ in range(10):
        log_doc = db.tutor_logs.find_one({"sessionId": session_id})
        if log_doc:
            break
        time.sleep(0.5)
    assert log_doc is not None, f"tutor_logs has no entry for sessionId={session_id}"
    assert log_doc.get("projectId") == PROJECT_ID, \
        f"projectId not persisted. Got={log_doc.get('projectId')!r}"
    assert log_doc.get("companyId") == EXPECTED_COMPANY, \
        f"companyId not persisted. Got={log_doc.get('companyId')!r}"

    # POST feedback (rating 'up') against this exact entry
    msg_id = f"msg-{session_id}-1"
    fb_payload = {
        "projectId": PROJECT_ID,
        "companyId": EXPECTED_COMPANY,
        "sessionId": session_id,
        "messageId": msg_id,
        "rating": "up",
        "messageText": "Resposta do tutor",
        "userQuestion": message_text,
    }
    r2 = requests.post(f"{BASE_URL}/api/tutor/feedback", json=fb_payload, timeout=20)
    assert r2.status_code == 200, f"feedback POST failed: {r2.status_code} {r2.text[:300]}"

    # Hit the admin dashboard and look for the project
    time.sleep(1)
    r3 = requests.get(f"{BASE_URL}/api/admin/tutor-dashboard", headers=auth_headers, timeout=30)
    assert r3.status_code == 200, f"dashboard fetch failed: {r3.status_code}"
    data = r3.json()
    courses = data.get("courses") or []
    matched = next((c for c in courses if c.get("projectId") == PROJECT_ID), None)
    assert matched is not None, \
        f"Project {PROJECT_ID} missing from courses[]. Sample projectIds={[c.get('projectId') for c in courses[:10]]}"

    fb_summary = matched.get("feedbackSummary") or {}
    assert int(fb_summary.get("upTotal") or 0) >= 1, \
        f"upTotal should be >=1 after feedback POST. Got={fb_summary}"
    assert int(fb_summary.get("downTotal") or 0) >= 0
    # satisfactionPct = 100 when all up
    assert fb_summary.get("satisfactionPct") is not None

    # Also confirm the course appears nested under companies[].courseList[]
    companies = data.get("companies") or []
    found_in_company = False
    for company in companies:
        for cc in (company.get("courseList") or []):
            if cc.get("projectId") == PROJECT_ID:
                found_in_company = True
                break
        if found_in_company:
            break
    assert found_in_company, "Project not found under companies[].courseList[]"


# --- 2) Legacy backward-compat: no projectId/companyId still returns 200
def test_legacy_chat_without_attribution_still_works():
    session_id = f"{SESSION_PREFIX}legacy-{int(time.time())}"
    payload = {
        "message": "Hello tutor.",
        "courseTopic": "Generic",
        "courseContext": "Some context",
        "history": [],
        "sessionId": session_id,
    }
    r = requests.post(f"{BASE_URL}/api/tutor/chat", json=payload, timeout=90)
    assert r.status_code == 200, f"legacy chat failed: {r.status_code} {r.text[:300]}"
    assert "response" in r.json()


# --- 3) Feedback POST validation regression (iteration 127)
def test_feedback_validation_missing_fields():
    r = requests.post(f"{BASE_URL}/api/tutor/feedback", json={}, timeout=15)
    assert r.status_code in (400, 422), \
        f"Expected 4xx on empty body, got {r.status_code}: {r.text[:200]}"


# --- 4) Feedback-stats endpoint regression (iteration 128)
def test_feedback_stats_endpoint_structured(auth_headers):
    r = requests.get(
        f"{BASE_URL}/api/admin/tutor/feedback-stats",
        params={"projectId": PROJECT_ID},
        headers=auth_headers,
        timeout=30,
    )
    assert r.status_code == 200, f"feedback-stats failed: {r.status_code} {r.text[:300]}"
    data = r.json()
    for k in ("upTotal", "downTotal", "topNegative", "topPositive", "recent"):
        assert k in data, f"Missing key '{k}' in feedback-stats response. Keys={list(data.keys())}"


# --- 5) Widget JS payload inspection (iter 131 widget change)
def test_tutorjs_source_includes_projectid_in_chat_payload():
    """Verify the source file ships the new attribution fields."""
    path = "/app/backend/services/export_assets/tutor.js"
    with open(path, "r", encoding="utf-8") as f:
        src = f.read()
    assert "projectId: config.projectId" in src, \
        "tutor.js missing 'projectId: config.projectId' in chat payload"
    assert "companyId: config.companyId" in src, \
        "tutor.js missing 'companyId: config.companyId' in chat payload"


# --- 6) Export polling helper
def _poll_job(job_id, headers, timeout=420):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        r = requests.get(f"{BASE_URL}/api/job/{job_id}", headers=headers, timeout=30)
        if r.status_code != 200:
            time.sleep(2)
            continue
        last = r.json()
        st = last.get("status")
        if st == "completed":
            return last
        if st == "failed":
            pytest.fail(f"Job failed: {last.get('message')}")
        time.sleep(3)
    pytest.fail(f"Job timeout. Last: {last}")


# --- 7) HTML export carries projectId + companyId AND new widget code
def test_html_export_carries_attribution_and_new_widget(auth_headers):
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
    assert download_url, f"No downloadUrl: {result}"
    full_url = download_url if download_url.startswith("http") else f"{BASE_URL}{download_url}"
    dl = requests.get(full_url, headers=auth_headers, timeout=240)
    assert dl.status_code == 200, f"Download failed: {dl.status_code}"
    html = dl.text

    # iter 130 fix: tutorConfig stamps
    assert f'"projectId": "{PROJECT_ID}"' in html, \
        "projectId not stamped in exported HTML tutorConfig"
    assert f'"companyId": "{EXPECTED_COMPANY}"' in html, \
        "companyId not stamped in exported HTML tutorConfig"

    # iter 131 fix: widget chat payload references config.projectId
    assert "projectId: config.projectId" in html, \
        "Exported HTML does not contain the new widget payload field 'projectId: config.projectId'"
    assert "companyId: config.companyId" in html, \
        "Exported HTML does not contain the new widget payload field 'companyId: config.companyId'"


# --- 8) SCORM export carries projectId + companyId AND new widget code
def test_scorm_export_carries_attribution_and_new_widget(auth_headers):
    r = requests.post(
        f"{BASE_URL}/api/course/{PROJECT_ID}/export-scorm",
        headers=auth_headers,
        json={"singlePage": False},
        timeout=60,
    )
    assert r.status_code == 200, f"SCORM export init failed: {r.status_code} {r.text[:300]}"
    job_id = r.json()["jobId"]
    job = _poll_job(job_id, auth_headers, timeout=480)
    result = job.get("result") or {}
    download_url = result.get("downloadUrl") or result.get("url")
    assert download_url, f"No downloadUrl: {result}"
    full_url = download_url if download_url.startswith("http") else f"{BASE_URL}{download_url}"
    dl = requests.get(full_url, headers=auth_headers, timeout=300)
    assert dl.status_code == 200

    buf = io.BytesIO(dl.content)
    with zipfile.ZipFile(buf) as zf:
        names = zf.namelist()

        # course.json should carry tutorConfig with stamps
        cj_names = [n for n in names if n.endswith("course.json")]
        course_json_found_pid = False
        course_json_found_cid = False
        for n in cj_names:
            try:
                content = zf.read(n).decode("utf-8", errors="ignore")
            except Exception:
                continue
            if "tutorConfig" in content:
                if f'"projectId": "{PROJECT_ID}"' in content or f'"projectId":"{PROJECT_ID}"' in content:
                    course_json_found_pid = True
                if f'"companyId": "{EXPECTED_COMPANY}"' in content or f'"companyId":"{EXPECTED_COMPANY}"' in content:
                    course_json_found_cid = True
        assert course_json_found_pid, "projectId not found in any course.json inside SCORM zip"
        assert course_json_found_cid, "companyId not found in any course.json inside SCORM zip"

        # tutor.js inside scorm should have new widget payload field
        tjs_names = [n for n in names if n.endswith("tutor.js") or n.endswith(".js")]
        widget_payload_found = False
        for n in tjs_names:
            try:
                content = zf.read(n).decode("utf-8", errors="ignore")
            except Exception:
                continue
            if "projectId: config.projectId" in content:
                widget_payload_found = True
                break
        assert widget_payload_found, \
            "No JS file in SCORM zip contains 'projectId: config.projectId' (new widget code missing)"
