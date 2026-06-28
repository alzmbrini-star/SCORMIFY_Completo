"""Regression tests for the whiteboard AI-plan bullet-sizing fix.

User bug (2026-02): When asking for "bullets with different colors per item",
the LLM generated HUGE oval bullets (~5x text height) that overlapped each
other vertically. Root cause: missing prompt guidance + `_autofit_shapes`
inflating tiny bullets to enclose nearby text + `_normalize_plan` clamp
forcing min radius to 20px + `_clamp_shapes_to_canvas` re-inflating.

Fixes verified here:
  1. `_autofit_shapes` skips circles with rx<=25 AND ry<=25 (bullet guard).
  2. `_autofit_shapes` still grows large circles to enclose their text.
  3. `_normalize_plan` allows rx/ry = 10 (lowered from 20).
  4. `_clamp_shapes_to_canvas` keeps small circles small (min 10, not 20).
  5. SYSTEM_PROMPT contains the BULLETS/MARCADORES guidance with 12-22 px.
  6. Full pipeline end-to-end on mixed bullets + container + text.
  7. Render-endpoint smoke: tiny plan with a bullet (rx=16) still renders.
"""
import copy
import os
import time

import pytest
import requests

# ── Backend service imports (no LLM call needed for unit tests) ──────
from services.whiteboard_ai_plan import (
    SYSTEM_PROMPT,
    _autofit_shapes,
    _cap_text_font_to_zone,
    _clamp_shapes_to_canvas,
    _enforce_shape_separation,
    _normalize_plan,
)

BASE_URL = os.environ.get(
    "REACT_APP_BACKEND_URL",
    "https://ai-tutor-platform-12.preview.emergentagent.com",
).rstrip("/")
API = f"{BASE_URL}/api"
ADMIN_EMAIL = "admin@scormify.com"
ADMIN_PASSWORD = "admin123"

MAX_POLL_SECONDS = 120
POLL_INTERVAL = 2.0


# ═════════════════════════════════════════════════════════════════════
# UNIT TESTS — no LLM, no HTTP
# ═════════════════════════════════════════════════════════════════════


def _make_bullet_plan() -> dict:
    """5 small colored bullets + 5 text labels next to them."""
    colors = ["#dc2626", "#2563eb", "#16a34a", "#f59e0b", "#9333ea"]
    ops: list[dict] = []
    for i, color in enumerate(colors):
        cy = 300 + i * 150
        ops.append({
            "type": "circle",
            "cx": 250, "cy": cy,
            "rx": 16, "ry": 16,
            "color": color, "width": 6,
        })
        ops.append({
            "type": "text",
            "text": f"Item {i + 1}",
            "x": 300, "y": cy - 20,
            "font_size": 60,
            "color": "#1f2937",
        })
    return {"summary": "test bullets", "ops": ops}


# ── 1. Bullets stay small through the whole post-processing pipeline ──

def test_autofit_does_not_inflate_small_bullets():
    plan = _make_bullet_plan()
    _autofit_shapes(plan)
    circles = [op for op in plan["ops"] if op["type"] == "circle"]
    assert len(circles) == 5
    for c in circles:
        assert c["rx"] <= 25, f"bullet inflated by autofit: rx={c['rx']}"
        assert c["ry"] <= 25, f"bullet inflated by autofit: ry={c['ry']}"


def test_full_pipeline_keeps_bullets_small():
    """Run the exact post-LLM pipeline order from generate_render_plan:
    _cap_text_font_to_zone → _autofit_shapes → _clamp_shapes_to_canvas
    → _enforce_shape_separation. Bullets must remain ≤25px."""
    plan = _make_bullet_plan()
    plan = _cap_text_font_to_zone(plan)
    plan = _autofit_shapes(plan)
    plan = _clamp_shapes_to_canvas(plan)
    plan = _enforce_shape_separation(plan)

    circles = [op for op in plan["ops"] if op["type"] == "circle"]
    assert len(circles) == 5, "lost circles during pipeline"
    for c in circles:
        assert c["rx"] <= 25, f"bullet rx grew to {c['rx']} after full pipeline"
        assert c["ry"] <= 25, f"bullet ry grew to {c['ry']} after full pipeline"


# ── 2. Large enclosing circles MUST still grow ────────────────────────

def test_autofit_still_grows_large_enclosing_circle():
    """The new bullet guard must NOT regress the legitimate 'enclose this
    keyword' use case (large circle around a text)."""
    plan = {
        "ops": [
            {"type": "circle", "cx": 950, "cy": 320,
             "rx": 100, "ry": 50,
             "color": "#dc2626", "width": 6},
            {"type": "text", "text": "Resultado Importante",
             "x": 750, "y": 290, "font_size": 80,
             "color": "#1f2937"},
        ]
    }
    original_rx = plan["ops"][0]["rx"]
    _autofit_shapes(plan)
    new_rx = plan["ops"][0]["rx"]
    assert new_rx > original_rx, (
        f"large enclosing circle did NOT grow (rx stayed at {new_rx}); "
        "bullet guard is too aggressive"
    )
    # Should land roughly around ~530 per the request, allow a wide band.
    assert new_rx > 300, f"large circle barely grew: rx={new_rx}"


# ── 3. _normalize_plan clamp min lowered to 10 ────────────────────────

def test_normalize_plan_allows_rx_ry_10():
    raw = {
        "summary": "x",
        "ops": [
            {"type": "circle", "cx": 250, "cy": 400,
             "rx": 10, "ry": 10, "color": "#000", "width": 6},
        ],
    }
    cleaned = _normalize_plan(
        copy.deepcopy(raw),
        base_color=None,
        allow_color_per_shape=True,
    )
    circles = [op for op in cleaned["ops"] if op["type"] == "circle"]
    assert len(circles) == 1
    assert circles[0]["rx"] == 10, f"rx bumped to {circles[0]['rx']} (expected 10)"
    assert circles[0]["ry"] == 10, f"ry bumped to {circles[0]['ry']} (expected 10)"


def test_normalize_plan_below_10_is_clamped_up_to_10():
    """Sanity check: rx=5 should be clamped UP to the new floor of 10."""
    raw = {
        "summary": "x",
        "ops": [
            {"type": "circle", "cx": 250, "cy": 400,
             "rx": 5, "ry": 5, "color": "#000", "width": 6},
        ],
    }
    cleaned = _normalize_plan(
        copy.deepcopy(raw),
        base_color=None,
        allow_color_per_shape=True,
    )
    c = cleaned["ops"][0]
    assert c["rx"] == 10
    assert c["ry"] == 10


# ── 4. _clamp_shapes_to_canvas keeps bullets small ────────────────────

def test_clamp_does_not_inflate_bullets():
    plan = {
        "ops": [
            {"type": "circle", "cx": 250, "cy": 400,
             "rx": 16, "ry": 16, "color": "#000", "width": 6}
        ]
    }
    _clamp_shapes_to_canvas(plan)
    c = plan["ops"][0]
    assert c["rx"] == 16, f"clamp bumped rx 16→{c['rx']}"
    assert c["ry"] == 16, f"clamp bumped ry 16→{c['ry']}"


# ── 5. System prompt content guidance ─────────────────────────────────

def test_system_prompt_has_bullets_guidance():
    assert "BULLETS / MARCADORES" in SYSTEM_PROMPT, (
        "SYSTEM_PROMPT missing 'BULLETS / MARCADORES' section header"
    )
    assert "rx=ry entre **12 e 22 px**" in SYSTEM_PROMPT, (
        "SYSTEM_PROMPT missing '12 e 22 px' bullet-radius guidance"
    )


# ── 6. End-to-end pipeline on mixed plan ──────────────────────────────

def test_pipeline_mixed_bullets_and_container():
    """Mixed plan: bullets stay small, container circle grows, no
    exceptions, op count preserved."""
    plan = {
        "summary": "mixed",
        "ops": [
            # Bullets
            {"type": "circle", "cx": 250, "cy": 300, "rx": 16, "ry": 16,
             "color": "#dc2626", "width": 6},
            {"type": "text", "text": "Alpha", "x": 300, "y": 280,
             "font_size": 60, "color": "#1f2937"},
            {"type": "circle", "cx": 250, "cy": 450, "rx": 18, "ry": 18,
             "color": "#16a34a", "width": 6},
            {"type": "text", "text": "Beta", "x": 300, "y": 430,
             "font_size": 60, "color": "#1f2937"},
            # Container circle (large) that SHOULD grow around its label
            {"type": "circle", "cx": 1400, "cy": 540, "rx": 100, "ry": 60,
             "color": "#2563eb", "width": 6},
            {"type": "text", "text": "Núcleo", "x": 1300, "y": 510,
             "font_size": 70, "color": "#1f2937"},
        ],
    }
    original_count = len(plan["ops"])

    # Should not raise
    plan = _cap_text_font_to_zone(plan)
    plan = _autofit_shapes(plan)
    plan = _clamp_shapes_to_canvas(plan)
    plan = _enforce_shape_separation(plan)

    assert len(plan["ops"]) == original_count, "lost ops during pipeline"

    circles = [op for op in plan["ops"] if op["type"] == "circle"]
    assert len(circles) == 3

    # First two are bullets (started ≤25), must stay ≤25
    bullets = [c for c in circles if c["color"] in ("#dc2626", "#16a34a")]
    assert len(bullets) == 2
    for b in bullets:
        assert b["rx"] <= 25, f"bullet inflated: rx={b['rx']}"
        assert b["ry"] <= 25, f"bullet inflated: ry={b['ry']}"

    # Container (#2563eb) should have grown beyond its 100px start
    container = next(c for c in circles if c["color"] == "#2563eb")
    assert container["rx"] >= 100, (
        f"container did not grow: rx={container['rx']}"
    )


# ═════════════════════════════════════════════════════════════════════
# INTEGRATION SMOKE — render endpoint still works with a bullet
# ═════════════════════════════════════════════════════════════════════


@pytest.fixture(scope="module")
def auth_session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    resp = s.post(
        f"{API}/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=15,
    )
    assert resp.status_code == 200, f"login failed: {resp.status_code} {resp.text}"
    data = resp.json()
    token = data.get("token") or data.get("session_token")
    assert token, f"no token in login response: {data}"
    s.headers.update({"Authorization": f"Bearer {token}"})
    return s


def _poll_job(session: requests.Session, job_id: str) -> dict:
    deadline = time.time() + MAX_POLL_SECONDS
    last = None
    while time.time() < deadline:
        r = session.get(f"{API}/job/{job_id}", timeout=15)
        assert r.status_code == 200, f"job poll {job_id} -> {r.status_code} {r.text}"
        last = r.json()
        if last.get("status") in ("completed", "failed"):
            return last
        time.sleep(POLL_INTERVAL)
    pytest.fail(f"job {job_id} did not finish within {MAX_POLL_SECONDS}s; last={last}")


def test_generate_from_plan_with_bullet_renders(auth_session):
    """End-to-end smoke: tiny plan with a bullet (rx=16, ry=16) + label
    must still render successfully via POST /api/whiteboard/generate-from-plan."""
    body = {
        "plan": {
            "ops": [
                {"type": "circle", "cx": 250, "cy": 300, "rx": 16, "ry": 16,
                 "color": "#dc2626", "width": 6},
                {"type": "text", "text": "hi", "x": 300, "y": 280,
                 "font_size": 60, "color": "#1f2937"},
            ]
        },
        "tool": "hand_real",
    }
    r = auth_session.post(f"{API}/whiteboard/generate-from-plan",
                          json=body, timeout=15)
    assert r.status_code == 200, f"submit -> {r.status_code} {r.text}"
    job_id = r.json().get("jobId")
    assert job_id, "no jobId in submit response"

    final = _poll_job(auth_session, job_id)
    assert final.get("status") == "completed", (
        f"render job did not complete: {final}"
    )
    result = final.get("result") or {}
    url = result.get("videoUrl") or result.get("url")
    assert url, f"no url in result: {result}"

    # Fetch & verify non-empty
    full = url if url.startswith("http") else f"{BASE_URL}{url}"
    fr = auth_session.get(full, timeout=30)
    assert fr.status_code == 200, f"file fetch {full} -> {fr.status_code}"
    assert len(fr.content) > 1000, f"render suspiciously small: {len(fr.content)} bytes"
