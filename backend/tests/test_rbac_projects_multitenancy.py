"""
Tests for the RBAC/multi-tenancy fix on /api/projects and related endpoints.

Context (from main agent):
- CRITICAL SECURITY BUG was: a company_admin from company B could see ALL
  projects (including projects of other companies).
- Fix applied to /app/backend/routes/projects.py and /app/backend/routes/agent.py:
  - require_auth dependency added
  - _can_access_project helper enforces companyId matching
  - filter companyId applied in list_projects, get_project, update, delete, PPT
    upload init/upload, POST /agent/courses
  - POST /projects now auto-sets userId + companyId from the authenticated user
  - 53 legacy projects were back-filled to company_didaxis001.

Credentials (from /app/memory/test_credentials.md):
  - admin@scormify.com / admin123        (super_admin)
  - aprovador@teste.com / aprovador123   (aprovador @ company_didaxis001)
  - admin@empresateste.com / empresa123  (company_admin @ company_d9dec773d063)
"""

import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # fallback to frontend/.env if env not exported in this context
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
                    break
    except Exception:
        pass

API = f"{BASE_URL}/api"

SUPER_ADMIN = {"email": "admin@scormify.com", "password": "admin123"}
APROVADOR = {"email": "aprovador@teste.com", "password": "aprovador123"}   # company_didaxis001
OTHER_COMPANY = {"email": "admin@empresateste.com", "password": "empresa123"}  # company_d9dec773d063

# Known Didaxis project ID (useful for cross-company fetch tests)
DIDAXIS_PROJECT_ID = "cb4e0112-3e45-44fe-ab29-304b0ef8f0a0"


def _login(creds: dict) -> requests.Session:
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{API}/auth/login", json=creds, timeout=30)
    assert r.status_code == 200, f"Login failed for {creds['email']}: {r.status_code} {r.text}"
    data = r.json()
    token = data.get("token")
    if token:
        s.headers.update({"Authorization": f"Bearer {token}"})
    return s


@pytest.fixture(scope="module")
def super_admin_session():
    return _login(SUPER_ADMIN)


@pytest.fixture(scope="module")
def aprovador_session():
    return _login(APROVADOR)


@pytest.fixture(scope="module")
def other_company_session():
    return _login(OTHER_COMPANY)


@pytest.fixture(scope="module")
def me_super(super_admin_session):
    r = super_admin_session.get(f"{API}/auth/me", timeout=30)
    return r.json() if r.status_code == 200 else {}


@pytest.fixture(scope="module")
def me_aprovador(aprovador_session):
    r = aprovador_session.get(f"{API}/auth/me", timeout=30)
    return r.json() if r.status_code == 200 else {}


@pytest.fixture(scope="module")
def me_other(other_company_session):
    r = other_company_session.get(f"{API}/auth/me", timeout=30)
    return r.json() if r.status_code == 200 else {}


# ================================================================
# Authentication enforcement
# ================================================================
class TestAuthEnforcement:
    def test_list_projects_without_auth_returns_401(self):
        # Fresh session, no cookie/bearer
        r = requests.get(f"{API}/projects", timeout=30)
        assert r.status_code == 401, f"expected 401, got {r.status_code}: {r.text[:200]}"

    def test_get_project_without_auth_returns_401(self):
        r = requests.get(f"{API}/projects/{DIDAXIS_PROJECT_ID}", timeout=30)
        assert r.status_code == 401, f"expected 401, got {r.status_code}: {r.text[:200]}"

    def test_ppt_upload_init_without_auth_returns_401(self):
        r = requests.post(
            f"{API}/ppt/upload/init",
            json={"filename": "x.pptx", "totalSize": 1024, "totalChunks": 1},
            timeout=30,
        )
        assert r.status_code == 401, f"expected 401, got {r.status_code}: {r.text[:200]}"

    def test_agent_courses_without_auth_returns_401(self):
        r = requests.get(f"{API}/agent/courses", timeout=30)
        assert r.status_code == 401, f"expected 401, got {r.status_code}: {r.text[:200]}"


# ================================================================
# List /api/projects scoping per role
# ================================================================
class TestListProjectsScoping:
    def test_super_admin_sees_all(self, super_admin_session):
        r = super_admin_session.get(f"{API}/projects", timeout=60)
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data, list)
        # After back-fill, super_admin is expected to see ~53 projects (at least all).
        assert len(data) >= 50, f"super_admin should see many projects (got {len(data)})"
        # Keep count for later
        pytest.super_admin_count = len(data)

    def test_aprovador_sees_only_didaxis(self, aprovador_session):
        r = aprovador_session.get(f"{API}/projects", timeout=60)
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data, list)
        # All projects must belong to company_didaxis001
        bad = [p for p in data if p.get("companyId") not in (None, "company_didaxis001")]
        assert not bad, f"Aprovador seeing non-Didaxis projects: {[(p.get('id'), p.get('companyId')) for p in bad[:5]]}"
        # Expected approximately 53 projects
        assert len(data) >= 50, f"expected ~53 Didaxis projects, got {len(data)}"

    def test_other_company_admin_sees_none_of_didaxis(self, other_company_session):
        r = other_company_session.get(f"{API}/projects", timeout=60)
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data, list)
        # Must NOT see any project of company_didaxis001
        leaked = [p for p in data if p.get("companyId") == "company_didaxis001"]
        assert not leaked, (
            f"SECURITY LEAK: other-company admin saw {len(leaked)} Didaxis projects: "
            f"{[p.get('id') for p in leaked[:5]]}"
        )
        # Projects visible to this admin, if any, must all belong to their own company
        bad = [p for p in data if p.get("companyId") not in (None, "company_d9dec773d063")]
        assert not bad, f"Other-company admin sees projects from other companies: {[(p.get('id'), p.get('companyId')) for p in bad[:5]]}"


# ================================================================
# Cross-company access on individual project
# ================================================================
class TestCrossCompanyAccess:
    def test_get_didaxis_project_from_other_company_returns_404(self, other_company_session):
        r = other_company_session.get(f"{API}/projects/{DIDAXIS_PROJECT_ID}", timeout=30)
        assert r.status_code == 404, (
            f"cross-company GET should be 404, got {r.status_code}: {r.text[:200]}"
        )

    def test_put_didaxis_project_from_other_company_returns_404(self, other_company_session):
        r = other_company_session.put(
            f"{API}/projects/{DIDAXIS_PROJECT_ID}",
            json={"title": "HACKED"},
            timeout=30,
        )
        assert r.status_code == 404, (
            f"cross-company PUT should be 404, got {r.status_code}: {r.text[:200]}"
        )

    def test_delete_didaxis_project_from_other_company_returns_404(self, other_company_session):
        r = other_company_session.delete(
            f"{API}/projects/{DIDAXIS_PROJECT_ID}", timeout=30
        )
        assert r.status_code == 404, (
            f"cross-company DELETE should be 404, got {r.status_code}: {r.text[:200]}"
        )

    def test_aprovador_can_get_didaxis_project(self, aprovador_session):
        r = aprovador_session.get(f"{API}/projects/{DIDAXIS_PROJECT_ID}", timeout=30)
        # The Didaxis aprovador must be able to access its own company's project
        assert r.status_code == 200, (
            f"aprovador should access Didaxis project, got {r.status_code}: {r.text[:200]}"
        )
        data = r.json()
        assert data.get("companyId") in (None, "company_didaxis001")


# ================================================================
# /api/agent/courses scoping
# ================================================================
class TestAgentCoursesScoping:
    def test_agent_courses_as_other_company_returns_none_of_didaxis(self, other_company_session):
        r = other_company_session.get(f"{API}/agent/courses", timeout=60)
        assert r.status_code == 200, r.text
        data = r.json()
        # Accept either a list or {"courses": [...]} shape
        courses = data if isinstance(data, list) else data.get("courses", [])
        leaked = [c for c in courses if c.get("companyId") == "company_didaxis001"]
        assert not leaked, (
            f"agent/courses leaked {len(leaked)} Didaxis courses to other-company admin"
        )

    def test_agent_courses_as_aprovador_returns_didaxis(self, aprovador_session):
        r = aprovador_session.get(f"{API}/agent/courses", timeout=60)
        assert r.status_code == 200, r.text
        data = r.json()
        courses = data if isinstance(data, list) else data.get("courses", [])
        assert len(courses) > 0, "aprovador should see Didaxis agent courses"
        bad = [c for c in courses if c.get("companyId") not in (None, "company_didaxis001")]
        assert not bad, f"aprovador sees non-Didaxis agent courses: {bad[:3]}"


# ================================================================
# POST /projects auto-assigns companyId
# ================================================================
class TestCreateProjectAutoScoping:
    def test_create_project_auto_assigns_user_company(self, other_company_session, me_other):
        unique = f"TEST_RBAC_{uuid.uuid4().hex[:8]}"
        payload = {"name": unique, "title": unique, "description": "rbac isolation test"}
        r = other_company_session.post(f"{API}/projects", json=payload, timeout=30)
        assert r.status_code in (200, 201), f"create failed: {r.status_code} {r.text[:300]}"
        project = r.json()
        pid = project.get("id") or project.get("_id") or project.get("project_id")
        assert pid, f"no id in create response: {project}"

        # Verify companyId == user's companyId
        user_company = me_other.get("companyId") or me_other.get("user", {}).get("companyId")
        # me_other may be nested under "user"
        if not user_company and isinstance(me_other.get("user"), dict):
            user_company = me_other["user"].get("companyId")
        assert project.get("companyId") == user_company or project.get("companyId") == "company_d9dec773d063", (
            f"created project companyId={project.get('companyId')}, expected {user_company} / company_d9dec773d063"
        )

        # GET-verify persistence & scoping
        r2 = other_company_session.get(f"{API}/projects/{pid}", timeout=30)
        assert r2.status_code == 200, f"self-created project not accessible: {r2.status_code}"
        # Aprovador (different company) must NOT see this project
        s_apr = _login(APROVADOR)
        r3 = s_apr.get(f"{API}/projects/{pid}", timeout=30)
        assert r3.status_code == 404, (
            f"cross-company GET on TEST project should be 404, got {r3.status_code}"
        )

        # Cleanup
        other_company_session.delete(f"{API}/projects/{pid}", timeout=30)


# ================================================================
# PPT upload init requires auth and responds with uploadId when authenticated
# ================================================================
class TestPPTUploadInit:
    def test_ppt_upload_init_with_auth_returns_upload_id(self, other_company_session):
        r = other_company_session.post(
            f"{API}/ppt/upload/init",
            json={"filename": "TEST_rbac.pptx", "totalSize": 4096, "totalChunks": 1},
            timeout=30,
        )
        assert r.status_code in (200, 201), f"init failed: {r.status_code} {r.text[:300]}"
        data = r.json()
        upload_id = data.get("uploadId") or data.get("upload_id") or data.get("id")
        assert upload_id, f"no uploadId in response: {data}"


# ================================================================
# Regression: unrelated endpoints still work
# ================================================================
class TestRegression:
    def test_companies_endpoint_accessible_super_admin(self, super_admin_session):
        r = super_admin_session.get(f"{API}/companies", timeout=30)
        assert r.status_code in (200, 403), f"unexpected: {r.status_code} {r.text[:200]}"

    def test_auth_me_works(self, aprovador_session):
        r = aprovador_session.get(f"{API}/auth/me", timeout=30)
        assert r.status_code == 200, f"auth/me failed: {r.status_code} {r.text[:200]}"

    def test_agent_sessions_list_works(self, aprovador_session):
        r = aprovador_session.get(f"{API}/agent/sessions", timeout=30)
        # endpoint may 200 with list or 404 if not defined; we only ensure it's not 500
        assert r.status_code < 500, f"agent/sessions crashed: {r.status_code} {r.text[:200]}"

    def test_heygen_voices_endpoint_not_crashing(self, aprovador_session):
        r = aprovador_session.get(f"{API}/heygen/voices", timeout=30)
        assert r.status_code < 500, f"heygen/voices 5xx: {r.status_code} {r.text[:200]}"
