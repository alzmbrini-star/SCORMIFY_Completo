"""Tests for the Single-Page (vertical scroll) HTML export mode."""
import os
import re
import pytest
import requests

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8001")
SUPER = {"email": "admin@scormify.com", "password": "admin123"}


@pytest.fixture(scope="module")
def super_token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json=SUPER, timeout=10)
    r.raise_for_status()
    return r.json()["token"]


@pytest.fixture(scope="module")
def project_id(super_token):
    """Pick the first available project owned by super admin."""
    r = requests.get(
        f"{BASE_URL}/api/projects",
        headers={"Authorization": f"Bearer {super_token}"},
        timeout=10,
    )
    r.raise_for_status()
    items = r.json()
    assert len(items) > 0, "Need at least one project"
    return items[0]["id"]


def test_project_singlepagemode_field_persists(super_token, project_id):
    """PUT /api/projects/{id} must accept and persist singlePageMode."""
    # Set true
    r = requests.put(
        f"{BASE_URL}/api/projects/{project_id}",
        headers={"Authorization": f"Bearer {super_token}", "Content-Type": "application/json"},
        json={"singlePageMode": True},
        timeout=10,
    )
    assert r.status_code == 200
    assert r.json().get("singlePageMode") is True

    # Set false (cleanup)
    r2 = requests.put(
        f"{BASE_URL}/api/projects/{project_id}",
        headers={"Authorization": f"Bearer {super_token}", "Content-Type": "application/json"},
        json={"singlePageMode": False},
        timeout=10,
    )
    assert r2.status_code == 200
    assert r2.json().get("singlePageMode") is False


def test_export_html_singlepage_explicit_true(super_token, project_id):
    r = requests.post(
        f"{BASE_URL}/api/course/{project_id}/export-html",
        headers={"Authorization": f"Bearer {super_token}", "Content-Type": "application/json"},
        json={"singlePage": True},
        timeout=60,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("mode") == "single_page"
    assert "_singlepage_" in body.get("filename", ""), body
    # Fetch and verify single-page markers
    download = body["downloadUrl"]
    f = requests.get(f"{BASE_URL}{download}?preview=1", timeout=30)
    assert f.status_code == 200
    text = f.text
    assert 'class="sp-section"' in text
    assert 'data-testid="sp-next-btn"' in text
    assert 'data-testid="sp-menu-btn"' in text
    assert 'data-testid="sp-progress-fill"' in text
    assert "sp-end-card" in text
    # All sections (both normal sp-section variants and end-card) — only the first must be unlocked.
    # The section class can include modifiers (e.g. "sp-section sp-dark", "sp-end-card sp-section").
    all_sections = re.findall(r'<section[^>]+class="(?:sp-end-card\s+)?sp-section\b[^"]*"[^>]*>', text)
    locked_sections = re.findall(r'<section[^>]+class="(?:sp-end-card\s+)?sp-section\b[^"]*"[^>]+data-locked="true"', text)
    assert len(locked_sections) == len(all_sections) - 1, \
        f"expected {len(all_sections)-1} locked sections, got {len(locked_sections)} (total {len(all_sections)})"


def test_export_html_singlepage_explicit_false(super_token, project_id):
    r = requests.post(
        f"{BASE_URL}/api/course/{project_id}/export-html",
        headers={"Authorization": f"Bearer {super_token}", "Content-Type": "application/json"},
        json={"singlePage": False},
        timeout=60,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("mode") == "traditional"
    assert "_singlepage_" not in body.get("filename", "")


def test_export_html_respects_project_singlepagemode_default(super_token, project_id):
    """When body has no singlePage key, the project setting decides."""
    # Set project to single_page
    requests.put(
        f"{BASE_URL}/api/projects/{project_id}",
        headers={"Authorization": f"Bearer {super_token}", "Content-Type": "application/json"},
        json={"singlePageMode": True},
        timeout=10,
    ).raise_for_status()
    try:
        r = requests.post(
            f"{BASE_URL}/api/course/{project_id}/export-html",
            headers={"Authorization": f"Bearer {super_token}", "Content-Type": "application/json"},
            json={},  # no singlePage key
            timeout=60,
        )
        assert r.status_code == 200, r.text
        assert r.json().get("mode") == "single_page"
    finally:
        # Cleanup: reset
        requests.put(
            f"{BASE_URL}/api/projects/{project_id}",
            headers={"Authorization": f"Bearer {super_token}", "Content-Type": "application/json"},
            json={"singlePageMode": False},
            timeout=10,
        )


def test_export_html_preview_mode_serves_inline(super_token, project_id):
    """The /api/exports/{filename}?preview=1 must serve as text/html WITHOUT
    Content-Disposition: attachment so it can be opened in-browser for testing."""
    r = requests.post(
        f"{BASE_URL}/api/course/{project_id}/export-html",
        headers={"Authorization": f"Bearer {super_token}", "Content-Type": "application/json"},
        json={"singlePage": True},
        timeout=60,
    )
    download = r.json()["downloadUrl"]

    # ?preview=1 → no Content-Disposition: attachment
    f1 = requests.get(f"{BASE_URL}{download}?preview=1", timeout=15)
    assert f1.status_code == 200
    assert f1.headers.get("content-type", "").startswith("text/html")
    assert "attachment" not in (f1.headers.get("content-disposition", "") or "")

    # Without preview → forced download
    f2 = requests.get(f"{BASE_URL}{download}", timeout=15, allow_redirects=False)
    assert f2.status_code == 200
    cd = f2.headers.get("content-disposition", "") or ""
    assert "attachment" in cd
