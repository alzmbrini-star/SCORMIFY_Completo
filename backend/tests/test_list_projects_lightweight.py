"""Regression: GET /api/projects (list) must return a LIGHT projection so it
fits through production gateway limits.

Bug context (2026-04-29 user report): production console flooded with 520 Bad
Gateway and HTTP2_PROTOCOL_ERROR on `/api/projects`. Root cause: the listing
returned the FULL project document for every project (slides + inlined media
+ htmlContent). For companies with many heavy projects, the response could
exceed 50+ MB and trigger Cloudflare's 520 error (origin response too large/
timed out).

Fix: aggregation pipeline projects only metadata + first slide (for thumbnail
preview) + a precomputed `slidesCount`. Frontend uses `course.slidesCount`
for the badge instead of `course.slides.length`.
"""
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001")
SUPER_EMAIL = "admin@scormify.com"
SUPER_PASSWORD = "admin123"


def _login():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": SUPER_EMAIL, "password": SUPER_PASSWORD}, timeout=10)
    return r.json().get("token")


def test_list_projects_returns_lightweight_payload():
    """The list endpoint must NOT return more than 1 slide per project."""
    token = _login()
    r = requests.get(f"{BASE_URL}/api/projects", headers={"Authorization": f"Bearer {token}"}, timeout=15)
    assert r.status_code == 200
    projects = r.json()
    assert isinstance(projects, list)
    if not projects:
        return  # empty is valid
    for p in projects:
        course = p.get("course") or {}
        slides = course.get("slides") or []
        # Critical: no project should ship more than 1 slide in the listing
        assert len(slides) <= 1, f"Project {p.get('id')} returned {len(slides)} slides — should be at most 1"


def test_list_projects_includes_slides_count_for_badge():
    """course.slidesCount must be present (replacement for course.slides.length)."""
    token = _login()
    r = requests.get(f"{BASE_URL}/api/projects", headers={"Authorization": f"Bearer {token}"}, timeout=15)
    projects = r.json()
    if not projects:
        return
    for p in projects:
        course = p.get("course") or {}
        # Either slidesCount is present OR there are no slides
        if course.get("slides"):
            assert "slidesCount" in course
            assert isinstance(course["slidesCount"], int)
            assert course["slidesCount"] >= 0


def test_list_projects_response_under_5mb():
    """Response size must stay under 5 MB so it never trips production
    gateway limits (Cloudflare 520 was happening at >50 MB)."""
    token = _login()
    r = requests.get(f"{BASE_URL}/api/projects", headers={"Authorization": f"Bearer {token}"}, timeout=15)
    size_mb = len(r.content) / (1024 * 1024)
    assert size_mb < 5, f"Listing response is {size_mb:.1f} MB — too big, will trigger 520 in prod"


def test_get_single_project_still_returns_full_document():
    """The detail endpoint /api/projects/{id} MUST still return the full
    document (frontend Editor needs it). Only the LIST endpoint is light."""
    token = _login()
    list_r = requests.get(f"{BASE_URL}/api/projects", headers={"Authorization": f"Bearer {token}"}, timeout=15)
    projects = list_r.json()
    if not projects:
        return
    pid = projects[0]["id"]
    detail_r = requests.get(f"{BASE_URL}/api/projects/{pid}", headers={"Authorization": f"Bearer {token}"}, timeout=15)
    assert detail_r.status_code == 200
    detail = detail_r.json()
    course = detail.get("course") or {}
    slides = course.get("slides") or []
    # If the listing claimed more than 1 slide, the detail must return all of them
    list_count = (projects[0].get("course") or {}).get("slidesCount", 0)
    assert len(slides) == list_count, f"Detail returned {len(slides)} slides but listing said {list_count}"
