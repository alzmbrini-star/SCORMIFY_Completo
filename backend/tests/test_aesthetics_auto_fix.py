"""Tests for the deterministic LLM-independent auto-fix-contrast pipeline.

This is the feature that fixes the user's actual production bug:
simulators built by the AI Agent that have white text on light backgrounds
INSIDE the simulator (e.g., `.challenge-prompt {color:#fff;background:#e6e9ff}`).
The LLM never managed to fix it because it kept proposing universal
selectors that got stripped. The deterministic analyzer reads the CSS,
detects bad contrast, and emits targeted class overrides.
"""
import pytest
from routes.aesthetics import (
    _parse_html_css_rules,
    _resolve_background_for_selector,
    _auto_fix_html_contrast,
    _repair_html_document_contrast,
    _repair_element_contrast,
    _clean_aesthetic_fixes_from_html,
    _apply_style_fix,
)


class TestParseHtmlCssRules:
    def test_extracts_color_and_background_from_same_rule(self):
        html = '<html><head><style>.x{color:#fff;background:#e6e9ff;padding:10px}</style></head></html>'
        rules = _parse_html_css_rules(html)
        assert len(rules) == 1
        assert rules[0]["selector"] == ".x"
        assert rules[0]["color"] == "#fff"
        assert rules[0]["background"] == "#e6e9ff"

    def test_merges_separate_rules_for_same_selector(self):
        html = '<html><head><style>.x{background:#fff} .x{color:#000}</style></head></html>'
        rules = _parse_html_css_rules(html)
        assert len(rules) == 1
        assert rules[0]["color"] == "#000"
        assert rules[0]["background"] == "#fff"

    def test_skips_aesthetic_fix_tags(self):
        html = (
            '<html><head>'
            '<style>.real{color:#fff;background:#000}</style>'
            '<style data-aesthetic-fix="1">.fake{color:#0f172a}</style>'
            '</head></html>'
        )
        rules = _parse_html_css_rules(html)
        # Only the real rule should be parsed
        assert len(rules) == 1
        assert rules[0]["selector"] == ".real"

    def test_skips_at_rules(self):
        html = '<html><head><style>@keyframes spin{from{color:red}} .x{color:#000}</style></head></html>'
        rules = _parse_html_css_rules(html)
        # @keyframes content is in a nested block we skip via the at-rule check
        # But the inner from{color:red} might leak — accept either, just ensure .x is parsed
        assert any(r["selector"] == ".x" for r in rules)

    def test_skips_gradient_backgrounds(self):
        html = '<html><head><style>.x{color:#fff;background:linear-gradient(red,blue)}</style></head></html>'
        rules = _parse_html_css_rules(html)
        # Color extracted, background NOT (it's a gradient)
        assert rules[0]["color"] == "#fff"
        assert rules[0]["background"] is None


class TestResolveBackgroundForSelector:
    def test_self_background(self):
        rules = [{"selector": ".x", "color": None, "background": "#fff"}]
        assert _resolve_background_for_selector(rules, ".x") == "#fff"

    def test_descendant_walks_to_parent(self):
        rules = [
            {"selector": ".card", "color": None, "background": "#fff"},
            {"selector": ".card .child", "color": "#fff", "background": None},
        ]
        assert _resolve_background_for_selector(rules, ".card .child") == "#fff"

    def test_falls_back_when_unknown(self):
        rules = []
        assert _resolve_background_for_selector(rules, ".unknown", fallback="#abc") == "#abc"


class TestAutoFixHtmlContrast:
    def test_user_bug_case_white_on_light_lavender(self):
        """User's exact case: `.challenge-prompt` has white text on light
        lavender background (~1.5:1 contrast). Auto-fix must emit a
        targeted override flipping color to dark."""
        html = (
            '<html><head><style>'
            'body{background:#fff;font-family:sans-serif}'
            '.challenge-prompt{color:#fff;background:#e6e9ff;padding:14px;border-radius:8px}'
            '</style></head><body>'
            '<div class="challenge-prompt">Solicito a vossa senhoria...</div>'
            '</body></html>'
        )
        css = _auto_fix_html_contrast(html)
        assert ".challenge-prompt" in css
        assert "color:" in css.replace(" ", "")
        # The new color must be dark (not white)
        assert "#fff" not in css and "#ffffff" not in css.lower()
        # !important is required to win specificity
        assert "!important" in css

    def test_skips_rules_with_good_contrast(self):
        html = (
            '<html><head><style>'
            '.title{color:#000;background:#fff}'
            '.body-text{color:#0f172a;background:#f0f0f0}'
            '</style></head></html>'
        )
        css = _auto_fix_html_contrast(html)
        # Both have good contrast → no override needed
        assert css == ""

    def test_skips_universal_selectors(self):
        html = '<html><head><style>body *{color:#fff;background:#fff}</style></head></html>'
        css = _auto_fix_html_contrast(html)
        # `body *` is universal — never override
        assert "body *" not in css

    def test_uses_descendant_chain_for_bg(self):
        html = (
            '<html><head><style>'
            '.card{background:#ffffff;padding:20px}'
            '.card .label{color:#dddddd}'  # gray on white = ~1.5:1
            '</style></head></html>'
        )
        css = _auto_fix_html_contrast(html)
        assert ".card .label" in css
        assert "!important" in css

    def test_falls_back_to_body_bg(self):
        html = (
            '<html><head><style>'
            'body{background:#ffffff}'
            '.no-bg-of-its-own{color:#eeeeee}'  # near-white on white-body
            '</style></head></html>'
        )
        css = _auto_fix_html_contrast(html)
        assert ".no-bg-of-its-own" in css

    def test_no_styles_returns_empty(self):
        html = '<html><body>no styles</body></html>'
        assert _auto_fix_html_contrast(html) == ""

    def test_multiple_problems_each_get_targeted_fix(self):
        html = (
            '<html><head><style>'
            '.a{color:#fff;background:#fff}'
            '.b{color:#000;background:#000}'
            '.c{color:#0f172a;background:#fff}'  # good — should NOT be in output
            '</style></head></html>'
        )
        css = _auto_fix_html_contrast(html)
        assert ".a" in css and ".b" in css
        assert ".c { color" not in css.replace("  ", " ")

    def test_each_selector_only_emitted_once(self):
        """Even if the LLM provides duplicates, each selector should get
        only one override (not stack)."""
        html = (
            '<html><head><style>'
            '.x{color:#fff;background:#fff}'
            '.x{color:#fff}'  # duplicate
            '</style></head></html>'
        )
        css = _auto_fix_html_contrast(html)
        # Should only emit one rule for .x
        assert css.count(".x {") == 1 or css.count(".x{") == 1


class TestDomAwareContrastRepair:
    def test_inherited_white_text_inside_white_cards_is_repaired(self):
        """Regression for the blank white cards in the user's screenshot.

        The foreground is inherited from the dark body while the white
        background is painted by a nested card. Rule-only analysis cannot
        pair those two declarations; DOM-aware analysis must.
        """
        html = (
            "<html><head><style>"
            "body{background:#1c1917;color:#ffffff}"
            ".summary-card{background:#ffffff;border-radius:8px}"
            "</style></head><body>"
            "<div class='summary-card'><p>Conceito-chave visivel</p></div>"
            "</body></html>"
        )
        repaired, count = _repair_html_document_contrast(html, "#1c1917")
        assert count >= 1
        assert 'data-aesthetic-contrast-fix="dark"' in repaired
        assert "#0f172a" in repaired

    def test_inherited_dark_text_inside_dark_blue_banner_is_repaired(self):
        """Regression for the dark text on the blue pill/banner screenshot."""
        html = (
            "<html><head><style>"
            "body{background:#ffffff;color:#0f172a}"
            ".insight{background:#23456b;border-radius:24px}"
            "</style></head><body>"
            "<div class='insight'><span>Identifique seu nivel de confianca</span></div>"
            "</body></html>"
        )
        repaired, count = _repair_html_document_contrast(html, "#ffffff")
        assert count >= 1
        assert 'data-aesthetic-contrast-fix="light"' in repaired
        assert "#f8fafc" in repaired

    def test_nested_dark_card_preserves_good_white_text(self):
        html = (
            "<html><head><style>"
            "body{background:#ffffff;color:#0f172a}"
            ".quiz{background:#111827;color:#f8fafc}"
            "</style></head><body>"
            "<div class='quiz'><p>Quiz legivel</p></div>"
            "</body></html>"
        )
        repaired, count = _repair_html_document_contrast(html, "#ffffff")
        assert count == 0
        assert "data-aesthetic-contrast-fix" not in repaired

    def test_cleanup_removes_dom_markers_and_fix_style(self):
        html = (
            '<style data-aesthetic-fix="1">x{color:black}</style>'
            '<p data-aesthetic-contrast-fix="dark">Texto</p>'
        )
        cleaned = _clean_aesthetic_fixes_from_html(html)
        assert "data-aesthetic-fix" not in cleaned
        assert "data-aesthetic-contrast-fix" not in cleaned

    def test_regular_text_uses_its_own_banner_background(self):
        element = {
            "type": "text",
            "content": "Sabia que?",
            "style": {
                "fontColor": "#0f172a",
                "backgroundColor": "#23456b",
            },
        }
        slide = {"background": "#ffffff", "elements": [element]}
        assert _repair_element_contrast(element, slide) == 1
        assert element["style"]["fontColor"] == "#f8fafc"
        # The authored blue banner is a real design surface, not a disposable
        # analyzer plate, and must be preserved.
        assert element["style"]["backgroundColor"] == "#23456b"

    def test_style_fix_does_not_delete_authored_background(self):
        element = {
            "type": "text",
            "content": "Faixa informativa",
            "style": {
                "fontColor": "#0f172a",
                "backgroundColor": "#23456b",
                "borderRadius": 24,
            },
        }
        slide = {"background": "#ffffff", "elements": [element]}
        assert _apply_style_fix(element, slide, {"fontWeight": 600})
        assert element["style"]["backgroundColor"] == "#23456b"
        assert element["style"]["borderRadius"] == 24
        assert element["style"]["fontColor"] == "#f8fafc"
