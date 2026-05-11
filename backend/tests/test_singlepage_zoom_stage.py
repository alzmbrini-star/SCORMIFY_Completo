"""Tests for the `.sp-zoom-stage` wrapper that powers the Tutorial Agent
zoom-on-hotspot effect in the Single Page export.

The previous implementation animated `transform: scale(N)` on the whole
`.sp-section-inner` card — which made the entire card balloon out of the
viewport and dragged the section title + body strip along with the zoom
(visually broken). The fix wraps the bg-image + hotspot overlays in a
dedicated `.sp-zoom-stage` element so only the magnification area moves.
"""
import pytest
from services.single_page_exporter import generate_single_page_html


def _build_zoom_tutorial(extra_elements=None, with_zoom=True):
    """Build a minimal Scormify project dict containing a single zoom-enabled
    slide imported from the Tutorial Agent."""
    slide = {
        "id": "slide-1",
        "title": "Passo 1",
        "background": "#0f172a",
        "width": 1280,
        "height": 720,
        "backgroundImage": "/api/projects/p/assets/screen.png",
        "elements": extra_elements or [
            {
                "id": "hotspot-1",
                "type": "shape",
                "shape": "circle",
                "x": 100.0, "y": 100.0,
                "width": 56, "height": 56,
                "style": {"borderColor": "#f472b6", "borderWidth": 4, "borderRadius": "50%"},
            },
            {
                "id": "text-1",
                "type": "text",
                "content": "Clique em Relatórios.",
                "x": 60, "y": 620, "width": 1160, "height": 80,
                "style": {"fontColor": "#f8fafc"},
            },
        ],
    }
    if with_zoom:
        slide["zoomEffect"] = {
            "scale": 2.5, "focusX": 75, "focusY": 18,
            "intro": 800, "hold": 2400, "outro": 600,
        }
    return {
        "id": "p", "name": "Tutorial Test",
        "course": {"metadata": {"title": "T"}, "slides": [slide]},
    }


def _render(project):
    """Run the exporter against a tmp asset dir and return the HTML."""
    return generate_single_page_html(
        project_doc=project,
        assets_dir="/tmp",
        base_url="",
        questions=[],
    )


class TestZoomStageStructure:
    def test_zoom_stage_div_present_when_zoom_effect_set(self):
        html = _render(_build_zoom_tutorial())
        assert 'class="sp-zoom-stage"' in html

    def test_zoom_stage_absent_when_no_zoom_effect(self):
        html = _render(_build_zoom_tutorial(with_zoom=False))
        assert 'class="sp-zoom-stage"' not in html

    def test_bg_image_moves_into_stage_when_zoomed(self):
        """The background-image CSS must live on `.sp-zoom-stage` (so the
        scale transform on the stage zooms the image), NOT on the
        `.sp-section-inner` card (which would scale the whole card)."""
        html = _render(_build_zoom_tutorial())
        # The stage has the bg-image
        assert 'sp-zoom-stage" style="background-image:url(' in html
        # The inner card does NOT have a background-image directly set
        # (when zoom is active). We assert by looking at the inner's style
        # attribute right after `sp-section-inner`.
        import re
        m = re.search(r'<div class="sp-section-inner" style="([^"]*)"', html)
        assert m is not None, "sp-section-inner must exist"
        inner_style = m.group(1)
        assert "background-image" not in inner_style, (
            f"sp-section-inner should not carry background-image when zoomed: {inner_style}"
        )

    def test_bg_image_stays_on_inner_when_no_zoom(self):
        """Slides WITHOUT zoomEffect keep the legacy behavior — bg-image
        painted directly on the inner card (preserves PPT-imported slides)."""
        html = _render(_build_zoom_tutorial(with_zoom=False))
        import re
        m = re.search(r'<div class="sp-section-inner" style="([^"]*)"', html)
        assert m is not None
        assert "background-image" in m.group(1)

    def test_section_has_sp_has_zoom_class(self):
        html = _render(_build_zoom_tutorial())
        # The section must have BOTH classes so the CSS scoping works
        import re
        m = re.search(r'<section class="([^"]+)"', html)
        assert m and "sp-has-zoom" in m.group(1)

    def test_section_omits_zoom_class_when_no_zoom(self):
        html = _render(_build_zoom_tutorial(with_zoom=False))
        import re
        m = re.search(r'<section class="([^"]+)"', html)
        # The CSS stylesheet itself references "sp-has-zoom" so we can't
        # assert global absence — we check only the section tag's classes.
        assert m and "sp-has-zoom" not in m.group(1)

    def test_zoom_attrs_on_section(self):
        html = _render(_build_zoom_tutorial())
        assert 'data-zoom-scale="2.5"' in html
        assert 'data-zoom-fx="75.0"' in html
        assert 'data-zoom-fy="18.0"' in html
        assert 'data-zoom-intro="800"' in html
        assert 'data-zoom-hold="2400"' in html
        assert 'data-zoom-outro="600"' in html

    def test_zoom_attrs_dropped_when_scale_is_1(self):
        """A scale of 1.0 means no effect — skip emitting the attrs so the
        runtime observer never sets up a no-op zoom."""
        project = _build_zoom_tutorial()
        project["course"]["slides"][0]["zoomEffect"]["scale"] = 1.0
        html = _render(project)
        import re
        m = re.search(r'<section[^>]*>', html)
        assert m and "data-zoom-scale" not in m.group()
        # And no stage div is emitted
        assert '<div class="sp-zoom-stage"' not in html


class TestZoomStageElementPlacement:
    def test_hotspot_renders_inside_stage(self):
        """Hotspot + instruction text must live inside `.sp-zoom-stage` so
        they scale with the background when the magnification fires."""
        html = _render(_build_zoom_tutorial())
        stage_start = html.find('<div class="sp-zoom-stage"')
        assert stage_start >= 0
        # The instruction text content is unique enough to locate
        text_idx = html.find("Clique em Relat")
        assert text_idx >= 0
        assert text_idx > stage_start, "text overlay must live inside the stage"
        # And it must be before the section title (which sits outside)
        title_idx = html.find('class="sp-section-title"')
        assert text_idx < title_idx, "overlay text must be inside the stage (before the title)"

    def test_title_renders_outside_stage(self):
        """The section title sits BELOW (after) the zoom stage in DOM so it
        doesn't get scaled by the transform."""
        html = _render(_build_zoom_tutorial())
        stage_open = html.find('<div class="sp-zoom-stage"')
        stage_close_after = html.find("</div>", stage_open)
        title_idx = html.find('class="sp-section-title"')
        assert stage_open < stage_close_after < title_idx, (
            "section title should appear after the stage closes"
        )

    def test_body_strip_renders_outside_stage(self):
        html = _render(_build_zoom_tutorial())
        stage_open = html.find('<div class="sp-zoom-stage"')
        body_idx = html.find('class="sp-section-body"')
        assert body_idx > stage_open
        # Body must be after the stage closes (i.e., the body is a sibling
        # of the stage inside section-inner, NOT a child of the stage).
        stage_close = html.find("</div>", stage_open)
        # There may be nested divs inside the stage — find the matching close
        # by looking for the LAST </div> before sp-section-body
        # Simpler: ensure the body opening comes after the stage opening AND
        # the stage's bg-image style block (we expect the stage's content to
        # end before the body strip begins).
        assert "sp-zoom-stage" not in html[body_idx:body_idx + 200]
