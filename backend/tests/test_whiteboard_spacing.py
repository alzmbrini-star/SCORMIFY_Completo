"""Regression tests for the Whiteboard AI plan spacing pipeline
(`_cap_text_font_to_zone` + `_enforce_shape_separation`).

Captures the 2026-02 bug where the LLM produced shapes that overlapped
each other (text font was too big → autofit grew boxes into adjacent
zones, swallowing the central circle).
"""
import itertools
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.whiteboard_ai_plan import (  # noqa: E402
    _autofit_shapes,
    _cap_text_font_to_zone,
    _clamp_shapes_to_canvas,
    _enforce_shape_separation,
    _measure_text_bbox,
    MAX_BOXED_TEXT_WIDTH,
    MIN_FONT_SIZE,
)


def _aabb(op):
    if op["type"] == "rectangle":
        return (op["x"], op["y"], op["x"] + op["w"], op["y"] + op["h"])
    return (op["cx"] - op["rx"], op["cy"] - op["ry"],
            op["cx"] + op["rx"], op["cy"] + op["ry"])


def _has_overlap(plan):
    shapes = [op for op in plan["ops"] if op["type"] in ("rectangle", "circle")]
    for a, b in itertools.combinations(shapes, 2):
        A, B = _aabb(a), _aabb(b)
        ox = min(A[2], B[2]) - max(A[0], B[0])
        oy = min(A[3], B[3]) - max(A[1], B[1])
        if ox > 0 and oy > 0:
            return (a, b, ox, oy)
    return None


def test_long_text_font_is_capped():
    """A long label at font_size 70 should be scaled down to fit a zone."""
    plan = {
        "ops": [
            {"type": "text", "text": "PowerPoint/PDF/Word", "x": 160,
             "y": 280, "font_size": 70},
        ]
    }
    _cap_text_font_to_zone(plan)
    fs = plan["ops"][0]["font_size"]
    w, _ = _measure_text_bbox("PowerPoint/PDF/Word", fs)
    assert w <= MAX_BOXED_TEXT_WIDTH + 5, f"text still {w}px wide at fs={fs}"
    assert fs >= MIN_FONT_SIZE


def test_short_text_font_is_not_changed():
    """A short label that already fits must keep its requested size."""
    plan = {
        "ops": [
            {"type": "text", "text": "OK", "x": 800, "y": 480,
             "font_size": 90},
        ]
    }
    _cap_text_font_to_zone(plan)
    assert plan["ops"][0]["font_size"] == 90


def test_full_pipeline_resolves_user_scormify_layout():
    """End-to-end: the exact LLM output that produced the screenshot
    with overlapping boxes must come out cleanly separated."""
    plan = {
        "ops": [
            {"type": "text", "text": "PowerPoint/PDF/Word", "x": 160,
             "y": 280, "font_size": 70, "color": "#1f2937"},
            {"type": "rectangle", "x": 130, "y": 250, "w": 400, "h": 130,
             "width": 6, "color": "#dc2626"},
            {"type": "text", "text": "Vídeos/Docs Técnicos", "x": 160,
             "y": 640, "font_size": 70, "color": "#1f2937"},
            {"type": "rectangle", "x": 130, "y": 610, "w": 400, "h": 130,
             "width": 6, "color": "#dc2626"},
            {"type": "text", "text": "SCORMIFY", "x": 800, "y": 480,
             "font_size": 90, "color": "#2563eb"},
            {"type": "circle", "cx": 960, "cy": 520, "rx": 320, "ry": 100,
             "width": 8, "color": "#2563eb"},
            {"type": "text", "text": "SCoRM 1.2/Responsivo", "x": 1320,
             "y": 640, "font_size": 70, "color": "#1f2937"},
            {"type": "rectangle", "x": 1290, "y": 610, "w": 400, "h": 130,
             "width": 6, "color": "#16a34a"},
        ]
    }
    _cap_text_font_to_zone(plan)
    _autofit_shapes(plan)
    _clamp_shapes_to_canvas(plan)
    _enforce_shape_separation(plan)

    overlap = _has_overlap(plan)
    assert overlap is None, f"unexpected overlap: {overlap}"


def test_separation_pass_shrinks_overlapping_rect_not_circle():
    """When a rectangle would touch the central circle, the rectangle
    must be the one that shrinks (not the circle)."""
    plan = {
        "ops": [
            {"type": "rectangle", "x": 600, "y": 400, "w": 400, "h": 200,
             "width": 6, "color": "#dc2626"},
            {"type": "circle", "cx": 1100, "cy": 500, "rx": 250, "ry": 150,
             "width": 6, "color": "#2563eb"},
        ]
    }
    original_rx = 250
    _enforce_shape_separation(plan)

    rect, circ = plan["ops"]
    # Circle radius untouched.
    assert circ["rx"] == original_rx
    # Rectangle right edge is at least 30 px left of circle left edge.
    rect_right = rect["x"] + rect["w"]
    circle_left = circ["cx"] - circ["rx"]
    assert rect_right + 30 <= circle_left + 1, (
        f"rect right={rect_right}, circle left={circle_left}"
    )


def test_no_overlap_means_no_change():
    """Plans that already have well-separated shapes must be left alone."""
    plan = {
        "ops": [
            {"type": "rectangle", "x": 100, "y": 100, "w": 300, "h": 100,
             "width": 6, "color": "#dc2626"},
            {"type": "rectangle", "x": 800, "y": 100, "w": 300, "h": 100,
             "width": 6, "color": "#16a34a"},
        ]
    }
    snapshot = [(op["x"], op["w"]) for op in plan["ops"]]
    _enforce_shape_separation(plan)
    after = [(op["x"], op["w"]) for op in plan["ops"]]
    assert snapshot == after, "shapes were modified despite no overlap"
