"""Tests for the universal-selector stripper.

When the LLM generates CSS like `body * { color: #fff }` for an HTML-pesado
simulator, that selector destroys contrast in nested elements (white prompt
cards, cyan buttons with dark text). The strip removes overreaching rules
in preserve mode while keeping targeted class/id selectors that the LLM
might have authored carefully.
"""
import pytest
from routes.aesthetics import (
    _strip_universal_selectors,
    _strengthen_css_injection,
    _apply_html_style_fix,
)


class TestStripUniversalSelectors:
    def test_body_star_dropped(self):
        css = "body * { color: #fff }"
        out = _strip_universal_selectors(css)
        assert "body *" not in out
        # Nothing was specific enough to keep
        assert out.strip() == ""

    def test_bare_body_dropped(self):
        css = "body { color: #fff; background: #000 }"
        out = _strip_universal_selectors(css)
        assert "body" not in out or "body{" not in out.replace(" ", "")

    def test_bare_star_dropped(self):
        css = "* { color: red }"
        out = _strip_universal_selectors(css)
        assert "*" not in out or "color" not in out

    def test_inline_attr_selector_dropped(self):
        css = '[style*="color"] { color: #fff !important }'
        out = _strip_universal_selectors(css)
        assert "[style*=" not in out

    def test_class_selector_kept(self):
        css = ".option-btn { color: #000 }"
        out = _strip_universal_selectors(css)
        assert ".option-btn" in out
        assert "#000" in out

    def test_id_selector_kept(self):
        css = "#prompt { color: #fff }"
        out = _strip_universal_selectors(css)
        assert "#prompt" in out

    def test_targeted_body_descendant_kept(self):
        css = "body label.error { color: red }"
        out = _strip_universal_selectors(css)
        assert "body label.error" in out

    def test_mixed_drops_only_dangerous(self):
        css = "body * { color: #fff } .safe-class { color: #000 }"
        out = _strip_universal_selectors(css)
        assert "body *" not in out
        assert ".safe-class" in out

    def test_comma_list_with_one_dangerous_drops_whole_rule(self):
        # If any selector in a comma list is dangerous, the whole rule is dropped
        # (we can't selectively split safe declarations from dangerous ones)
        css = ".a, body *, .b { color: red }"
        out = _strip_universal_selectors(css)
        assert "color" not in out

    def test_empty_css_returns_empty(self):
        assert _strip_universal_selectors("") == ""

    def test_no_braces_kept_as_is(self):
        # If LLM gives raw declarations without braces, leave alone
        # (they'll be wrapped by the !important step but won't have a
        # selector at all so this case shouldn't really happen)
        out = _strip_universal_selectors("color: #fff")
        assert out == "color: #fff"


class TestPreserveModeStripsLLMUniversal:
    def test_preserve_mode_drops_body_star_from_llm_css(self):
        # This is the exact bug: LLM emitted `body * {color:#fff}` and
        # destroyed contrast in nested cards/buttons.
        out = _strengthen_css_injection(
            "body * { color: #fff !important }",
            preserve_html_typography=True,
        )
        assert "body *" not in out

    def test_preserve_mode_keeps_targeted_selector_from_llm(self):
        out = _strengthen_css_injection(
            ".dark-label { color: #fff }",
            preserve_html_typography=True,
        )
        assert ".dark-label" in out

    def test_normal_mode_keeps_universal_selectors(self):
        # Non-preserve mode is for plain text elements — LLM's broad rules are OK
        out = _strengthen_css_injection(
            "body * { color: #fff }",
            preserve_html_typography=False,
        )
        assert "body *" in out


class TestEndToEndUserScenario:
    def test_simulator_with_white_card_and_cyan_buttons_unaffected(self):
        """User's reported scenario: simulator with dark body, white prompt
        card, and cyan buttons with dark text. LLM proposes
        `body * {color:#fff}` thinking it'll fix dark-mode contrast. Our
        preserve-mode pipeline must strip that rule so the white card and
        cyan buttons keep their original dark text."""
        element = {
            "type": "html",
            "htmlContent": (
                "<html><head><style>"
                "body{background:#0f172a}"
                ".prompt-box{background:#fff;color:#000;padding:1em}"
                ".option-btn{background:#22d3ee;color:#000;padding:0.5em}"
                "</style></head><body>"
                "<h1>Detector de Vieses</h1>"
                "<div class='prompt-box'>Sua missao</div>"
                "<button class='option-btn'>A) opcao</button>"
                "<button class='option-btn'>B) opcao</button>"
                "</body></html>"
            ),
        }
        # LLM proposes overreaching CSS
        _apply_html_style_fix(
            element,
            css="body * { color: #fff !important; font-size: 16px }",
            target_color="#ffffff",
            preserve_html_typography=True,
        )
        injected = element["htmlContent"]
        # Find what was actually injected
        import re as re_mod
        m = re_mod.search(r'<style data-aesthetic-fix="1">([\s\S]*?)</style>', injected)
        if m is None:
            # Fix produced nothing — that's actually OK in this case
            return
        injected_css = m.group(1)
        # The dangerous `body *` rule must NOT be present
        assert "body *" not in injected_css, (
            f"FAIL: body * survived injection in preserve mode. "
            f"Injected CSS: {injected_css}"
        )
        # font-size px must have been converted to em
        assert "16px" not in injected_css

    def test_simulator_with_targeted_fix_still_applies(self):
        """If the LLM is smart and uses a class selector, that should still work."""
        element = {
            "type": "html",
            "htmlContent": "<html><head><style>.bad-text{color:#888}</style></head><body><p class='bad-text'>x</p></body></html>",
        }
        _apply_html_style_fix(
            element,
            css=".bad-text { color: #f8fafc !important }",
            target_color="#f8fafc",
            preserve_html_typography=True,
        )
        injected = element["htmlContent"]
        assert "data-aesthetic-fix" in injected
        # Targeted class selector survives
        assert ".bad-text" in injected
