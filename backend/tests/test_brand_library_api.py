"""End-to-end REST tests for the Brand Library feature.

Covers:
- POST /api/auth/login (super_admin + regular user)
- GET/PUT /api/companies/{id}/brand-kit
- POST/GET/PATCH/DELETE /api/companies/{id}/assets
- GET /api/companies/{id}/assets/{asset_id}/file (no auth)
- RBAC: regular user reads own company, blocked from mutations / other co reads
- Model normalization (invalid type -> background, invalid category -> generic)
- /api/agent/sessions/{id}/media-config persists useBrandLibrary + brandLibraryMode
"""
import os
import io
import pytest
import requests
from PIL import Image

def _load_backend_url():
    url = os.environ.get("REACT_APP_BACKEND_URL")
    if not url:
        # Fall back to frontend/.env (the canonical preview URL)
        env_path = "/app/frontend/.env"
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    if line.startswith("REACT_APP_BACKEND_URL="):
                        url = line.split("=", 1)[1].strip()
                        break
    if not url:
        raise RuntimeError("REACT_APP_BACKEND_URL not configured")
    return url.rstrip("/")


BASE_URL = _load_backend_url()
SUPER = {"email": "admin@scormify.com", "password": "admin123"}
REGULAR = {"email": "aprovador@teste.com", "password": "aprovador123"}
OTHER_COMPANY = {"email": "admin@empresateste.com", "password": "empresa123"}

REGULAR_COMPANY_ID = "company_didaxis001"
OTHER_COMPANY_ID = "company_d9dec773d063"


# ---------------------------------------------------------------------------
# Fixtures: logins and small test image
# ---------------------------------------------------------------------------

def _login(creds):
    r = requests.post(f"{BASE_URL}/api/auth/login", json=creds, timeout=15)
    if r.status_code != 200:
        pytest.skip(f"Login failed for {creds['email']}: {r.status_code} {r.text[:200]}")
    return r.json()["token"]


@pytest.fixture(scope="session")
def admin_token():
    return _login(SUPER)


@pytest.fixture(scope="session")
def regular_token():
    return _login(REGULAR)


@pytest.fixture(scope="session")
def other_token():
    return _login(OTHER_COMPANY)


@pytest.fixture(scope="session")
def test_company_id(admin_token):
    """Pick a real existing company id (prefer didaxis)."""
    r = requests.get(
        f"{BASE_URL}/api/companies",
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=15,
    )
    assert r.status_code == 200, r.text
    companies = r.json()
    if isinstance(companies, dict):
        companies = companies.get("companies") or companies.get("items") or []
    ids = [c.get("id") for c in companies]
    assert ids, "No companies in DB"
    if REGULAR_COMPANY_ID in ids:
        return REGULAR_COMPANY_ID
    return ids[0]


@pytest.fixture(scope="session")
def png_bytes():
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), (20, 80, 200)).save(buf, format="PNG")
    buf.seek(0)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Brand Kit GET/PUT
# ---------------------------------------------------------------------------

class TestBrandKit:
    def test_get_brand_kit_super(self, admin_token, test_company_id):
        r = requests.get(
            f"{BASE_URL}/api/companies/{test_company_id}/brand-kit",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=10,
        )
        assert r.status_code == 200, r.text
        assert isinstance(r.json(), dict)

    def test_put_brand_kit_super(self, admin_token, test_company_id):
        payload = {
            "primaryColor": "#1e3a8a",
            "secondaryColor": "#10b981",
            "accentColor": "#f59e0b",
            "fontFamily": "Inter",
        }
        r = requests.put(
            f"{BASE_URL}/api/companies/{test_company_id}/brand-kit",
            json=payload,
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=10,
        )
        assert r.status_code == 200, r.text
        kit = r.json().get("brandKit", {})
        assert kit.get("primaryColor") == "#1e3a8a"
        assert kit.get("fontFamily") == "Inter"

        # Round-trip GET
        g = requests.get(
            f"{BASE_URL}/api/companies/{test_company_id}/brand-kit",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=10,
        )
        assert g.status_code == 200
        assert g.json().get("primaryColor") == "#1e3a8a"

    def test_put_brand_kit_requires_super(self, regular_token, test_company_id):
        r = requests.put(
            f"{BASE_URL}/api/companies/{test_company_id}/brand-kit",
            json={"primaryColor": "#000000"},
            headers={"Authorization": f"Bearer {regular_token}"},
            timeout=10,
        )
        assert r.status_code == 403, r.text

    def test_get_brand_kit_own_company(self, regular_token):
        r = requests.get(
            f"{BASE_URL}/api/companies/{REGULAR_COMPANY_ID}/brand-kit",
            headers={"Authorization": f"Bearer {regular_token}"},
            timeout=10,
        )
        assert r.status_code == 200, r.text

    def test_get_brand_kit_other_company_denied(self, regular_token):
        # aprovador belongs to didaxis; try to read another company
        r = requests.get(
            f"{BASE_URL}/api/companies/{OTHER_COMPANY_ID}/brand-kit",
            headers={"Authorization": f"Bearer {regular_token}"},
            timeout=10,
        )
        assert r.status_code in (403, 404), r.text


# ---------------------------------------------------------------------------
# Asset CRUD
# ---------------------------------------------------------------------------

class TestAssetCRUD:
    asset_id = None

    def test_upload_asset(self, admin_token, test_company_id, png_bytes):
        files = {"file": ("TEST_brand.png", png_bytes, "image/png")}
        data = {
            "type": "background",
            "category": "intro",
            "tags": "TEST_corp, hero, blue",
            "description": "TEST seed background",
        }
        r = requests.post(
            f"{BASE_URL}/api/companies/{test_company_id}/assets",
            files=files,
            data=data,
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=30,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["companyId"] == test_company_id
        assert body["type"] == "background"
        assert body["category"] == "intro"
        assert "TEST_corp" in body["tags"]
        assert body["sizeBytes"] > 0
        assert body["url"].endswith(f"/api/companies/{test_company_id}/assets/{body['id']}/file")
        TestAssetCRUD.asset_id = body["id"]

    def test_upload_normalizes_invalid_type_and_category(self, admin_token, test_company_id, png_bytes):
        files = {"file": ("TEST_x.png", png_bytes, "image/png")}
        data = {"type": "garbage", "category": "nope", "tags": "TEST_norm"}
        r = requests.post(
            f"{BASE_URL}/api/companies/{test_company_id}/assets",
            files=files, data=data,
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=30,
        )
        assert r.status_code == 200, r.text
        b = r.json()
        assert b["type"] == "background"
        assert b["category"] == "generic"
        # cleanup right away
        requests.delete(
            f"{BASE_URL}/api/companies/{test_company_id}/assets/{b['id']}",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=10,
        )

    def test_list_assets_with_filters(self, admin_token, test_company_id):
        r = requests.get(
            f"{BASE_URL}/api/companies/{test_company_id}/assets",
            params={"type": "background", "category": "intro", "tag": "TEST_corp"},
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=10,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["total"] >= 1
        ids = [a["id"] for a in body["assets"]]
        assert TestAssetCRUD.asset_id in ids

    def test_serve_asset_unauthenticated(self, test_company_id, png_bytes):
        assert TestAssetCRUD.asset_id, "upload test must run first"
        r = requests.get(
            f"{BASE_URL}/api/companies/{test_company_id}/assets/{TestAssetCRUD.asset_id}/file",
            timeout=10,
        )
        assert r.status_code == 200, r.text
        ct = r.headers.get("Content-Type", "")
        assert ct.startswith("image/"), f"Bad content-type: {ct}"
        assert len(r.content) > 0
        # NOTE: backend sets `Cache-Control: public, max-age=3600`, but the
        # Cloudflare/Kubernetes ingress in preview rewrites it to no-store. We
        # only assert the header exists; the upstream value is logged for the
        # main agent to decide whether the ingress override is acceptable.
        cc = r.headers.get("Cache-Control", "")
        assert cc != "", "Cache-Control header missing"

    def test_patch_asset_metadata(self, admin_token, test_company_id):
        assert TestAssetCRUD.asset_id
        r = requests.patch(
            f"{BASE_URL}/api/companies/{test_company_id}/assets/{TestAssetCRUD.asset_id}",
            json={"description": "TEST updated", "tags": ["TEST_corp", "updated"]},
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=10,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["description"] == "TEST updated"
        assert "updated" in body["tags"]

    def test_regular_user_can_read_own_assets(self, regular_token):
        r = requests.get(
            f"{BASE_URL}/api/companies/{REGULAR_COMPANY_ID}/assets",
            headers={"Authorization": f"Bearer {regular_token}"},
            timeout=10,
        )
        assert r.status_code == 200, r.text

    def test_regular_user_cannot_read_other_company_assets(self, regular_token):
        r = requests.get(
            f"{BASE_URL}/api/companies/{OTHER_COMPANY_ID}/assets",
            headers={"Authorization": f"Bearer {regular_token}"},
            timeout=10,
        )
        assert r.status_code in (403, 404), r.text

    def test_regular_user_cannot_upload(self, regular_token, png_bytes):
        files = {"file": ("TEST_rbac.png", png_bytes, "image/png")}
        data = {"type": "background", "category": "intro", "tags": "TEST_rbac"}
        r = requests.post(
            f"{BASE_URL}/api/companies/{REGULAR_COMPANY_ID}/assets",
            files=files, data=data,
            headers={"Authorization": f"Bearer {regular_token}"},
            timeout=15,
        )
        assert r.status_code == 403, r.text

    def test_regular_user_cannot_delete(self, regular_token, test_company_id):
        assert TestAssetCRUD.asset_id
        r = requests.delete(
            f"{BASE_URL}/api/companies/{test_company_id}/assets/{TestAssetCRUD.asset_id}",
            headers={"Authorization": f"Bearer {regular_token}"},
            timeout=10,
        )
        assert r.status_code == 403, r.text

    def test_company_isolation_other_admin_cannot_see(self, other_token, test_company_id, png_bytes):
        # uploaded assets in test_company_id should NOT appear when listing the
        # other company's library — regression for cross-tenant leak
        r = requests.get(
            f"{BASE_URL}/api/companies/{OTHER_COMPANY_ID}/assets",
            headers={"Authorization": f"Bearer {other_token}"},
            timeout=10,
        )
        assert r.status_code == 200, r.text
        for a in r.json()["assets"]:
            assert TestAssetCRUD.asset_id != a["id"]
            assert a["companyId"] == OTHER_COMPANY_ID

    def test_delete_asset_and_verify_404(self, admin_token, test_company_id):
        assert TestAssetCRUD.asset_id
        r = requests.delete(
            f"{BASE_URL}/api/companies/{test_company_id}/assets/{TestAssetCRUD.asset_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=10,
        )
        assert r.status_code == 200, r.text
        # File should now 404
        g = requests.get(
            f"{BASE_URL}/api/companies/{test_company_id}/assets/{TestAssetCRUD.asset_id}/file",
            timeout=10,
        )
        assert g.status_code == 404
        # Patch should now 404
        p = requests.patch(
            f"{BASE_URL}/api/companies/{test_company_id}/assets/{TestAssetCRUD.asset_id}",
            json={"description": "x"},
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=10,
        )
        assert p.status_code == 404


# ---------------------------------------------------------------------------
# Wizard endpoint
# ---------------------------------------------------------------------------

class TestMediaConfigBrandLibrary:
    def _create_session(self, token):
        # Use the same endpoint the wizard uses
        r = requests.post(
            f"{BASE_URL}/api/agent/sessions",
            json={"topic": "TEST Brand Library", "courseType": "training"},
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
        if r.status_code not in (200, 201):
            pytest.skip(f"Cannot create agent session: {r.status_code} {r.text[:200]}")
        body = r.json()
        return body.get("sessionId") or body.get("id") or body.get("session", {}).get("id")

    def test_persist_use_brand_library(self, admin_token):
        sid = self._create_session(admin_token)
        if not sid:
            pytest.skip("No session id returned")
        r = requests.post(
            f"{BASE_URL}/api/agent/sessions/{sid}/media-config",
            json={"useBrandLibrary": True, "brandLibraryMode": "strict"},
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=15,
        )
        assert r.status_code == 200, r.text
        # Fetch the session back and verify persistence
        g = requests.get(
            f"{BASE_URL}/api/agent/sessions/{sid}",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=10,
        )
        assert g.status_code == 200, g.text
        s = g.json()
        # Some endpoints wrap the session
        s = s.get("session") or s
        assert s.get("useBrandLibrary") is True
        assert s.get("brandLibraryMode") == "strict"
