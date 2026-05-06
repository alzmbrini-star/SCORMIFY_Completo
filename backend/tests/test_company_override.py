"""Tests for company override on project creation + cost report endpoint.

Covers:
- POST /api/projects accepts companyId from super_admin (and uses it)
- POST /api/projects with companyId from regular admin (silently dropped)
- POST /api/projects with invalid companyId (400)
- PUT /api/projects/{id} with companyId (super_admin reassigns; regular admin dropped)
- POST /api/agent/sessions accepts companyId
- GET /api/admin/cost-report returns aggregated structure
"""
from __future__ import annotations

import os
import requests


BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or "http://localhost:8001").rstrip("/")


def _login_super():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": "admin@scormify.com", "password": "admin123"},
        timeout=10,
    )
    r.raise_for_status()
    return r.json()["token"], r.json().get("user", {})


def _login_company():
    """Optional company-scoped admin (skip silently if not seeded)."""
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": "admin@empresateste.com", "password": "empresa123"},
        timeout=10,
    )
    if r.status_code != 200:
        return None, None
    return r.json()["token"], r.json().get("user", {})


def _list_companies(token):
    r = requests.get(f"{BASE_URL}/api/companies",
                       headers={"Authorization": f"Bearer {token}"}, timeout=10)
    if r.status_code != 200:
        return []
    data = r.json()
    return data if isinstance(data, list) else data.get("companies", [])


def test_create_project_super_admin_sets_company():
    """Super_admin can attribute a new project to a different company."""
    token, _user = _login_super()
    companies = _list_companies(token)
    if len(companies) < 2:
        return  # need at least 2 companies to verify cross-company assignment
    target = companies[0]["id"]
    r = requests.post(
        f"{BASE_URL}/api/projects",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"name": "Test cross-company project", "companyId": target},
        timeout=15,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["companyId"] == target


def test_create_project_invalid_company_400():
    token, _ = _login_super()
    r = requests.post(
        f"{BASE_URL}/api/projects",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"name": "Test bad", "companyId": "no-such-company"},
        timeout=15,
    )
    assert r.status_code == 400, r.text


def test_create_project_no_companyid_uses_user_company():
    """Without companyId, the project inherits the creator's companyId."""
    token, user = _login_super()
    r = requests.post(
        f"{BASE_URL}/api/projects",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"name": "Test default company"},
        timeout=15,
    )
    assert r.status_code == 200
    if user.get("companyId"):
        assert r.json()["companyId"] == user["companyId"]


def test_regular_admin_cannot_override_company():
    """A non-super-admin cannot reattribute via the body — companyId is
    silently ignored and falls back to user's own."""
    super_token, _ = _login_super()
    other_token, other_user = _login_company()
    if not other_token:
        return
    companies = _list_companies(super_token)
    # Pick a company that's NOT the regular admin's
    foreign = next((c for c in companies if c["id"] != other_user.get("companyId")), None)
    if not foreign:
        return
    r = requests.post(
        f"{BASE_URL}/api/projects",
        headers={"Authorization": f"Bearer {other_token}", "Content-Type": "application/json"},
        json={"name": "Try foreign company", "companyId": foreign["id"]},
        timeout=15,
    )
    assert r.status_code == 200, r.text
    # Should fall back to the regular admin's own companyId
    assert r.json()["companyId"] == other_user.get("companyId")


def test_update_project_super_admin_can_reassign():
    """Super_admin can move an existing project to a different company."""
    token, _ = _login_super()
    companies = _list_companies(token)
    if len(companies) < 2:
        return
    # Create a project owned by company A, then move to company B
    a, b = companies[0]["id"], companies[1]["id"]
    create = requests.post(
        f"{BASE_URL}/api/projects",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"name": "Reassign me", "companyId": a},
        timeout=15,
    )
    assert create.status_code == 200
    pid = create.json()["id"]
    upd = requests.put(
        f"{BASE_URL}/api/projects/{pid}",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"companyId": b},
        timeout=15,
    )
    assert upd.status_code == 200, upd.text
    # Verify via GET
    fetch = requests.get(
        f"{BASE_URL}/api/projects/{pid}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    assert fetch.status_code == 200
    assert fetch.json()["companyId"] == b


def test_update_project_regular_admin_cannot_reassign():
    super_token, _ = _login_super()
    other_token, other_user = _login_company()
    if not other_token:
        return
    # Create project owned by the regular admin's own company
    create = requests.post(
        f"{BASE_URL}/api/projects",
        headers={"Authorization": f"Bearer {other_token}", "Content-Type": "application/json"},
        json={"name": "Cannot reassign me"},
        timeout=15,
    )
    assert create.status_code == 200
    pid = create.json()["id"]
    own_company = other_user.get("companyId")
    # Try to reassign to a DIFFERENT company — should silently drop
    companies = _list_companies(super_token)
    foreign = next((c for c in companies if c["id"] != own_company), None)
    if not foreign:
        return
    upd = requests.put(
        f"{BASE_URL}/api/projects/{pid}",
        headers={"Authorization": f"Bearer {other_token}", "Content-Type": "application/json"},
        json={"companyId": foreign["id"]},
        timeout=15,
    )
    assert upd.status_code == 200
    # Verify project still belongs to the original company
    fetch = requests.get(
        f"{BASE_URL}/api/projects/{pid}",
        headers={"Authorization": f"Bearer {other_token}"},
        timeout=10,
    )
    assert fetch.status_code == 200
    assert fetch.json()["companyId"] == own_company


def test_create_agent_session_with_company_id():
    token, _ = _login_super()
    companies = _list_companies(token)
    if not companies:
        return
    target = companies[0]["id"]
    r = requests.post(
        f"{BASE_URL}/api/agent/sessions",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"contentText": "test content", "companyId": target},
        timeout=15,
    )
    assert r.status_code == 200, r.text
    assert r.json().get("companyId") == target


def test_cost_report_requires_super_admin():
    """Regular admin gets empty companies + access denied message."""
    other_token, _ = _login_company()
    if not other_token:
        return
    r = requests.get(
        f"{BASE_URL}/api/admin/cost-report",
        headers={"Authorization": f"Bearer {other_token}"},
        timeout=15,
    )
    # Either 403 OR 200 with empty companies + denial message
    if r.status_code == 200:
        body = r.json()
        assert body.get("companies") == []
        assert "super-admin" in (body.get("detail") or "").lower()
    else:
        assert r.status_code in (401, 403)


def test_cost_report_super_admin_returns_companies():
    token, _ = _login_super()
    r = requests.get(
        f"{BASE_URL}/api/admin/cost-report",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert "companies" in data
    assert "generatedAt" in data
    # Each company entry has the expected shape
    for c in data["companies"]:
        assert "companyId" in c
        assert "companyName" in c
        assert "projects" in c and "total" in c["projects"]
        assert "krea" in c and "total" in c["krea"]
        assert "leonardo" in c and "total" in c["leonardo"]
        assert "tutor" in c and "total" in c["tutor"]


def test_cost_report_supports_date_filters():
    """from/to ISO dates filter the createdAt of all aggregated collections."""
    token, _ = _login_super()
    r = requests.get(
        f"{BASE_URL}/api/admin/cost-report",
        headers={"Authorization": f"Bearer {token}"},
        params={"from": "2099-01-01", "to": "2099-12-31"},  # future range — empty
        timeout=20,
    )
    assert r.status_code == 200
    data = r.json()
    # All counts should be zero for a future date range
    for c in data["companies"]:
        assert c["projects"]["total"] == 0
        assert c["krea"]["total"] == 0
        assert c["leonardo"]["total"] == 0
        assert c["tutor"]["total"] == 0
