"""Backend tests for the new POST /api/density/generate-image endpoint.

Validates auth/ownership guards and basic happy-path: returns a real
image URL backed by an actual JPEG persisted to /app/storage/projects/.../assets/.

Note: The happy-path test calls Gemini (~15-25s). The test will not
be skipped but is allowed to take time.
"""
import os
import io
import time
import pytest
import requests


def _load_backend_url() -> str:
    url = os.environ.get("REACT_APP_BACKEND_URL", "").strip()
    if not url:
        try:
            with open("/app/frontend/.env", "r") as f:
                for line in f:
                    if line.startswith("REACT_APP_BACKEND_URL="):
                        url = line.split("=", 1)[1].strip()
                        break
        except FileNotFoundError:
            pass
    return url.rstrip("/")


BASE_URL = _load_backend_url()
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@scormify.com"
ADMIN_PASS = "admin123"
OTHER_COMPANY_EMAIL = "admin@empresateste.com"
OTHER_COMPANY_PASS = "empresa123"

TARGET_PROJECT_ID = "83dffbd3-5aee-4140-b81c-f0395c061a6b"


def _login(email: str, password: str) -> str:
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, f"Login failed for {email}: {r.status_code} {r.text}"
    body = r.json()
    return body.get("token") or body.get("access_token")


@pytest.fixture(scope="module")
def admin_token():
    return _login(ADMIN_EMAIL, ADMIN_PASS)


@pytest.fixture(scope="module")
def other_company_token():
    try:
        return _login(OTHER_COMPANY_EMAIL, OTHER_COMPANY_PASS)
    except AssertionError:
        return None


def _auth_headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# --- Auth / validation guards ---

def test_generate_image_requires_auth():
    r = requests.post(
        f"{API}/density/generate-image",
        json={"projectId": TARGET_PROJECT_ID, "imagePrompt": "test"},
        timeout=15,
    )
    assert r.status_code in (401, 403), f"Expected 401/403, got {r.status_code}: {r.text}"


def test_generate_image_empty_prompt_returns_400(admin_token):
    r = requests.post(
        f"{API}/density/generate-image",
        headers=_auth_headers(admin_token),
        json={"projectId": TARGET_PROJECT_ID, "imagePrompt": ""},
        timeout=15,
    )
    assert r.status_code == 400, f"Expected 400, got {r.status_code}: {r.text}"


def test_generate_image_unknown_project_returns_404(admin_token):
    r = requests.post(
        f"{API}/density/generate-image",
        headers=_auth_headers(admin_token),
        json={"projectId": "does-not-exist-xyz", "imagePrompt": "diagram of fraud triangle"},
        timeout=30,
    )
    assert r.status_code == 404, f"Expected 404, got {r.status_code}: {r.text}"


def test_generate_image_cross_tenant_forbidden(other_company_token):
    """A company_admin from a different company should NOT be able to
    generate-image into the Didaxis project. Super_admin bypasses this
    (covered indirectly by happy-path)."""
    if not other_company_token:
        pytest.skip("Other-company user not available")
    r = requests.post(
        f"{API}/density/generate-image",
        headers=_auth_headers(other_company_token),
        json={"projectId": TARGET_PROJECT_ID, "imagePrompt": "diagram"},
        timeout=15,
    )
    # company_admin role: the route only checks role NOT IN ("super_admin","admin")
    # so company_admin DOES enter the ownership branch. Project belongs to
    # another company so we expect 403 OR 404 (if project filtered upstream).
    assert r.status_code in (403, 404), f"Expected 403/404 for cross-tenant, got {r.status_code}: {r.text}"


# --- Happy path (slow, ~15-25s) ---

def test_generate_image_happy_path(admin_token):
    payload = {
        "projectId": TARGET_PROJECT_ID,
        "imagePrompt": "Infographic illustration of corporate internal controls with three pillars",
        "suggestionId": "test-suggestion-pytest-001",
    }
    start = time.time()
    r = requests.post(
        f"{API}/density/generate-image",
        headers=_auth_headers(admin_token),
        json=payload,
        timeout=90,
    )
    elapsed = time.time() - start
    assert r.status_code == 200, f"Expected 200, got {r.status_code} in {elapsed:.1f}s: {r.text}"
    body = r.json()
    assert "url" in body and body["url"].startswith("/api/projects/")
    assert "filename" in body and body["filename"].endswith(".jpg")
    assert body.get("width") == 1200
    assert body.get("height") == 1200
    # Verify the asset URL actually serves a real JPEG
    asset_url = f"{BASE_URL}{body['url']}"
    a = requests.get(asset_url, headers={"Authorization": f"Bearer {admin_token}"}, timeout=30)
    assert a.status_code == 200, f"Asset URL not served: {a.status_code}"
    content = a.content
    assert len(content) > 5000, f"Asset suspiciously small: {len(content)}B"
    # JPEG magic bytes
    assert content[:3] == b"\xff\xd8\xff", "Not a valid JPEG"


def test_generate_image_idempotent_same_suggestion(admin_token):
    """Same suggestionId + prompt should reuse the same filename (md5 seed)."""
    payload = {
        "projectId": TARGET_PROJECT_ID,
        "imagePrompt": "Idempotency probe prompt",
        "suggestionId": "test-suggestion-pytest-idempotent",
    }
    r1 = requests.post(f"{API}/density/generate-image", headers=_auth_headers(admin_token), json=payload, timeout=90)
    assert r1.status_code == 200
    r2 = requests.post(f"{API}/density/generate-image", headers=_auth_headers(admin_token), json=payload, timeout=90)
    assert r2.status_code == 200
    assert r1.json()["filename"] == r2.json()["filename"], "Filename should be deterministic"
