"""Tests for the nuclear `/aesthetics/force-high-contrast` endpoint.

Validates the bypass-the-analyzer flow that forces every text/html element
in every slide to high contrast.
"""
import os
import pytest

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "scormify_test_fhc")
os.environ.setdefault("REACT_APP_BACKEND_URL", "http://localhost")
os.environ.setdefault("EMERGENT_LLM_KEY", "test-key")


def _make_project(pid: str, slides: list):
    return {
        "id": pid,
        "name": "T",
        "ownerId": "u",
        "course": {"slides": slides},
        "createdAt": "2026-01-01T00:00:00Z",
        "updatedAt": "2026-01-01T00:00:00Z",
    }


@pytest.mark.asyncio(loop_scope="session")
async def test_force_high_contrast_rewrites_rgba_alpha_text():
    from server import app as _wrapped  # noqa: F401  ensures startup ran
    from routes.aesthetics import force_high_contrast_all_slides
    from routes.deps import db
    import uuid as _uuid

    pid = f"test-fhc-{_uuid.uuid4().hex[:8]}"
    await db.projects.delete_one({"id": pid})
    slides = [{
        "id": "s0",
        "title": "Test",
        "background": "#ffffff",
        "elements": [{
            "id": "e0", "type": "html",
            "x": 0, "y": 0, "width": 1920, "height": 820,
            "style": {"fontColor": "#ffffff", "opacity": 0.3},
            "htmlContent": (
                '<div>'
                '<h2 style="color:rgba(255,255,255,0.3);opacity:0.3;">Invisible</h2>'
                '<p style="color:#ffffff;">White on white</p>'
                '</div>'
            ),
        }],
    }]
    await db.projects.insert_one(_make_project(pid, slides))

    result = await force_high_contrast_all_slides(
        pid, user={"user_id": "test", "role": "super_admin"},
    )
    assert result["fixed"] >= 1
    assert result["canRevert"] is True

    p = await db.projects.find_one({"id": pid}, {"_id": 0})
    el = p["course"]["slides"][0]["elements"][0]
    html = el["htmlContent"]
    assert "color:rgba(255,255,255,0.3)" not in html
    assert "color:#ffffff" not in html
    assert "opacity:0.3" not in html
    assert el["style"]["fontColor"] == "#0f172a"
    assert el["style"]["opacity"] == 1
    assert "data-aesthetic-fix" in html
    await db.projects.delete_one({"id": pid})


@pytest.mark.asyncio(loop_scope="session")
async def test_force_high_contrast_dark_slide_uses_light_text():
    from server import app as _wrapped  # noqa: F401
    from routes.aesthetics import force_high_contrast_all_slides
    from routes.deps import db
    import uuid as _uuid

    pid = f"test-fhc-{_uuid.uuid4().hex[:8]}"
    await db.projects.delete_one({"id": pid})
    slides = [{
        "id": "s0", "title": "Dark", "background": "#0f172a",
        "elements": [{
            "id": "e0", "type": "html",
            "x": 0, "y": 0, "width": 1920, "height": 820,
            "style": {},
            "htmlContent": '<p style="color:#0f172a;">Dark on dark</p>',
        }],
    }]
    await db.projects.insert_one(_make_project(pid, slides))

    await force_high_contrast_all_slides(
        pid, user={"user_id": "test", "role": "super_admin"},
    )
    p = await db.projects.find_one({"id": pid}, {"_id": 0})
    el = p["course"]["slides"][0]["elements"][0]
    assert el["style"]["fontColor"].lower() in ("#f8fafc", "#ffffff")
    assert "color:#0f172a" not in el["htmlContent"].lower()
    await db.projects.delete_one({"id": pid})


@pytest.mark.asyncio(loop_scope="session")
async def test_force_high_contrast_skips_non_textual_elements():
    from server import app as _wrapped  # noqa: F401
    from routes.aesthetics import force_high_contrast_all_slides
    from routes.deps import db
    import uuid as _uuid

    pid = f"test-fhc-{_uuid.uuid4().hex[:8]}"
    await db.projects.delete_one({"id": pid})
    slides = [{
        "id": "s0", "title": "Img", "background": "#ffffff",
        "elements": [{
            "id": "e0", "type": "image",
            "src": "/test.png",
            "x": 0, "y": 0, "width": 100, "height": 100,
            "style": {"opacity": 0.5},
        }],
    }]
    await db.projects.insert_one(_make_project(pid, slides))

    result = await force_high_contrast_all_slides(
        pid, user={"user_id": "test", "role": "super_admin"},
    )
    assert result["fixed"] == 0
    p = await db.projects.find_one({"id": pid}, {"_id": 0})
    el = p["course"]["slides"][0]["elements"][0]
    assert el["style"]["opacity"] == 0.5
    await db.projects.delete_one({"id": pid})


@pytest.mark.asyncio(loop_scope="session")
async def test_force_high_contrast_creates_revertible_snapshot():
    from server import app as _wrapped  # noqa: F401
    from routes.aesthetics import force_high_contrast_all_slides
    from routes.deps import db
    import uuid as _uuid

    pid = f"test-fhc-{_uuid.uuid4().hex[:8]}"
    await db.projects.delete_one({"id": pid})
    await db.aesthetic_snapshots.delete_one({"projectId": pid})
    slides = [{
        "id": "s0", "title": "T", "background": "#ffffff",
        "elements": [{
            "id": "e0", "type": "html",
            "x": 0, "y": 0, "width": 100, "height": 100,
            "style": {},
            "htmlContent": '<p style="color:#fff;">Invisible</p>',
        }],
    }]
    await db.projects.insert_one(_make_project(pid, slides))

    await force_high_contrast_all_slides(
        pid, user={"user_id": "test", "role": "super_admin"},
    )
    snap = await db.aesthetic_snapshots.find_one({"projectId": pid}, {"_id": 0})
    assert snap is not None
    assert snap["kind"] == "force_high_contrast"
    snap_html = snap["slidesBefore"][0]["elements"][0]["htmlContent"]
    assert "color:#fff" in snap_html
    await db.projects.delete_one({"id": pid})
    await db.aesthetic_snapshots.delete_one({"projectId": pid})


@pytest.mark.asyncio(loop_scope="session")
async def test_force_high_contrast_preserves_white_text_on_dark_simulator():
    """Regression test for production bug: simulator with dark internal body
    (`body{background:#1e293b}`) on a LIGHT slide was getting its white
    titles forced to dark by the nuclear sweep, making them invisible.

    The fix detects `_extract_dominant_html_bg` and uses THAT internal bg
    for the contrast decision, preserving legible white-on-dark."""
    from server import app as _wrapped  # noqa: F401
    from routes.aesthetics import force_high_contrast_all_slides
    from routes.deps import db
    import uuid as _uuid

    pid = f"test-fhc-sim-{_uuid.uuid4().hex[:8]}"
    await db.projects.delete_one({"id": pid})
    simulator_html = (
        "<!DOCTYPE html><html><head>"
        "<style>body{background:#1e293b;color:#f1f5f9}.card{background:#0f172a}</style>"
        "</head><body>"
        "<h1 style=\"color:#ffffff;\">Simulador Adoção</h1>"
        "<button style=\"background:#1e293b;color:#ffffff;\">Dados Limpos</button>"
        "</body></html>"
    )
    slides = [{
        "id": "s0", "title": "Sim", "background": "#ffffff",  # LIGHT slide
        "elements": [{
            "id": "e0", "type": "html",
            "x": 0, "y": 0, "width": 1920, "height": 820,
            "style": {},
            "htmlContent": simulator_html,
        }],
    }]
    await db.projects.insert_one(_make_project(pid, slides))

    await force_high_contrast_all_slides(
        pid, user={"user_id": "test", "role": "super_admin"},
    )
    p = await db.projects.find_one({"id": pid}, {"_id": 0})
    el = p["course"]["slides"][0]["elements"][0]
    html = el["htmlContent"]
    # White title MUST be preserved — it's legible on the dark internal bg
    assert "color:#ffffff" in html, (
        "Simulator white text on dark internal bg must NOT be forced dark"
    )
    # The body-level <style> must NOT have an override that flips colors —
    # we only inject overrides when internal_bg is undetectable.
    assert 'data-aesthetic-fix' not in html
    await db.projects.delete_one({"id": pid})
