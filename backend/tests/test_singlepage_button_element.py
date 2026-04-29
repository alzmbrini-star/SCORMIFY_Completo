"""Tests: button element renderer in Single Page export.

Bug context (2026-04-29 user report): a slide had a button element with
startTime=3.48 / endTime=5 to appear after 3 seconds in the timeline, but
the button never showed up. Root cause: the dispatcher in `_render_element`
had no `case` for type='button' — fell through to the default empty string.
"""
from services.single_page_exporter import (
    _render_button_element_inner,
    _render_element,
    generate_single_page_html,
)


_BUTTON_WITH_URL = {
    "id": "btn1",
    "type": "button",
    "buttonText": "Baixar PDF",
    "buttonUrl": "https://example.com/file.pdf",
    "openInNewTab": True,
    "buttonStyle": "primary",
    "style": {"fontSize": 16, "borderRadius": 8, "fontWeight": "bold"},
}

_BUTTON_NO_URL = {
    "id": "btn2",
    "type": "button",
    "buttonText": "Continuar",
    "buttonStyle": "secondary",
}


def test_button_with_url_renders_anchor_tag():
    out = _render_button_element_inner(_BUTTON_WITH_URL, 0, 0)
    assert '<a href="https://example.com/file.pdf"' in out
    assert 'target="_blank"' in out
    assert 'rel="noopener noreferrer"' in out
    assert ">Baixar PDF</a>" in out
    # Marked as interactive that gates progression
    assert 'data-required="true"' in out
    assert 'sp-interactive' in out


def test_button_without_url_renders_passive_button():
    out = _render_button_element_inner(_BUTTON_NO_URL, 0, 0)
    assert "<button" in out
    assert ">Continuar</button>" in out
    assert "<a " not in out


def test_button_dispatched_in_render_element():
    """Regression: make sure the dispatch in _render_element doesn't drop
    type='button' (the original bug)."""
    out = _render_element(_BUTTON_WITH_URL, "p1", "/tmp", "", 0, 0, {})
    assert "Baixar PDF" in out
    assert out != ""


def test_button_with_timeline_gets_wrapped():
    """When a button has startTime>0, it must be wrapped in `.sp-element-timed`
    so the timeline engine reveals it on schedule."""
    btn = dict(_BUTTON_WITH_URL)
    btn["startTime"] = 3.48
    btn["endTime"] = 5.0
    out = _render_element(btn, "p1", "/tmp", "", 0, 0, {})
    assert 'class="sp-element-timed"' in out
    assert 'data-start-time="3.48"' in out
    assert 'data-end-time="5.0"' in out


def test_button_in_full_export():
    """E2E: a project with a slide containing only a button (no other elements)
    must render the button visibly."""
    project = {
        "id": "p1", "name": "Test",
        "course": {"slides": [
            {"id": "s1", "title": "x", "elements": [_BUTTON_WITH_URL]},
        ]},
    }
    html = generate_single_page_html(project, "/tmp", "")
    assert "Baixar PDF" in html
    assert "https://example.com/file.pdf" in html


def test_button_palette_styles():
    """Each `buttonStyle` value should map to a distinct visual palette."""
    for style, color in [("primary", "#2563eb"), ("destructive", "#dc2626"), ("success", "#16a34a")]:
        b = dict(_BUTTON_WITH_URL)
        b["buttonStyle"] = style
        out = _render_button_element_inner(b, 0, 0)
        assert color in out


def test_button_text_is_html_escaped():
    """Button text must be escaped to prevent injection."""
    btn = dict(_BUTTON_WITH_URL)
    btn["buttonText"] = '<script>alert(1)</script>'
    out = _render_button_element_inner(btn, 0, 0)
    assert "<script>" not in out
    assert "&lt;script&gt;" in out


def test_shape_element_renders():
    """Shape elements render as decorative blocks (no required interactive)."""
    from services.single_page_exporter import _render_shape_element_inner
    shape = {"type": "shape", "shapeType": "rectangle", "width": 200, "height": 100,
             "style": {"fill": "#f59e0b"}}
    out = _render_shape_element_inner(shape)
    assert "sp-shape" in out
    assert "width:200px" in out
    assert "height:100px" in out
    assert "#f59e0b" in out
    # No gating
    assert 'data-required="true"' not in out
