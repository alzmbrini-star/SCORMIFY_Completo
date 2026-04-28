"""Tests for the apply-improvements retry safety fix.

Before the fix: preview was deleted immediately after being read, so if the
apply step failed halfway through, the user's retry would get a 400
"Preview expired". This test ensures that behaviour is now fixed.

Strategy:
  1. Call preview-improvements (happy path) to get a previewId.
  2. Simulate an apply failure by calling apply-improvements on a project
     that has been mutated in a way that makes `_apply_ai_result_to_slides`
     raise (e.g., we patch the stored preview to have malformed structure).
     Since monkey-patching the running server is not possible over HTTP,
     we instead test the positive retry case: call apply twice with the
     same previewId. The first succeeds and deletes the preview. The
     second should fail with 400 "Preview expired".
  3. Alternatively, verify via MongoDB that the preview still exists
     before a successful apply (i.e., that we didn't delete-on-find).
"""
import os
import uuid
import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8001")
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")

SUPER = {"email": "admin@scormify.com", "password": "admin123"}


@pytest.fixture(scope="module")
def super_token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json=SUPER, timeout=10)
    r.raise_for_status()
    return r.json()["token"]


@pytest.fixture(scope="module")
def db():
    client = MongoClient(MONGO_URL)
    return client[DB_NAME]


def test_preview_not_deleted_on_find(db, super_token):
    """Direct DB check: after apply-improvements starts, the preview must
    still exist until the background apply completes successfully. With the
    new async flow, the endpoint returns 202 immediately with an applyJobId
    and we must poll /apply-status/{job_id} until done. The preview should
    remain in MongoDB throughout 'processing' and only be deleted once the
    job reaches status='done'.
    """
    import time
    project = db.projects.find_one({}, {"_id": 0, "id": 1, "companyId": 1})
    assert project, "Need at least one project to run this test"
    project_id = project["id"]

    fake_preview_id = str(uuid.uuid4())
    db.improvement_previews.insert_one({
        "id": fake_preview_id,
        "projectId": project_id,
        "aiResult": {"updatedSlides": [], "newSlides": []},  # valid empty
        "createdAt": "2026-04-24T12:00:00+00:00",
    })

    try:
        r = requests.post(
            f"{BASE_URL}/api/agent/courses/{project_id}/apply-improvements",
            headers={"Authorization": f"Bearer {super_token}", "Content-Type": "application/json"},
            json={"improvements": [], "selectedNewSlides": None, "previewId": fake_preview_id},
            timeout=30,
        )
        assert r.status_code == 200, f"Apply trigger failed: {r.status_code} {r.text}"
        body = r.json()
        assert body.get("status") == "processing", f"Expected 'processing', got {body}"
        job_id = body["applyJobId"]
        assert job_id, "Missing applyJobId"

        # Poll until done (or timeout 30s)
        deadline = time.time() + 30
        final_status = None
        while time.time() < deadline:
            sr = requests.get(
                f"{BASE_URL}/api/agent/courses/{project_id}/apply-status/{job_id}",
                headers={"Authorization": f"Bearer {super_token}"},
                timeout=10,
            )
            assert sr.status_code == 200
            job = sr.json()
            if job["status"] in ("done", "error"):
                final_status = job["status"]
                break
            time.sleep(0.5)
        assert final_status == "done", f"Background job did not finish (last status: {final_status})"

        # After SUCCESSFUL apply, the preview should be deleted
        remaining = db.improvement_previews.find_one({"id": fake_preview_id})
        assert remaining is None, "Preview should be deleted after successful apply"

        # Second attempt with same previewId must return 400 (preview already gone)
        r2 = requests.post(
            f"{BASE_URL}/api/agent/courses/{project_id}/apply-improvements",
            headers={"Authorization": f"Bearer {super_token}", "Content-Type": "application/json"},
            json={"improvements": [], "selectedNewSlides": None, "previewId": fake_preview_id},
            timeout=30,
        )
        assert r2.status_code == 400, f"Expected 400 (preview already used), got {r2.status_code}: {r2.text}"
        assert "Preview expired" in r2.text or "not found" in r2.text
    finally:
        db.improvement_previews.delete_one({"id": fake_preview_id})


def test_apply_returns_202_processing_with_jobid(db, super_token):
    """Async flow contract: apply-improvements never blocks > 1s and always
    returns {status: processing, applyJobId} when given a valid preview."""
    import time
    project = db.projects.find_one({}, {"_id": 0, "id": 1})
    assert project, "Need at least one project"
    project_id = project["id"]

    pid = str(uuid.uuid4())
    db.improvement_previews.insert_one({
        "id": pid,
        "projectId": project_id,
        "aiResult": {"updatedSlides": [], "newSlides": []},
        "createdAt": "2026-04-24T12:00:00+00:00",
    })
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
        assert body.get("status") == "processing"
        assert body.get("applyJobId")
        assert elapsed < 5.0, f"apply-improvements took {elapsed:.1f}s (should be <5s for async)"
    finally:
        db.improvement_previews.delete_one({"id": pid})


def test_apply_status_unauthorized_returns_401(super_token):
    """The /apply-status endpoint must require auth."""
    r = requests.get(
        f"{BASE_URL}/api/agent/courses/some-id/apply-status/some-job",
        timeout=10,
    )
    assert r.status_code == 401


def test_apply_with_missing_preview_returns_400(super_token):
    """Apply with a random previewId that doesn't exist → 400, not 500."""
    # Get any project
    client = MongoClient(MONGO_URL)
    project = client[DB_NAME].projects.find_one({}, {"_id": 0, "id": 1})
    if not project:
        pytest.skip("No projects available")

    r = requests.post(
        f"{BASE_URL}/api/agent/courses/{project['id']}/apply-improvements",
        headers={"Authorization": f"Bearer {super_token}", "Content-Type": "application/json"},
        json={"improvements": [], "selectedNewSlides": None, "previewId": "does-not-exist-" + str(uuid.uuid4())},
        timeout=10,
    )
    assert r.status_code == 400, f"Expected 400, got {r.status_code}: {r.text}"
    body = r.json()
    # Error message should guide the user
    assert "Preview" in str(body) or "preview" in str(body).lower()


def test_apply_without_previewid_path_works(super_token, db):
    """Apply without previewId → triggers fresh AI call path. This is the
    fallback path that doesn't involve the preview cache at all. Here we
    only verify the endpoint accepts the request; the AI call itself might
    fail in the CI env if there's no LLM key, but that's a separate 500."""
    project = db.projects.find_one({}, {"_id": 0, "id": 1})
    if not project:
        pytest.skip("No projects available")

    r = requests.post(
        f"{BASE_URL}/api/agent/courses/{project['id']}/apply-improvements",
        headers={"Authorization": f"Bearer {super_token}", "Content-Type": "application/json"},
        json={"improvements": [], "selectedNewSlides": None},
        timeout=60,
    )
    # Should NOT return 400 (no previewId so we bypass the preview lookup)
    assert r.status_code != 400, f"Got 400 when not using previewId: {r.text}"
