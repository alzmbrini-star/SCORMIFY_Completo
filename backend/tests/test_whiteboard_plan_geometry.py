"""Regression: whiteboard plan geometry polish (texts inside shapes,
arrows retracted to shape borders)."""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.whiteboard_ai_plan import (
    ARROW_GAP, TEXT_INNER_PAD, polish_plan_geometry,
    _measure_text_bbox, _point_in_shape, _text_fits_shape, _text_metrics,
)


def _plan():
    return {
        "summary": "screenshot repro",
        "ops": [
            {"type": "text", "text": "PowerPoint/PDF/Word", "x": 420, "y": 330, "font_size": 54},
            {"type": "rectangle", "x": 400, "y": 300, "w": 380, "h": 100, "width": 5},
            {"type": "text", "text": "Vídeos/Docs", "x": 450, "y": 430, "font_size": 54},
            {"type": "rectangle", "x": 410, "y": 400, "w": 250, "h": 90, "width": 5},
            {"type": "text", "text": "SCORMIFY", "x": 950, "y": 420, "font_size": 80},
            {"type": "circle", "cx": 1030, "cy": 450, "rx": 230, "ry": 130, "width": 7},
            {"type": "text", "text": "SCORM 1.2", "x": 1360, "y": 330, "font_size": 54},
            {"type": "rectangle", "x": 1340, "y": 300, "w": 280, "h": 90, "width": 5},
            {"type": "arrow", "x1": 790, "y1": 350, "x2": 920, "y2": 430, "width": 6},
            {"type": "arrow", "x1": 670, "y1": 450, "x2": 940, "y2": 455, "width": 6},
        ],
    }


def test_arrows_end_outside_all_shapes():
    plan = polish_plan_geometry(_plan())
    shapes = [o for o in plan["ops"] if o["type"] in ("rectangle", "circle")]
    for op in plan["ops"]:
        if op["type"] != "arrow":
            continue
        for pt in ((op["x1"], op["y1"]), (op["x2"], op["y2"])):
            for sh in shapes:
                # 2px numeric tolerance on the inflated border
                assert not _point_in_shape(pt, sh, ARROW_GAP - 2), (
                    f"arrow endpoint {pt} still inside shape {sh}"
                )


def test_arrow_keeps_direction_and_min_length():
    plan = polish_plan_geometry(_plan())
    arrows = [o for o in plan["ops"] if o["type"] == "arrow"]
    orig = [o for o in _plan()["ops"] if o["type"] == "arrow"]
    for a, o in zip(arrows, orig):
        assert math.hypot(a["x2"] - a["x1"], a["y2"] - a["y1"]) >= 30
        # direction preserved (dot product > 0)
        d1 = (a["x2"] - a["x1"], a["y2"] - a["y1"])
        d0 = (o["x2"] - o["x1"], o["y2"] - o["y1"])
        assert d1[0] * d0[0] + d1[1] * d0[1] > 0


def test_texts_fit_and_centered_in_shapes():
    plan = polish_plan_geometry(_plan())
    ops = plan["ops"]
    pairs = [(0, 1), (2, 3), (4, 5), (6, 7)]  # (text idx, shape idx)
    for ti, si in pairs:
        t, sh = ops[ti], ops[si]
        tw, th = _measure_text_bbox(t["text"], t["font_size"])
        assert _text_fits_shape(sh, tw, th, TEXT_INNER_PAD - 4), (
            f"text {t['text']!r} fs={t['font_size']} does not fit {sh}"
        )
        # horizontally centered (by real ink width) within 6px
        ink_w, _, _ = _text_metrics(t["text"], t["font_size"])
        if sh["type"] == "rectangle":
            scx = sh["x"] + sh["w"] / 2
        else:
            scx = sh["cx"]
        assert abs((t["x"] + ink_w / 2) - scx) <= 6


def test_bullets_and_free_text_untouched():
    plan = {
        "summary": "s",
        "ops": [
            {"type": "text", "text": "Item um", "x": 300, "y": 400, "font_size": 60},
            {"type": "circle", "cx": 250, "cy": 430, "rx": 16, "ry": 16, "width": 6},
            {"type": "text", "text": "Livre", "x": 1500, "y": 800, "font_size": 60},
        ],
    }
    out = polish_plan_geometry({**plan, "ops": [dict(o) for o in plan["ops"]]})
    assert out["ops"][0]["x"] == 300 and out["ops"][0]["font_size"] == 60
    assert out["ops"][2]["x"] == 1500
