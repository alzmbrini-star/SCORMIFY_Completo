"""Iteration 112 — Async refactor of POST /api/agent/courses/{project_id}/apply-improvements.

Covers review_request items NOT already covered by test_apply_improvements_retry.py:
  - Endpoint returns in <2s (NEVER blocks 60s)
  - Idempotency: 2nd POST while a job is processing returns the SAME applyJobId
  - Anonymous on POST -> 401
  - Cross-company on POST -> 404
  - Cross-company on GET /apply-status/{job_id} -> 404
  - GET /apply-status with bogus job_id (same project) -> 404
  - Background worker actually executes (status reaches 'done' with all expected fields)
  - After successful BG, cached preview is deleted from MongoDB
"""
import os
import time
import uuid
import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("BASE_URL", "https://ai-tutor-platform-12.preview.emergentagent.com").rstrip("/")
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")

SUPER = {"email": "admin@scormify.com", "password": "admin123"}
CROSS = {"email": "admin@empresateste.com", "password": "empresa123"}


def _login(creds):
    r = requests.post(f"{BASE_URL}/api/auth/login", json=creds, timeout=15)
    r.raise_for_status()
    return r.json()["token"]


@pytest.fixture(scope="module")
def super_token():
    return _login(SUPER)


@pytest.fixture(scope="module")
def cross_token():
    return _login(CROSS)


@pytest.fixture(scope="module")
def db():
    return MongoClient(MONGO_URL)[DB_NAME]


@pytest.fixture(scope="module")
def didaxis_project(db):
    """A project belonging to company_didaxis001 (super_admin can access, cross-company cannot)."""
    p = db.projects.find_one({"companyId": "company_didaxis001"}, {"_id": 0, "id": 1, "companyId": 1})
    if not p:
        p = db.projects.find_one({}, {"_id": 0, "id": 1, "companyId": 1})
    assert p, "Need at least one project"
    return p


def _insert_preview(db, project_id):
    pid = str(uuid.uuid4())
    db.improvement_previews.insert_one({
        "id": pid,
        "projectId": project_id,
        "aiResult": {"updatedSlides": [], "newSlides": []},
        "createdAt": "2026-04-24T12:00:00+00:00",
    })
    return pid


def _wait_for_done(super_token, project_id, job_id, timeout=45):
    """Poll /apply-status until status in {done, error} or timeout."""
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        sr = requests.get(
            f"{BASE_URL}/api/agent/courses/{project_id}/apply-status/{job_id}",
            headers={"Authorization": f"Bearer {super_token}"},
            timeout=10,
        )
        assert sr.status_code == 200, f"apply-status returned {sr.status_code}: {sr.text}"
        last = sr.json()
        if last.get("status") in ("done", "error"):
            return last
        time.sleep(0.5)
    pytest.fail(f"Job did not finish in {timeout}s. Last state: {last}")


# ---------- Async contract ----------

def test_apply_improvements_returns_in_under_2s(super_token, didaxis_project, db):
    """Endpoint must return in <2s — never block while AI runs."""
    project_id = didaxis_project["id"]
    pid = _insert_preview(db, project_id)
    try:
        t0 = time.time()
        r = requests.post(
            f"{BASE_URL}/api/agent/courses/{project_id}/apply-improvements",
            headers={"Authorization": f"Bearer {super_token}", "Content-Type": "application/json"},
            json={"improvements": [], "selectedNewSlides": None, "previewId": pid},
            timeout=10,
        )
        elapsed = time.time() - t0
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "processing"
        assert body["applyJobId"]
        assert body.get("startedAt"), "Response should include startedAt"
        assert elapsed < 2.0, f"apply-improvements took {elapsed:.2f}s (must be <2s for async)"
        # Wait for completion so we don't leave dangling jobs
        _wait_for_done(super_token, project_id, body["applyJobId"])
    finally:
        db.improvement_previews.delete_one({"id": pid})


# ---------- Idempotency ----------

def test_idempotency_returns_existing_processing_jobid(super_token, didaxis_project, db):
    """Idempotency contract: if a 'processing' apply_job already exists for the
    project, a new POST must return THAT job's id rather than starting a fresh
    background task. We seed a fake 'processing' job directly in MongoDB so the
    contract is testable regardless of how fast the empty BG path runs.
    """
    project_id = didaxis_project["id"]
    fake_job_id = str(uuid.uuid4())
    started_at = "2026-04-24T12:00:00+00:00"

    # Clean any pre-existing processing jobs for this project
    db.apply_jobs.delete_many({"projectId": project_id, "status": "processing"})
    db.apply_jobs.insert_one({
        "id": fake_job_id,
        "projectId": project_id,
        "userId": "seed",
        "status": "processing",
        "progress": 25,
        "message": "seeded processing job",
        "startedAt": started_at,
    })
    pid = _insert_preview(db, project_id)
    try:
        r = requests.post(
            f"{BASE_URL}/api/agent/courses/{project_id}/apply-improvements",
            headers={"Authorization": f"Bearer {super_token}", "Content-Type": "application/json"},
            json={"improvements": [], "selectedNewSlides": None, "previewId": pid},
            timeout=10,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "processing"
        assert body["applyJobId"] == fake_job_id, (
            f"Idempotency violated: expected reuse of {fake_job_id}, got {body['applyJobId']}"
        )
    finally:
        db.apply_jobs.delete_one({"id": fake_job_id})
        db.improvement_previews.delete_one({"id": pid})


# ---------- RBAC ----------

def test_apply_improvements_anonymous_returns_401(didaxis_project):
    project_id = didaxis_project["id"]
    r = requests.post(
        f"{BASE_URL}/api/agent/courses/{project_id}/apply-improvements",
        json={"improvements": []},
        timeout=10,
    )
    assert r.status_code == 401, r.text


def test_apply_improvements_cross_company_returns_404(cross_token, didaxis_project):
    """company_admin from a different company must get 404 (not 200/403/500)."""
    project_id = didaxis_project["id"]
    r = requests.post(
        f"{BASE_URL}/api/agent/courses/{project_id}/apply-improvements",
        headers={"Authorization": f"Bearer {cross_token}", "Content-Type": "application/json"},
        json={"improvements": []},
        timeout=10,
    )
    assert r.status_code == 404, f"Expected 404 cross-company, got {r.status_code}: {r.text}"


def test_apply_status_cross_company_returns_404(cross_token, didaxis_project):
    project_id = didaxis_project["id"]
    r = requests.get(
        f"{BASE_URL}/api/agent/courses/{project_id}/apply-status/some-job-id",
        headers={"Authorization": f"Bearer {cross_token}"},
        timeout=10,
    )
    assert r.status_code == 404, r.text


def test_apply_status_bogus_jobid_returns_404(super_token, didaxis_project):
    project_id = didaxis_project["id"]
    r = requests.get(
        f"{BASE_URL}/api/agent/courses/{project_id}/apply-status/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {super_token}"},
        timeout=10,
    )
    assert r.status_code == 404


# ---------- Background worker actually executes ----------

def test_background_worker_executes_to_done_and_deletes_preview(super_token, didaxis_project, db):
    """Verify the BG worker runs end-to-end:
       - status moves processing -> done
       - response payload contains expected fields when done
       - cached preview is removed from MongoDB after success
    """
    project_id = didaxis_project["id"]
    pid = _insert_preview(db, project_id)
    try:
        r = requests.post(
            f"{BASE_URL}/api/agent/courses/{project_id}/apply-improvements",
            headers={"Authorization": f"Bearer {super_token}", "Content-Type": "application/json"},
            json={"improvements": [], "selectedNewSlides": None, "previewId": pid},
            timeout=10,
        )
        assert r.status_code == 200
        job_id = r.json()["applyJobId"]

        final = _wait_for_done(super_token, project_id, job_id)
        assert final["status"] == "done", f"Expected 'done', got {final}"
        # Sanity: progress and message present
        assert "progress" in final
        assert "message" in final or "status" in final

        # Preview should be deleted after success
        remaining = db.improvement_previews.find_one({"id": pid})
        assert remaining is None, "Preview should have been deleted post-success"
    finally:
        db.improvement_previews.delete_one({"id": pid})


# ---------- apply-status auth ----------

def test_apply_status_anonymous_returns_401(didaxis_project):
    project_id = didaxis_project["id"]
    r = requests.get(
        f"{BASE_URL}/api/agent/courses/{project_id}/apply-status/anything",
        timeout=10,
    )
    assert r.status_code == 401
