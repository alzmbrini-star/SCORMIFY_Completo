"""Tests for slide classification + HTML typography preservation logic.

Validates that:
- Cover slides are classified as 'capa' and get larger title suggestions in prompt context.
- HTML-heavy slides are classified as 'html_heavy' so the apply pipeline preserves their internal typography.
- The strengthen_css_injection helper converts px → em when preserve_html_typography is True.
"""
import pytest
from routes.aesthetics import (
    _classify_slide,
    _strengthen_css_injection,
    _apply_html_style_fix,
    _build_slide_context,
)


class TestClassifySlide:
    def test_first_slide_with_few_elements_is_cover(self):
        slide = {"title": "Welcome", "elements": [{"type": "text", "content": "Hi"}]}
        assert _classify_slide(slide, 0, 10) == "capa"

    def test_first_slide_with_many_elements_is_content(self):
        slide = {"title": "Intro", "elements": [{"type": "text"}] * 8}
        assert _classify_slide(slide, 0, 10) == "conteudo"

    def test_html_majority_is_html_heavy(self):
        slide = {
            "title": "Simulator",
            "elements": [
                {"type": "html", "htmlContent": "<div>x</div>"},
                {"type": "text"},
            ],
        }
        assert _classify_slide(slide, 5, 10) == "html_heavy"

    def test_full_bleed_html_is_html_heavy(self):
        # Single large HTML covering 80% of slide → html_heavy
        slide = {
            "title": "Sim",
            "width": 1920,
            "height": 1080,
            "elements": [
                {"type": "html", "width": 1700, "height": 1000, "htmlContent": "<x/>"},
                {"type": "text", "width": 200, "height": 50},
            ],
        }
        assert _classify_slide(slide, 3, 10) == "html_heavy"

    def test_regular_content_slide(self):
        slide = {
            "title": "Content",
            "elements": [
                {"type": "text"},
                {"type": "image"},
                {"type": "text"},
                {"type": "shape"},
                {"type": "text"},
            ],
        }
        assert _classify_slide(slide, 5, 10) == "conteudo"

    def test_empty_slide_first_is_cover(self):
        assert _classify_slide({"elements": []}, 0, 10) == "capa"

    def test_empty_slide_middle_is_content(self):
        assert _classify_slide({"elements": []}, 5, 10) == "conteudo"

    def test_keyword_capa_marks_as_cover(self):
        slide = {"title": "Boas-vindas ao curso", "elements": [{"type": "text"}, {"type": "image"}]}
        assert _classify_slide(slide, 5, 10) == "capa"


class TestSlideContextLabel:
    def test_cover_slide_gets_capa_label(self):
        slide = {"title": "Welcome", "elements": [{"type": "text"}]}
        ctx = _build_slide_context(slide, 0, 10)
        assert "[CAPA]" in ctx

    def test_content_slide_gets_conteudo_label(self):
        slide = {"title": "Content", "elements": [{"type": "text"}] * 6}
        ctx = _build_slide_context(slide, 5, 10)
        assert "[CONTEUDO]" in ctx

    def test_html_heavy_slide_gets_html_pesado_label(self):
        slide = {
            "title": "Simulator",
            "elements": [
                {"type": "html", "htmlContent": "<x/>"},
                {"type": "html", "htmlContent": "<y/>"},
            ],
        }
        ctx = _build_slide_context(slide, 3, 10)
        assert "[HTML-PESADO]" in ctx


class TestPreserveHtmlTypography:
    def test_px_font_size_converted_to_em(self):
        css = "color:#fff;font-size:18px"
        out = _strengthen_css_injection(css, preserve_html_typography=True)
        assert "18px" not in out, "Pixel font-size must NOT survive in preserve mode"
        assert "1.05em" in out, "Should convert to relative em"
        assert "color" in out

    def test_em_font_size_kept_unchanged(self):
        css = "font-size:1.2em"
        out = _strengthen_css_injection(css, preserve_html_typography=True)
        assert "1.2em" in out

    def test_padding_stripped_in_preserve_mode(self):
        css = "padding:20px;color:#fff"
        out = _strengthen_css_injection(css, preserve_html_typography=True)
        assert "padding" not in out, "Padding should be stripped to preserve simulator design"
        assert "color" in out

    def test_margin_stripped_in_preserve_mode(self):
        css = "margin:10px;background:#000"
        out = _strengthen_css_injection(css, preserve_html_typography=True)
        assert "margin" not in out
        assert "background" in out

    def test_line_height_stripped_in_preserve_mode(self):
        css = "line-height:1.5;color:#fff"
        out = _strengthen_css_injection(css, preserve_html_typography=True)
        assert "line-height" not in out

    def test_normal_mode_keeps_px_and_padding(self):
        # When NOT preserving, all properties pass through with !important
        css = "font-size:18px;padding:20px"
        out = _strengthen_css_injection(css, preserve_html_typography=False)
        assert "18px" in out
        assert "padding" in out


class TestApplyHtmlStyleFixPreservation:
    def test_preserve_mode_strips_pixel_font_size_in_simulator(self):
        element = {
            "type": "html",
            "htmlContent": "<html><head></head><body>x</body></html>",
        }
        _apply_html_style_fix(
            element,
            "color:#f8fafc;font-size:14px;padding:8px",
            target_color="#f8fafc",
            preserve_html_typography=True,
        )
        html = element["htmlContent"]
        # Color override survives
        assert "f8fafc" in html
        # px font size and padding NOT in the injection
        assert "font-size:14px" not in html
        assert "padding:8px" not in html

    def test_normal_mode_keeps_pixel_font_size(self):
        element = {
            "type": "html",
            "htmlContent": "<html><head></head><body>x</body></html>",
        }
        _apply_html_style_fix(
            element,
            "color:#f8fafc;font-size:14px;padding:8px",
            target_color="#f8fafc",
            preserve_html_typography=False,
        )
        html = element["htmlContent"]
        assert "font-size:14px" in html
        assert "padding:8px" in html
