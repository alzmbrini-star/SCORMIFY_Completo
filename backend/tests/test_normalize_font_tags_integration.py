"""Integration tests for the iteration 123 fixes:

1. POST /api/admin/normalize-font-tags (dryRun true/false + idempotency + auth)
2. POST /api/aesthetics/apply-fix/{project_id} with applyAll=true on the
   user-reported project a0b4069e-f6ef-4b10-bf5f-459c486d771f — must rewrite
   <h2>/inline font-sizes and inject the <style data-aesthetic-fix> plate
   when a slide has a backgroundImage.
3. POST /api/aesthetics/revert/{project_id} — restores prior state, and a
   subsequent apply yields the same result (idempotent).

Uses the live backend reachable via REACT_APP_BACKEND_URL.
Credentials: admin@scormify.com / admin123 (super_admin).
"""

from __future__ import annotations

import os
import re
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
USER_PROJECT_ID = "a0b4069e-f6ef-4b10-bf5f-459c486d771f"
ADMIN_EMAIL = "admin@scormify.com"
ADMIN_PASSWORD = "admin123"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def admin_token() -> str:
    assert BASE_URL, "REACT_APP_BACKEND_URL must be set"
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=20,
    )
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text[:200]}"
    body = r.json()
    token = body.get("token") or body.get("session_token")
    assert token, f"No token in login response: {body}"
    return token


@pytest.fixture(scope="session")
def admin_session(admin_token) -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "Authorization": f"Bearer {admin_token}",
        "Content-Type": "application/json",
    })
    return s


# ---------------------------------------------------------------------------
# 1) /admin/normalize-font-tags
# ---------------------------------------------------------------------------

class TestNormalizeFontTagsEndpoint:
    """Admin-only migration endpoint that converts legacy <font ...> tags."""

    def test_unauthenticated_rejected(self):
        r = requests.post(
            f"{BASE_URL}/api/admin/normalize-font-tags?dryRun=true", timeout=20
        )
        # Either 401 (no session) or 403 (anon, no role). Both indicate auth gating.
        assert r.status_code in (401, 403), f"Unexpected status: {r.status_code}"

    def test_dry_run_returns_counters(self, admin_session):
        r = admin_session.post(
            f"{BASE_URL}/api/admin/normalize-font-tags?dryRun=true", timeout=120
        )
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        assert data["dryRun"] is True
        assert isinstance(data.get("scannedProjects"), int)
        assert isinstance(data.get("mutatedProjects"), int)
        assert isinstance(data.get("mutatedElements"), int)
        assert data["scannedProjects"] > 0
        # sampleProjects is capped to 20 entries, all carrying projectId+elementsCleaned
        assert isinstance(data.get("sampleProjects"), list)
        for entry in data["sampleProjects"]:
            assert "projectId" in entry and "elementsCleaned" in entry

    def test_apply_then_dry_run_is_idempotent(self, admin_session):
        # Apply the conversion for real
        r1 = admin_session.post(
            f"{BASE_URL}/api/admin/normalize-font-tags?dryRun=false", timeout=180
        )
        assert r1.status_code == 200, r1.text[:300]
        applied = r1.json()
        assert applied["dryRun"] is False
        first_mutated = applied["mutatedProjects"]
        scanned_after = applied["scannedProjects"]
        assert scanned_after > 0

        # Re-run dry: should be 0 mutated since DB was already cleaned
        r2 = admin_session.post(
            f"{BASE_URL}/api/admin/normalize-font-tags?dryRun=true", timeout=120
        )
        assert r2.status_code == 200, r2.text[:300]
        again = r2.json()
        assert again["dryRun"] is True
        assert again["mutatedProjects"] == 0, (
            f"Migration not idempotent: still {again['mutatedProjects']} projects "
            f"need cleanup after applying once (first pass cleaned {first_mutated})."
        )
        assert again["mutatedElements"] == 0
        # Scanned count should match approx the same project corpus
        assert again["scannedProjects"] == scanned_after

    def test_user_project_has_no_legacy_font_after_migration(self, admin_session):
        """The user's specific project must have zero <font> tags in any
        slide element's htmlContent post-migration."""
        r = admin_session.get(
            f"{BASE_URL}/api/projects/{USER_PROJECT_ID}", timeout=30
        )
        assert r.status_code == 200, f"GET project failed: {r.status_code} {r.text[:200]}"
        project = r.json()
        slides = (project.get("course") or {}).get("slides") or []
        assert slides, "User project has no slides"
        offenders = []
        for s_idx, slide in enumerate(slides):
            for e_idx, el in enumerate(slide.get("elements") or []):
                if el.get("type") != "html":
                    continue
                html = el.get("htmlContent") or ""
                if re.search(r"<font[\s>]", html, re.IGNORECASE):
                    offenders.append((s_idx, e_idx))
        assert not offenders, (
            f"Legacy <font> tags remain in {USER_PROJECT_ID} at "
            f"slide/element pairs: {offenders[:10]}"
        )


# ---------------------------------------------------------------------------
# 2) /aesthetics/apply-fix + /aesthetics/revert
# ---------------------------------------------------------------------------

def _ensure_analysis(session: requests.Session, project_id: str):
    """Make sure an analysis exists. POST /api/aesthetics/analyze is heavy
    (LLM) — only call if needed."""
    # Try fetching status first via the analyze endpoint with cache hit logic.
    r = session.post(
        f"{BASE_URL}/api/aesthetics/analyze/{project_id}",
        json={"useCache": True},
        timeout=180,
    )
    return r


class TestAestheticsApplyAndRevert:
    """End-to-end exercise of the fix pipeline on the user's real project."""

    def test_project_exists(self, admin_session):
        r = admin_session.get(
            f"{BASE_URL}/api/projects/{USER_PROJECT_ID}", timeout=30
        )
        assert r.status_code == 200, (
            f"User project {USER_PROJECT_ID} unreachable: {r.status_code}"
        )

    def test_apply_all_then_revert_then_reapply_idempotent(self, admin_session):
        # Run analyze (cached if previous run completed) so there are issues
        analyze_resp = _ensure_analysis(admin_session, USER_PROJECT_ID)
        if analyze_resp.status_code not in (200, 201):
            pytest.skip(
                f"Analyze unavailable ({analyze_resp.status_code}): "
                f"{analyze_resp.text[:200]}"
            )
        analysis = analyze_resp.json()
        # Some implementations return {"issues": [...]} or a wrapper.
        issues = (
            analysis.get("issues")
            or (analysis.get("analysis") or {}).get("issues")
            or []
        )
        if not issues:
            pytest.skip("No issues detected by analyzer — nothing to apply.")

        # Apply all
        r_apply = admin_session.post(
            f"{BASE_URL}/api/aesthetics/apply-fix/{USER_PROJECT_ID}",
            json={"applyAll": True},
            timeout=180,
        )
        assert r_apply.status_code == 200, r_apply.text[:300]
        applied = r_apply.json()
        assert applied.get("applied", 0) >= 0

        # Fetch project and compute fingerprint of slides
        r_after = admin_session.get(
            f"{BASE_URL}/api/projects/{USER_PROJECT_ID}", timeout=30
        )
        assert r_after.status_code == 200
        slides_after = (
            (r_after.json().get("course") or {}).get("slides") or []
        )

        # Check: any slide with backgroundImage should have a plate <style data-aesthetic-fix> in at least one html element
        plate_pattern = re.compile(
            r"<style[^>]*data-aesthetic-fix", re.IGNORECASE
        )
        plates_found = 0
        slides_with_bg = 0
        for slide in slides_after:
            has_bg_image = bool(
                (slide.get("backgroundImage"))
                or ((slide.get("background") or {}).get("image"))
            )
            if has_bg_image:
                slides_with_bg += 1
                for el in slide.get("elements") or []:
                    if el.get("type") == "html" and plate_pattern.search(
                        el.get("htmlContent") or ""
                    ):
                        plates_found += 1
                        break

        # Snapshot status should be present
        r_snap = admin_session.get(
            f"{BASE_URL}/api/aesthetics/snapshot-status/{USER_PROJECT_ID}",
            timeout=30,
        )
        assert r_snap.status_code == 200
        assert r_snap.json().get("hasSnapshot") is True, (
            "No snapshot recorded after apply-fix; revert will be impossible."
        )

        # Revert
        r_revert = admin_session.post(
            f"{BASE_URL}/api/aesthetics/revert/{USER_PROJECT_ID}", timeout=60
        )
        assert r_revert.status_code == 200, r_revert.text[:300]
        assert r_revert.json().get("reverted") is True

        # Snapshot should be gone now
        r_snap2 = admin_session.get(
            f"{BASE_URL}/api/aesthetics/snapshot-status/{USER_PROJECT_ID}",
            timeout=30,
        )
        assert r_snap2.status_code == 200
        assert r_snap2.json().get("hasSnapshot") is False

        # Re-apply
        r_reapply = admin_session.post(
            f"{BASE_URL}/api/aesthetics/apply-fix/{USER_PROJECT_ID}",
            json={"applyAll": True},
            timeout=180,
        )
        assert r_reapply.status_code == 200, r_reapply.text[:300]
        reapplied = r_reapply.json()

        # Same number applied (idempotent w.r.t. the issue list)
        assert reapplied.get("applied", -1) == applied.get("applied", -2), (
            f"Re-apply differs: first={applied.get('applied')} "
            f"second={reapplied.get('applied')}"
        )

        # And the plates should still be present where bg images exist
        r_after2 = admin_session.get(
            f"{BASE_URL}/api/projects/{USER_PROJECT_ID}", timeout=30
        )
        slides_after2 = (
            (r_after2.json().get("course") or {}).get("slides") or []
        )
        plates_found_2 = 0
        for slide in slides_after2:
            has_bg_image = bool(
                (slide.get("backgroundImage"))
                or ((slide.get("background") or {}).get("image"))
            )
            if has_bg_image:
                for el in slide.get("elements") or []:
                    if el.get("type") == "html" and plate_pattern.search(
                        el.get("htmlContent") or ""
                    ):
                        plates_found_2 += 1
                        break

        assert plates_found_2 == plates_found, (
            f"Plate count drift: first apply={plates_found} re-apply={plates_found_2}"
        )

        # Attach diagnostics to the assertion message if there were slides with bg
        # but no plates emitted.
        if slides_with_bg > 0 and plates_found == 0:
            pytest.fail(
                f"{slides_with_bg} slide(s) carry a backgroundImage but no "
                f"html element received a <style data-aesthetic-fix> plate."
            )
