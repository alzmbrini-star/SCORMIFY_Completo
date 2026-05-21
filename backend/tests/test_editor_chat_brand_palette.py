"""Tests for Editor Chat `apply_brand_palette` op (2026-05-21).

Applies the company's BrandKit colors (and font) to slides, sweeping
fontColor to win WCAG AA contrast against the new solid background.
NO plates — color-swap strategy only.
"""
from routes.editor_chat import _apply_ops


KIT = {
    "primaryColor": "#0f172a",   # near-black slate
    "accentColor": "#f59e0b",    # amber-500
    "secondaryColor": "#f8fafc", # near-white
    "fontFamily": "Inter, sans-serif",
}


def _course():
    return [
        {"id": "s0", "title": "A", "background": "#ffffff", "elements": [
            {"type": "text", "content": "hi", "style": {"fontColor": "#666", "fontSize": 16}},
        ]},
        {"id": "s1", "title": "B", "background": "#ffffff",
         "backgroundImage": "/api/old/bg.png",
         "elements": [
            {"type": "html", "htmlContent": "<p>do not touch</p>", "style": {}},
            {"type": "text", "content": "world", "style": {
                "fontColor": "#000", "textBackgroundColor": "#0f172a",  # plate residue
                "padding": "12px", "borderRadius": "8px",
            }},
        ]},
        {"id": "s2", "title": "C", "background": "#ffffff", "elements": []},
    ]


class TestApplyBrandPalette:
    def test_default_primary_paints_all_slides(self):
        slides = _course()
        applied = _apply_ops(slides, [{"type": "apply_brand_palette"}],
                             brand_kit=KIT)
        # All 3 slides get the primary color as background
        for s in slides:
            assert s["background"] == "#0f172a"
        assert applied[0]["backgroundUsed"] == "#0f172a"
        assert applied[0]["affectedSlides"] == [0, 1, 2]

    def test_text_font_color_swapped_for_wcag(self):
        slides = _course()
        _apply_ops(slides, [{"type": "apply_brand_palette"}], brand_kit=KIT)
        # Text element on s0: was #666 on white, now needs white-ish for dark bg
        c = slides[0]["elements"][0]["style"]["fontColor"]
        assert c == "#f8fafc"  # LIGHT_FALLBACK
        # color alias kept in sync
        assert slides[0]["elements"][0]["style"]["color"] == "#f8fafc"

    def test_brand_font_family_applied_to_text(self):
        slides = _course()
        _apply_ops(slides, [{"type": "apply_brand_palette"}], brand_kit=KIT)
        assert slides[0]["elements"][0]["style"]["fontFamily"] == "Inter, sans-serif"

    def test_html_quiz_scenario_image_shape_skipped(self):
        slides = _course()
        _apply_ops(slides, [{"type": "apply_brand_palette"}], brand_kit=KIT)
        # The html element on s1 stays untouched
        html_el = slides[1]["elements"][0]
        assert html_el["type"] == "html"
        assert "fontColor" not in (html_el.get("style") or {})

    def test_plate_residue_stripped_from_text(self):
        slides = _course()
        _apply_ops(slides, [{"type": "apply_brand_palette"}], brand_kit=KIT)
        # Text on s1: previously had textBackgroundColor + padding + borderRadius
        st = slides[1]["elements"][1]["style"]
        for banned in ("textBackgroundColor", "backgroundColor", "padding", "borderRadius"):
            assert banned not in st, f"banned {banned} still present"

    def test_target_accent_uses_accent_color(self):
        slides = _course()
        _apply_ops(slides, [{"type": "apply_brand_palette", "target": "accent"}],
                   brand_kit=KIT)
        assert slides[0]["background"] == "#f59e0b"
        # Amber is bright → text should be dark
        assert slides[0]["elements"][0]["style"]["fontColor"] == "#0f172a"

    def test_target_secondary_uses_secondary(self):
        slides = _course()
        _apply_ops(slides, [{"type": "apply_brand_palette", "target": "secondary"}],
                   brand_kit=KIT)
        assert slides[0]["background"] == "#f8fafc"

    def test_target_fallback_when_missing(self):
        slides = _course()
        kit = {"primaryColor": "#1e293b"}  # only primary defined
        _apply_ops(slides, [{"type": "apply_brand_palette", "target": "accent"}],
                   brand_kit=kit)
        # accent not defined → falls back to primary
        assert slides[0]["background"] == "#1e293b"

    def test_range_from_to_inclusive(self):
        slides = _course()
        _apply_ops(slides, [{
            "type": "apply_brand_palette",
            "fromIndex": 1, "toIndex": 2,
        }], brand_kit=KIT)
        # Slide 0 untouched
        assert slides[0]["background"] == "#ffffff"
        assert slides[1]["background"] == "#0f172a"
        assert slides[2]["background"] == "#0f172a"

    def test_clear_background_image_option(self):
        slides = _course()
        assert slides[1].get("backgroundImage")  # precondition
        _apply_ops(slides, [{
            "type": "apply_brand_palette",
            "allSlides": True,
            "clearBackgroundImage": True,
        }], brand_kit=KIT)
        assert "backgroundImage" not in slides[1]

    def test_preserves_background_image_by_default(self):
        slides = _course()
        _apply_ops(slides, [{"type": "apply_brand_palette"}], brand_kit=KIT)
        # backgroundImage NOT cleared unless explicitly asked
        assert slides[1].get("backgroundImage") == "/api/old/bg.png"

    def test_empty_kit_is_silent_noop(self):
        slides = _course()
        applied = _apply_ops(slides, [{"type": "apply_brand_palette"}], brand_kit={})
        assert applied == []
        # Backgrounds untouched
        assert slides[0]["background"] == "#ffffff"

    def test_invalid_hex_in_kit_skipped(self):
        slides = _course()
        kit = {"primaryColor": "not-a-color"}
        applied = _apply_ops(slides, [{"type": "apply_brand_palette"}], brand_kit=kit)
        assert applied == []

    def test_text_elements_count_in_applied_payload(self):
        slides = _course()
        applied = _apply_ops(slides, [{"type": "apply_brand_palette"}], brand_kit=KIT)
        # 1 text on s0 + 1 text on s1 + 0 on s2 = 2 text swaps
        assert applied[0]["textElementsUpdated"] == 2

    def test_op_records_font_family(self):
        slides = _course()
        applied = _apply_ops(slides, [{"type": "apply_brand_palette"}], brand_kit=KIT)
        assert applied[0]["fontFamily"] == "Inter, sans-serif"
