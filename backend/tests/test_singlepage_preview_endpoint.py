"""Tests for the Single Page Live Preview endpoint."""
from __future__ import annotations

import os
import requests


BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or "http://localhost:8001").rstrip("/")


def _login():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": "admin@scormify.com", "password": "admin123"},
        timeout=10,
    )
    r.raise_for_status()
    return r.json()["token"]


def _first_project_id(token):
    r = requests.get(f"{BASE_URL}/api/projects",
                       headers={"Authorization": f"Bearer {token}"}, timeout=10)
    r.raise_for_status()
    data = r.json()
    projs = data if isinstance(data, list) else data.get("projects", [])
    return projs[0]["id"] if projs else None


def test_preview_requires_auth():
    pid = "fake-id"
    r = requests.get(f"{BASE_URL}/api/projects/{pid}/preview-singlepage", timeout=10)
    assert r.status_code in (401, 403)


def test_preview_returns_404_for_unknown_project():
    token = _login()
    r = requests.get(
        f"{BASE_URL}/api/projects/nonexistent-uuid-1234/preview-singlepage",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    assert r.status_code == 404


def test_preview_returns_html_for_real_project():
    token = _login()
    pid = _first_project_id(token)
    if not pid:
        # Skip silently if no projects exist in the DB
        return
    r = requests.get(
        f"{BASE_URL}/api/projects/{pid}/preview-singlepage",
        headers={"Authorization": f"Bearer {token}"},
        timeout=60,
    )
    assert r.status_code == 200, r.text[:500]
    assert "text/html" in r.headers.get("content-type", "")
    body = r.text
    # Must contain the Single Page markers
    assert "<!DOCTYPE html>" in body
    assert "sp-section" in body
    # No-cache header so the preview always reflects the latest project state
    cache_control = r.headers.get("cache-control", "")
    assert "no-store" in cache_control or "no-cache" in cache_control


def test_preview_blocks_cross_company_access():
    """A regular admin from another company cannot preview a project that
    doesn't belong to their company."""
    # Try to login as the company-level admin (test_credentials.md fallback)
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": "admin@empresateste.com", "password": "empresa123"},
        timeout=10,
    )
    if r.status_code != 200:
        # Test user not seeded — skip silently
        return
    other_token = r.json()["token"]
    super_token = _login()
    pid = _first_project_id(super_token)
    if not pid:
        return
    # Get the project and check if it belongs to a different company than the
    # other_admin. If they happen to share company, skip.
    proj_resp = requests.get(
        f"{BASE_URL}/api/projects/{pid}",
        headers={"Authorization": f"Bearer {super_token}"}, timeout=10,
    )
    if proj_resp.status_code != 200:
        return
    proj_company = proj_resp.json().get("companyId")
    me = requests.get(
        f"{BASE_URL}/api/auth/me",
        headers={"Authorization": f"Bearer {other_token}"}, timeout=10,
    )
    if me.status_code != 200:
        return
    other_company = me.json().get("companyId")
    if proj_company == other_company:
        return  # same company — would legitimately have access
    # Different companies → expect 403 or 404
    r = requests.get(
        f"{BASE_URL}/api/projects/{pid}/preview-singlepage",
        headers={"Authorization": f"Bearer {other_token}"}, timeout=30,
    )
    assert r.status_code in (403, 404)
