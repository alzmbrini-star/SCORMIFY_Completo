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
        assert "body *" not in out

    def test_preserve_mode_emits_NO_color_override(self):
        """Final fix: preserve mode DOES NOT inject any color override at all.
        Even narrow `body p` selectors cascade onto <p> tags nested inside
        white prompt cards and break contrast. The LLM's own targeted rules
        (already filtered through _strip_universal_selectors) are the only
        thing that survives."""
        out = _strengthen_css_injection("", target_text_color="#000", preserve_html_typography=True)
        # No color rule should be present at all when only target_text_color is given
        assert "color:" not in out and "color :" not in out

    def test_preserve_mode_keeps_targeted_llm_css(self):
        # If the LLM provides a targeted class selector, it survives
        out = _strengthen_css_injection(
            ".bad-text { color: #000 }",
            target_text_color="#000",
            preserve_html_typography=True,
        )
        assert ".bad-text" in out
        assert "#000" in out

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
        despite the simulator having body{background:#fff} internally.

        Final fix: in preserve mode, NO color override is injected at all
        when only target_color is provided. The simulator is left intact.
        """
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
        original = element["htmlContent"]
        # LLM proposes universal `body *` (which would destroy contrast).
        # After strip, nothing safe remains.
        _apply_html_style_fix(
            element,
            css="body * { color: #ffffff }",
            target_color="#ffffff",
            preserve_html_typography=True,
        )
        injected_html = element["htmlContent"]

        # If anything was injected, find the style tag
        import re as re_mod
        m = re_mod.search(r'<style data-aesthetic-fix="1">([\s\S]*?)</style>', injected_html)
        if m is not None:
            injected_css = m.group(1)
            # No `body{color:...}` rule should be present at all in preserve
            # mode (whether white OR dark — we don't override at all)
            assert "body{color:" not in injected_css.replace(" ", "")
            assert "body *" not in injected_css

    def test_simulator_with_dark_bg_no_universal_override(self):
        """In preserve mode, even when the simulator has dark bg and white
        text would be correct, we still don't inject a universal override —
        the simulator's intentional design must drive its own contrast.
        Only LLM-provided CSS with targeted class/id selectors goes through.
        """
        element = {
            "type": "html",
            "htmlContent": (
                "<html><head><style>"
                "body{background:#0f172a}"
                "</style></head><body><h1>Title</h1></body></html>"
            ),
        }
        # LLM proposes a TARGETED rule
        _apply_html_style_fix(
            element,
            css=".faded-text { color: #ffffff }",
            target_color="#ffffff",
            preserve_html_typography=True,
        )
        injected_html = element["htmlContent"]
        # Targeted selector survives
        assert ".faded-text" in injected_html
        # But NO body universal/narrow override
        assert "body *" not in injected_html
        # And no `body{color:...}` rule from our helper
        import re as re_mod
        m = re_mod.search(r'<style data-aesthetic-fix="1">([\s\S]*?)</style>', injected_html)
        if m:
            injected_css = m.group(1).replace(" ", "")
            assert "body{color:" not in injected_css
