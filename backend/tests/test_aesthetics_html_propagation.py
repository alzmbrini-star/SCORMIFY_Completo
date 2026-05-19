"""Tests for the HTML inline-style propagation fix in the Aesthetic Analyzer.

User bug (P0): when the LLM emits a `style` fix on a `type=html` element
(e.g., the "Fontes" suggestion that says "increase fontSize to 48"), only
the OUTER element.style.fontSize was being updated. The visible text inside
the iframe stayed at the original size because the inline `<h2 style="font-size:31px">`
inside htmlContent was untouched.

The fix: `_apply_style_fix` now calls `_propagate_style_to_html_content`
which uses BeautifulSoup to REWRITE inline styles in htmlContent directly.
"""
import copy
import pytest

from routes.aesthetics import (
    _apply_style_fix,
    _propagate_style_to_html_content,
    _rewrite_inline_color,
    _rewrite_inline_font_size,
)


# ---------------------------------------------------------------------------
# Reproducer from real user data — project a0b4069e-... slide 9 element 1
# ---------------------------------------------------------------------------

USER_BUG_HTML = (
    '<div style="padding:20px;font-family:Inter, sans-serif;">'
    '<h2 style="font-family:Inter, sans-serif;font-size:31px;font-weight:700;'
    'color:#ffffff;margin:20px 0 14px 0;text-align:center;">'
    'Conclusão e Próximos Passos</h2>'
    '<h3>Sintetizando o Aprendizado</h3>'
    '<p style="font-family:Inter, sans-serif;font-size:20px;'
    'color:rgba(255,255,255,0.75);line-height:1.7;margin:0 0 12px 0;'
    'text-align:center;">'
    'Ao longo deste treinamento, exploramos...</p>'
    '</div>'
)


def _make_user_bug_element_and_slide():
    return (
        {"type": "html", "htmlContent": USER_BUG_HTML, "style": {}},
        {"background": "#1e3a8a", "backgroundImage": "/api/...img.jpg"},
    )


def test_user_fontes_suggestion_scales_inline_font_sizes():
    """LLM 'Fontes' fix: fontSize 31 -> 48 should grow the visible h2."""
    el, sl = _make_user_bug_element_and_slide()
    # Exactly the change set the user's analysis emits
    fix_changes = {"fontSize": 48, "fontWeight": "800", "fontColor": "#f8fafc"}
    applied = _apply_style_fix(el, sl, fix_changes)

    assert applied is True, "style fix must report a change"
    new_html = el["htmlContent"]

    # The dominant inline font-size (was 31px) MUST be exactly the target 48px
    assert "font-size:48px" in new_html, "Title should grow to the target px"
    # The 20px paragraph should scale proportionally (20 * 48/31 ≈ 31)
    assert "font-size:20px" not in new_html, "Paragraph should also scale"
    # Outer element.style.fontSize is also updated (legacy field, no regression)
    assert el["style"]["fontSize"] == 48
    assert el["style"]["fontWeight"] == "800"


def test_user_fontes_suggestion_propagates_font_weight():
    """h2 had font-weight:700 — must become 800 per the LLM fix."""
    el, sl = _make_user_bug_element_and_slide()
    _apply_style_fix(el, sl, {"fontSize": 48, "fontWeight": "800", "fontColor": "#f8fafc"})
    new_html = el["htmlContent"]
    assert "font-weight:800" in new_html, "h2 inline font-weight should be replaced"
    # The paragraph had NO font-weight declaration → must STAY without it
    assert new_html.count("font-weight") <= 2, (
        "Should not add font-weight to tags that didn't have it"
    )


def test_idempotent_apply():
    """Applying the same fix twice must produce the same html (no piling)."""
    el, sl = _make_user_bug_element_and_slide()
    _apply_style_fix(el, sl, {"fontSize": 48, "fontWeight": "800", "fontColor": "#f8fafc"})
    after_first = el["htmlContent"]
    _apply_style_fix(el, sl, {"fontSize": 48, "fontWeight": "800", "fontColor": "#f8fafc"})
    after_second = el["htmlContent"]
    assert after_first == after_second


# ---------------------------------------------------------------------------
# White-on-white scenario (older recurring bug)
# ---------------------------------------------------------------------------

WHITE_ON_WHITE_HTML = (
    '<div style="padding:20px;background:#ffffff;">'
    '<h2 style="color:#ffffff;font-size:32px;">Invisible Title</h2>'
    '<p style="color:#ffffff;font-size:18px;">Invisible body text</p>'
    '</div>'
)


def test_white_on_white_in_html_forced_to_dark():
    el = {"type": "html", "htmlContent": WHITE_ON_WHITE_HTML, "style": {}}
    sl = {"background": "#ffffff"}
    # LLM proposes only fontSize change — we expect the contrast sweep to
    # ALSO fix the invisible inline colors.
    applied = _apply_style_fix(el, sl, {"fontSize": 56})
    assert applied is True
    new_html = el["htmlContent"]
    # Inline `color:#ffffff` MUST be replaced (would be invisible on white bg)
    assert "color:#ffffff" not in new_html.lower(), (
        "Invisible white-on-white inline color must be rewritten"
    )
    # h2 grows to 56px exactly (was the dominant size at 32)
    assert "font-size:56px" in new_html


def test_legible_accent_colors_preserved():
    """Brand orange `color:#f59e0b` on dark navy bg already has decent contrast
    relative to white. The propagation MUST NOT flatten intentional accents
    when the LLM color change is purely cosmetic.

    Specifically: with new_color=#f8fafc (almost white) and an existing
    `color:#f59e0b` on `background:#1e3a8a` (orange on navy), the orange
    has ~6.4:1 contrast — passes WCAG. We should NOT rewrite it.
    """
    html = (
        '<div style="background:#1e3a8a;padding:10px;">'
        '<span style="color:#f59e0b;font-size:17px;">Hora de Praticar!</span>'
        '<h2 style="color:#ffffff;font-size:34px;">Teste seus Conhecimentos</h2>'
        '</div>'
    )
    el = {"type": "html", "htmlContent": html, "style": {}}
    sl = {"background": "#1e3a8a"}
    _apply_style_fix(el, sl, {"fontSize": 48, "fontColor": "#f8fafc"})
    new_html = el["htmlContent"]
    # Orange accent has good contrast vs navy — must be PRESERVED
    assert "#f59e0b" in new_html, "Intentional accent color must not be flattened"
    # White title color is also legible on navy — accepted to be rewritten
    # to #f8fafc since the LLM explicitly requested it (and contrast is fine)
    # Either #ffffff or #f8fafc is acceptable; both readable.
    title_color_ok = ("color:#f8fafc" in new_html.lower()) or ("color:#ffffff" in new_html.lower())
    assert title_color_ok


# ---------------------------------------------------------------------------
# Unit tests for the inline rewriter helpers
# ---------------------------------------------------------------------------

def test_rewrite_inline_color_only_when_failing():
    # White on white fails → replace
    out = _rewrite_inline_color("color:#ffffff;font-size:20px", "#0f172a", "#ffffff", only_when_failing=True)
    assert "color:#0f172a" in out
    # Orange on navy passes → keep
    out = _rewrite_inline_color("color:#f59e0b;font-size:17px", "#000000", "#1e3a8a", only_when_failing=True)
    assert "color:#f59e0b" in out
    assert "color:#000000" not in out


def test_rewrite_inline_font_size_scales_and_targets():
    # Title (dominant) → exactly target_size
    out = _rewrite_inline_font_size("font-size:31px", scale=48/31.0, target_size=48, is_dominant_tag=True)
    assert "font-size:48px" in out
    # Other text → proportional
    out = _rewrite_inline_font_size("font-size:20px", scale=48/31.0, target_size=48, is_dominant_tag=False)
    assert "font-size:31px" in out  # 20 * 48/31 ≈ 30.97 → rounds to 31
    # No px (em-based) → untouched
    out = _rewrite_inline_font_size("font-size:1.5em", scale=2.0, target_size=48)
    assert "font-size:1.5em" in out


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_no_inline_sizes_falls_back_to_style_block():
    """If htmlContent uses browser defaults for sizes, we inject a <style>
    block targeting h1-h6 with the new size."""
    el = {
        "type": "html",
        "htmlContent": "<h2>Browser default sized</h2><p>Body</p>",
        "style": {},
    }
    sl = {"background": "#ffffff"}
    _apply_style_fix(el, sl, {"fontSize": 56, "fontColor": "#0f172a"})
    new_html = el["htmlContent"]
    # Fallback <style data-aesthetic-fix> block must be injected
    assert "data-aesthetic-fix" in new_html
    assert "font-size: 56px" in new_html or "font-size:56px" in new_html
    assert "h1,h2,h3,h4,h5,h6" in new_html.replace(" ", "")


def test_non_html_element_unchanged_by_propagator():
    el = {"type": "text", "content": "Plain text", "style": {}}
    sl = {"background": "#ffffff"}
    out = _propagate_style_to_html_content(el, {"fontSize": 48}, sl)
    assert out is False
