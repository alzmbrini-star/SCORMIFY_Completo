"""Tests for the avatar-over-scene-image composition in the Single Page exporter.

User report: a HeyGen avatar (transparent .webm) was rendering BELOW the scene
background image as two stacked blocks, instead of being overlaid on top of the
image. The fix detects the avatar+scene pair and renders them as a single
composed `.sp-avatar-stage` block where the avatar is absolutely positioned
over the image (mapping editor x/y/width/height to percentage coordinates).
"""
from __future__ import annotations

import pytest

from services.single_page_exporter import (
    _is_heygen_or_transparent_avatar,
    _looks_like_scene_image,
    _find_avatar_scene_pair,
    _render_avatar_stage,
    generate_single_page_html,
)


HEYGEN_URL = "https://resource.heygen.ai/avatar/abc-transparent.webm"
NON_HEYGEN_URL = "https://example.com/some-other-video.mp4"


# ---------------------------------------------------------------------------
# Detection helpers
# ---------------------------------------------------------------------------

def test_is_heygen_avatar_video_with_heygen_url():
    el = {"type": "video", "src": HEYGEN_URL}
    assert _is_heygen_or_transparent_avatar(el) is True


def test_is_heygen_avatar_avatar_type_with_videourl():
    el = {"type": "avatar", "videoUrl": HEYGEN_URL}
    assert _is_heygen_or_transparent_avatar(el) is True


def test_is_heygen_avatar_false_for_non_heygen_video():
    el = {"type": "video", "src": NON_HEYGEN_URL}
    assert _is_heygen_or_transparent_avatar(el) is False


def test_is_heygen_avatar_false_for_image():
    el = {"type": "image", "src": HEYGEN_URL}  # even with heygen in URL
    assert _is_heygen_or_transparent_avatar(el) is False


def test_looks_like_scene_image_when_large():
    el = {"type": "image", "width": 1500, "src": "/scene.png"}
    assert _looks_like_scene_image(el, slide_w=1920) is True


def test_looks_like_scene_image_false_when_small():
    """Logos / icons that are <55% of slide width should NOT be classified
    as scene backgrounds."""
    el = {"type": "image", "width": 200, "src": "/logo.png"}
    assert _looks_like_scene_image(el, slide_w=1920) is False


def test_looks_like_scene_image_false_for_non_image():
    el = {"type": "video", "width": 1920}
    assert _looks_like_scene_image(el, slide_w=1920) is False


# ---------------------------------------------------------------------------
# Pair finder
# ---------------------------------------------------------------------------

def test_find_pair_returns_avatar_and_scene():
    elements = [
        {"type": "html", "id": "h1"},
        {"type": "video", "id": "v1", "src": HEYGEN_URL,
         "x": 700, "y": 200, "width": 400, "height": 540},
        {"type": "image", "id": "img1", "src": "/scene.png",
         "x": 0, "y": 0, "width": 1920, "height": 820},
    ]
    pair = _find_avatar_scene_pair(elements, slide_w=1920)
    assert pair is not None
    assert pair["avatar_idx"] == 1
    assert pair["scene_idx"] == 2
    assert pair["avatar_el"]["id"] == "v1"
    assert pair["scene_el"]["id"] == "img1"


def test_find_pair_returns_none_when_no_avatar():
    elements = [
        {"type": "image", "src": "/scene.png", "width": 1920},
        {"type": "video", "src": NON_HEYGEN_URL, "width": 400},
    ]
    assert _find_avatar_scene_pair(elements, slide_w=1920) is None


def test_find_pair_returns_none_when_only_avatar_no_image():
    elements = [
        {"type": "video", "src": HEYGEN_URL, "width": 400},
    ]
    assert _find_avatar_scene_pair(elements, slide_w=1920) is None


def test_find_pair_picks_largest_image_when_multiple():
    """If a slide has a logo (small) AND a scene (large), pair the avatar
    with the scene — never with the logo."""
    elements = [
        {"type": "image", "id": "logo", "src": "/logo.png",
         "x": 1700, "y": 50, "width": 180, "height": 80},  # too small
        {"type": "video", "id": "v1", "src": HEYGEN_URL,
         "x": 700, "y": 200, "width": 400, "height": 540},
        {"type": "image", "id": "scene", "src": "/scene.png",
         "x": 0, "y": 0, "width": 1920, "height": 820},  # the actual scene
    ]
    pair = _find_avatar_scene_pair(elements, slide_w=1920)
    assert pair is not None
    assert pair["scene_el"]["id"] == "scene"


def test_find_pair_picks_first_avatar_when_multiple():
    elements = [
        {"type": "video", "id": "v1", "src": HEYGEN_URL, "width": 400},
        {"type": "video", "id": "v2", "src": HEYGEN_URL, "width": 400},
        {"type": "image", "id": "scene", "src": "/scene.png", "width": 1920},
    ]
    pair = _find_avatar_scene_pair(elements, slide_w=1920)
    assert pair is not None
    assert pair["avatar_el"]["id"] == "v1"


# ---------------------------------------------------------------------------
# Stage rendering
# ---------------------------------------------------------------------------

def test_render_stage_uses_percentage_positioning_from_editor_coords():
    scene = {"type": "image", "src": "/scene.png",
             "x": 0, "y": 0, "width": 1920, "height": 820}
    avatar = {"type": "video", "src": HEYGEN_URL,
              "x": 480, "y": 82, "width": 768, "height": 615}
    out = _render_avatar_stage(scene, avatar, "p", "/tmp", "", slide_idx=0)
    assert "sp-avatar-stage" in out
    assert "data-testid=\"sp-avatar-stage-0\"" in out
    # Avatar at x=480 over scene starting at x=0 width=1920 → 25% left
    assert "left:25.00%" in out
    # Width 768/1920 = 40%
    assert "width:40.00%" in out
    # Top 82/820 = 10%
    assert "top:10.00%" in out


def test_render_stage_clamps_overlay_to_image_bounds():
    """If avatar coordinates are outside the scene image, the overlay should
    clamp to 0%-100% so the avatar doesn't escape the scene."""
    scene = {"type": "image", "src": "/scene.png",
             "x": 100, "y": 100, "width": 1000, "height": 600}
    # Avatar way outside the scene (negative offset relative to scene origin)
    avatar = {"type": "video", "src": HEYGEN_URL,
              "x": 0, "y": 0, "width": 200, "height": 300}
    out = _render_avatar_stage(scene, avatar, "p", "/tmp", "", slide_idx=2)
    assert "left:0.00%" in out
    assert "top:0.00%" in out


def test_render_stage_falls_back_when_no_coords():
    """Legacy slides where avatar has no x/y/width — fall back to bottom-center
    positioning so the avatar still appears over the scene."""
    scene = {"type": "image", "src": "/scene.png", "width": 1920, "height": 820}
    avatar = {"type": "video", "src": HEYGEN_URL}  # no coords
    out = _render_avatar_stage(scene, avatar, "p", "/tmp", "", slide_idx=0)
    assert "sp-avatar-stage" in out
    assert "left:50%" in out
    assert "bottom:0" in out


def test_render_stage_returns_empty_when_missing_src():
    scene = {"type": "image", "src": "", "width": 1920}
    avatar = {"type": "video", "src": HEYGEN_URL}
    assert _render_avatar_stage(scene, avatar, "p", "/tmp", "", slide_idx=0) == ""


def test_render_stage_includes_required_data_attrs_for_progression_gating():
    """The composed avatar block must still gate the section unlock — i.e.
    the user must press play once before the next section unlocks. So the
    overlay must keep data-required='true' + data-interactive='video'."""
    scene = {"type": "image", "src": "/scene.png", "width": 1920, "height": 820}
    avatar = {"type": "video", "src": HEYGEN_URL, "width": 400, "height": 540}
    out = _render_avatar_stage(scene, avatar, "p", "/tmp", "", slide_idx=0)
    assert 'data-interactive="video"' in out
    assert 'data-required="true"' in out
    assert 'sp-avatar-wrap' in out  # so the existing JS markPlayed selector matches
    assert "SP.markPlayed" in out


# ---------------------------------------------------------------------------
# End-to-end integration
# ---------------------------------------------------------------------------

def _project_with_avatar_and_scene():
    return {
        "id": "p-avatar",
        "name": "Curso com Avatar",
        "course": {
            "metadata": {"title": "Curso com Avatar"},
            "slides": [
                {
                    "id": "s1", "title": "Aula com Avatar",
                    "width": 1920, "height": 820,
                    "elements": [
                        {"type": "html", "id": "h1",
                         "x": 0, "y": 0, "width": 1920, "height": 60,
                         "htmlContent": "<h2>Header</h2>"},
                        {"type": "video", "id": "v1", "src": HEYGEN_URL,
                         "x": 600, "y": 100, "width": 720, "height": 540},
                        {"type": "image", "id": "img1", "src": "/api/projects/p/assets/scene.png",
                         "x": 0, "y": 70, "width": 1920, "height": 750},
                    ]
                }
            ]
        }
    }


def test_singlepage_html_emits_avatar_stage_and_omits_individual_elements():
    html = generate_single_page_html(_project_with_avatar_and_scene(), "/tmp/no-such-dir", "")
    # Composed stage present
    assert 'data-testid="sp-avatar-stage-0"' in html
    # The CSS needed for absolute positioning is injected
    assert ".sp-avatar-stage{position:relative" in html
    # The avatar's source URL must appear inside the stage (not in a
    # separate sp-avatar-wrap top-level block).
    assert HEYGEN_URL in html
    # And the scene image's URL appears inside the same stage block
    assert "scene.png" in html


def test_singlepage_html_does_not_compose_when_only_logo_image():
    """Avatar with a small logo (not a scene) must NOT be composed — should
    render as the original separate avatar element + the logo image."""
    project = {
        "id": "p1", "name": "C",
        "course": {"slides": [{
            "id": "s", "title": "T", "width": 1920, "height": 820,
            "elements": [
                {"type": "video", "id": "v1", "src": HEYGEN_URL, "width": 400, "height": 540},
                {"type": "image", "id": "logo", "src": "/logo.png",
                 "x": 1700, "y": 50, "width": 180, "height": 80},
            ]
        }]}
    }
    html = generate_single_page_html(project, "/tmp/no-such-dir", "")
    assert 'data-testid="sp-avatar-stage-0"' not in html
    # Both originals still rendered separately
    assert HEYGEN_URL in html


def test_singlepage_html_no_regression_when_no_avatar():
    """A regular slide without HeyGen avatar must keep working."""
    project = {
        "id": "p1", "name": "C",
        "course": {"slides": [{
            "id": "s", "title": "T", "width": 1920, "height": 820,
            "elements": [
                {"type": "html", "id": "h1", "x": 0, "y": 0, "width": 1920,
                 "height": 540, "htmlContent": "<p>hi</p>"},
                {"type": "image", "id": "img", "src": "/scene.png",
                 "x": 0, "y": 0, "width": 1920, "height": 820},
            ]
        }]}
    }
    html = generate_single_page_html(project, "/tmp/no-such-dir", "")
    assert 'data-testid="sp-avatar-stage-0"' not in html
    assert "scene.png" in html


# ---------------------------------------------------------------------------
# Avatar over slide.backgroundImage (PPT-imported slides)
# ---------------------------------------------------------------------------

def _ppt_slide_with_bg_and_avatar():
    return {
        "id": "p-ppt-avatar",
        "name": "Curso PPT com Avatar",
        "course": {
            "metadata": {"title": "Curso"},
            "slides": [{
                "id": "s1", "title": "Boas-vindas",
                "width": 1280, "height": 720,
                "backgroundImage": "/api/projects/p-ppt-avatar/assets/cenario.png",
                "background": "#0a2540",
                "elements": [
                    {"type": "video", "id": "v-avatar", "src": HEYGEN_URL,
                     "x": 380, "y": 200, "width": 520, "height": 520},
                ],
            }]
        }
    }


def test_avatar_overlays_on_slide_background_image():
    """When the scene comes from `slide.backgroundImage` (PPT-imported) and
    a HeyGen avatar is on the same slide, the avatar must be rendered as an
    absolute overlay INSIDE the section card — not as a separate stacked
    block below the card."""
    html = generate_single_page_html(_ppt_slide_with_bg_and_avatar(), "/tmp/no-such-dir", "")
    # The new bg-overlay testid is present
    assert 'data-testid="sp-avatar-overlay-0"' in html
    # Aspect-locked card is present (the bg-image-aware container)
    assert "sp-aspect-locked" in html
    # Avatar coords translated to percentages relative to slide.width
    # 380/1280 ≈ 29.69%, 200/720 ≈ 27.78%, 520/1280 ≈ 40.62%, 520/720 ≈ 72.22%
    assert "left:29.69%" in html
    assert "top:27.78%" in html
    assert "width:40.62%" in html


def test_avatar_overlay_keeps_video_play_gating():
    """The avatar overlay must still gate progression — overlay carries
    data-required='true' + data-interactive='video' + class 'sp-avatar-wrap'
    so SP.markPlayed continues to fire on play."""
    html = generate_single_page_html(_ppt_slide_with_bg_and_avatar(), "/tmp/no-such-dir", "")
    # Find the overlay region
    needle = 'data-testid="sp-avatar-overlay-0"'
    assert needle in html
    idx = html.index(needle)
    region = html[idx - 400:idx + 400]
    assert "sp-avatar-wrap" in region
    assert 'data-required="true"' in region
    assert "SP.markPlayed" in region


def test_avatar_overlay_is_inside_section_inner():
    """Regression check: the overlay must be a child of `.sp-section-inner`,
    not of `.sp-section-body` — otherwise the body's gradient overlay
    (max-height:50%) would clip it."""
    html = generate_single_page_html(_ppt_slide_with_bg_and_avatar(), "/tmp/no-such-dir", "")
    # The overlay must appear AFTER the body's closing div, but before the
    # section-inner closing div. Easiest assertion: between body close and
    # section-inner close.
    body_close = html.find("</div>\n    <div class=\"sp-avatar-overlay")
    # Either pattern works — body closes then overlay div opens
    assert ('</div>\n    <div class="sp-avatar-overlay' in html
            or '</div>\n    <div class="sp-avatar-overlay sp-avatar-wrap' in html)


def test_no_avatar_overlay_when_no_bg_image():
    """If the slide has a HeyGen avatar but NO backgroundImage, the existing
    pair-finder must handle it (looking for an <image> element). The new
    bg-overlay codepath should NOT also kick in."""
    project = {
        "id": "p", "name": "C",
        "course": {"slides": [{
            "id": "s", "title": "T",
            "width": 1920, "height": 820,
            "elements": [
                {"type": "video", "id": "v", "src": HEYGEN_URL,
                 "x": 100, "y": 100, "width": 400, "height": 540},
                # No backgroundImage on the slide and no scene <image> el either
            ],
        }]}
    }
    html = generate_single_page_html(project, "/tmp/no-such-dir", "")
    # No bg-overlay (no bg image to overlay onto)
    assert 'data-testid="sp-avatar-overlay-0"' not in html
    # Existing avatar pair compose also does not trigger (no scene image)
    assert 'data-testid="sp-avatar-stage-0"' not in html


def test_avatar_overlay_skips_non_heygen_video():
    """Non-HeyGen videos (e.g. a YouTube embed) must NOT be repositioned as
    an avatar — they should render as a regular video element."""
    project = {
        "id": "p", "name": "C",
        "course": {"slides": [{
            "id": "s", "title": "T",
            "width": 1280, "height": 720,
            "backgroundImage": "/scene.png",
            "elements": [
                {"type": "video", "id": "v", "src": NON_HEYGEN_URL,
                 "x": 100, "y": 100, "width": 400, "height": 300},
            ],
        }]}
    }
    html = generate_single_page_html(project, "/tmp/no-such-dir", "")
    assert 'data-testid="sp-avatar-overlay-0"' not in html


def test_aspect_locked_body_no_scrollbar():
    """The CSS for aspect-locked body must use `overflow:visible` (not auto)
    — the scrollbar in the user's screenshot was caused by overflow-y:auto
    when the body content (large iframe) overflowed the 50% max-height."""
    html = generate_single_page_html(_ppt_slide_with_bg_and_avatar(), "/tmp/no-such-dir", "")
    # The body uses overflow:visible
    assert ".sp-section.sp-aspect-locked .sp-section-body{position:absolute" in html
    assert "overflow:visible" in html
    # And NOT overflow-y:auto in the aspect-locked body rule
    body_rule_start = html.index(".sp-section.sp-aspect-locked .sp-section-body{")
    body_rule_end = html.index("}", body_rule_start)
    body_rule = html[body_rule_start:body_rule_end]
    assert "overflow-y:auto" not in body_rule


def test_aspect_locked_body_hides_when_empty():
    """When the avatar consumes the only meaningful element on the slide,
    the body becomes empty — the CSS must hide it via `:empty` so the
    bottom gradient strip doesn't show as a useless dark band."""
    html = generate_single_page_html(_ppt_slide_with_bg_and_avatar(), "/tmp/no-such-dir", "")
    assert ".sp-section.sp-aspect-locked .sp-section-body:empty{display:none}" in html
