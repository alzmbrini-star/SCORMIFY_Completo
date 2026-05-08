"""Critical regression tests for the 'invisible text after apply' bug.

The Aesthetic Analyzer was forcing white text on simulators (built by the
AI Agent) regardless of their internal background. When a quiz/simulator
had `body{background:#fff}` (a white card on top of a dark slide), the
universal `body * {color:#fff}` injection turned every label, title and
input placeholder invisible.

Fix: detect the simulator's internal background from htmlContent, then
sanity-check `target_text_color` via WCAG before emitting the override.
If contrast fails, flip the polarity automatically.
"""
import pytest
from routes.aesthetics import (
    _extract_dominant_html_bg,
    _strengthen_css_injection,
    _apply_html_style_fix,
)


# ---------------------------------------------------------------------------
# _extract_dominant_html_bg
# ---------------------------------------------------------------------------

class TestExtractDominantHtmlBg:
    def test_body_in_style_block(self):
        html = "<html><head><style>body { background: #fff; color: #000 }</style></head><body>x</body></html>"
        assert _extract_dominant_html_bg(html) == "#fff"

    def test_body_background_color_property(self):
        html = "<html><head><style>body{background-color:#f5f5f5}</style></head><body>x</body></html>"
        assert _extract_dominant_html_bg(html) == "#f5f5f5"

    def test_body_inline_style(self):
        html = '<html><body style="background: #ffffff; padding: 20px">x</body></html>'
        assert _extract_dominant_html_bg(html) == "#ffffff"

    def test_container_class_inline_bg(self):
        html = '<html><body><div class="container" style="background:#fff;padding:1em">x</div></body></html>'
        assert _extract_dominant_html_bg(html) == "#fff"

    def test_gradient_rejected(self):
        html = "<html><head><style>body{background:linear-gradient(red,blue)}</style></head><body>x</body></html>"
        # gradient cannot be WCAG-checked
        assert _extract_dominant_html_bg(html) is None

    def test_image_url_rejected(self):
        html = "<html><head><style>body{background:url(x.png)}</style></head><body>x</body></html>"
        assert _extract_dominant_html_bg(html) is None

    def test_no_bg_returns_none(self):
        html = "<html><body>just text</body></html>"
        assert _extract_dominant_html_bg(html) is None

    def test_priority_style_over_container(self):
        # body in <style> wins over container inline
        html = '<html><head><style>body{background:#0f172a}</style></head><body><div class="container" style="background:#fff">x</div></body></html>'
        assert _extract_dominant_html_bg(html) == "#0f172a"


# ---------------------------------------------------------------------------
# _strengthen_css_injection — WCAG sanity-check of target_text_color
# ---------------------------------------------------------------------------

class TestTargetColorPolarityFlip:
    def test_white_text_on_white_bg_flips_to_dark(self):
        # The user's actual bug: target=white, bg=white → flip to dark
        out = _strengthen_css_injection("", target_text_color="#ffffff", html_bg="#ffffff")
        # The flipped color should be the dark fallback, NOT white
        assert "#ffffff" not in out.replace("#fff", "")  # tolerant for "fff" being part of text
        # Must contain the dark fallback color (or at least something non-white)
        assert "#0f172a" in out or "#000" in out

    def test_dark_text_on_dark_bg_flips_to_light(self):
        out = _strengthen_css_injection("", target_text_color="#0f172a", html_bg="#111111")
        assert "#0f172a" not in out
        assert "#f8fafc" in out or "#fff" in out

    def test_good_contrast_kept(self):
        # White on dark bg is fine — keep it
        out = _strengthen_css_injection("", target_text_color="#ffffff", html_bg="#000000")
        assert "#ffffff" in out

    def test_no_html_bg_skips_check(self):
        # When we cannot detect bg, trust the LLM's choice
        out = _strengthen_css_injection("", target_text_color="#ffffff", html_bg=None)
        assert "#ffffff" in out


# ---------------------------------------------------------------------------
# _strengthen_css_injection — narrower selectors in preserve mode
# ---------------------------------------------------------------------------

class TestPreserveModeSelectors:
    def test_preserve_mode_avoids_universal_body_star(self):
        out = _strengthen_css_injection("", target_text_color="#000", preserve_html_typography=True)
        # Universal `body *` selector must NOT appear in preserve mode
        # (it would override intentional contrast inside nested cards)
        assert "body *" not in out

    def test_preserve_mode_uses_text_tag_selectors(self):
        out = _strengthen_css_injection("", target_text_color="#000", preserve_html_typography=True)
        # Should target text-bearing tags only
        assert "body p" in out
        assert "body h1" in out
        assert "body label" in out

    def test_preserve_mode_skips_elements_with_background(self):
        out = _strengthen_css_injection("", target_text_color="#000", preserve_html_typography=True)
        # Skip elements with their own bg (intentional cards)
        assert ":not([style*=background])" in out

    def test_normal_mode_uses_universal_selector(self):
        out = _strengthen_css_injection("", target_text_color="#000", preserve_html_typography=False)
        assert "body *" in out


# ---------------------------------------------------------------------------
# End-to-end regression of the user's bug
# ---------------------------------------------------------------------------

class TestUserBugRegression:
    def test_simulator_with_white_bg_does_not_get_white_text(self):
        """User reported: card branco com texto preto legível (antes) ficou
        com tudo invisível (depois). Cause: `body * {color:#fff}` injected
        despite the simulator having body{background:#fff} internally."""
        element = {
            "type": "html",
            "htmlContent": (
                "<html><head><style>"
                "body{background:#ffffff;color:#0f172a;padding:20px}"
                ".container{background:#fff}"
                "</style></head><body>"
                "<div class='container'>"
                "<h1>Desafio do Descomplicador</h1>"
                "<p>Sua missão: Transformar...</p>"
                "<input placeholder='Digite aqui'/>"
                "</div></body></html>"
            ),
        }
        # LLM proposes white text (which is wrong for this internally-white card)
        _apply_html_style_fix(
            element,
            css="color:#ffffff",
            target_color="#ffffff",
            preserve_html_typography=True,
        )
        injected_html = element["htmlContent"]
        # The aesthetic-fix style tag should NOT contain `color:#ffffff` for body
        # (the polarity check should have flipped it to dark)
        # Find the injected style tag
        import re as re_mod
        m = re_mod.search(r'<style data-aesthetic-fix="1">([\s\S]*?)</style>', injected_html)
        assert m is not None, "Aesthetic fix style tag must be present"
        injected_css = m.group(1)
        # In the injected CSS, the body color override must NOT be white
        # (the WCAG check must have flipped it)
        # Allow #fff or #ffffff to appear ONLY inside !important markers etc — but the body{color:...} must be dark
        body_color = re_mod.search(r"body\s*\{\s*color\s*:\s*([^;}!]+)", injected_css)
        assert body_color is not None
        chosen_color = body_color.group(1).strip().lower()
        assert chosen_color not in ("#ffffff", "#fff", "white"), (
            f"FAIL: body color was set to {chosen_color} on a white-background simulator. "
            "This is the exact bug the user reported."
        )

    def test_simulator_with_dark_bg_keeps_white_text(self):
        """When the simulator has a DARK internal background (e.g., dark mode
        UI), forcing white text is correct and must be kept."""
        element = {
            "type": "html",
            "htmlContent": (
                "<html><head><style>"
                "body{background:#0f172a}"
                "</style></head><body><h1>Title</h1></body></html>"
            ),
        }
        _apply_html_style_fix(
            element,
            css="color:#ffffff",
            target_color="#ffffff",
            preserve_html_typography=True,
        )
        injected_html = element["htmlContent"]
        # Must keep white because contrast is good
        assert "#ffffff" in injected_html
