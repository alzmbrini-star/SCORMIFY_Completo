"""Regression: `opacity` field stored as string (e.g., "0.5") in the DB
used to crash _build_slide_context with `TypeError: '<' not supported
between instances of 'str' and 'int'`. Make sure we coerce safely."""
from routes.aesthetics import _build_slide_context


def test_opacity_as_string_does_not_crash():
    slide = {
        "title": "x",
        "background": "#1e3a8a",
        "elements": [
            {"type": "text", "content": "hi", "style": {"opacity": "0.5"}},
        ],
    }
    # Should not raise
    out = _build_slide_context(slide, 0, 1)
    assert "opacity=0.5" in out


def test_opacity_as_int_one_skipped():
    slide = {
        "title": "x",
        "background": "#1e3a8a",
        "elements": [
            {"type": "text", "content": "hi", "style": {"opacity": 1}},
        ],
    }
    out = _build_slide_context(slide, 0, 1)
    assert "opacity=" not in out


def test_opacity_invalid_string_skipped():
    slide = {
        "title": "x",
        "background": "#1e3a8a",
        "elements": [
            {"type": "text", "content": "hi", "style": {"opacity": "auto"}},
        ],
    }
    # Garbage in opacity must not crash
    out = _build_slide_context(slide, 0, 1)
    assert "opacity=" not in out


def test_opacity_none_skipped():
    slide = {
        "title": "x",
        "background": "#1e3a8a",
        "elements": [
            {"type": "text", "content": "hi", "style": {}},
        ],
    }
    out = _build_slide_context(slide, 0, 1)
    assert "opacity=" not in out


def test_xy_wh_as_strings_does_not_crash():
    """The DB sometimes stores coordinates as strings ('120', '80.5').
    The format `{x:.0f}` requires a number, so we must coerce."""
    slide = {
        "title": "x",
        "background": "#1e3a8a",
        "elements": [
            {"type": "text", "content": "hi", "x": "120", "y": "80",
             "width": "300", "height": "60", "style": {}},
        ],
    }
    # Must not raise
    out = _build_slide_context(slide, 0, 1)
    assert "at (120,80)" in out


def test_font_size_as_string_does_not_crash():
    slide = {
        "title": "x",
        "background": "#1e3a8a",
        "elements": [
            {"type": "text", "content": "hi", "style": {"fontSize": "32"}},
        ],
    }
    out = _build_slide_context(slide, 0, 1)
    assert "fontSize=32" in out
