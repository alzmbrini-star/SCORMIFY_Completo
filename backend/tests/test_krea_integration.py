"""Backend tests for the Krea AI integration.

Follows the same pattern as other Scormify backend tests (test_agent_rbac.py):
hits the live backend via REACT_APP_BACKEND_URL and requires admin@scormify.com
credentials. Falls back to localhost:8001 when running locally.

Covers:
- GET /api/krea/status (configured + models count)
- GET /api/krea/models (full catalog with metadata)
- POST /api/krea/generate (bad input paths — we don't hit real Krea API)
- Unit tests on the service layer (pure functions, mocked httpx)
"""
from __future__ import annotations

import os
import pytest
import requests


BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or "http://localhost:8001").rstrip("/")
SUPER_ADMIN_EMAIL = "admin@scormify.com"
SUPER_ADMIN_PASSWORD = "admin123"


def _login() -> str:
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": SUPER_ADMIN_EMAIL, "password": SUPER_ADMIN_PASSWORD},
        timeout=10,
    )
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text}"
    data = r.json()
    return data["token"]


@pytest.fixture(scope="module")
def admin_token() -> str:
    return _login()


@pytest.fixture
def auth_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


# ---------------------------------------------------------------------------
# Unit: model catalog + auth helpers (service-level, no backend required)
# ---------------------------------------------------------------------------

def test_models_catalog_has_at_least_10_models():
    from services import krea_ai
    assert len(krea_ai.KREA_IMAGE_MODELS) >= 10
    for m in krea_ai.KREA_IMAGE_MODELS:
        assert m["id"]
        assert m["path"]
        assert m["label"]
        assert m["tier"] in ("standard", "premium")
        assert m["maxWidth"] > 0
        assert m["maxHeight"] > 0
        assert m["approxCostUSD"] > 0


def test_get_model_meta_returns_dict_for_valid_id():
    from services import krea_ai
    meta = krea_ai.get_model_meta("flux-1-dev")
    assert meta is not None
    assert meta["id"] == "flux-1-dev"
    assert "flux" in meta["path"].lower()


def test_get_model_meta_returns_none_for_unknown_id():
    from services import krea_ai
    assert krea_ai.get_model_meta("nonexistent-model-xyz") is None


def test_auth_headers_requires_env(monkeypatch):
    from services import krea_ai
    monkeypatch.setenv("KREA_API_KEY", "")
    with pytest.raises(ValueError, match="KREA_API_KEY"):
        krea_ai._auth_headers()


def test_auth_headers_uses_bearer_id_secret(monkeypatch):
    from services import krea_ai
    monkeypatch.setenv("KREA_API_KEY", "myid:mysecret")
    headers = krea_ai._auth_headers()
    assert headers["Authorization"] == "Bearer myid:mysecret"
    assert headers["Content-Type"] == "application/json"


def test_is_configured_true_when_key_set(monkeypatch):
    from services import krea_ai
    monkeypatch.setenv("KREA_API_KEY", "a:b")
    assert krea_ai.is_configured() is True


def test_is_configured_false_when_key_empty(monkeypatch):
    from services import krea_ai
    monkeypatch.setenv("KREA_API_KEY", "")
    assert krea_ai.is_configured() is False


def test_flagship_and_popular_models_present():
    """Regression guard — if someone drops a popular model from the curated
    list, catch it here before users notice."""
    from services import krea_ai
    ids = {m["id"] for m in krea_ai.KREA_IMAGE_MODELS}
    expected = {"krea-1", "flux-1-dev", "flux-1.1-pro", "imagen-4", "nano-banana-2", "ideogram-3.0"}
    missing = expected - ids
    assert not missing, f"Missing popular Krea models: {missing}"


# ---------------------------------------------------------------------------
# Endpoints: /api/krea/status and /api/krea/models (live backend)
# ---------------------------------------------------------------------------

def test_krea_status_requires_auth():
    r = requests.get(f"{BASE_URL}/api/krea/status", timeout=10)
    assert r.status_code in (401, 403)


def test_krea_status_reports_configured(auth_headers):
    r = requests.get(f"{BASE_URL}/api/krea/status", headers=auth_headers, timeout=10)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["configured"] is True
    assert data["models"] >= 10


def test_krea_models_requires_auth():
    r = requests.get(f"{BASE_URL}/api/krea/models", timeout=10)
    assert r.status_code in (401, 403)


def test_krea_models_returns_catalog(auth_headers):
    r = requests.get(f"{BASE_URL}/api/krea/models", headers=auth_headers, timeout=10)
    assert r.status_code == 200, r.text
    models = r.json()["models"]
    assert len(models) >= 10
    ids = {m["id"] for m in models}
    assert "flux-1-dev" in ids
    assert "krea-1" in ids
    assert "imagen-4" in ids
    assert "nano-banana-2" in ids


def test_krea_models_include_metadata(auth_headers):
    r = requests.get(f"{BASE_URL}/api/krea/models", headers=auth_headers, timeout=10)
    assert r.status_code == 200
    models = r.json()["models"]
    # Pick flux-1-dev and verify full metadata shape
    flux = next((m for m in models if m["id"] == "flux-1-dev"), None)
    assert flux is not None
    assert flux["label"]
    assert flux["description"]
    assert flux["tier"] in ("standard", "premium")
    assert flux["maxWidth"] > 0
    assert flux["approxCostUSD"] > 0
    assert flux["approxTimeSeconds"] > 0


# ---------------------------------------------------------------------------
# POST /api/krea/generate — input validation (no real Krea API hits)
# ---------------------------------------------------------------------------

def test_krea_generate_400_when_prompt_missing(auth_headers):
    r = requests.post(
        f"{BASE_URL}/api/krea/generate",
        headers=auth_headers,
        json={"modelId": "flux-1-dev", "prompt": ""},
        timeout=10,
    )
    assert r.status_code == 400


def test_krea_generate_400_when_model_unknown(auth_headers):
    r = requests.post(
        f"{BASE_URL}/api/krea/generate",
        headers=auth_headers,
        json={"modelId": "bogus-model-999", "prompt": "abc"},
        timeout=10,
    )
    assert r.status_code == 400


def test_krea_generate_400_when_modelid_missing(auth_headers):
    r = requests.post(
        f"{BASE_URL}/api/krea/generate",
        headers=auth_headers,
        json={"modelId": "", "prompt": "abc"},
        timeout=10,
    )
    assert r.status_code == 400


def test_krea_generate_requires_auth():
    r = requests.post(
        f"{BASE_URL}/api/krea/generate",
        json={"modelId": "flux-1-dev", "prompt": "abc"},
        timeout=10,
    )
    assert r.status_code in (401, 403)


# ---------------------------------------------------------------------------
# POST /api/krea/jobs/{id}/save — input validation
# ---------------------------------------------------------------------------

def test_krea_save_400_when_no_projectid(auth_headers):
    r = requests.post(
        f"{BASE_URL}/api/krea/jobs/fake-job-id/save",
        headers=auth_headers,
        json={},
        timeout=10,
    )
    assert r.status_code == 400


def test_krea_save_requires_auth():
    r = requests.post(
        f"{BASE_URL}/api/krea/jobs/fake-job-id/save",
        json={"projectId": "x"},
        timeout=10,
    )
    assert r.status_code in (401, 403)


# ---------------------------------------------------------------------------
# GET /api/admin/integrations-health — krea is part of the response
# ---------------------------------------------------------------------------

def test_health_check_includes_krea(auth_headers):
    """The admin integrations-health dashboard must include the Krea integration
    so admins can see its status alongside Leonardo/HeyGen/ElevenLabs/etc."""
    r = requests.get(
        f"{BASE_URL}/api/admin/integrations-health?_t=fresh",
        headers=auth_headers,
        timeout=15,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert "krea" in data["integrations"]
    krea_status = data["integrations"]["krea"]
    assert krea_status["status"] in ("ok", "error", "not_configured")
    # If the key is set in preview env, expect ok + model count
    if krea_status["status"] == "ok":
        assert krea_status.get("balance", {}).get("modelsAvailable", 0) >= 10


def test_health_check_krea_unit_no_key(monkeypatch):
    """Unit-level test of the _check_krea helper when key is absent."""
    import asyncio
    from routes import health as health_mod

    monkeypatch.setenv("KREA_API_KEY", "")
    result = asyncio.run(health_mod._check_krea())
    assert result["status"] == "not_configured"


def test_health_check_krea_unit_bad_format(monkeypatch):
    """Key without colon should be flagged as invalid format."""
    import asyncio
    from routes import health as health_mod

    monkeypatch.setenv("KREA_API_KEY", "no-colon-here")
    result = asyncio.run(health_mod._check_krea())
    assert result["status"] == "error"
    assert "format" in result["error"].lower() or "api_id" in result["error"].lower()
