"""Tests for the "skip visual duplicates on bg-image slides" rule.

User report: PPT-imported slides rendered the scene (via slide.backgroundImage)
AND the extracted text elements on top of it — the duplicated title bled
through behind the avatar overlay. Fix: on any slide with backgroundImage,
skip text/shape/line/image elements and also skip html elements that don't
contain interactive markup (iframe/button/link/form).

Non-bg slides (regular Editor-native slides) are unaffected.
"""
from __future__ import annotations

import pytest

from services.single_page_exporter import generate_single_page_html


def _ppt_slide(extra_elements=None):
    """Build a PPT-imported-style slide (has backgroundImage) with the caller
    adding any extra elements for the test."""
    return {
        "id": "p", "name": "c",
        "course": {"slides": [{
            "id": "s1", "title": "Boas-vindas",
            "width": 1280, "height": 720,
            "backgroundImage": "/api/projects/p/assets/scene.png",
            "elements": extra_elements or [],
        }]}
    }


def test_skip_text_elements_on_bg_slide():
    """Plain text elements must be hidden on bg-image slides to avoid
    duplicating the content already in the scene image."""
    html = generate_single_page_html(
        _ppt_slide([
            {"type": "text", "id": "t1", "content": "A TRILHA DO VENDEDOR",
             "x": 100, "y": 600, "width": 800, "height": 80},
        ]),
        "/tmp/no-such-dir", "",
    )
    assert "A TRILHA DO VENDEDOR" not in html


def test_skip_shape_line_image_elements_on_bg_slide():
    html = generate_single_page_html(
        _ppt_slide([
            {"type": "shape", "id": "sh", "content": "should not appear"},
            {"type": "line", "id": "ln", "content": "also hidden"},
            {"type": "image", "id": "im", "src": "/hidden.png",
             "width": 1200, "height": 400},
        ]),
        "/tmp/no-such-dir", "",
    )
    assert "should not appear" not in html
    assert "also hidden" not in html
    assert "/hidden.png" not in html


def test_skip_html_without_interactive_markup():
    """HTML elements with only text/headings (no iframe/button/link) are
    duplicates and must be skipped."""
    html = generate_single_page_html(
        _ppt_slide([
            {"type": "html", "id": "h1",
             "htmlContent": "<h2>Título duplicado</h2><p>Texto que já está no bg</p>",
             "x": 0, "y": 0, "width": 1280, "height": 100},
        ]),
        "/tmp/no-such-dir", "",
    )
    assert "Título duplicado" not in html
    assert "Texto que já está no bg" not in html


def test_keep_html_with_iframe():
    """Author-added iframe (e.g. embed de vídeo, mapa) must survive the
    duplicate filter."""
    html = generate_single_page_html(
        _ppt_slide([
            {"type": "html", "id": "h1",
             "htmlContent": '<iframe src="https://www.youtube.com/embed/xyz"></iframe>',
             "x": 0, "y": 0, "width": 800, "height": 450},
        ]),
        "/tmp/no-such-dir", "",
    )
    assert "youtube.com/embed/xyz" in html


def test_keep_html_with_button():
    html = generate_single_page_html(
        _ppt_slide([
            {"type": "html", "id": "h1",
             "htmlContent": '<button onclick="alert(1)">Clique aqui</button>',
             "x": 100, "y": 500, "width": 200, "height": 50},
        ]),
        "/tmp/no-such-dir", "",
    )
    assert "Clique aqui" in html


def test_keep_html_with_link():
    html = generate_single_page_html(
        _ppt_slide([
            {"type": "html", "id": "h1",
             "htmlContent": '<a href="https://example.com">Saiba mais</a>',
             "x": 0, "y": 0, "width": 200, "height": 40},
        ]),
        "/tmp/no-such-dir", "",
    )
    assert "Saiba mais" in html


def test_keep_html_with_form():
    html = generate_single_page_html(
        _ppt_slide([
            {"type": "html", "id": "h1",
             "htmlContent": '<form><input type="text" name="q"/></form>',
             "x": 0, "y": 0, "width": 300, "height": 80},
        ]),
        "/tmp/no-such-dir", "",
    )
    assert '<form>' in html or 'name="q"' in html


def test_keep_interactive_flag_overrides_dedup():
    """When author explicitly marks element `interactive: true`, keep it
    even if it has no iframe/button/link markup."""
    html = generate_single_page_html(
        _ppt_slide([
            {"type": "html", "id": "h1", "interactive": True,
             "htmlContent": "<p>Dica contextual</p>"},
        ]),
        "/tmp/no-such-dir", "",
    )
    assert "Dica contextual" in html


def test_keep_quiz_element_on_bg_slide():
    """Quiz elements must never be skipped — they are interactive by nature."""
    html = generate_single_page_html(
        _ppt_slide([
            {"type": "quiz", "id": "q1", "quizConfig": {"title": "Quiz Test"}},
        ]),
        "/tmp/no-such-dir", "",
    )
    # Quiz renders a start button regardless
    assert "Quiz Test" in html or 'class="sp-quiz"' in html


def test_keep_video_element_on_bg_slide():
    """Videos (non-HeyGen) must never be skipped."""
    html = generate_single_page_html(
        _ppt_slide([
            {"type": "video", "id": "v1", "src": "https://example.com/x.mp4"},
        ]),
        "/tmp/no-such-dir", "",
    )
    assert "example.com/x.mp4" in html


def test_non_bg_slide_still_renders_all_elements():
    """A regular (non-PPT) slide without backgroundImage keeps all its
    elements — the dedup rule only applies to bg-image slides."""
    project = {
        "id": "p", "name": "c",
        "course": {"slides": [{
            "id": "s1", "title": "Native",
            "width": 1920, "height": 820,
            "elements": [
                {"type": "text", "id": "t", "content": "Editor-native text"},
                {"type": "html", "id": "h",
                 "htmlContent": "<p>Also kept</p>"},
                {"type": "image", "id": "i", "src": "/pic.png",
                 "width": 600, "height": 400},
            ],
        }]}
    }
    html = generate_single_page_html(project, "/tmp/no-such-dir", "")
    assert "Editor-native text" in html
    assert "Also kept" in html
    assert "/pic.png" in html


def test_bg_slide_with_avatar_has_clean_layout():
    """Full integration: a PPT slide with bg-image + HeyGen avatar + text
    duplicates → avatar renders as overlay, text duplicates are gone, no
    scrollbar."""
    HEYGEN_URL = "https://resource.heygen.ai/avatar/abc-transparent.webm"
    html = generate_single_page_html(
        _ppt_slide([
            {"type": "text", "id": "t", "content": "A TRILHA DO VENDEDOR"},
            {"type": "html", "id": "h",
             "htmlContent": "<h1>Subtítulo duplicado</h1>",
             "x": 0, "y": 500, "width": 1280, "height": 100},
            {"type": "video", "id": "v", "src": HEYGEN_URL,
             "x": 100, "y": 200, "width": 400, "height": 500},
        ]),
        "/tmp/no-such-dir", "",
    )
    # Avatar overlay is rendered
    assert 'data-testid="sp-avatar-overlay-0"' in html
    # Text duplicates are gone
    assert "A TRILHA DO VENDEDOR" not in html
    assert "Subtítulo duplicado" not in html
    # Scene bg image is still referenced
    assert "scene.png" in html
