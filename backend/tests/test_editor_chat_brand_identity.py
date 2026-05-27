"""Tests for the combined `apply_brand_identity` op (2026-05-21).

Single command that applies brand background image + brand palette
(colors + font) + brand logo as watermark, all in one go. Designed as
the "instant onboarding" for imported courses.
"""
from routes.editor_chat import _apply_ops


KIT = {
    "primaryColor": "#0f172a",
    "accentColor": "#f59e0b",
    "secondaryColor": "#f8fafc",
    "fontFamily": "Inter",
}

BG = [{
    "id": "casset_aaa", "name": "Capa", "category": "cover", "tags": [],
    "url": "/api/companies/co1/assets/casset_aaa/file",
}]

LOGO_URL = "/api/companies/co1/assets/logo_001/file"


def _course():
    return [
        {"id": "s0", "title": "A", "background": "#fff", "elements": [
            {"type": "text", "content": "hi", "style": {"fontColor": "#000"}},
        ]},
        {"id": "s1", "title": "B", "background": "#fff", "elements": [
            {"type": "html", "htmlContent": "<p>quiz</p>"},
            {"type": "text", "content": "world", "style": {
                "fontColor": "#000", "padding": "12px", "textBackgroundColor": "#222",
            }},
        ]},
        {"id": "s2", "title": "C", "background": "#fff", "elements": []},
    ]


class TestApplyBrandIdentity:
    def test_all_three_components_default_on(self):
        slides = _course()
        applied = _apply_ops(slides, [{"type": "apply_brand_identity"}],
                             brand_backgrounds=BG, brand_kit=KIT, brand_logo_url=LOGO_URL)
        op_res = applied[0]
        # Background image attached
        assert op_res["backgroundImageUsed"] == BG[0]["url"]
        # Palette applied (primary color)
        assert op_res["paletteBackgroundUsed"] == "#0f172a"
        # Logo inserted on every slide (3)
        assert op_res["logoInsertedCount"] == 3
        # Font applied
        assert op_res["fontFamily"] == "Inter"

    def test_each_slide_gets_brand_bg_image(self):
        slides = _course()
        _apply_ops(slides, [{"type": "apply_brand_identity"}],
                   brand_backgrounds=BG, brand_kit=KIT, brand_logo_url=LOGO_URL)
        for s in slides:
            assert s["backgroundImage"] == BG[0]["url"]

    def test_palette_paints_solid_bg(self):
        slides = _course()
        _apply_ops(slides, [{"type": "apply_brand_identity"}],
                   brand_backgrounds=BG, brand_kit=KIT, brand_logo_url=LOGO_URL)
        for s in slides:
            assert s["background"] == "#0f172a"

    def test_text_fontColor_swapped_for_wcag(self):
        slides = _course()
        _apply_ops(slides, [{"type": "apply_brand_identity"}],
                   brand_backgrounds=BG, brand_kit=KIT, brand_logo_url=LOGO_URL)
        # Dark bg → light text required
        assert slides[0]["elements"][0]["style"]["fontColor"] == "#f8fafc"

    def test_plate_residue_stripped_via_identity_op(self):
        slides = _course()
        _apply_ops(slides, [{"type": "apply_brand_identity"}],
                   brand_backgrounds=BG, brand_kit=KIT, brand_logo_url=LOGO_URL)
        text_on_s1 = slides[1]["elements"][1]
        for banned in ("padding", "textBackgroundColor", "backgroundColor", "borderRadius"):
            assert banned not in text_on_s1["style"]

    def test_logo_element_added_with_isBrandLogo_marker(self):
        slides = _course()
        _apply_ops(slides, [{"type": "apply_brand_identity"}],
                   brand_backgrounds=BG, brand_kit=KIT, brand_logo_url=LOGO_URL)
        # Each slide should have exactly 1 logo element
        for s in slides:
            logos = [e for e in s["elements"] if e.get("isBrandLogo")]
            assert len(logos) == 1
            assert logos[0]["src"] == LOGO_URL
            assert logos[0]["type"] == "image"

    def test_logo_idempotent_on_repeated_calls(self):
        """Re-running the identity op should NOT duplicate logos."""
        slides = _course()
        for _ in range(3):
            _apply_ops(slides, [{"type": "apply_brand_identity"}],
                       brand_backgrounds=BG, brand_kit=KIT, brand_logo_url=LOGO_URL)
        for s in slides:
            logos = [e for e in s["elements"] if e.get("isBrandLogo")]
            assert len(logos) == 1, "logo duplicated across re-applications"

    def test_apply_logo_false_skips_logo(self):
        slides = _course()
        _apply_ops(slides, [{"type": "apply_brand_identity", "applyLogo": False}],
                   brand_backgrounds=BG, brand_kit=KIT, brand_logo_url=LOGO_URL)
        for s in slides:
            assert not any(e.get("isBrandLogo") for e in s["elements"])

    def test_apply_background_false_skips_image(self):
        slides = _course()
        _apply_ops(slides, [{"type": "apply_brand_identity", "applyBackground": False}],
                   brand_backgrounds=BG, brand_kit=KIT, brand_logo_url=LOGO_URL)
        for s in slides:
            assert "backgroundImage" not in s
        # Palette + logo still applied
        assert slides[0]["background"] == "#0f172a"
        assert any(e.get("isBrandLogo") for e in slides[0]["elements"])

    def test_apply_palette_false_keeps_original_colors(self):
        slides = _course()
        _apply_ops(slides, [{"type": "apply_brand_identity", "applyPalette": False}],
                   brand_backgrounds=BG, brand_kit=KIT, brand_logo_url=LOGO_URL)
        # Background colors untouched
        for s in slides:
            assert s["background"] == "#fff"
        # But BG image and logo applied
        for s in slides:
            assert s["backgroundImage"] == BG[0]["url"]
            assert any(e.get("isBrandLogo") for e in s["elements"])

    def test_range_only_affects_subset(self):
        slides = _course()
        _apply_ops(slides, [{"type": "apply_brand_identity", "fromIndex": 1, "toIndex": 2}],
                   brand_backgrounds=BG, brand_kit=KIT, brand_logo_url=LOGO_URL)
        # Slide 0 untouched
        assert "backgroundImage" not in slides[0]
        assert slides[0]["background"] == "#fff"
        assert not any(e.get("isBrandLogo") for e in slides[0]["elements"])
        # Slides 1 and 2 updated
        for idx in (1, 2):
            assert slides[idx]["backgroundImage"] == BG[0]["url"]
            assert slides[idx]["background"] == "#0f172a"

    def test_logo_corner_top_left(self):
        slides = _course()
        _apply_ops(slides, [{"type": "apply_brand_identity", "logoCorner": "top-left"}],
                   brand_backgrounds=BG, brand_kit=KIT, brand_logo_url=LOGO_URL)
        logo = next(e for e in slides[0]["elements"] if e.get("isBrandLogo"))
        assert logo["x"] == 24 and logo["y"] == 24

    def test_logo_corner_bottom_right(self):
        slides = _course()
        _apply_ops(slides, [{"type": "apply_brand_identity", "logoCorner": "bottom-right"}],
                   brand_backgrounds=BG, brand_kit=KIT, brand_logo_url=LOGO_URL)
        logo = next(e for e in slides[0]["elements"] if e.get("isBrandLogo"))
        # logo box is 96 wide × round(96/2.5)=38 tall
        # 1920 - 96 - 24 = 1800; 820 - 38 - 24 = 758
        assert logo["x"] == 1800 and logo["y"] == 758

    def test_no_logo_url_skips_logo_silently(self):
        slides = _course()
        applied = _apply_ops(slides, [{"type": "apply_brand_identity"}],
                             brand_backgrounds=BG, brand_kit=KIT, brand_logo_url="")
        # No logo elements added but BG + palette still applied
        for s in slides:
            assert not any(e.get("isBrandLogo") for e in s["elements"])
        assert applied[0]["logoInsertedCount"] == 0
        assert applied[0]["backgroundImageUsed"] == BG[0]["url"]

    def test_html_quiz_scenario_text_swap_skipped(self):
        slides = _course()
        _apply_ops(slides, [{"type": "apply_brand_identity"}],
                   brand_backgrounds=BG, brand_kit=KIT, brand_logo_url=LOGO_URL)
        # html element on s1 must NOT have fontColor injected
        html_el = slides[1]["elements"][0]
        assert html_el["type"] == "html"
        assert "fontColor" not in (html_el.get("style") or {})

    def test_palette_target_accent(self):
        slides = _course()
        _apply_ops(slides, [{
            "type": "apply_brand_identity",
            "paletteTarget": "accent",
        }], brand_backgrounds=BG, brand_kit=KIT, brand_logo_url=LOGO_URL)
        assert slides[0]["background"] == "#f59e0b"

    def test_empty_brand_kit_skips_palette_only(self):
        slides = _course()
        applied = _apply_ops(slides, [{"type": "apply_brand_identity"}],
                             brand_backgrounds=BG, brand_kit={}, brand_logo_url=LOGO_URL)
        # Background untouched (palette skipped) but bg image + logo applied
        for s in slides:
            assert s["background"] == "#fff"
            assert s["backgroundImage"] == BG[0]["url"]
            assert any(e.get("isBrandLogo") for e in s["elements"])
        assert applied[0]["paletteBackgroundUsed"] == ""
