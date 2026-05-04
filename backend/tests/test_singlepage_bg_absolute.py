"""Tests for absolute-positioned overlay rendering on bg-image slides.

User feedback: PPT-imported slides have a backgroundImage AND text/html
elements that are intentional content (not duplicates) — author placed text
boxes, buttons, links on top of the scene. The renderer must honor the
editor coordinates by converting x/y/w/h to percentages of slide.width ×
slide.height and rendering each element as an absolute-positioned overlay
inside the section-inner card.
"""
from __future__ import annotations

import pytest

from services.single_page_exporter import generate_single_page_html


def _ppt_slide(extra_elements=None, bg_image="/api/projects/p/assets/scene.png"):
    return {
        "id": "p", "name": "c",
        "course": {"slides": [{
            "id": "s1", "title": "Boas-vindas",
            "width": 1280, "height": 720,
            "backgroundImage": bg_image,
            "elements": extra_elements or [],
        }]}
    }


# ---------------------------------------------------------------------------
# Elements with editor coords → absolute % positioning
# ---------------------------------------------------------------------------

def test_text_element_renders_with_absolute_positioning():
    """Text element with editor coords gets converted to %-based absolute
    positioning over the bg image — content is preserved (not stripped)."""
    html = generate_single_page_html(
        _ppt_slide([
            {"type": "text", "id": "t1", "content": "A TRILHA DO VENDEDOR",
             "x": 320, "y": 100, "width": 640, "height": 200},
        ]),
        "/tmp/no-such-dir", "",
    )
    # Content is preserved
    assert "A TRILHA DO VENDEDOR" in html
    # Wrapped in absolute-positioned sp-bg-element
    assert 'class="sp-bg-element"' in html
    # 320/1280=25%, 100/720≈13.89%, 640/1280=50%, 200/720≈27.78%
    assert "left:25.00%" in html
    assert "width:50.00%" in html


def test_html_element_renders_with_absolute_positioning():
    html = generate_single_page_html(
        _ppt_slide([
            {"type": "html", "id": "h1",
             "htmlContent": "<h1>Subtítulo importante</h1>",
             "x": 0, "y": 360, "width": 1280, "height": 100},
        ]),
        "/tmp/no-such-dir", "",
    )
    assert "Subtítulo importante" in html
    assert 'class="sp-bg-element"' in html
    assert "left:0.00%" in html
    assert "top:50.00%" in html  # 360/720 = 50%


def test_button_element_renders_with_absolute_positioning():
    """Author-added button must render at its editor position."""
    html = generate_single_page_html(
        _ppt_slide([
            {"type": "html", "id": "btn",
             "htmlContent": '<button>INICIAR JORNADA</button>',
             "x": 480, "y": 540, "width": 320, "height": 80},
        ]),
        "/tmp/no-such-dir", "",
    )
    assert "INICIAR JORNADA" in html
    assert 'class="sp-bg-element"' in html


def test_image_element_renders_with_absolute_positioning():
    html = generate_single_page_html(
        _ppt_slide([
            {"type": "image", "id": "i", "src": "/logo.png",
             "x": 60, "y": 60, "width": 200, "height": 80},
        ]),
        "/tmp/no-such-dir", "",
    )
    assert "/logo.png" in html
    assert 'class="sp-bg-element"' in html


def test_clamps_coords_outside_slide_bounds():
    """Coords > slide.width / slide.height should clamp to 100%."""
    html = generate_single_page_html(
        _ppt_slide([
            {"type": "text", "id": "t",
             "content": "Out of bounds",
             "x": 2000, "y": 1500, "width": 800, "height": 200},
        ]),
        "/tmp/no-such-dir", "",
    )
    assert "Out of bounds" in html
    # Clamped to 100%
    assert "left:100.00%" in html
    assert "top:100.00%" in html


def test_falls_back_to_body_flow_when_no_coords():
    """Element with width/height = 0 falls back to body flow (legacy)."""
    html = generate_single_page_html(
        _ppt_slide([
            {"type": "text", "id": "t", "content": "No coords text",
             "x": 0, "y": 0, "width": 0, "height": 0},
        ]),
        "/tmp/no-such-dir", "",
    )
    # Content preserved
    assert "No coords text" in html


def test_avatar_overlay_works_alongside_absolute_text():
    """Full integration: PPT slide with bg + avatar (HeyGen) + text +
    button. All must render correctly together."""
    HEYGEN_URL = "https://resource.heygen.ai/avatar/x-transparent.webm"
    html = generate_single_page_html(
        _ppt_slide([
            {"type": "text", "id": "t", "content": "A TRILHA DO VENDEDOR",
             "x": 400, "y": 80, "width": 700, "height": 200},
            {"type": "html", "id": "btn",
             "htmlContent": '<button>INICIAR JORNADA</button>',
             "x": 480, "y": 540, "width": 320, "height": 80},
            {"type": "video", "id": "v", "src": HEYGEN_URL,
             "x": 100, "y": 200, "width": 400, "height": 500},
        ]),
        "/tmp/no-such-dir", "",
    )
    # Text preserved
    assert "A TRILHA DO VENDEDOR" in html
    assert "INICIAR JORNADA" in html
    # Avatar rendered as overlay
    assert 'data-testid="sp-avatar-overlay-0"' in html
    # Each non-avatar element wrapped in sp-bg-element
    assert html.count('class="sp-bg-element"') == 2  # text + button (not avatar)


def test_non_bg_slide_still_uses_body_flow():
    """Editor-native slides without backgroundImage continue using the body
    flow rendering (no absolute positioning override)."""
    project = {
        "id": "p", "name": "c",
        "course": {"slides": [{
            "id": "s1", "title": "Native",
            "width": 1920, "height": 820,
            "elements": [
                {"type": "text", "id": "t", "content": "Editor-native text",
                 "x": 100, "y": 100, "width": 1720, "height": 200},
            ],
        }]}
    }
    html = generate_single_page_html(project, "/tmp/no-such-dir", "")
    assert "Editor-native text" in html
    # No sp-bg-element wrapper (no bg-image)
    assert 'class="sp-bg-element"' not in html


def test_quiz_element_on_bg_slide_renders_with_positioning():
    """Quizzes also get the absolute-positioning treatment when they have
    valid editor coords."""
    html = generate_single_page_html(
        _ppt_slide([
            {"type": "quiz", "id": "q",
             "x": 200, "y": 300, "width": 800, "height": 300,
             "quizConfig": {"title": "Quiz Test"}},
        ]),
        "/tmp/no-such-dir", "",
    )
    # Quiz block is wrapped in absolute positioning
    assert 'class="sp-bg-element"' in html
