"""Tests for the WCAG contrast calculator + Aesthetic Analyzer pipeline."""
import pytest
from services import wcag


class TestWcagBasics:
    def test_parse_hex_short(self):
        assert wcag.parse_hex("#fff") == (255, 255, 255)
        assert wcag.parse_hex("#000") == (0, 0, 0)

    def test_parse_hex_long(self):
        assert wcag.parse_hex("#FF8800") == (255, 136, 0)
        assert wcag.parse_hex("#0f172a") == (15, 23, 42)

    def test_parse_rgb_string(self):
        assert wcag.parse_hex("rgb(10, 20, 30)") == (10, 20, 30)
        assert wcag.parse_hex("rgba(10,20,30,0.5)") == (10, 20, 30)

    def test_parse_invalid_returns_none(self):
        assert wcag.parse_hex("") is None
        assert wcag.parse_hex(None) is None
        assert wcag.parse_hex("transparent") is None
        assert wcag.parse_hex("not-a-color") is None

    def test_contrast_white_on_black_is_max(self):
        # White on black is the canonical max ratio (~21:1)
        ratio = wcag.contrast_ratio("#ffffff", "#000000")
        assert ratio > 20

    def test_contrast_white_on_white_is_min(self):
        ratio = wcag.contrast_ratio("#ffffff", "#ffffff")
        assert ratio == pytest.approx(1.0, abs=0.01)

    def test_contrast_grey_on_white_fails_aa(self):
        # #999 on #fff is 2.85:1 — fails 4.5 threshold
        ratio = wcag.contrast_ratio("#999999", "#ffffff")
        assert ratio < 4.5

    def test_contrast_dark_grey_on_white_passes_aa(self):
        # #555 on #fff is 7.46:1 — passes
        ratio = wcag.contrast_ratio("#555555", "#ffffff")
        assert ratio > 4.5


class TestEnforceMinContrast:
    def test_passing_color_unchanged(self):
        # Black on white is already >20:1 — should pass through unchanged
        assert wcag.enforce_min_contrast("#000000", "#ffffff") == "#000000"

    def test_failing_color_replaced_with_dark(self):
        # White text on white bg → must replace with dark
        result = wcag.enforce_min_contrast("#ffffff", "#ffffff")
        assert result == wcag.DARK_FALLBACK

    def test_failing_color_on_dark_bg_replaced_with_light(self):
        # Dark grey text on dark bg → must replace with light
        result = wcag.enforce_min_contrast("#222222", "#111111")
        assert result == wcag.LIGHT_FALLBACK

    def test_borderline_grey_promoted(self):
        # #888 on white = ~3.5:1 — fails 4.5. Should upgrade to dark.
        result = wcag.enforce_min_contrast("#888888", "#ffffff")
        assert result == wcag.DARK_FALLBACK


class TestPickPlateColor:
    def test_white_text_gets_dark_plate(self):
        plate = wcag.pick_plate_color("#ffffff")
        assert "0,0,0" in plate or "15,23,42" in plate or plate == wcag.DARK_PLATE

    def test_black_text_gets_light_plate(self):
        plate = wcag.pick_plate_color("#000000")
        assert plate == wcag.LIGHT_PLATE


class TestNeedsPlate:
    def test_image_background_always_needs_plate(self):
        assert wcag.needs_plate("/api/img.png", "#ffffff", "#ffffff") is True

    def test_solid_bg_with_good_contrast_does_not_need_plate(self):
        # Black on white — perfect, no plate needed
        assert wcag.needs_plate(None, "#ffffff", "#000000") is False

    def test_solid_bg_with_poor_contrast_needs_plate(self):
        # White on white — needs plate
        assert wcag.needs_plate(None, "#ffffff", "#ffffff") is True
