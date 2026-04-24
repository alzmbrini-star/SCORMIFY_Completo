"""
P0 re-test (iteration_109): validates that ALL sub-resource endpoints under
/api/projects/{project_id}/... and /api/course/{project_id} now require auth
and enforce cross-company isolation (via _can_access_project).

- Anonymous request → 401 (NOT 200, NOT 405)
- Cross-company authenticated request (admin@empresateste.com) against
  Didaxis project cb4e0112-3e45-44fe-ab29-304b0ef8f0a0 → 404
- Super admin can still mutate any project (regression)
- Company admin of Didaxis (aprovador@teste.com) can still mutate Didaxis
  project (regression)
"""

import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
                break

API = f"{BASE_URL}/api"

SUPER_ADMIN = {"email": "admin@scormify.com", "password": "admin123"}
APROVADOR = {"email": "aprovador@teste.com", "password": "aprovador123"}
OTHER_COMPANY = {"email": "admin@empresateste.com", "password": "empresa123"}

DIDAXIS_PROJECT_ID = "cb4e0112-3e45-44fe-ab29-304b0ef8f0a0"


def _login(creds: dict) -> requests.Session:
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{API}/auth/login", json=creds, timeout=30)
    assert r.status_code == 200, f"Login failed for {creds['email']}: {r.status_code} {r.text[:200]}"
    token = r.json().get("token")
    if token:
        s.headers.update({"Authorization": f"Bearer {token}"})
    return s


@pytest.fixture(scope="module")
def super_session():
    return _login(SUPER_ADMIN)


@pytest.fixture(scope="module")
def aprov_session():
    return _login(APROVADOR)


@pytest.fixture(scope="module")
def other_session():
    return _login(OTHER_COMPANY)


# ---------------------------------------------------------------------------
# The list of sub-resource endpoints to probe. Each entry is:
#   (method, path_template, body_or_None)
# path_template uses {pid} for project_id, {sid} for slide_id,
# {eid} for element_id, {aid} for audio_id, {anid} for annotation_id.
# Bodies are harmless payloads; we only care about the HTTP status codes.
# ---------------------------------------------------------------------------
FAKE_SID = "00000000-0000-4000-8000-000000000001"
FAKE_EID = "00000000-0000-4000-8000-000000000002"
FAKE_AID = "00000000-0000-4000-8000-000000000003"
FAKE_ANID = "00000000-0000-4000-8000-000000000004"

ENDPOINTS = [
    # (name, method, path_tpl, json_body_or_None)
    ("get_course",            "GET",    "/course/{pid}",                                          None),
    ("save_course",           "POST",   "/course/{pid}/save",                                     {"course": {"title": "x"}}),
    ("create_slide",          "POST",   "/projects/{pid}/slides",                                 {"title": "x", "background": "#fff"}),
    ("update_slide",          "PUT",    "/projects/{pid}/slides/" + FAKE_SID,                     {"title": "x"}),
    ("delete_slide",          "DELETE", "/projects/{pid}/slides/" + FAKE_SID,                     None),
    ("duplicate_slide",       "POST",   "/projects/{pid}/slides/" + FAKE_SID + "/duplicate",      None),
    ("normalize_dims",        "POST",   "/projects/{pid}/normalize-dimensions",                   None),
    ("reorder_slides",        "POST",   "/projects/{pid}/slides/reorder",                         {"slideIds": []}),
    ("add_element",           "POST",   "/projects/{pid}/slides/" + FAKE_SID + "/elements",       {"type": "text", "x": 0, "y": 0, "width": 10, "height": 10}),
    ("update_element",        "PUT",    "/projects/{pid}/slides/" + FAKE_SID + "/elements/" + FAKE_EID, {"x": 1}),
    ("delete_element",        "DELETE", "/projects/{pid}/slides/" + FAKE_SID + "/elements/" + FAKE_EID, None),
    # Multipart endpoints — bodies handled via a separate helper below (not via json)
    ("upload_media",          "POST_MULTIPART", "/projects/{pid}/media",                          "png"),
    ("add_slide_audio",       "POST_MULTIPART", "/projects/{pid}/slides/" + FAKE_SID + "/audio",  "mp3"),
    ("set_global_audio",      "POST_MULTIPART", "/projects/{pid}/global-audio",                   "mp3"),
    ("remove_global_audio",   "DELETE", "/projects/{pid}/global-audio",                           None),
    ("update_global_audio_vol", "PUT",  "/projects/{pid}/global-audio/volume?volume=0.5",         None),
    ("remove_slide_audio",    "DELETE", "/projects/{pid}/slides/" + FAKE_SID + "/audio/" + FAKE_AID, None),
    ("update_slide_audio_vol","PUT",    "/projects/{pid}/slides/" + FAKE_SID + "/audio/" + FAKE_AID + "/volume?volume=0.5", None),
    ("update_slide_audio_timing", "PUT","/projects/{pid}/slides/" + FAKE_SID + "/audio/" + FAKE_AID + "/timing", {"startTime": 0}),
    ("add_annotation",        "POST",   "/projects/{pid}/slides/" + FAKE_SID + "/annotations",    {"type": "drawing", "points": [{"x": 0, "y": 0}]}),
    ("update_annotation",     "PUT",    "/projects/{pid}/slides/" + FAKE_SID + "/annotations/" + FAKE_ANID, {"text": "y"}),
    ("delete_annotation",     "DELETE", "/projects/{pid}/slides/" + FAKE_SID + "/annotations/" + FAKE_ANID, None),
    ("apply_design_template", "POST",   "/projects/{pid}/apply-design-template",                  {"designTemplateId": "corporate"}),
    ("fix_simulators",        "POST",   "/projects/{pid}/fix-simulators",                         None),
]


def _do(session_or_none, method: str, path: str, body):
    url = f"{API}{path}"
    req = session_or_none.request if session_or_none is not None else requests.request
    if method == "POST_MULTIPART":
        # body here carries the extension ("png", "mp3") to build a minimal file
        ext = body if isinstance(body, str) else "bin"
        mime = {"png": "image/png", "mp3": "audio/mpeg"}.get(ext, "application/octet-stream")
        # 1x1 PNG placeholder or a tiny MP3 frame header — content doesn't matter because
        # auth/companyId check runs before file content is used.
        dummy = b"\x89PNG\r\n\x1a\n" if ext == "png" else b"ID3\x03\x00\x00\x00\x00\x00\x00"
        files = {"file": (f"dummy.{ext}", dummy, mime)}
        # requests needs no Content-Type header for multipart (it sets it). Strip json header.
        headers = None
        if session_or_none is not None:
            headers = {k: v for k, v in session_or_none.headers.items() if k.lower() != "content-type"}
            return requests.post(url, files=files, headers=headers, timeout=30)
        return requests.post(url, files=files, timeout=30)
    kwargs = {"timeout": 30}
    if body is not None:
        kwargs["json"] = body
    return req(method, url, **kwargs)


# ===========================================================================
# Anonymous → 401 for every sub-resource endpoint
# ===========================================================================
class TestAnonymous401:
    @pytest.mark.parametrize("name,method,tpl,body", ENDPOINTS, ids=[e[0] for e in ENDPOINTS])
    def test_anonymous_returns_401(self, name, method, tpl, body):
        path = tpl.format(pid=DIDAXIS_PROJECT_ID)
        r = _do(None, method, path, body)
        assert r.status_code == 401, (
            f"{name} {method} {path}: expected 401, got {r.status_code}: {r.text[:200]}"
        )


# ===========================================================================
# Cross-company (admin@empresateste.com vs Didaxis project) → 404
# ===========================================================================
class TestCrossCompany404:
    @pytest.mark.parametrize("name,method,tpl,body", ENDPOINTS, ids=[e[0] for e in ENDPOINTS])
    def test_cross_company_returns_404(self, other_session, name, method, tpl, body):
        path = tpl.format(pid=DIDAXIS_PROJECT_ID)
        r = _do(other_session, method, path, body)
        assert r.status_code == 404, (
            f"{name} {method} {path}: expected 404, got {r.status_code}: {r.text[:200]}"
        )


# ===========================================================================
# Regression: Didaxis aprovador can mutate Didaxis project content
# ===========================================================================
class TestAprovadorCanMutate:
    def test_aprovador_create_update_delete_slide(self, aprov_session):
        # CREATE
        title = f"TEST_RETEST_{uuid.uuid4().hex[:8]}"
        r = aprov_session.post(
            f"{API}/projects/{DIDAXIS_PROJECT_ID}/slides",
            json={"title": title, "background": "#ffffff"},
            timeout=30,
        )
        assert r.status_code in (200, 201), f"create slide: {r.status_code} {r.text[:200]}"
        slide = r.json()
        sid = slide.get("id") or slide.get("slide_id") or slide.get("_id")
        assert sid, f"missing slide id in response: {slide}"

        try:
            # UPDATE
            r2 = aprov_session.put(
                f"{API}/projects/{DIDAXIS_PROJECT_ID}/slides/{sid}",
                json={"title": title + "_upd"},
                timeout=30,
            )
            assert r2.status_code in (200, 204), f"update slide: {r2.status_code} {r2.text[:200]}"
        finally:
            # DELETE (cleanup)
            rd = aprov_session.delete(
                f"{API}/projects/{DIDAXIS_PROJECT_ID}/slides/{sid}", timeout=30
            )
            assert rd.status_code in (200, 204), (
                f"cleanup delete slide: {rd.status_code} {rd.text[:200]}"
            )


# ===========================================================================
# Regression: Super admin can mutate any project (using Didaxis)
# ===========================================================================
class TestSuperAdminCanMutate:
    def test_super_admin_create_and_delete_slide(self, super_session):
        title = f"TEST_RETEST_SA_{uuid.uuid4().hex[:8]}"
        r = super_session.post(
            f"{API}/projects/{DIDAXIS_PROJECT_ID}/slides",
            json={"title": title, "background": "#eeeeee"},
            timeout=30,
        )
        assert r.status_code in (200, 201), f"SA create slide: {r.status_code} {r.text[:200]}"
        slide = r.json()
        sid = slide.get("id") or slide.get("slide_id") or slide.get("_id")
        assert sid, f"missing slide id in SA create response: {slide}"

        rd = super_session.delete(
            f"{API}/projects/{DIDAXIS_PROJECT_ID}/slides/{sid}", timeout=30
        )
        assert rd.status_code in (200, 204), (
            f"SA cleanup delete: {rd.status_code} {rd.text[:200]}"
        )


# ===========================================================================
# Regression: GET /course/{pid} works for authorized user
# ===========================================================================
class TestGetCourseRegression:
    def test_aprovador_can_get_didaxis_course(self, aprov_session):
        r = aprov_session.get(f"{API}/course/{DIDAXIS_PROJECT_ID}", timeout=30)
        assert r.status_code == 200, f"get course: {r.status_code} {r.text[:200]}"

    def test_super_admin_can_get_didaxis_course(self, super_session):
        r = super_session.get(f"{API}/course/{DIDAXIS_PROJECT_ID}", timeout=30)
        assert r.status_code == 200, f"SA get course: {r.status_code} {r.text[:200]}"


# ===========================================================================
# Post-test cleanup: no TEST_RETEST_* slides left on Didaxis project
# ===========================================================================
class TestCleanupVerification:
    def test_no_leftover_test_slides(self, super_session):
        r = super_session.get(f"{API}/course/{DIDAXIS_PROJECT_ID}", timeout=30)
        if r.status_code != 200:
            pytest.skip(f"cannot fetch course to verify cleanup: {r.status_code}")
        data = r.json()
        # Course response may wrap slides under data.get("course", {}).get("slides")
        course = data.get("course", data) if isinstance(data, dict) else {}
        slides = course.get("slides") or data.get("slides") or []
        leftovers = [
            s for s in slides
            if isinstance(s, dict) and isinstance(s.get("title"), str)
            and s["title"].startswith("TEST_RETEST_")
        ]
        assert not leftovers, f"leftover TEST_RETEST_ slides: {[s.get('id') for s in leftovers]}"


# ===========================================================================
# TARGETED: confirm update_annotation enforces _can_access_project on a REAL
# (existing) annotation — this is the one endpoint suspected of missing the
# guard. We create slide+annotation as aprovador, then try cross-company PUT
# as admin@empresateste.com. If the guard is missing, the other company will
# get 200 and actually modify the annotation.
# ===========================================================================
class TestUpdateAnnotationGuard:
    def test_cross_company_update_annotation_returns_404(
        self, aprov_session, other_session, super_session
    ):
        # 1) aprovador creates a slide on Didaxis project
        r = aprov_session.post(
            f"{API}/projects/{DIDAXIS_PROJECT_ID}/slides",
            json={"title": "TEST_RETEST_guard", "background": "#fff"},
            timeout=30,
        )
        assert r.status_code in (200, 201), r.text[:200]
        sid = r.json().get("id")
        assert sid

        try:
            # 2) add an annotation
            r2 = aprov_session.post(
                f"{API}/projects/{DIDAXIS_PROJECT_ID}/slides/{sid}/annotations",
                json={"type": "drawing", "points": [{"x": 10, "y": 10}]},
                timeout=30,
            )
            assert r2.status_code in (200, 201), f"create annotation: {r2.status_code} {r2.text[:200]}"
            anid = r2.json().get("id")
            assert anid

            # 3) cross-company PUT must be 404 (isolation)
            r3 = other_session.put(
                f"{API}/projects/{DIDAXIS_PROJECT_ID}/slides/{sid}/annotations/{anid}",
                json={"text": "HACKED_BY_OTHER_COMPANY"},
                timeout=30,
            )
            assert r3.status_code == 404, (
                f"SECURITY LEAK on update_annotation: cross-company PUT returned "
                f"{r3.status_code} (expected 404). Body: {r3.text[:200]}"
            )

            # 4) anonymous PUT must be 401
            r4 = requests.put(
                f"{API}/projects/{DIDAXIS_PROJECT_ID}/slides/{sid}/annotations/{anid}",
                json={"text": "HACKED_ANON"},
                timeout=30,
            )
            assert r4.status_code == 401, (
                f"update_annotation missing require_auth on anon: got {r4.status_code}"
            )
        finally:
            # cleanup
            aprov_session.delete(
                f"{API}/projects/{DIDAXIS_PROJECT_ID}/slides/{sid}", timeout=30
            )
