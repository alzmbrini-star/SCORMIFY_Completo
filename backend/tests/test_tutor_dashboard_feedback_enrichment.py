"""Tests for the new bulk feedbackSummary enrichment on
GET /api/admin/tutor-dashboard (iteration 129).

The dashboard endpoint now augments each course (in `courses[]` and
in `companies[].courseList[]`) with:
    feedbackSummary: {upTotal, downTotal, satisfactionPct}

We seed:
  - tutor_logs rows (so the course shows up in the dashboard aggregation
    — the bulk feedback lookup only enriches projectIds that appear in
    tutor_logs).
  - tutor_feedback rows via the public POST /api/tutor/feedback so the
    full path is exercised.

Cleanup uses sessionId prefix 'uisess-' + 'ftest-' and tutor_logs marked
with a custom 'testTag' field, scrubbed in fixtures.
"""
import os
import time
import uuid
from datetime import datetime, timezone

import pytest
import requests
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv("/app/frontend/.env")
load_dotenv("/app/backend/.env")

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or "").rstrip("/")
MONGO_URL = os.environ.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME")
assert BASE_URL, "REACT_APP_BACKEND_URL is not set"

ADMIN_EMAIL = "admin@scormify.com"
ADMIN_PASSWORD = "admin123"

DASH_URL = f"{BASE_URL}/api/admin/tutor-dashboard"
FEEDBACK_URL = f"{BASE_URL}/api/tutor/feedback"
STATS_URL = f"{BASE_URL}/api/admin/tutor/feedback-stats"

# Test project IDs we will seed
PID_MAIN = "test-project-129"
PID_ISO_A = "isolation-A-129"
PID_ISO_B = "isolation-B-129"
TEST_PIDS = [PID_MAIN, PID_ISO_A, PID_ISO_B]
TEST_TAG = "iter129-dash-enrich"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def api():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def admin_token(api):
    r = api.post(f"{BASE_URL}/api/auth/login",
                 json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text}"
    return r.json().get("token") or r.json().get("access_token")


@pytest.fixture(scope="module")
def auth_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}",
            "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def db():
    client = MongoClient(MONGO_URL)
    yield client[DB_NAME]
    client.close()


def _clean(db):
    db.tutor_feedback.delete_many({"sessionId": {"$regex": "^(uisess|ftest)-"}})
    db.tutor_feedback.delete_many({"projectId": {"$in": TEST_PIDS}})
    db.tutor_logs.delete_many({"testTag": TEST_TAG})


@pytest.fixture(scope="module", autouse=True)
def setup_and_teardown(db, api):
    """Seed tutor_logs once for the whole module, clean before and after."""
    _clean(db)

    now = datetime.now(timezone.utc).isoformat()
    # Seed at least one tutor_logs row per test project so they show up
    # in the dashboard aggregation. The bulk enrichment only matches
    # projectIds that appear in tutor_logs.
    docs = []
    for pid in TEST_PIDS:
        docs.append({
            "sessionId": f"uisess-log-{uuid.uuid4().hex[:6]}",
            "projectId": pid,
            "companyId": "",
            "courseTopic": f"Course {pid}",
            "question": "seed q",
            "response": "seed a",
            "estimatedInputTokens": 100,
            "estimatedOutputTokens": 50,
            "estimatedCostUSD": 0.0001,
            "model": "gemini-3-flash",
            "createdAt": now,
            "testTag": TEST_TAG,
        })
    db.tutor_logs.insert_many(docs)
    yield
    _clean(db)


def _post_feedback(api, project_id, rating, sess_suffix=None, msg_id=None):
    session_id = f"uisess-{sess_suffix or uuid.uuid4().hex[:8]}"
    message_id = msg_id or f"m-{uuid.uuid4().hex[:6]}"
    r = api.post(FEEDBACK_URL, json={
        "sessionId": session_id,
        "messageId": message_id,
        "rating": rating,
        "projectId": project_id,
        "question": "q",
        "answer": "a",
    })
    assert r.status_code == 200, f"feedback seed failed {r.status_code} {r.text}"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestDashboardEnrichmentBasic:
    """Seed 4 up + 2 down on PID_MAIN; verify both courses[] and
    companies[].courseList[] carry the same feedbackSummary."""

    def test_dashboard_top_level_courses_carry_feedback(self, api, auth_headers, db):
        # Clean only feedback (logs stay from module fixture)
        db.tutor_feedback.delete_many({"projectId": PID_MAIN})

        for _ in range(4):
            _post_feedback(api, PID_MAIN, "up")
        for _ in range(2):
            _post_feedback(api, PID_MAIN, "down")

        start = time.time()
        r = requests.get(DASH_URL, headers=auth_headers)
        elapsed = time.time() - start
        assert r.status_code == 200, r.text
        # Smoke check perf
        assert elapsed < 2.0, f"dashboard slow: {elapsed:.2f}s"
        body = r.json()

        # Find our test course in top-level courses[]
        match = [c for c in body["courses"] if c.get("projectId") == PID_MAIN]
        assert len(match) >= 1, f"course {PID_MAIN} not in courses[]"
        fb = match[0].get("feedbackSummary")
        assert fb is not None, "feedbackSummary missing in top-level courses[]"
        assert fb["upTotal"] == 4
        assert fb["downTotal"] == 2
        assert fb["satisfactionPct"] == 67

    def test_dashboard_companies_courselist_carries_feedback(self, api, auth_headers, db):
        # Re-seed in case prior test cleaned. Use idempotent assertion.
        db.tutor_feedback.delete_many({"projectId": PID_MAIN})
        for _ in range(4):
            _post_feedback(api, PID_MAIN, "up")
        for _ in range(2):
            _post_feedback(api, PID_MAIN, "down")

        r = requests.get(DASH_URL, headers=auth_headers)
        assert r.status_code == 200
        body = r.json()

        # Walk companies[] to find a courseList row with projectId=PID_MAIN
        found = None
        for comp in body.get("companies", []):
            for cs in comp.get("courseList", []):
                if cs.get("projectId") == PID_MAIN:
                    found = cs
                    break
            if found:
                break
        assert found is not None, "PID_MAIN not in any companies[].courseList[]"
        fb = found.get("feedbackSummary")
        assert fb is not None, "feedbackSummary missing in companies[].courseList[]"
        assert fb["upTotal"] == 4
        assert fb["downTotal"] == 2
        assert fb["satisfactionPct"] == 67

    def test_courses_without_feedback_have_zero_defaults(self, api, auth_headers, db):
        # Make sure isolation projects have NO feedback
        db.tutor_feedback.delete_many({"projectId": {"$in": [PID_ISO_A, PID_ISO_B]}})

        r = requests.get(DASH_URL, headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        iso_courses = [c for c in body["courses"]
                       if c.get("projectId") in (PID_ISO_A, PID_ISO_B)]
        assert len(iso_courses) >= 2, "isolation courses missing"
        for c in iso_courses:
            fb = c.get("feedbackSummary")
            assert fb is not None, f"feedbackSummary missing on {c.get('projectId')}"
            assert fb == {"upTotal": 0, "downTotal": 0, "satisfactionPct": None}, \
                f"expected zero defaults, got {fb} on {c.get('projectId')}"


class TestDashboardCrossProjectIsolation:
    def test_iso_a_and_b_do_not_bleed(self, api, auth_headers, db):
        db.tutor_feedback.delete_many({"projectId": {"$in": [PID_ISO_A, PID_ISO_B]}})

        # A: 5 ups
        for _ in range(5):
            _post_feedback(api, PID_ISO_A, "up")
        # B: 3 downs
        for _ in range(3):
            _post_feedback(api, PID_ISO_B, "down")

        r = requests.get(DASH_URL, headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        by_pid = {c["projectId"]: c for c in body["courses"] if c.get("projectId")}
        assert PID_ISO_A in by_pid, "iso A not found"
        assert PID_ISO_B in by_pid, "iso B not found"
        fb_a = by_pid[PID_ISO_A]["feedbackSummary"]
        fb_b = by_pid[PID_ISO_B]["feedbackSummary"]
        assert fb_a["upTotal"] == 5 and fb_a["downTotal"] == 0, fb_a
        assert fb_a["satisfactionPct"] == 100
        assert fb_b["upTotal"] == 0 and fb_b["downTotal"] == 3, fb_b
        assert fb_b["satisfactionPct"] == 0


class TestBackwardCompat:
    """The per-course /admin/tutor/feedback-stats endpoint from
    iteration 128 must still work identically."""

    def test_per_course_stats_still_works(self, api, auth_headers, db):
        db.tutor_feedback.delete_many({"projectId": PID_MAIN})
        for _ in range(4):
            _post_feedback(api, PID_MAIN, "up")
        for _ in range(2):
            _post_feedback(api, PID_MAIN, "down")

        r = requests.get(STATS_URL, params={"projectId": PID_MAIN, "limit": 5},
                         headers=auth_headers)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["upTotal"] == 4
        assert body["downTotal"] == 2
        assert body["ratedTotal"] == 6
        assert body["satisfactionPct"] == 67


class TestDashboardPerformance:
    def test_dashboard_responds_under_2s(self, auth_headers):
        start = time.time()
        r = requests.get(DASH_URL, headers=auth_headers)
        elapsed = time.time() - start
        assert r.status_code == 200
        assert elapsed < 2.0, f"dashboard took {elapsed:.2f}s — bulk enrichment may be N+1"
