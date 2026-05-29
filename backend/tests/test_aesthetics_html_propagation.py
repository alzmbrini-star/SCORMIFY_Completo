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


@pytest.mark.skip(reason="Author policy (2026-05): type=html elements must NOT receive fontSize changes from the analyzer. See _apply_style_fix TYPOGRAPHY_BLOCKED_FOR_HTML guard.")
def test_user_fontes_suggestion_scales_inline_font_sizes():
    """[DEPRECATED] LLM 'Fontes' fix used to propagate fontSize → inline html.
    Now blocked: analyzer only touches color/contrast in type=html."""
    el, sl = _make_user_bug_element_and_slide()
    fix_changes = {"fontSize": 48, "fontWeight": "800", "fontColor": "#f8fafc"}
    applied = _apply_style_fix(el, sl, fix_changes)
    assert applied is True
    new_html = el["htmlContent"]
    assert "font-size:48px" in new_html
    assert "font-size:20px" not in new_html
    assert el["style"]["fontSize"] == 48
    assert el["style"]["fontWeight"] == "800"


@pytest.mark.skip(reason="Author policy: see test_user_fontes_suggestion_scales_inline_font_sizes")
def test_user_fontes_suggestion_propagates_font_weight():
    """[DEPRECATED] fontWeight propagation to type=html is disabled."""
    el, sl = _make_user_bug_element_and_slide()
    _apply_style_fix(el, sl, {"fontSize": 48, "fontWeight": "800", "fontColor": "#f8fafc"})
    new_html = el["htmlContent"]
    assert "font-weight:800" in new_html
    assert new_html.count("font-weight") <= 2


def test_html_typography_protected_against_size_changes():
    """Author policy: analyzer must NEVER shrink/grow font-size on type=html.
    Visible inline sizes (31px on h2, 20px on p) must remain intact even when
    the LLM suggests fontSize:48."""
    el, sl = _make_user_bug_element_and_slide()
    original = el["htmlContent"]
    _apply_style_fix(el, sl, {"fontSize": 48, "fontWeight": "800"})
    # The outer element.style must also NOT get a fontSize bump — guard runs
    # before the style[].assign line.
    assert "fontSize" not in (el.get("style") or {})
    # Inline html sizes preserved
    assert "font-size:31px" in el["htmlContent"]
    assert "font-size:20px" in el["htmlContent"]
    # No accidental wholesale rewrite of the html beyond expected color sweep
    assert el["htmlContent"].count("<h2") == original.count("<h2")


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
    # LLM proposes a fontColor change — the contrast sweep + inline rewriter
    # together must remove the invisible white-on-white pattern.
    # (Author policy disallows fontSize on type=html; we use fontColor here.)
    applied = _apply_style_fix(el, sl, {"fontColor": "#0f172a"})
    assert applied is True
    new_html = el["htmlContent"]
    # Inline `color:#ffffff` MUST be replaced (would be invisible on white bg)
    assert "color:#ffffff" not in new_html.lower(), (
        "Invisible white-on-white inline color must be rewritten"
    )
    # font-size on the html must NOT change (typography protected)
    assert "font-size:32px" in new_html


def test_legible_accent_colors_preserved():
    """Brand orange `color:#f59e0b` on dark navy bg already has decent contrast
    relative to white. The propagation MUST NOT flatten intentional accents
    when the LLM color change is purely cosmetic.
    """
    html = (
        '<div style="background:#1e3a8a;padding:10px;">'
        '<span style="color:#f59e0b;font-size:17px;">Hora de Praticar!</span>'
        '<h2 style="color:#ffffff;font-size:34px;">Teste seus Conhecimentos</h2>'
        '</div>'
    )
    el = {"type": "html", "htmlContent": html, "style": {}}
    sl = {"background": "#1e3a8a"}
    _apply_style_fix(el, sl, {"fontColor": "#f8fafc"})
    new_html = el["htmlContent"]
    # Orange accent has good contrast vs navy — must be PRESERVED
    assert "#f59e0b" in new_html, "Intentional accent color must not be flattened"
    # White title color is also legible on navy — accepted either way
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
    """If htmlContent uses browser defaults for sizes AND the analyzer needs
    to push a color, the colorless-text pass injects inline color directly
    on each tag (fontSize/fontWeight intentionally skipped for type=html)."""
    el = {
        "type": "html",
        "htmlContent": "<h2>Browser default sized</h2><p>Body</p>",
        "style": {},
    }
    sl = {"background": "#ffffff"}
    _apply_style_fix(el, sl, {"fontColor": "#0f172a"})
    new_html = el["htmlContent"]
    # Each tag must now have inline color
    assert 'color:#0f172a' in new_html.replace(" ", "")
    assert "<h2 style=" in new_html or 'style="color' in new_html


def test_non_html_element_unchanged_by_propagator():
    el = {"type": "text", "content": "Plain text", "style": {}}
    sl = {"background": "#ffffff"}
    out = _propagate_style_to_html_content(el, {"fontSize": 48}, sl)
    assert out is False


# ---------------------------------------------------------------------------
# Background-image plate (option A from user)
# ---------------------------------------------------------------------------

def test_bg_image_does_not_inject_plate_anymore():
    """v6 (no-overlay): even on slides with bgImage, NO plate is injected.
    Only font color is swapped if needed for contrast."""
    el = {
        "type": "html",
        "htmlContent": (
            '<div style="padding:20px;">'
            '<h2 style="color:#ffffff;font-size:31px;">Conclusão</h2>'
            '<p style="color:rgba(255,255,255,0.75);font-size:20px;">Body</p>'
            '</div>'
        ),
        "style": {},
    }
    sl = {"background": "#1e3a8a", "backgroundImage": "/api/.../bg.jpg"}
    _apply_style_fix(el, sl, {"fontSize": 48, "fontColor": "#ffffff"})
    html = el["htmlContent"]
    # NO plate markers, NO data-aesthetic-fix style tags
    assert "data-aesthetic-plate" not in html, "v6: no plate markers should be added"
    assert "rgba(15,23,42" not in html, "v6: no dark plate rgba"
    assert "rgba(248,250,252" not in html, "v6: no light plate rgba"


def test_bg_image_low_contrast_text_color_swapped():
    """When inline text color fails WCAG vs slide.background (solid color,
    ignoring bgImage variability), swap the inline color. NO plate overlay."""
    el = {
        "type": "html",
        "htmlContent": (
            '<h2 style="color:#ffffff;">Invisible on white slide</h2>'
        ),
        "style": {},
    }
    sl = {"background": "#ffffff", "backgroundImage": "/img.jpg"}
    _apply_style_fix(el, sl, {"fontSize": 56})
    html = el["htmlContent"]
    # White color must be replaced with high-contrast (dark)
    assert "color:#ffffff" not in html.lower()
    # No plate overlay (markers or rgba backdrops)
    assert "data-aesthetic-plate" not in html
    assert "rgba(15,23,42,0.78)" not in html
    assert "rgba(248,250,252,0.88)" not in html
    # Iframe body must not get an opaque background painted on it
    assert "html,body{background:rgba" not in html.replace(" ", "").lower()
    assert "body{background:rgba" not in html.replace(" ", "").lower()


def test_cleanup_strips_legacy_plate_artifacts():
    """Applying a style fix to an element that ALREADY has plate artifacts
    from v3/v4/v5 must strip them clean (no-overlay migration path).

    Note: a fresh `<style data-aesthetic-fix>` for font-size fallback may
    be re-injected by the propagator if the element lacks inline sizes,
    but it MUST NOT contain plate/overlay rules (rgba backdrops, body
    background, plate markers)."""
    legacy_html = (
        '<style data-aesthetic-fix="1">html,body{background:rgba(15,23,42,0.78) !important;}</style>'
        '<h2 data-aesthetic-plate="1" style="color:#ffffff;">Title</h2>'
        '<p data-aesthetic-plate="1" style="color:#ffffff;">Body</p>'
    )
    el = {"type": "html", "htmlContent": legacy_html, "style": {}}
    sl = {"background": "#1e3a8a", "backgroundImage": "/img.jpg"}
    _apply_style_fix(el, sl, {"fontSize": 64})
    html = el["htmlContent"]
    # Plate markers and old overlay rules removed
    assert "data-aesthetic-plate" not in html
    assert "rgba(15,23,42,0.78)" not in html
    assert "html,body{background" not in html.replace(" ", "").lower()
    # Text preserved
    assert "Title" in html
    assert "Body" in html


# ---------------------------------------------------------------------------
# Legacy HTML4 <font color="X"> support (the AI Agent emits these)
# ---------------------------------------------------------------------------

LEGACY_FONT_HTML = (
    '<div style="text-align:center;padding:20px;">'
    '<h1 style="font-family:Inter, sans-serif;font-size:72px;font-weight:900;">'
    '<font color="#000000">Capa: O Jeito Intelbras de Atender</font></h1>'
    '<p style="font-family:Inter, sans-serif;font-size:30px;">'
    '<font color="#000000">Bem-vindo ao treinamento...</font></p>'
    '</div>'
)


def test_legacy_font_color_rewritten_when_llm_proposes():
    """<font color="#000"> must be rewritten when LLM proposes a new color
    (matches the user's actual project where AI Agent emits HTML4 markup)."""
    el = {"type": "html", "htmlContent": LEGACY_FONT_HTML, "style": {}}
    sl = {"background": "#1e3a8a", "backgroundImage": "/img.jpg"}
    _apply_style_fix(el, sl, {"fontColor": "#f8fafc", "fontSize": 72})
    new_html = el["htmlContent"]
    # Both <font color="#000000"> must have flipped to the LLM target
    assert 'color="#000000"' not in new_html, "Black font color should be replaced"
    assert 'color="#f8fafc"' in new_html, "Should have new light color in <font> attr"


def test_plate_polarity_uses_font_attr_color():
    """v6 (no-overlay): when <font color> fails WCAG vs html_bg, the legacy
    color must be flipped to high-contrast. NO plate is injected."""
    el = {"type": "html", "htmlContent": LEGACY_FONT_HTML, "style": {}}
    sl = {"background": "#1e3a8a", "backgroundImage": "/img.jpg"}
    # Apply only a size change — leave color decisions to defense-in-depth.
    _apply_style_fix(el, sl, {"fontSize": 72})
    new_html = el["htmlContent"]
    # <font color="#000000"> failed WCAG vs html_bg (navy), so it gets
    # flipped to high-contrast (light).
    assert 'color="#000000"' not in new_html
    # No plate overlay anymore (v6)
    assert "data-aesthetic-plate" not in new_html
    assert "rgba(15,23,42,0.78)" not in new_html


def test_legacy_font_color_left_alone_when_legible():
    """If <font color> already has good contrast against html_bg, do not
    rewrite it (preserve intentional brand colors). E.g., orange accent
    on dark navy."""
    html = (
        '<h2><font color="#f59e0b">Highlighted</font></h2>'
    )
    el = {"type": "html", "htmlContent": html, "style": {}}
    sl = {"background": "#1e3a8a"}  # navy
    # Trigger propagation via fontSize change (no fontColor)
    _apply_style_fix(el, sl, {"fontSize": 56})
    new_html = el["htmlContent"]
    # orange ~6.4:1 on navy passes WCAG → must be preserved
    assert 'color="#f59e0b"' in new_html


# ---------------------------------------------------------------------------
# Colorless-text-tag injection (the real user bug from screenshot)
# ---------------------------------------------------------------------------

def test_colorless_h3_gets_inline_color_on_light_bg():
    """User's screenshot: <h3>Consolidando...</h3> WITHOUT inline color
    was rendering as light gray (iframe fallback #f1f5f9) on a white slide.
    After the propagator runs, the h3 MUST get an inline color matching
    the slide bg contrast."""
    html = (
        '<h2 style="color:#000000;">Title</h2>'
        '<h3>Subtitle without color</h3>'
        '<p style="color:#000000;">Body</p>'
        '<h3>Another subtitle without color</h3>'
    )
    el = {"type": "html", "htmlContent": html, "style": {}}
    sl = {"background": "#ffffff"}  # white slide
    _apply_style_fix(el, sl, {"fontColor": "#0f172a"})
    new_html = el["htmlContent"]
    # Both h3 elements must now have inline `color:` declarations
    assert new_html.count("<h3") == 2
    # Count h3 tags WITHOUT a style attr — should be ZERO after the fix
    import re
    h3_without_style = re.findall(r'<h3(?![^>]*style=)', new_html)
    assert len(h3_without_style) == 0, (
        "Every h3 must have an inline style after the colorless-text pass"
    )
    # The color must be DARK (slide is white)
    h3_with_dark = re.findall(r'<h3[^>]*style="color:#0f172a', new_html)
    assert len(h3_with_dark) >= 2, "h3s should be forced to dark on white bg"


def test_colorless_text_inherits_through_font_ancestor():
    """A `<p>` wrapped in `<font color="...">` already gets color from
    cascade — the propagator must NOT redundantly inject another inline
    color, otherwise the font ancestor's color is preserved but the inner
    inline overrides it."""
    html = '<font color="#000000"><p>Inherits black via font ancestor</p></font>'
    el = {"type": "html", "htmlContent": html, "style": {}}
    sl = {"background": "#ffffff"}
    _apply_style_fix(el, sl, {"fontColor": "#0f172a"})
    new_html = el["htmlContent"]
    # The <p> should NOT have its own style="color:..." since the
    # <font> ancestor handles it.
    import re
    p_with_color = re.search(r'<p[^>]*style="[^"]*color:', new_html)
    assert p_with_color is None


def test_colorless_text_skipped_when_legible_inline_color_exists():
    """When the tag has an inline color already, the colorless pass must
    leave it alone — even if that color happens to match the new safe
    fallback."""
    html = '<p style="color:#666666;">Mid-gray text</p>'
    el = {"type": "html", "htmlContent": html, "style": {}}
    sl = {"background": "#ffffff"}
    _apply_style_fix(el, sl, {"fontColor": "#0f172a"})
    new_html = el["htmlContent"]
    # The original `color:#666666` MUST stay (the inline-color rewrite
    # branch governs whether it gets swapped — not this pass).
    import re
    colors = re.findall(r'color:\s*(#[0-9a-fA-F]+)', new_html)
    # No DUPLICATE color declarations on the p (would happen if we prepended)
    assert colors.count("#666666") == 1


def test_colorless_dark_bg_gets_light_text():
    """Inverse polarity: a <p> without color on a dark slide must get
    LIGHT inline color, not dark."""
    html = '<p>No color set</p>'
    el = {"type": "html", "htmlContent": html, "style": {}}
    sl = {"background": "#0f172a"}  # dark navy slide
    _apply_style_fix(el, sl, {"fontColor": "#f8fafc"})
    new_html = el["htmlContent"]
    # The p must be wrapped in inline style with a LIGHT color
    import re
    m = re.search(r'<p[^>]*style="color:(#[0-9a-fA-F]+)', new_html)
    assert m is not None, f"p should have inline color injected; got: {new_html}"
    # Check it's a light value
    color_hex = m.group(1).lstrip("#")
    r, g, b = int(color_hex[:2], 16), int(color_hex[2:4], 16), int(color_hex[4:6], 16)
    lum = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255
    assert lum > 0.5, f"p color should be LIGHT on dark slide; lum={lum} color={color_hex}"
