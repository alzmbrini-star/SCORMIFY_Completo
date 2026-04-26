"""
P2 Backend: RBAC re-test for /agent/courses/{id}/* and /agent/projects/{id}/* endpoints
Plus smoke test for the new /app/backend/routes/agent_approvals.py module.

Covers:
- 11 sub-resource endpoints: anon -> 401, cross-company -> 404, same-company -> 200/4xx (NOT 401/404)
- Approval queue + approve/reject endpoints (RBAC + 404 for non-existent IDs)
- /agent/clear-stuck-caches: anon -> 401, aprovador -> 403, super_admin -> 200
"""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # Fallback: read from frontend/.env (the Source of truth for public URL)
    try:
        with open("/app/frontend/.env") as _f:
            for _line in _f:
                if _line.startswith("REACT_APP_BACKEND_URL="):
                    BASE_URL = _line.split("=", 1)[1].strip().rstrip("/")
                    break
    except Exception:
        pass
DIDAXIS_PROJECT_ID = "cb4e0112-3e45-44fe-ab29-304b0ef8f0a0"

SUPER_ADMIN = ("admin@scormify.com", "admin123")
APROVADOR = ("aprovador@teste.com", "aprovador123")
CROSS_COMPANY_ADMIN = ("admin@empresateste.com", "empresa123")


def _login(email, password):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, f"login failed for {email}: {r.status_code} {r.text}"
    return r.json().get("token")


@pytest.fixture(scope="module")
def super_admin_headers():
    return {"Authorization": f"Bearer {_login(*SUPER_ADMIN)}"}


@pytest.fixture(scope="module")
def aprovador_headers():
    return {"Authorization": f"Bearer {_login(*APROVADOR)}"}


@pytest.fixture(scope="module")
def cross_company_headers():
    return {"Authorization": f"Bearer {_login(*CROSS_COMPANY_ADMIN)}"}


# ENDPOINTS: list of (method, path_template, payload_or_None)
# path_template uses {pid} placeholder for project_id
SUBRESOURCE_ENDPOINTS = [
    ("POST", "/api/agent/courses/{pid}/analyze", {}),
    ("POST", "/api/agent/courses/{pid}/preview-improvements", {"improvements": []}),
    ("POST", "/api/agent/courses/{pid}/apply-improvements", {"improvements": []}),
    ("POST", "/api/agent/courses/{pid}/undo-improvements", {}),
    ("GET", "/api/agent/projects/{pid}/heygen-status", None),
    ("POST", "/api/agent/projects/{pid}/generate-narration", {}),
    ("GET", "/api/agent/projects/{pid}/narration-status", None),
    ("GET", "/api/agent/projects/{pid}/avatar-settings", None),
    ("PUT", "/api/agent/projects/{pid}/avatar-settings",
        {"avatarType": "heygen", "voiceId": "v1", "voiceProvider": "elevenlabs"}),
    ("GET", "/api/agent/projects/{pid}/avatar-generation-status", None),
]


def _do(method, url, headers=None, json_body=None):
    return requests.request(method, url, headers=headers or {}, json=json_body, timeout=30)


# -------------------- ANONYMOUS -> 401 --------------------
class TestAnonymousReturns401:
    @pytest.mark.parametrize("method,path,body", SUBRESOURCE_ENDPOINTS)
    def test_anon_subresource_401(self, method, path, body):
        url = f"{BASE_URL}{path.format(pid=DIDAXIS_PROJECT_ID)}"
        r = _do(method, url, json_body=body)
        assert r.status_code == 401, f"{method} {path}: expected 401, got {r.status_code} {r.text[:200]}"

    # Also test submit-improvements-for-approval (now in agent_approvals.py)
    def test_anon_submit_for_approval_401(self):
        url = f"{BASE_URL}/api/agent/courses/{DIDAXIS_PROJECT_ID}/submit-improvements-for-approval"
        r = _do("POST", url, json_body={"previewId": "x", "targetCompanyId": "y"})
        assert r.status_code == 401

    def test_anon_approval_queue_401(self):
        r = _do("GET", f"{BASE_URL}/api/agent/approval-queue")
        assert r.status_code == 401

    def test_anon_approve_improvement_401(self):
        fake_id = str(uuid.uuid4())
        r = _do("POST", f"{BASE_URL}/api/agent/improvement-approvals/{fake_id}/approve", json_body={})
        assert r.status_code == 401

    def test_anon_reject_improvement_401(self):
        fake_id = str(uuid.uuid4())
        r = _do("POST", f"{BASE_URL}/api/agent/improvement-approvals/{fake_id}/reject", json_body={"reason": ""})
        assert r.status_code == 401

    def test_anon_clear_stuck_caches_401(self):
        r = _do("POST", f"{BASE_URL}/api/agent/clear-stuck-caches", json_body={})
        assert r.status_code == 401


# -------------------- CROSS-COMPANY -> 404 --------------------
class TestCrossCompanyReturns404:
    @pytest.mark.parametrize("method,path,body", SUBRESOURCE_ENDPOINTS)
    def test_cross_company_subresource_404(self, method, path, body, cross_company_headers):
        url = f"{BASE_URL}{path.format(pid=DIDAXIS_PROJECT_ID)}"
        r = _do(method, url, headers=cross_company_headers, json_body=body)
        assert r.status_code == 404, (
            f"{method} {path}: cross-company expected 404, got {r.status_code} {r.text[:200]}"
        )

    def test_cross_company_submit_for_approval_404(self, cross_company_headers):
        url = f"{BASE_URL}/api/agent/courses/{DIDAXIS_PROJECT_ID}/submit-improvements-for-approval"
        r = _do("POST", url, headers=cross_company_headers,
                json_body={"previewId": "x", "targetCompanyId": "y"})
        assert r.status_code == 404


# -------------------- SAME-COMPANY -> NOT 401/404 --------------------
class TestSameCompanyAllowed:
    """Same-company aprovador/super_admin must pass past require_auth + load_authorized_project.
    Acceptable status codes: 200, 400 (validation), 422 (pydantic), 500 (downstream issue
    unrelated to RBAC). NEVER 401 or 404."""

    @pytest.mark.parametrize("method,path,body", SUBRESOURCE_ENDPOINTS)
    def test_aprovador_same_company_passes_rbac(self, method, path, body, aprovador_headers):
        url = f"{BASE_URL}{path.format(pid=DIDAXIS_PROJECT_ID)}"
        r = _do(method, url, headers=aprovador_headers, json_body=body)
        assert r.status_code not in (401, 404), (
            f"{method} {path}: same-company should pass RBAC, got {r.status_code} {r.text[:200]}"
        )

    def test_super_admin_subresources_pass(self, super_admin_headers):
        # Spot-check a couple via super_admin (should also pass)
        for method, path, body in SUBRESOURCE_ENDPOINTS[:3]:
            url = f"{BASE_URL}{path.format(pid=DIDAXIS_PROJECT_ID)}"
            r = _do(method, url, headers=super_admin_headers, json_body=body)
            assert r.status_code not in (401, 404), (
                f"super_admin {method} {path}: got {r.status_code}"
            )


# -------------------- APPROVAL QUEUE + APPROVE/REJECT --------------------
class TestApprovalEndpoints:
    def test_approval_queue_aprovador_returns_list(self, aprovador_headers):
        r = _do("GET", f"{BASE_URL}/api/agent/approval-queue", headers=aprovador_headers)
        assert r.status_code == 200, f"queue: {r.status_code} {r.text[:200]}"
        data = r.json()
        assert isinstance(data, list)

    def test_approval_queue_super_admin_returns_list(self, super_admin_headers):
        r = _do("GET", f"{BASE_URL}/api/agent/approval-queue", headers=super_admin_headers)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_approve_fake_id_returns_404(self, aprovador_headers):
        fake_id = str(uuid.uuid4())
        r = _do("POST", f"{BASE_URL}/api/agent/improvement-approvals/{fake_id}/approve",
                headers=aprovador_headers, json_body={})
        assert r.status_code == 404, f"expected 404 for fake id, got {r.status_code} {r.text[:200]}"

    def test_reject_fake_id_returns_404(self, aprovador_headers):
        fake_id = str(uuid.uuid4())
        r = _do("POST", f"{BASE_URL}/api/agent/improvement-approvals/{fake_id}/reject",
                headers=aprovador_headers, json_body={"reason": "test"})
        assert r.status_code == 404


# -------------------- CLEAR STUCK CACHES (super_admin only) --------------------
class TestClearStuckCaches:
    def test_aprovador_forbidden_403(self, aprovador_headers):
        r = _do("POST", f"{BASE_URL}/api/agent/clear-stuck-caches",
                headers=aprovador_headers, json_body={})
        assert r.status_code == 403, f"aprovador: expected 403, got {r.status_code} {r.text[:200]}"

    def test_super_admin_allowed_200(self, super_admin_headers):
        r = _do("POST", f"{BASE_URL}/api/agent/clear-stuck-caches",
                headers=super_admin_headers, json_body={})
        assert r.status_code == 200, f"super_admin: expected 200, got {r.status_code} {r.text[:200]}"
        body = r.json()
        assert "cachesCleared" in body
        assert "stuckSessionsReset" in body
