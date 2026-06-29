"""Tests for the public Tutor IA feedback endpoint + export inlining
of the new stats UI markers."""
import os
import io
import time
import json
import asyncio
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
    return r.json().get("access_token") or r.json().get("token")


@pytest.fixture(scope="module")
def auth_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}",
            "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def db():
    client = MongoClient(MONGO_URL)
    yield client[DB_NAME]
    client.close()


def _mongo_find_one(db, query):
    return db.tutor_feedback.find_one(query)


def _mongo_delete(db, query):
    return db.tutor_feedback.delete_many(query)


# ---------------------------------------------------------------------------
# POST /api/tutor/feedback — happy path + persistence
# ---------------------------------------------------------------------------

class TestFeedbackHappyPath:
    def test_post_thumbs_up_persists(self, api, db):
        session_id = f"TEST_sess_{uuid.uuid4().hex[:8]}"
        message_id = "tm-1"
        try:
            r = api.post(f"{BASE_URL}/api/tutor/feedback", json={
                "sessionId": session_id,
                "messageId": message_id,
                "rating": "up",
                "projectId": "TEST_proj_1",
                "question": "Qual é o objetivo?",
                "answer": "Explicar conceitos básicos.",
            })
            assert r.status_code == 200, r.text
            body = r.json()
            assert body == {"ok": True, "rating": "up"}

            doc = _mongo_find_one(db,
                                  {"sessionId": session_id, "messageId": message_id})
            assert doc is not None, "Feedback was not persisted"
            assert doc["rating"] == "up"
            assert doc["projectId"] == "TEST_proj_1"
            assert doc["question"] == "Qual é o objetivo?"
            assert "createdAt" in doc and "updatedAt" in doc
        finally:
            _mongo_delete(db, {"sessionId": session_id})


class TestFeedbackUpsert:
    def test_idempotent_upsert_keeps_createdAt(self, api, db):
        session_id = f"TEST_sess_{uuid.uuid4().hex[:8]}"
        message_id = "tm-up"
        try:
            r1 = api.post(f"{BASE_URL}/api/tutor/feedback", json={
                "sessionId": session_id, "messageId": message_id, "rating": "up"})
            assert r1.status_code == 200

            doc1 = _mongo_find_one(db,
                                   {"sessionId": session_id, "messageId": message_id})
            assert doc1 and doc1["rating"] == "up"
            created_first = doc1["createdAt"]
            updated_first = doc1["updatedAt"]

            time.sleep(1.1)

            r2 = api.post(f"{BASE_URL}/api/tutor/feedback", json={
                "sessionId": session_id, "messageId": message_id, "rating": "down"})
            assert r2.status_code == 200
            assert r2.json() == {"ok": True, "rating": "down"}

            # Only one doc should exist
            count = db.tutor_feedback.count_documents(
                {"sessionId": session_id, "messageId": message_id})
            assert count == 1, f"Expected 1 upserted doc, got {count}"

            doc2 = _mongo_find_one(db,
                                   {"sessionId": session_id, "messageId": message_id})
            assert doc2["rating"] == "down"
            assert doc2["createdAt"] == created_first, "createdAt should be preserved"
            assert doc2["updatedAt"] != updated_first, "updatedAt should advance"
        finally:
            _mongo_delete(db, {"sessionId": session_id})

    def test_rating_can_be_cleared_to_null(self, api, db):
        session_id = f"TEST_sess_{uuid.uuid4().hex[:8]}"
        message_id = "tm-clear"
        try:
            api.post(f"{BASE_URL}/api/tutor/feedback", json={
                "sessionId": session_id, "messageId": message_id, "rating": "up"})
            r = api.post(f"{BASE_URL}/api/tutor/feedback", json={
                "sessionId": session_id, "messageId": message_id, "rating": None})
            assert r.status_code == 200
            assert r.json() == {"ok": True, "rating": None}
            doc = _mongo_find_one(db,
                                  {"sessionId": session_id, "messageId": message_id})
            assert doc is not None and doc["rating"] is None
        finally:
            _mongo_delete(db, {"sessionId": session_id})


# ---------------------------------------------------------------------------
# Validation errors
# ---------------------------------------------------------------------------

class TestFeedbackValidation:
    def test_missing_session_id(self, api):
        r = api.post(f"{BASE_URL}/api/tutor/feedback",
                     json={"messageId": "m1", "rating": "up"})
        assert r.status_code == 400
        assert "sessionId" in r.json().get("detail", "")

    def test_missing_message_id(self, api):
        r = api.post(f"{BASE_URL}/api/tutor/feedback",
                     json={"sessionId": "s1", "rating": "up"})
        assert r.status_code == 400
        assert "messageId" in r.json().get("detail", "")

    def test_invalid_rating(self, api):
        r = api.post(f"{BASE_URL}/api/tutor/feedback",
                     json={"sessionId": "s1", "messageId": "m1",
                           "rating": "maybe"})
        assert r.status_code == 400
        assert "rating" in r.json().get("detail", "").lower()

    def test_invalid_json(self, api):
        # Send raw garbage with json content-type
        r = requests.post(
            f"{BASE_URL}/api/tutor/feedback",
            data="not-json-at-all",
            headers={"Content-Type": "application/json"})
        assert r.status_code == 400
        assert "Invalid JSON" in r.json().get("detail", "")


# ---------------------------------------------------------------------------
# CORS preflight
# ---------------------------------------------------------------------------

class TestFeedbackCors:
    def test_options_preflight_returns_204(self, api):
        r = requests.options(
            f"{BASE_URL}/api/tutor/feedback",
            headers={
                "Origin": "https://student.lms.example",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            })
        # Either the route's own 204 handler or the global CORS middleware
        # should answer successfully.
        assert r.status_code in (200, 204), f"Got {r.status_code}: {r.text}"


# ---------------------------------------------------------------------------
# Export inlining — verify the exported HTML contains the new tutor stats
# UI/JS strings.
# ---------------------------------------------------------------------------

class TestExportInliningStats:
    REQUIRED_STRINGS = [
        "tutor-stats-button",
        'data-testid="tutor-stats-pane"',
        "toggleStats",
        "/api/tutor/feedback",
        "tutor-stats-bar-chart",
    ]

    def test_export_contains_stats_markers(self, api, auth_headers):
        # Pick the first available project
        r = api.get(f"{BASE_URL}/api/projects", headers=auth_headers)
        assert r.status_code == 200, r.text
        projects = r.json()
        if isinstance(projects, dict):
            projects = projects.get("items") or projects.get("projects") or []
        assert len(projects) > 0, "No projects available to export"
        project_id = projects[0].get("id") or projects[0].get("_id") or projects[0].get("projectId")
        assert project_id

        # Kick off export
        r = api.post(f"{BASE_URL}/api/course/{project_id}/export-html",
                     headers=auth_headers, json={"singlePage": False})
        assert r.status_code in (200, 202), f"export-html failed: {r.status_code} {r.text}"
        job = r.json()
        job_id = job.get("jobId") or job.get("id") or job.get("job_id")
        assert job_id, f"No jobId in {job}"

        # Poll until completed using /api/job endpoint
        download_url = None
        deadline = time.time() + 180
        last = None
        while time.time() < deadline:
            sr = api.get(f"{BASE_URL}/api/job/{job_id}", headers=auth_headers)
            if sr.status_code == 200:
                s = sr.json()
                last = s
                status = (s.get("status") or "").lower()
                if status == "completed":
                    download_url = (s.get("result") or {}).get("downloadUrl") \
                        or s.get("downloadUrl")
                    break
                if status == "failed":
                    pytest.fail(f"Export job failed: {s}")
            time.sleep(2)
        assert download_url, f"Export never completed. Last={last}"

        # Download the HTML (may be relative)
        if download_url.startswith("/"):
            download_url = BASE_URL + download_url
        dr = requests.get(download_url, headers=auth_headers, allow_redirects=True)
        assert dr.status_code == 200, f"Download failed: {dr.status_code}"
        html = dr.text

        missing = [s for s in self.REQUIRED_STRINGS if s not in html]
        assert not missing, f"Exported HTML missing markers: {missing}"
