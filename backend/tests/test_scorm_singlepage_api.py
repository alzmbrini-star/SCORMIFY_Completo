"""Iteration 114 — API/contract tests for SCORM 1.2 single-page export.

Covers all the request body branches + response shape + ZIP package contents:
  * mode='single_page' when body={"singlePage": true}
  * mode='traditional' when body={"singlePage": false}
  * empty body respects project.singlePageMode (override hierarchy)
  * filename contains _singlepage_ marker for single-page mode
  * generated ZIP contains imsmanifest.xml + 4 XSDs + index.html + scorm-api.js
  * imsmanifest.xml declares scormtype=sco, schemaversion=1.2 + correct refs
"""
from __future__ import annotations

import io
import os
import re
import zipfile
from typing import Optional

import pytest
import requests


def _load_react_backend_url() -> str:
    val = os.environ.get("REACT_APP_BACKEND_URL")
    if val:
        return val.rstrip("/")
    # Fall back to /app/frontend/.env so this works under pytest without the env var.
    env_path = "/app/frontend/.env"
    if os.path.exists(env_path):
        with open(env_path) as fh:
            for line in fh:
                line = line.strip()
                if line.startswith("REACT_APP_BACKEND_URL="):
                    return line.split("=", 1)[1].strip().rstrip("/")
    raise RuntimeError("REACT_APP_BACKEND_URL not set and not found in /app/frontend/.env")


BASE_URL = _load_react_backend_url()
ADMIN_EMAIL = "admin@scormify.com"
ADMIN_PASSWORD = "admin123"
PROJECT_ID = "0bc5a90c-0128-46ee-bd4d-86756f712725"


# ---------------- fixtures ----------------

@pytest.fixture(scope="module")
def auth_token() -> str:
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=30,
    )
    if r.status_code != 200:
        pytest.skip(f"Login failed: {r.status_code} {r.text}")
    token = r.json().get("token") or r.json().get("access_token")
    assert token, f"No token in login response: {r.json()}"
    return token


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}


def _set_project_single_page(headers: dict, value: bool) -> None:
    r = requests.put(
        f"{BASE_URL}/api/projects/{PROJECT_ID}",
        json={"singlePageMode": value},
        headers=headers,
        timeout=30,
    )
    assert r.status_code == 200, f"PUT singlePageMode={value} failed: {r.status_code} {r.text}"


def _download(url_path: str, headers: dict) -> bytes:
    full = url_path if url_path.startswith("http") else f"{BASE_URL}{url_path}"
    r = requests.get(full, headers=headers, timeout=120)
    assert r.status_code == 200, f"Download {full} failed: {r.status_code}"
    return r.content


# ---------------- override hierarchy tests ----------------

def test_export_scorm_explicit_single_page_true(auth_headers):
    """Body singlePage=true forces mode='single_page' regardless of project setting."""
    _set_project_single_page(auth_headers, False)  # project says traditional
    r = requests.post(
        f"{BASE_URL}/api/course/{PROJECT_ID}/export-scorm",
        json={"singlePage": True},
        headers=auth_headers,
        timeout=180,
    )
    assert r.status_code == 200, f"{r.status_code} {r.text}"
    body = r.json()
    assert body.get("mode") == "single_page", body
    assert "downloadUrl" in body
    assert "_singlepage_" in body["downloadUrl"], (
        f"Expected _singlepage_ marker in downloadUrl, got {body['downloadUrl']}"
    )
    assert body["downloadUrl"].endswith(".zip")


def test_export_scorm_explicit_single_page_false(auth_headers):
    """Body singlePage=false forces traditional mode even if project says singlePageMode=true."""
    _set_project_single_page(auth_headers, True)
    try:
        r = requests.post(
            f"{BASE_URL}/api/course/{PROJECT_ID}/export-scorm",
            json={"singlePage": False},
            headers=auth_headers,
            timeout=180,
        )
        assert r.status_code == 200, f"{r.status_code} {r.text}"
        body = r.json()
        assert body.get("mode") == "traditional", body
        assert "_singlepage_" not in body["downloadUrl"], body["downloadUrl"]
    finally:
        _set_project_single_page(auth_headers, False)


def test_export_scorm_empty_body_uses_project_setting_true(auth_headers):
    """No body / empty body → mode comes from project.singlePageMode."""
    _set_project_single_page(auth_headers, True)
    try:
        r = requests.post(
            f"{BASE_URL}/api/course/{PROJECT_ID}/export-scorm",
            json={},  # empty body
            headers=auth_headers,
            timeout=180,
        )
        assert r.status_code == 200, f"{r.status_code} {r.text}"
        assert r.json().get("mode") == "single_page"
    finally:
        _set_project_single_page(auth_headers, False)


def test_export_scorm_empty_body_uses_project_setting_false(auth_headers):
    """No body when project.singlePageMode=false → traditional."""
    _set_project_single_page(auth_headers, False)
    r = requests.post(
        f"{BASE_URL}/api/course/{PROJECT_ID}/export-scorm",
        json={},
        headers=auth_headers,
        timeout=180,
    )
    assert r.status_code == 200, f"{r.status_code} {r.text}"
    assert r.json().get("mode") == "traditional"


# ---------------- ZIP package content tests ----------------

@pytest.fixture(scope="module")
def fresh_single_page_zip(auth_headers) -> zipfile.ZipFile:
    """POST a fresh single-page export and return the zip object."""
    r = requests.post(
        f"{BASE_URL}/api/course/{PROJECT_ID}/export-scorm",
        json={"singlePage": True},
        headers=auth_headers,
        timeout=240,
    )
    assert r.status_code == 200, f"{r.status_code} {r.text}"
    download_url = r.json()["downloadUrl"]
    zip_bytes = _download(download_url, auth_headers)
    assert zip_bytes[:2] == b"PK", "Not a valid ZIP"
    return zipfile.ZipFile(io.BytesIO(zip_bytes))


def test_zip_contains_required_scorm_files(fresh_single_page_zip):
    names = set(fresh_single_page_zip.namelist())
    required = {
        "imsmanifest.xml",
        "index.html",
        "scorm-api.js",
        "adlcp_rootv1p2.xsd",
        "ims_xml.xsd",
        "imscp_rootv1p1p2.xsd",
        "imsmd_rootv1p2p1.xsd",
    }
    missing = required - names
    assert not missing, f"Missing required SCORM files in ZIP: {missing}\nGot: {sorted(names)}"


def test_imsmanifest_declares_sco_and_scorm_1_2(fresh_single_page_zip):
    manifest = fresh_single_page_zip.read("imsmanifest.xml").decode("utf-8")
    # scormtype="sco" on the resource
    assert 'scormtype="sco"' in manifest, "scormtype=sco missing"
    # SCORM 1.2 schemaversion
    assert re.search(r"<schemaversion[^>]*>\s*1\.2\s*</schemaversion>", manifest), (
        "schemaversion 1.2 missing in manifest"
    )
    # references both index.html and scorm-api.js
    assert 'href="index.html"' in manifest
    assert "scorm-api.js" in manifest
    # adlcp namespace present (SCORM 1.2)
    assert "adlcp_rootv1p2" in manifest


def test_index_html_has_scorm_mode_and_helpers(fresh_single_page_zip):
    idx = fresh_single_page_zip.read("index.html").decode("utf-8")
    assert 'src="scorm-api.js"' in idx
    assert "SCORM_MODE = true" in idx
    for helper in (
        "scormSaveState",
        "scormReportQuiz",
        "scormUpdateScore",
        "scormMarkComplete",
        "scormRestoreState",
    ):
        assert helper in idx, f"index.html missing helper {helper}"


def test_scorm_api_js_exposes_required_methods(fresh_single_page_zip):
    api_js = fresh_single_page_zip.read("scorm-api.js").decode("utf-8")
    for method in (
        "init",
        "setLocation",
        "saveSuspend",
        "getSuspend",
        "recordInteraction",
        "setScore",
        "complete",
        "commit",
        "finish",
    ):
        # methods are written as `init: function(...)` or `init(` etc.
        assert re.search(rf"\b{method}\s*[:(]", api_js), (
            f"scorm-api.js missing '{method}' method"
        )
    assert "findAPI" in api_js, "scorm-api.js missing findAPI walker"


def test_advance_bug_fix_state_index_updates_before_unlock(fresh_single_page_zip):
    """Regression: state.currentIndex must be assigned BEFORE unlockSection() inside advance()
    so scormSaveState (called from unlockSection chain) persists the NEW location."""
    idx = fresh_single_page_zip.read("index.html").decode("utf-8")
    # Locate the advance function body
    m = re.search(r"advance\s*:\s*function\s*\([^)]*\)\s*\{", idx) \
        or re.search(r"function\s+advance\s*\([^)]*\)\s*\{", idx) \
        or re.search(r"SP\.advance\s*=\s*function\s*\([^)]*\)\s*\{", idx)
    assert m, "Could not locate advance() function in index.html"
    snippet = idx[m.start(): m.start() + 1500]
    # Find positions of the assignment and the unlockSection call
    set_pos = snippet.find("state.currentIndex")
    unlock_pos = snippet.find("unlockSection")
    assert set_pos != -1, f"state.currentIndex not assigned in advance(): {snippet[:600]}"
    assert unlock_pos != -1, f"unlockSection not called in advance(): {snippet[:600]}"
    assert set_pos < unlock_pos, (
        "Regression: state.currentIndex must be set BEFORE unlockSection. "
        f"Got assignment at {set_pos}, unlock at {unlock_pos}.\n{snippet[:700]}"
    )
