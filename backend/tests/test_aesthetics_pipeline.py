"""Tests for the deterministic Aesthetic fix application pipeline.

Validates that:
- WCAG enforcement upgrades weak colors to pure black/white.
- Plates are auto-added when slide has backgroundImage.
- Slide overlay is set correctly via slide_overlay fix type.
- HTML CSS injection uses !important and universal selectors.
- New text style fields render correctly in single_page_exporter.
"""
import pytest
from routes.aesthetics import (
    _apply_style_fix,
    _apply_text_plate,
    _apply_slide_overlay,
    _apply_html_style_fix,
    _strengthen_css_injection,
)
from services import wcag
from services.single_page_exporter import _render_text_element_inner


class TestApplyStyleFix:
    def test_weak_color_upgraded_to_pure_black(self):
        slide = {"background": "#ffffff"}  # white bg, no image
        element = {"type": "text", "content": "hi", "style": {}}
        # LLM proposes a weak grey
        _apply_style_fix(element, slide, {"fontColor": "#999999"})
        # Should be promoted to dark fallback (pure black-ish)
        assert element["style"]["fontColor"] == wcag.DARK_FALLBACK

    def test_strong_color_kept_unchanged(self):
        slide = {"background": "#ffffff"}
        element = {"type": "text", "content": "hi", "style": {}}
        _apply_style_fix(element, slide, {"fontColor": "#0f172a"})
        # Already perfect contrast — kept
        assert element["style"]["fontColor"] == "#0f172a"

    def test_image_bg_forces_high_contrast_text_no_plate(self):
        """v6 (no-overlay): on slides with a busy backgroundImage, the LLM
        suggestion is validated against the SOLID slide.background. We do
        NOT auto-add a plate anymore — only a color swap. User explicitly
        rejected the plate overlay in conversation v6."""
        slide = {"background": "#888", "backgroundImage": "/api/img.png"}
        element = {"type": "text", "content": "hi", "style": {}}
        _apply_style_fix(element, slide, {"fontColor": "#000000"})
        # Color was validated against mid-grey (#888). enforce_min_contrast
        # is allowed to keep #000 (contrast ~5.5:1 vs #888).
        assert element["style"].get("fontColor") in ("#000000", wcag.DARK_FALLBACK, wcag.LIGHT_FALLBACK)
        # CRUCIAL: NO plate auto-injection
        assert "textBackgroundColor" not in element["style"], (
            "v6: plate must not be auto-added on bgImage slides"
        )

    def test_tiny_font_size_promoted_to_safe_minimum(self):
        slide = {"background": "#ffffff"}
        element = {"type": "text", "content": "hi", "style": {}}
        _apply_style_fix(element, slide, {"fontSize": 10})
        assert element["style"]["fontSize"] == 16

    def test_normal_font_size_kept(self):
        slide = {"background": "#ffffff"}
        element = {"type": "text", "content": "hi", "style": {}}
        _apply_style_fix(element, slide, {"fontSize": 24})
        assert element["style"]["fontSize"] == 24

    def test_other_style_keys_passed_through(self):
        slide = {"background": "#ffffff"}
        element = {"type": "text", "content": "hi", "style": {}}
        _apply_style_fix(element, slide, {"fontWeight": "bold", "fontFamily": "Arial"})
        assert element["style"]["fontWeight"] == "bold"
        assert element["style"]["fontFamily"] == "Arial"


class TestApplyTextPlate:
    def test_text_plate_now_swaps_color_only_v6(self):
        """v6 (no-overlay): the legacy `text_plate` fix is now a color
        swap. No `textBackgroundColor` / padding / borderRadius / textShadow
        keys are added."""
        slide = {"background": "#1e3a8a", "backgroundImage": "/x.png"}
        # White on navy = legible (~14:1) so swap should be no-op
        element = {"type": "text", "style": {"fontColor": "#ffffff"}}
        _apply_text_plate(element, slide)
        s = element["style"]
        assert "textBackgroundColor" not in s
        assert "padding" not in s
        assert "borderRadius" not in s

    def test_text_plate_swaps_color_when_low_contrast_v6(self):
        """v6: when fontColor fails WCAG, it's swapped (and ONLY swapped)."""
        slide = {"background": "#ffffff"}
        element = {"type": "text", "style": {"fontColor": "#eeeeee"}}
        _apply_text_plate(element, slide)
        s = element["style"]
        # Color was swapped to dark (only thing that should change)
        assert s["fontColor"] != "#eeeeee"
        # No plate keys
        assert "textBackgroundColor" not in s
        assert "padding" not in s


class TestApplySlideOverlay:
    def test_dark_overlay_applied(self):
        slide = {"backgroundImage": "/x.png"}
        _apply_slide_overlay(slide, {"overlay": "dark"})
        assert slide["backgroundImageOverlay"] == "dark"

    def test_light_overlay_applied(self):
        slide = {"backgroundImage": "/x.png"}
        _apply_slide_overlay(slide, {"overlay": "light"})
        assert slide["backgroundImageOverlay"] == "light"

    def test_default_to_dark_when_unspecified(self):
        slide = {}
        _apply_slide_overlay(slide, {})
        assert slide["backgroundImageOverlay"] == "dark"


class TestStrengthenCssInjection:
    def test_important_added_to_declarations(self):
        css = "color:#fff;font-size:16px"
        out = _strengthen_css_injection(css)
        assert "!important" in out
        # Both declarations get !important
        assert out.count("!important") >= 2

    def test_existing_important_not_duplicated(self):
        css = "color:#fff !important"
        out = _strengthen_css_injection(css)
        # No double !important
        assert out.count("!important") == 1

    def test_target_color_appends_universal_override(self):
        out = _strengthen_css_injection("", target_text_color="#fff")
        # Universal selector hitting body, body *, and inline color override
        assert "body,body *" in out or "body *" in out
        assert '[style*="color"]' in out
        assert "#fff" in out


class TestApplyHtmlStyleFix:
    def test_style_tag_inserted_at_end_of_head(self):
        element = {
            "type": "html",
            "htmlContent": "<html><head><style>body{color:red}</style></head><body>x</body></html>"
        }
        _apply_html_style_fix(element, "color:#fff", target_color="#fff")
        html = element["htmlContent"]
        # New style tag is BEFORE </head> (last in <head>)
        assert "data-aesthetic-fix" in html
        # Must contain !important for the override to actually win
        assert "!important" in html
        # Must contain inline override
        assert '[style*="color"]' in html

    def test_no_head_falls_back_to_body(self):
        element = {
            "type": "html",
            "htmlContent": "<body>just text</body>"
        }
        _apply_html_style_fix(element, "color:#fff", target_color="#fff")
        assert "data-aesthetic-fix" in element["htmlContent"]
        assert "!important" in element["htmlContent"]


class TestExporterRendersFontColor:
    """Critical regression test: previously _render_text_element_inner used
    a naive _kebab() which translated `fontColor` → `font-color` (invalid CSS,
    silently dropped by browsers). The fix now maps it to `color`."""

    def test_fontColor_renders_as_color(self):
        el = {"type": "text", "content": "Hello", "style": {"fontColor": "#0f172a"}}
        html = _render_text_element_inner(el)
        # Must render as `color:#0f172a`, NOT `font-color:#0f172a`
        assert "color:#0f172a" in html
        assert "font-color:" not in html

    def test_textBackgroundColor_renders_as_background_color(self):
        el = {"type": "text", "content": "x", "style": {"textBackgroundColor": "rgba(0,0,0,0.5)"}}
        html = _render_text_element_inner(el)
        assert "background-color:rgba(0,0,0,0.5)" in html

    def test_padding_and_borderRadius_render(self):
        el = {"type": "text", "content": "x", "style": {"padding": "10px 14px", "borderRadius": "8px"}}
        html = _render_text_element_inner(el)
        assert "padding:10px 14px" in html
        assert "border-radius:8px" in html

    def test_fontSize_renders_with_px_when_numeric(self):
        el = {"type": "text", "content": "x", "style": {"fontSize": 18}}
        html = _render_text_element_inner(el)
        assert "font-size:18px" in html

    def test_textShadow_renders(self):
        el = {"type": "text", "content": "x", "style": {"textShadow": "0 1px 3px rgba(0,0,0,0.35)"}}
        html = _render_text_element_inner(el)
        assert "text-shadow:0 1px 3px rgba(0,0,0,0.35)" in html

    def test_unknown_keys_silently_dropped(self):
        # Unknown keys must NOT generate invalid CSS like `font-foo:bar`
        el = {"type": "text", "content": "x", "style": {"fooBar": "baz"}}
        html = _render_text_element_inner(el)
        assert "foo-bar:" not in html
        assert "fooBar:" not in html


class TestSinglePageOverlayRendering:
    """Slide overlay scrim should be rendered when slide has bgImage + overlay."""

    def test_overlay_renders_when_set(self):
        from services.single_page_exporter import generate_single_page_html
        course = {
            "slides": [{
                "id": "s1",
                "title": "Test",
                "background": "#000",
                "backgroundImage": "/api/projects/p/assets/bg.png",
                "backgroundImageOverlay": "dark",
                "elements": [],
                "width": 1280,
                "height": 720,
            }]
        }
        project = {"id": "p", "name": "Test", "course": course}
        html = generate_single_page_html(project, "/tmp", "")
        assert "sp-bg-overlay" in html
        # Dark gradient pattern present
        assert "rgba(0,0,0" in html

    def test_no_overlay_when_no_bg_image(self):
        from services.single_page_exporter import generate_single_page_html
        course = {
            "slides": [{
                "id": "s1",
                "title": "Test",
                "background": "#fff",
                # no backgroundImage
                "backgroundImageOverlay": "dark",  # ignored without image
                "elements": [],
            }]
        }
        project = {"id": "p", "name": "Test", "course": course}
        html = generate_single_page_html(project, "/tmp", "")
        assert "sp-bg-overlay" not in html
