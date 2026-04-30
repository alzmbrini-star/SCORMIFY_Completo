"""Tests for the PPT-imported slide aspect-ratio fix in Single Page export.

User reported: PPT-imported slides rendered as tiny horizontal banners with
massive empty space below — the slide background image was being squished
into a thin band because the section card had no height constraint.

Fix: when a slide has a `backgroundImage` AND known width/height (typical
of PPT-imported content), the section card is locked to the slide's aspect
ratio via CSS `aspect-ratio` and uses a wider max-width + thinner padding.
"""
from __future__ import annotations

from services.single_page_exporter import generate_single_page_html


def _ppt_imported_project(width=1280, height=720):
    return {
        "id": "p-ppt",
        "name": "PPT Imported",
        "course": {
            "metadata": {"title": "Curso PPT"},
            "slides": [
                {
                    "id": "s1", "title": "Aula 1",
                    "width": width, "height": height,
                    "backgroundImage": "/api/projects/p-ppt/assets/slide1.png",
                    "background": "#0a2540",
                    "elements": [],
                }
            ]
        }
    }


def _editor_native_project():
    """Slide created in the Editor (no backgroundImage, just elements)."""
    return {
        "id": "p-native",
        "name": "Editor Native",
        "course": {
            "metadata": {"title": "Curso"},
            "slides": [
                {"id": "s1", "title": "Aula 1",
                 "width": 1920, "height": 820,
                 "elements": [
                     {"type": "html", "id": "e1",
                      "x": 0, "y": 0, "width": 1920, "height": 540,
                      "htmlContent": "<p>Conteudo</p>"},
                 ]}
            ]
        }
    }


def test_ppt_slide_locks_aspect_ratio_to_slide_dimensions():
    """A PPT slide with backgroundImage + 1280×720 dims must produce CSS
    `aspect-ratio:1280/720` on the section card AND the `sp-aspect-locked`
    class so the wider-max-width CSS kicks in."""
    html = generate_single_page_html(_ppt_imported_project(1280, 720), "/tmp/no-such-dir", "")
    assert "aspect-ratio:1280/720" in html
    assert "sp-aspect-locked" in html


def test_ppt_slide_169_widescreen_aspect():
    """PowerPoint 16:9 widescreen is typically 1920×1080."""
    html = generate_single_page_html(_ppt_imported_project(1920, 1080), "/tmp/no-such-dir", "")
    assert "aspect-ratio:1920/1080" in html


def test_ppt_slide_43_classic_aspect():
    """PowerPoint 4:3 classic is typically 960×720."""
    html = generate_single_page_html(_ppt_imported_project(960, 720), "/tmp/no-such-dir", "")
    assert "aspect-ratio:960/720" in html


def test_ppt_slide_includes_min_height_for_small_viewports():
    """Below the aspect-ratio rule, a min-height ensures small viewports
    (mobile-portrait) still show the slide at a usable size."""
    html = generate_single_page_html(_ppt_imported_project(1280, 720), "/tmp/no-such-dir", "")
    assert "min-height:520px" in html


def test_native_editor_slide_NOT_aspect_locked():
    """Editor-native slides (no backgroundImage) keep the original card
    layout — no aspect-locking class on the actual <section> element."""
    html = generate_single_page_html(_editor_native_project(), "/tmp/no-such-dir", "")
    # The CSS rule selectors `.sp-section.sp-aspect-locked` are always present;
    # check only the <section ...> tag does NOT carry the class.
    import re
    section_tags = re.findall(r'<section\s+class="([^"]+)"', html)
    assert section_tags, "expected at least one <section> tag"
    assert all("sp-aspect-locked" not in cls for cls in section_tags)


def test_ppt_slide_without_dimensions_still_renders_safely():
    """If width/height are None (legacy/corrupt PPT imports), we should NOT
    emit a broken aspect-ratio rule — only the bg-image background-size:cover
    layer should be applied."""
    project = _ppt_imported_project(0, 0)
    project["course"]["slides"][0]["width"] = None
    project["course"]["slides"][0]["height"] = None
    html = generate_single_page_html(project, "/tmp/no-such-dir", "")
    # No invalid aspect-ratio
    assert "aspect-ratio:0/0" not in html
    assert "aspect-ratio:None/None" not in html
    # bg image still applied
    assert "background-image:url" in html


def test_ppt_aspect_locked_css_overrides_default_padding():
    """The CSS for sp-aspect-locked sets thinner padding so the background
    fills the card properly — verify the CSS rule is in the output."""
    html = generate_single_page_html(_ppt_imported_project(), "/tmp/no-such-dir", "")
    # Wider max-width override
    assert ".sp-section.sp-aspect-locked .sp-section-inner" in html
    assert "min(95vw,1600px)" in html
    # Title is repositioned (absolute) so it doesn't push body off the slide
    assert ".sp-section.sp-aspect-locked .sp-section-title" in html


def test_ppt_aspect_locked_mobile_fallback():
    """On screens < 768px the aspect-ratio is unset so portrait phones don't
    get a tiny squished slide. A min-height keeps it visible."""
    html = generate_single_page_html(_ppt_imported_project(), "/tmp/no-such-dir", "")
    # Look for the @media block that overrides aspect-ratio for mobile
    needle = ".sp-section.sp-aspect-locked .sp-section-inner{aspect-ratio:auto"
    assert needle in html


def test_ppt_aspect_locked_no_repeat_on_bg_image():
    """When the slide background tiles, it gets visually noisy. Force
    no-repeat so PPT slides render cleanly."""
    html = generate_single_page_html(_ppt_imported_project(), "/tmp/no-such-dir", "")
    assert "background-repeat:no-repeat" in html


def test_ppt_aspect_locked_does_not_break_dark_mode():
    """A dark slide background must still flip text color via .sp-dark."""
    project = _ppt_imported_project()
    project["course"]["slides"][0]["background"] = "#0a2540"  # dark
    html = generate_single_page_html(project, "/tmp/no-such-dir", "")
    assert "sp-dark" in html
    assert "sp-aspect-locked" in html
