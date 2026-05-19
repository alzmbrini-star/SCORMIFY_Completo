"""Tests for per-region bgImage luminance analysis.

Validates the fix for the user's recurring complaint: "Analisador de
estética só leva em conta a cor do background... ignora a imagem".
"""
from io import BytesIO
from PIL import Image
import pytest

from services import bg_image_luminance as bil
from routes.aesthetics import _build_slide_context, _effective_bg_for_element


def _make_image(width=200, height=200, regions=None):
    """Create a tiny test image with optional colored regions.

    `regions` is a list of (x, y, w, h, (r,g,b)).
    """
    img = Image.new("RGB", (width, height), (30, 58, 138))  # navy bg
    if regions:
        for (rx, ry, rw, rh, rgb) in regions:
            for px in range(rx, rx + rw):
                for py in range(ry, ry + rh):
                    img.putpixel((px, py), rgb)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ---------- analyze_region ----------

def test_analyze_region_all_dark():
    img = _make_image(100, 100)  # navy everywhere
    info = bil.analyze_region(img, 0.0, 0.0, 1.0, 1.0)
    assert info["tone"] == "dark"
    assert info["recommendedTextColor"] == bil.LIGHT_TEXT
    assert info["luminance"] < 0.35


def test_analyze_region_all_white():
    img = _make_image(100, 100, [(0, 0, 100, 100, (255, 255, 255))])
    info = bil.analyze_region(img, 0.0, 0.0, 1.0, 1.0)
    assert info["tone"] == "light"
    assert info["recommendedTextColor"] == bil.DARK_TEXT
    assert info["luminance"] > 0.9


def test_analyze_region_only_inspects_specified_region():
    """The image is mostly dark navy but has a white square in the center.
    A region targeting the center should return LIGHT; one targeting a
    corner should return DARK."""
    img = _make_image(200, 200, [(60, 60, 80, 80, (255, 255, 255))])

    center = bil.analyze_region(img, 0.4, 0.4, 0.2, 0.2)
    assert center["tone"] == "light"
    assert center["recommendedTextColor"] == bil.DARK_TEXT

    corner = bil.analyze_region(img, 0.0, 0.0, 0.1, 0.1)
    assert corner["tone"] == "dark"
    assert corner["recommendedTextColor"] == bil.LIGHT_TEXT


def test_analyze_region_mixed_zone_flagged():
    """Region with a 50/50 split of dark and light pixels has high stddev."""
    img = _make_image(200, 200, [(100, 0, 100, 200, (255, 255, 255))])
    info = bil.analyze_region(img, 0.0, 0.0, 1.0, 1.0)
    assert info["isMixed"] is True
    assert info["stddev"] > 0.2


def test_analyze_region_handles_empty_image():
    info = bil.analyze_region(b"not-an-image", 0.0, 0.0, 1.0, 1.0)
    assert info is None


# ---------- _effective_bg_for_element ----------

def test_effective_bg_returns_region_luminance_when_available():
    slide = {"background": "#1e3a8a", "backgroundImage": "/img.png"}
    el = {
        "type": "text",
        "_bgRegionLuminance": {
            "luminance": 0.93,
            "stddev": 0.05,
            "tone": "light",
            "recommendedTextColor": "#0f172a",
            "isMixed": False,
        },
    }
    bg, has_image = _effective_bg_for_element(slide, el)
    # luminance 0.93 → 237/255 → ~#ededed
    assert bg.startswith("#ed") or bg.startswith("#ec") or bg.startswith("#ee")
    assert has_image is True


def test_effective_bg_falls_back_to_solid_without_region_info():
    slide = {"background": "#1e3a8a", "backgroundImage": "/img.png"}
    el = {"type": "text"}
    bg, has_image = _effective_bg_for_element(slide, el)
    assert bg == "#1e3a8a"
    assert has_image is True


def test_effective_bg_no_image_uses_solid():
    slide = {"background": "#ffffff"}
    el = {"type": "text"}
    bg, has_image = _effective_bg_for_element(slide, el)
    assert bg == "#ffffff"
    assert has_image is False


# ---------- _build_slide_context integrates region info ----------

def test_slide_context_reports_per_element_region():
    """The user's actual bug: slide.background=#1e3a8a + bgImage with
    white shape in middle. Element in middle → analyzer should report
    LIGHT region, recommending DARK text. Without this fix, the analyzer
    only saw #1e3a8a (navy) and recommended LIGHT text = invisible."""
    img = _make_image(800, 200, [(200, 0, 400, 200, (255, 255, 255))])
    slide = {
        "title": "Test",
        "background": "#1e3a8a",
        "backgroundImage": "/x.png",
        "width": 800,
        "height": 200,
        "elements": [
            {"type": "text", "x": 300, "y": 50, "width": 200, "height": 100,
             "content": "Hello", "style": {"fontColor": "#ffffff"}},
            {"type": "text", "x": 0, "y": 0, "width": 100, "height": 100,
             "content": "Corner", "style": {"fontColor": "#ffffff"}},
        ],
    }
    ctx = _build_slide_context(slide, 0, 1, bg_image_bytes=img)
    # First element sits over the white region → recommends DARK text
    assert "bgRegion=light" in ctx
    assert "recommend=#0f172a" in ctx
    # Corner sits over navy → recommends LIGHT text
    assert "bgRegion=dark" in ctx
    assert "recommend=#f8fafc" in ctx
    # Both elements should have their luminance baked onto the slide dict
    # so a subsequent _apply_style_fix can reuse it
    assert slide["elements"][0].get("_bgRegionLuminance") is not None
    assert slide["elements"][1].get("_bgRegionLuminance") is not None


def test_slide_context_no_image_does_not_call_region_analysis():
    slide = {
        "title": "Plain", "background": "#1e3a8a", "width": 800, "height": 200,
        "elements": [
            {"type": "text", "x": 0, "y": 0, "width": 100, "height": 100,
             "content": "x", "style": {"fontColor": "#ffffff"}},
        ],
    }
    ctx = _build_slide_context(slide, 0, 1)
    assert "bgRegion=" not in ctx
    # WCAG ratio uses solid bg
    assert "wcag=" in ctx
