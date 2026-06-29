"""Tests for the new admin GET /api/admin/tutor/feedback-stats endpoint.

The test seeds data via the public POST /api/tutor/feedback endpoint so
the full persistence path stays exercised. All seed docs use sessionId
prefix 'ftest-' and projectIds 'ftest-proj-*' for easy cleanup.
"""
import os
import uuid

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

STATS_URL = f"{BASE_URL}/api/admin/tutor/feedback-stats"
FEEDBACK_URL = f"{BASE_URL}/api/tutor/feedback"


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
    body = r.json()
    return body.get("access_token") or body.get("token")


@pytest.fixture(scope="module")
def auth_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}",
            "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def db():
    client = MongoClient(MONGO_URL)
    yield client[DB_NAME]
    client.close()


@pytest.fixture(autouse=True)
def cleanup_ftest_data(db):
    """Clean up any ftest- seeded data before & after each test."""
    db.tutor_feedback.delete_many({"sessionId": {"$regex": "^ftest-"}})
    yield
    db.tutor_feedback.delete_many({"sessionId": {"$regex": "^ftest-"}})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _seed(api, project_id, question, rating, session_suffix=None, msg_id=None,
          answer="some answer"):
    """Seed a single feedback row via the public POST endpoint."""
    session_id = f"ftest-{session_suffix or uuid.uuid4().hex[:8]}"
    message_id = msg_id or f"m-{uuid.uuid4().hex[:6]}"
    r = api.post(FEEDBACK_URL, json={
        "sessionId": session_id,
        "messageId": message_id,
        "rating": rating,
        "projectId": project_id,
        "question": question,
        "answer": answer,
    })
    assert r.status_code == 200, f"Seed failed: {r.status_code} {r.text}"
    return session_id, message_id


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

class TestStatsHappyPath:
    """6 ratings: 4 up / 2 down over 2 questions on ftest-proj-A."""

    def test_aggregate_counts_and_satisfaction(self, api, auth_headers):
        pid = "ftest-proj-A"
        # 4 ups across 2 questions, 2 downs
        _seed(api, pid, "What is X?", "up")
        _seed(api, pid, "What is X?", "up")
        _seed(api, pid, "What is X?", "up")
        _seed(api, pid, "What is Y?", "up")
        _seed(api, pid, "What is X?", "down")
        _seed(api, pid, "What is Y?", "down")

        r = requests.get(STATS_URL, params={"projectId": pid, "limit": 5},
                         headers=auth_headers)
        assert r.status_code == 200, r.text
        body = r.json()

        assert body["upTotal"] == 4
        assert body["downTotal"] == 2
        assert body["ratedTotal"] == 6
        assert body["satisfactionPct"] == 67  # round(4/6*100) = 67
        assert body["scope"] == "course"
        assert body["projectId"] == pid

        # topNegative — at least 1 with down >= 1
        assert isinstance(body["topNegative"], list)
        assert len(body["topNegative"]) >= 1
        assert body["topNegative"][0]["down"] >= 1

        # topPositive — at least 1 with up >= 1
        assert isinstance(body["topPositive"], list)
        assert len(body["topPositive"]) >= 1
        assert body["topPositive"][0]["up"] >= 1

        # recent: up to 20, sorted by updatedAt desc
        assert isinstance(body["recent"], list)
        assert len(body["recent"]) <= 20
        assert len(body["recent"]) == 6
        ts = [r.get("updatedAt") for r in body["recent"] if r.get("updatedAt")]
        assert ts == sorted(ts, reverse=True), "recent must be sorted by updatedAt desc"


# ---------------------------------------------------------------------------
# Empty project (never crashes / never 404s)
# ---------------------------------------------------------------------------

class TestStatsEmptyProject:
    def test_empty_project_returns_zero_payload(self, api, auth_headers):
        r = requests.get(STATS_URL,
                         params={"projectId": "ftest-proj-EMPTY"},
                         headers=auth_headers)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["upTotal"] == 0
        assert body["downTotal"] == 0
        assert body["ratedTotal"] == 0
        assert body["satisfactionPct"] is None
        assert body["topNegative"] == []
        assert body["topPositive"] == []
        assert body["recent"] == []


# ---------------------------------------------------------------------------
# Cross-project isolation
# ---------------------------------------------------------------------------

class TestStatsCrossProjectIsolation:
    def test_project_a_and_b_do_not_bleed(self, api, auth_headers):
        pid_a, pid_b = "ftest-proj-A", "ftest-proj-B"

        # A: 1 up, 2 down
        _seed(api, pid_a, "qa1", "up")
        _seed(api, pid_a, "qa2", "down")
        _seed(api, pid_a, "qa3", "down")
        # B: 3 up
        _seed(api, pid_b, "qb1", "up")
        _seed(api, pid_b, "qb2", "up")
        _seed(api, pid_b, "qb3", "up")

        ra = requests.get(STATS_URL, params={"projectId": pid_a},
                          headers=auth_headers)
        rb = requests.get(STATS_URL, params={"projectId": pid_b},
                          headers=auth_headers)
        assert ra.status_code == 200 and rb.status_code == 200
        ba, bb = ra.json(), rb.json()

        assert ba["upTotal"] == 1
        assert ba["downTotal"] == 2
        assert bb["upTotal"] == 3
        assert bb["downTotal"] == 0


# ---------------------------------------------------------------------------
# Auth required
# ---------------------------------------------------------------------------

class TestStatsAuth:
    def test_missing_auth_returns_401(self):
        r = requests.get(STATS_URL, params={"projectId": "ftest-proj-A"})
        assert r.status_code in (401, 403), f"Expected 401/403, got {r.status_code}"

    def test_invalid_token_returns_401(self):
        r = requests.get(STATS_URL,
                         params={"projectId": "ftest-proj-A"},
                         headers={"Authorization": "Bearer notavalidtoken"})
        assert r.status_code in (401, 403)


# ---------------------------------------------------------------------------
# Cleared (null) rating must not be counted
# ---------------------------------------------------------------------------

class TestStatsClearedRating:
    def test_null_rating_excluded(self, api, auth_headers):
        pid = "ftest-proj-CLEAR"
        # Seed an up, then clear it to null on the same (sessionId, messageId)
        session_id, message_id = _seed(api, pid, "qx", "up",
                                        session_suffix="clear", msg_id="m-clear")
        r = api.post(FEEDBACK_URL, json={
            "sessionId": session_id,
            "messageId": message_id,
            "rating": None,
            "projectId": pid,
            "question": "qx",
            "answer": "ans",
        })
        assert r.status_code == 200

        # Add a second clean down for context
        _seed(api, pid, "qy", "down")

        r = requests.get(STATS_URL, params={"projectId": pid},
                         headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        # Cleared message must NOT count in totals
        assert body["upTotal"] == 0, body
        assert body["downTotal"] == 1, body
        assert body["ratedTotal"] == 1


# ---------------------------------------------------------------------------
# topNegative ordering: by -down then -up
# ---------------------------------------------------------------------------

class TestStatsTopNegativeOrdering:
    def test_top_negative_ordering(self, api, auth_headers):
        pid = "ftest-proj-ORDER"
        # Q1: 3 down
        for _ in range(3):
            _seed(api, pid, "Question 1", "down")
        # Q2: 1 down
        _seed(api, pid, "Question 2", "down")
        # Q3: 2 down
        for _ in range(2):
            _seed(api, pid, "Question 3", "down")

        r = requests.get(STATS_URL, params={"projectId": pid, "limit": 10},
                         headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        top = body["topNegative"]
        assert len(top) == 3
        # Expected order: Q1(3), Q3(2), Q2(1)
        assert top[0]["question"] == "Question 1" and top[0]["down"] == 3
        assert top[1]["question"] == "Question 3" and top[1]["down"] == 2
        assert top[2]["question"] == "Question 2" and top[2]["down"] == 1
