"""Regression: HTML iframe heights in Single Page export must respect the
element's authored height — header-style HTML elements (e.g. a 60px gradient
bar in the editor) must NOT balloon to 540px in the export.

Bug context (2026-04-29 user report): a thin header HTML element appeared as a
huge ~700px gradient block in the Single Page output because `min-height:540px`
was hardcoded for ALL iframes regardless of authored size.
"""
from services.single_page_exporter import _render_html_element_inner


_HTML_WITH_STYLES = '<style>body{background:linear-gradient(90deg,#7c3aed,#ec4899)}</style>' \
                    '<div>Cultura de Atualização e Impactos Estruturais</div>'


def test_thin_header_uses_authored_height():
    """Element authored as 60px-tall header should render iframe at 60px,
    not 540px."""
    el = {"type": "html", "htmlContent": _HTML_WITH_STYLES, "height": 60}
    out = _render_html_element_inner(el, "p1", "/tmp", "", 0, 0)
    assert "height:60px" in out
    assert "min-height:540px" not in out


def test_very_short_header_clamps_to_60():
    """If author set height to 8px (mistakenly tiny) clamp UP to 60px so the
    iframe remains visible/clickable."""
    el = {"type": "html", "htmlContent": _HTML_WITH_STYLES, "height": 8}
    out = _render_html_element_inner(el, "p1", "/tmp", "", 0, 0)
    assert "height:60px" in out


def test_tall_html_clamps_to_720():
    """Author asked for 1080px — clamp DOWN to 720px to avoid giant scrolls."""
    el = {"type": "html", "htmlContent": _HTML_WITH_STYLES, "height": 1080}
    out = _render_html_element_inner(el, "p1", "/tmp", "", 0, 0)
    assert "height:720px" in out
    assert "height:1080" not in out


def test_normal_height_passed_through():
    el = {"type": "html", "htmlContent": _HTML_WITH_STYLES, "height": 400}
    out = _render_html_element_inner(el, "p1", "/tmp", "", 0, 0)
    assert "height:400px" in out


def test_missing_height_falls_back_to_540():
    el = {"type": "html", "htmlContent": _HTML_WITH_STYLES}
    out = _render_html_element_inner(el, "p1", "/tmp", "", 0, 0)
    assert "min-height:540px" in out


def test_invalid_height_falls_back():
    el = {"type": "html", "htmlContent": _HTML_WITH_STYLES, "height": "broken"}
    out = _render_html_element_inner(el, "p1", "/tmp", "", 0, 0)
    assert "min-height:540px" in out


def test_zero_height_falls_back():
    el = {"type": "html", "htmlContent": _HTML_WITH_STYLES, "height": 0}
    out = _render_html_element_inner(el, "p1", "/tmp", "", 0, 0)
    assert "min-height:540px" in out


def test_iframe_reset_css_injected_to_kill_scrollbars():
    """Regression: iframe must inject `body{margin:0;overflow:hidden}` reset
    CSS into the base64 payload so default body margin (8px) doesn't push
    content past a thin iframe (e.g. 60px header) and force scrollbars."""
    import base64
    el = {"type": "html", "htmlContent": "<style>body{background:red}</style><div>X</div>", "height": 60}
    out = _render_html_element_inner(el, "p1", "/tmp", "", 0, 0)
    # Extract base64 payload from data: URI
    import re
    m = re.search(r"base64,([A-Za-z0-9+/=]+)", out)
    assert m, "iframe should have base64 src"
    payload = base64.b64decode(m.group(1)).decode("utf-8")
    # Reset CSS must be present
    assert "html,body{margin:0 !important" in payload
    assert "overflow:hidden" in payload
    assert "box-sizing:border-box" in payload


def test_thin_header_left_justify_override():
    """Thin headers (<100px) often use `margin-left:auto` to push text to the
    right edge of the slide canvas. In Single Page the iframe is narrower than
    the slide, so right-aligned text is clipped. Force left-align."""
    import base64, re
    el = {"type": "html", "htmlContent": "<style>span{font-size:16px}</style><div style='display:flex'><span></span><span style='margin-left:auto'>Long text that would be clipped on the right</span></div>", "height": 60}
    out = _render_html_element_inner(el, "p1", "/tmp", "", 0, 0)
    m = re.search(r"base64,([A-Za-z0-9+/=]+)", out)
    payload = base64.b64decode(m.group(1)).decode("utf-8")
    # Override applied for thin iframes
    assert "justify-content:flex-start !important" in payload
    assert "text-align:left !important" in payload
    assert 'margin-left:0 !important' in payload


def test_normal_height_iframe_does_NOT_left_align_override():
    """The left-align override should ONLY apply to thin headers (<100px).
    Normal-sized iframes (e.g. body content with intentional right-aligned
    elements) must preserve the author's layout."""
    import base64, re
    el = {"type": "html", "htmlContent": "<style>body{}</style><div>x</div>", "height": 400}
    out = _render_html_element_inner(el, "p1", "/tmp", "", 0, 0)
    m = re.search(r"base64,([A-Za-z0-9+/=]+)", out)
    payload = base64.b64decode(m.group(1)).decode("utf-8")
    # Reset CSS still present
    assert "overflow:hidden" in payload
    # But left-align override is NOT
    assert "justify-content:flex-start" not in payload
    assert "text-align:left !important" not in payload
