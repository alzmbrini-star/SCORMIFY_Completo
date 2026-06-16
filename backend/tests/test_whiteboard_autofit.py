"""Regression tests for the Whiteboard AI plan autofit logic.

Captures the 2026-02 bug where a narrow box around wide text was not
growing (because the text's CENTER fell off the box's right edge, so
the old `cx-inside-box` matcher rejected the association). After the
fix the matcher uses (vertical center inside box) ∧ (any horizontal
overlap), which catches the "narrow box / wide text" case as well.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.whiteboard_ai_plan import (  # noqa: E402
    _autofit_shapes,
    _measure_text_bbox,
)


def test_narrow_box_grows_to_fit_wide_text():
    """LLM-produced narrow box around wide text must be expanded."""
    plan = {
        "ops": [
            # Wide text at font_size 70 — Caveat "PowerPoint/PDF/Word"
            # measures ~541 px advance.
            {"type": "text", "text": "PowerPoint/PDF/Word", "x": 160,
             "y": 280, "font_size": 70},
            # Box that is WAY too narrow (300 px). Pre-fix the autofit
            # would skip this entirely because text cx fell outside x1+PAD.
            {"type": "rectangle", "x": 130, "y": 250, "w": 300, "h": 130,
             "width": 6, "color": "#dc2626"},
        ]
    }
    _autofit_shapes(plan)

    rect = plan["ops"][1]
    text_w, _ = _measure_text_bbox("PowerPoint/PDF/Word", 70)
    expected_right_min = 160 + text_w  # text right edge

    # The right side of the box must extend past the text right edge.
    assert rect["x"] + rect["w"] >= expected_right_min, (
        f"box did not grow: x={rect['x']} w={rect['w']} "
        f"(right={rect['x'] + rect['w']}) but text reaches {expected_right_min}"
    )
    # And the box must keep a healthy padding (>= 30 px) to the right.
    actual_padding = (rect["x"] + rect["w"]) - expected_right_min
    assert actual_padding >= 30, (
        f"insufficient right padding: {actual_padding} px"
    )


def test_already_wide_box_is_not_shrunk():
    """When the LLM already gave a generous box, we must not shrink it."""
    plan = {
        "ops": [
            {"type": "text", "text": "Curso SCORM 1.2", "x": 1320,
             "y": 280, "font_size": 70},
            {"type": "rectangle", "x": 1290, "y": 250, "w": 630, "h": 130,
             "width": 6, "color": "#16a34a"},
        ]
    }
    _autofit_shapes(plan)
    rect = plan["ops"][1]
    # Width must not have shrunk.
    assert rect["w"] >= 630


def test_text_outside_box_is_not_associated():
    """A text that is NOT close to a box must not trigger growth."""
    plan = {
        "ops": [
            # Text in upper-left
            {"type": "text", "text": "Title", "x": 100, "y": 100,
             "font_size": 70},
            # Box in lower-right, far away.
            {"type": "rectangle", "x": 1500, "y": 800, "w": 300, "h": 100,
             "width": 6, "color": "#1f2937"},
        ]
    }
    _autofit_shapes(plan)
    rect = plan["ops"][1]
    assert rect["x"] == 1500
    assert rect["y"] == 800
    assert rect["w"] == 300
    assert rect["h"] == 100


def test_two_stacked_boxes_match_correct_texts():
    """Two boxes vertically stacked must each match only their own text."""
    plan = {
        "ops": [
            {"type": "text", "text": "PowerPoint/PDF/Word", "x": 160,
             "y": 280, "font_size": 70},
            {"type": "text", "text": "Vídeos/Docs Técnicos", "x": 160,
             "y": 640, "font_size": 70},
            # Upper box — narrow on purpose
            {"type": "rectangle", "x": 130, "y": 250, "w": 250, "h": 130,
             "width": 6, "color": "#dc2626"},
            # Lower box — narrow on purpose
            {"type": "rectangle", "x": 130, "y": 610, "w": 250, "h": 130,
             "width": 6, "color": "#dc2626"},
        ]
    }
    _autofit_shapes(plan)

    upper, lower = plan["ops"][2], plan["ops"][3]
    text_w_upper, _ = _measure_text_bbox("PowerPoint/PDF/Word", 70)
    text_w_lower, _ = _measure_text_bbox("Vídeos/Docs Técnicos", 70)

    assert upper["x"] + upper["w"] >= 160 + text_w_upper
    assert lower["x"] + lower["w"] >= 160 + text_w_lower
    # And the upper box must NOT have grown to fit the lower text
    # (vertical separation: upper y∈[250, 380], lower text cy≈675 — out).
    assert upper["y"] + upper["h"] <= 500  # well above the lower text


def test_circle_grows_around_wide_label():
    """Circle around a long label must expand its rx accordingly."""
    plan = {
        "ops": [
            {"type": "text", "text": "Transformação Digital", "x": 700,
             "y": 480, "font_size": 90},
            {"type": "circle", "cx": 960, "cy": 520, "rx": 100, "ry": 60,
             "width": 6, "color": "#2563eb"},
        ]
    }
    _autofit_shapes(plan)
    circle = plan["ops"][1]
    text_w, _ = _measure_text_bbox("Transformação Digital", 90)
    # rx must be large enough that the inscribed text rectangle fits.
    # Use the same inscribed-ellipse rule the implementation uses.
    assert circle["rx"] >= int((text_w / 2) * 1.0)  # at minimum touches edge
