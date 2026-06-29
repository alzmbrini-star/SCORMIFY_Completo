"""Verify exported HTML inlines new Tutor IA maximize + message-actions code."""
import os
import time
import pytest
import requests


def _load_backend_url():
    url = os.environ.get('REACT_APP_BACKEND_URL')
    if not url:
        try:
            with open('/app/frontend/.env', 'r') as f:
                for line in f:
                    if line.startswith('REACT_APP_BACKEND_URL='):
                        url = line.split('=', 1)[1].strip()
                        break
        except FileNotFoundError:
            pass
    assert url, "REACT_APP_BACKEND_URL not set"
    return url.rstrip('/')


BASE_URL = _load_backend_url()
ADMIN_EMAIL = "admin@scormify.com"
ADMIN_PASSWORD = "admin123"

REQUIRED_MARKERS = [
    ".tutor-backdrop",
    ".tutor-panel.maximized",
    "toggleMaximize",
    'data-testid="tutor-maximize-button"',
    'data-testid="tutor-msg-copy"',
]


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
                      timeout=30)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    data = r.json()
    return data.get("token") or data.get("access_token")


@pytest.fixture(scope="module")
def headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def project_id(headers):
    r = requests.get(f"{BASE_URL}/api/projects", headers=headers, timeout=30)
    assert r.status_code == 200, f"List projects failed: {r.status_code}"
    body = r.json()
    items = body if isinstance(body, list) else (body.get("projects") or body.get("items") or [])
    assert items, "No projects available for export test"
    return items[0].get("id") or items[0].get("_id") or items[0].get("projectId")


def _poll_job(job_id, headers, timeout=180):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        r = requests.get(f"{BASE_URL}/api/job/{job_id}", headers=headers, timeout=30)
        if r.status_code == 200:
            j = r.json()
            last = j
            status = j.get("status")
            if status == "completed":
                return j
            if status == "failed":
                pytest.fail(f"Export job failed: {j}")
        time.sleep(2)
    pytest.fail(f"Job did not complete in time. Last={last}")


def test_export_html_inlines_new_tutor_assets(headers, project_id):
    # Trigger export
    r = requests.post(
        f"{BASE_URL}/api/course/{project_id}/export-html",
        headers=headers,
        json={"singlePage": False},
        timeout=60,
    )
    assert r.status_code in (200, 202), f"Export failed: {r.status_code} {r.text}"
    data = r.json()
    job_id = data.get("jobId") or data.get("job_id") or data.get("id")
    assert job_id, f"No jobId in {data}"

    result = _poll_job(job_id, headers)
    download_url = (result.get("result") or {}).get("downloadUrl") or result.get("downloadUrl")
    assert download_url, f"No downloadUrl in completed job: {result}"

    if download_url.startswith("/"):
        download_url = BASE_URL + download_url

    dl = requests.get(download_url, headers=headers, timeout=60)
    assert dl.status_code == 200, f"Download failed: {dl.status_code}"
    html = dl.text

    # Save for inspection / Playwright reuse
    out_path = "/tmp/exported_tutor_test.html"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)

    missing = [m for m in REQUIRED_MARKERS if m not in html]
    assert not missing, f"Missing markers in exported HTML: {missing} (saved to {out_path})"
