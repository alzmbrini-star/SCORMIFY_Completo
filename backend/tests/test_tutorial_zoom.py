"""Tests for the zoom effect mapping from Tutorial Agent → Scormify slide."""
import pytest
from routes.tutorial_integration import _step_to_slide


class TestZoomEffect:
    def test_zoom_effect_attached_when_click_and_zoom(self):
        step = {"action_type": "click", "click_x": 640, "click_y": 360}
        slide = _step_to_slide(step, "/bg.png", 0, zoom_level=2.5)
        z = slide.get("zoomEffect")
        assert z is not None
        # Scale gets capped at ZOOM_MAX (1.6) — 2.5 was overwhelming on
        # full-screen exports per user feedback ("estourado na tela").
        assert z["scale"] == 1.6
        # 640/1280 = 50%, in range
        assert z["focusX"] == 50.0
        assert z["focusY"] == 50.0
        # Animation timings present
        assert z["intro"] > 0
        assert z["hold"] > 0
        assert z["outro"] > 0

    def test_zoom_scale_capped_at_max(self):
        """Even when the Agent's zoom_level is high (2.5x, 3x, ...), the
        importer caps it to a sane maximum so the magnify stays readable."""
        for incoming in [2.0, 2.5, 3.0, 5.0]:
            step = {"action_type": "click", "click_x": 640, "click_y": 360}
            slide = _step_to_slide(step, "/bg.png", 0, zoom_level=incoming)
            assert slide["zoomEffect"]["scale"] <= 1.6, (
                f"scale should be capped to 1.6 for zoom_level={incoming}"
            )

    def test_zoom_preserves_lower_zoom_levels(self):
        """Below the cap, the explicit zoom_level passes through unchanged."""
        step = {"action_type": "click", "click_x": 640, "click_y": 360}
        slide = _step_to_slide(step, "/bg.png", 0, zoom_level=1.3)
        assert slide["zoomEffect"]["scale"] == 1.3

    def test_zoom_skipped_when_no_click_coords(self):
        step = {"action_type": "scroll"}
        slide = _step_to_slide(step, "/bg.png", 0, zoom_level=2.5)
        assert "zoomEffect" not in slide

    def test_zoom_skipped_when_zoom_level_1(self):
        step = {"action_type": "click", "click_x": 100, "click_y": 100}
        slide = _step_to_slide(step, "/bg.png", 0, zoom_level=1.0)
        assert "zoomEffect" not in slide

    def test_focus_point_clamped_to_safe_window(self):
        """focusX/Y must be clamped to 20-80% so transform-origin at the
        extremes doesn't push the magnified image out of the card."""
        # Click at top-left corner
        step = {"action_type": "click", "click_x": 5, "click_y": 5}
        slide = _step_to_slide(step, "/bg.png", 0, zoom_level=1.5)
        z = slide["zoomEffect"]
        assert z["focusX"] >= 20.0
        assert z["focusY"] >= 20.0

        # Click at bottom-right corner
        step2 = {"action_type": "click", "click_x": 1270, "click_y": 710}
        slide2 = _step_to_slide(step2, "/bg.png", 0, zoom_level=1.5)
        z2 = slide2["zoomEffect"]
        assert z2["focusX"] <= 80.0
        assert z2["focusY"] <= 80.0

    def test_focus_uses_screenshot_dimensions_when_provided(self):
        """When the step declares screenshot dimensions, use those for the
        percentage calculation (PPT screenshots can be 1366x768)."""
        step = {
            "action_type": "click",
            "click_x": 683,  # half of 1366
            "click_y": 384,  # half of 768
            "screenshot_width": 1366,
            "screenshot_height": 768,
        }
        slide = _step_to_slide(step, "/bg.png", 0, zoom_level=2.5)
        z = slide["zoomEffect"]
        # Should be ~50% regardless of screenshot pixel size
        assert 49.0 <= z["focusX"] <= 51.0
        assert 49.0 <= z["focusY"] <= 51.0

    def test_invalid_zoom_level_becomes_no_effect(self):
        step = {"action_type": "click", "click_x": 100, "click_y": 100}
        slide = _step_to_slide(step, "/bg.png", 0, zoom_level="abc")
        assert "zoomEffect" not in slide

    def test_zoom_rounded_to_2_decimals(self):
        step = {"action_type": "click", "click_x": 333, "click_y": 333}
        slide = _step_to_slide(step, "/bg.png", 0, zoom_level=2.5)
        z = slide["zoomEffect"]
        # Values must be neat (max 2 decimals)
        assert z["focusX"] == round(z["focusX"], 2)
        assert z["focusY"] == round(z["focusY"], 2)
