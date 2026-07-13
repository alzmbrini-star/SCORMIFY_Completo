"""Regression: whiteboard line-art icon catalog (lucide) support."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.whiteboard_icons import (
    ICONS_DIR, icon_strokes, list_icon_names, resolve_icon_name,
)
from services.whiteboard_ai_plan import _normalize_plan, polish_plan_geometry


def test_catalog_present():
    assert ICONS_DIR.exists()
    assert len(list_icon_names()) > 1500


def test_resolve_exact_alias_fuzzy():
    assert resolve_icon_name("tree-deciduous") == "tree-deciduous"
    assert resolve_icon_name("árvore") == "tree-deciduous"
    assert resolve_icon_name("tree") == "tree-deciduous"
    assert resolve_icon_name("cadeira") == "armchair"
    assert resolve_icon_name("chair") == "armchair"
    assert resolve_icon_name("hous") == "house"           # fuzzy
    assert resolve_icon_name("xyzzy-not-a-thing") is None


def test_strokes_scaled_and_centered():
    strokes = icon_strokes("tree-deciduous", 500, 400, 200)
    assert len(strokes) >= 1
    xs = [p[0] for s in strokes for p in s]
    ys = [p[1] for s in strokes for p in s]
    assert 400 - 2 <= min(xs) and max(xs) <= 600 + 2
    assert 300 - 2 <= min(ys) and max(ys) <= 500 + 2
    # multiple sampled points per stroke
    assert sum(len(s) for s in strokes) > 40


def test_normalize_accepts_icon_and_resolves_name():
    plan = _normalize_plan(
        {"summary": "s", "ops": [
            {"type": "icon", "name": "árvore", "x": 400, "y": 400, "size": 240, "width": 5},
            {"type": "icon", "name": "not-a-real-icon-zzz", "x": 100, "y": 100, "size": 200},
        ]},
        base_color=None, allow_color_per_shape=True,
    )
    icons = [o for o in plan["ops"] if o["type"] == "icon"]
    assert len(icons) == 1
    assert icons[0]["name"] == "tree-deciduous"
    assert icons[0]["size"] == 240


def test_arrows_retract_from_icons():
    plan = {
        "summary": "s",
        "ops": [
            {"type": "icon", "name": "tree-deciduous", "x": 900, "y": 450, "size": 300, "width": 5},
            # arrow tip lands in the middle of the icon box
            {"type": "arrow", "x1": 400, "y1": 450, "x2": 890, "y2": 450, "width": 6},
        ],
    }
    out = polish_plan_geometry(plan)
    arrow = [o for o in out["ops"] if o["type"] == "arrow"][0]
    # icon box left edge = 900-150 = 750; gap 16 → tip must be ≤ ~736
    assert arrow["x2"] <= 750 - 10
