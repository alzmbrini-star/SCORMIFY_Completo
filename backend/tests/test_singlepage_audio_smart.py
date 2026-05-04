"""Tests for SFX, background music, and smart avatar positioning in the
Single Page export."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from services.single_page_exporter import (
    _render_slide_sfx,
    _find_background_music,
    _smart_avatar_position,
    generate_single_page_html,
)


# ---------------------------------------------------------------------------
# SFX rendering
# ---------------------------------------------------------------------------

def test_sfx_renders_hidden_audio():
    slide = {"audio": [
        {"id": "a1", "type": "sfx", "src": "/api/projects/p/assets/ding.mp3"}
    ]}
    out = _render_slide_sfx(slide, 2, "p", "/tmp", "")
    assert 'class="sp-sfx"' in out
    assert 'data-sfx-section="2"' in out
    assert 'data-testid="sp-sfx-2"' in out
    assert 'aria-hidden="true"' in out
    assert 'style="display:none"' in out
    assert 'class="sp-sfx-audio"' in out


def test_sfx_only_matches_sfx_type():
    """Narration and background entries must not bleed into SFX."""
    slide = {"audio": [
        {"type": "narration", "src": "/n.mp3"},
        {"type": "sfx", "src": "/s.mp3"},
        {"type": "background", "src": "/b.mp3"},
    ]}
    out = _render_slide_sfx(slide, 0, "p", "/tmp", "")
    assert out.count('class="sp-sfx-audio"') == 1
    assert "/s.mp3" in out
    assert "/n.mp3" not in out
    assert "/b.mp3" not in out


def test_sfx_returns_empty_when_no_sfx_entries():
    slide = {"audio": [{"type": "narration", "src": "/n.mp3"}]}
    assert _render_slide_sfx(slide, 0, "p", "/tmp", "") == ""


def test_sfx_default_volume_is_0_6_clamped():
    """SFX should default to volume 0.6 (softer than narration at 1.0)."""
    slide = {"audio": [{"type": "sfx", "src": "/s.mp3"}]}
    out = _render_slide_sfx(slide, 0, "p", "/tmp", "")
    assert 'data-volume="0.6"' in out


def test_sfx_respects_explicit_volume():
    slide = {"audio": [{"type": "sfx", "src": "/s.mp3", "volume": 0.25}]}
    out = _render_slide_sfx(slide, 0, "p", "/tmp", "")
    assert 'data-volume="0.25"' in out


def test_sfx_skips_entries_without_src():
    slide = {"audio": [{"type": "sfx", "src": ""}, {"type": "sfx", "src": "/valid.mp3"}]}
    out = _render_slide_sfx(slide, 0, "p", "/tmp", "")
    assert out.count('class="sp-sfx-audio"') == 1


# ---------------------------------------------------------------------------
# Background music discovery
# ---------------------------------------------------------------------------

def test_bg_music_finds_first_background_audio_across_slides():
    course = {"slides": [
        {"audio": [{"type": "narration", "src": "/n.mp3"}]},
        {"audio": [{"type": "background", "src": "/bg.mp3", "volume": 0.15}]},
        {"audio": [{"type": "background", "src": "/bg2.mp3"}]},  # should be ignored
    ]}
    result = _find_background_music(course, "p", "/tmp", "")
    assert result is not None
    assert "/bg.mp3" in result["src"]
    assert result["volume"] == 0.15


def test_bg_music_default_volume_is_0_2():
    """Background music defaults to 0.2 (quiet ambient) when volume is unset."""
    course = {"slides": [{"audio": [{"type": "background", "src": "/bg.mp3"}]}]}
    result = _find_background_music(course, "p", "/tmp", "")
    assert result is not None
    assert result["volume"] == 0.2


def test_bg_music_clamps_volume():
    course = {"slides": [{"audio": [{"type": "background", "src": "/bg.mp3", "volume": 5.0}]}]}
    result = _find_background_music(course, "p", "/tmp", "")
    assert result["volume"] == 1.0


def test_bg_music_returns_none_when_no_background_audio():
    course = {"slides": [{"audio": [{"type": "narration", "src": "/n.mp3"}]}]}
    assert _find_background_music(course, "p", "/tmp", "") is None


def test_bg_music_returns_none_for_empty_course():
    assert _find_background_music({}, "p", "/tmp", "") is None
    assert _find_background_music({"slides": []}, "p", "/tmp", "") is None


# ---------------------------------------------------------------------------
# End-to-end: SFX + bg music in generated HTML
# ---------------------------------------------------------------------------

def _project_with_sfx_and_bg():
    return {
        "id": "p-audio",
        "name": "Curso Com Audio",
        "course": {
            "metadata": {"title": "C"},
            "slides": [
                {"id": "s1", "title": "Aula",
                 "width": 1920, "height": 820,
                 "elements": [{"type": "html", "id": "h",
                               "x": 0, "y": 0, "width": 1920, "height": 540,
                               "htmlContent": "<p>x</p>"}],
                 "audio": [
                     {"type": "narration", "src": "/n.mp3"},
                     {"type": "sfx", "src": "/ding.mp3", "volume": 0.5},
                     {"type": "background", "src": "/ambient.mp3", "volume": 0.18},
                 ]},
            ]
        }
    }


def test_singlepage_html_emits_sfx_block():
    html = generate_single_page_html(_project_with_sfx_and_bg(), "/tmp/no-such-dir", "")
    assert 'data-testid="sp-sfx-0"' in html
    assert "/ding.mp3" in html


def test_singlepage_html_emits_bg_music_audio_and_button():
    html = generate_single_page_html(_project_with_sfx_and_bg(), "/tmp/no-such-dir", "")
    assert 'id="sp-bg-music"' in html
    assert 'data-testid="sp-bg-music"' in html
    assert 'data-testid="sp-bg-music-toggle"' in html
    assert "/ambient.mp3" in html


def test_singlepage_html_emits_sfx_js_runtime():
    html = generate_single_page_html(_project_with_sfx_and_bg(), "/tmp/no-such-dir", "")
    assert "function observeSfx" in html
    assert "function playSfxForSection" in html
    assert "observeSfx()" in html


def test_singlepage_html_emits_bg_music_js_runtime():
    html = generate_single_page_html(_project_with_sfx_and_bg(), "/tmp/no-such-dir", "")
    assert "function setupBgMusic" in html
    assert "BG_MUSIC_MUTE_KEY" in html
    assert "sp:bgmusic:muted" in html
    assert "setupBgMusic()" in html


def test_singlepage_narration_still_works_alongside_sfx_and_bg():
    html = generate_single_page_html(_project_with_sfx_and_bg(), "/tmp/no-such-dir", "")
    assert "/n.mp3" in html
    assert 'data-testid="sp-narration-0"' in html


def test_singlepage_no_bg_music_elements_when_not_configured():
    project = {
        "id": "p", "name": "c",
        "course": {"slides": [
            {"id": "s", "title": "t", "width": 1920, "height": 820,
             "elements": [{"type": "html", "id": "h",
                           "x": 0, "y": 0, "width": 1920, "height": 540,
                           "htmlContent": "<p>x</p>"}],
             "audio": []}
        ]}
    }
    html = generate_single_page_html(project, "/tmp/no-such-dir", "")
    assert 'id="sp-bg-music"' not in html
    assert 'data-testid="sp-bg-music-toggle"' not in html


# ---------------------------------------------------------------------------
# Smart avatar positioning
# ---------------------------------------------------------------------------

def _make_test_image(tmp_path: Path, dark_column: int) -> Path:
    """Create a test image where one of the 3 bottom columns is darker.
    dark_column: 0=left, 1=center, 2=right.
    """
    from PIL import Image
    w, h = 300, 300
    img = Image.new("L", (w, h), 200)  # light everywhere
    # Make bottom 40% a specific column darker
    top = int(h * 0.60)
    col_w = w // 3
    left = dark_column * col_w
    right = left + col_w if dark_column < 2 else w
    dark_region = Image.new("L", (right - left, h - top), 30)  # very dark
    img.paste(dark_region, (left, top))
    img = img.convert("RGB")
    out = tmp_path / f"scene_{dark_column}.png"
    img.save(out)
    return out


def test_smart_avatar_picks_left_column_when_left_is_darkest(tmp_path):
    img = _make_test_image(tmp_path, dark_column=0)
    result = _smart_avatar_position(str(img))
    assert result is not None
    assert result["column"] == 0
    # Avatar should be in the left third (left < ~16%)
    assert result["left"] < 20


def test_smart_avatar_picks_center_column(tmp_path):
    img = _make_test_image(tmp_path, dark_column=1)
    result = _smart_avatar_position(str(img))
    assert result is not None
    assert result["column"] == 1
    # Centered: 33 < left < 67
    assert 30 < result["left"] < 50


def test_smart_avatar_picks_right_column(tmp_path):
    img = _make_test_image(tmp_path, dark_column=2)
    result = _smart_avatar_position(str(img))
    assert result is not None
    assert result["column"] == 2
    # Right third (> ~55%)
    assert result["left"] > 55


def test_smart_avatar_returns_none_for_missing_file():
    assert _smart_avatar_position("/nonexistent/file.png") is None


def test_smart_avatar_returns_none_for_empty_path():
    assert _smart_avatar_position("") is None


def test_smart_avatar_anchors_to_bottom(tmp_path):
    img = _make_test_image(tmp_path, dark_column=1)
    result = _smart_avatar_position(str(img))
    assert result is not None
    # Avatar is bottom-anchored: top ≈ 100 - height
    assert abs(result["top"] + result["height"] - 100) < 1


def test_smart_avatar_dimensions_are_sensible(tmp_path):
    img = _make_test_image(tmp_path, dark_column=1)
    result = _smart_avatar_position(str(img))
    assert result is not None
    assert 20 < result["width"] < 50   # not tiny, not huge
    assert 40 < result["height"] < 70  # half-to-two-thirds of card


# ---------------------------------------------------------------------------
# Smart avatar trigger: slide.smartAvatar flag + auto (zero coords)
# ---------------------------------------------------------------------------

def _slide_with_avatar_and_bg(smart=False, avatar_coords=(600, 200, 400, 400)):
    ax, ay, aw, ah = avatar_coords
    slide = {
        "id": "s1", "title": "T",
        "width": 1280, "height": 720,
        "backgroundImage": "/api/projects/p/assets/scene.png",
        "elements": [{"type": "video", "id": "v",
                      "src": "https://resource.heygen.ai/avatar/x-transparent.webm",
                      "x": ax, "y": ay, "width": aw, "height": ah}],
    }
    if smart:
        slide["smartAvatar"] = True
    return {"id": "p", "name": "c", "course": {"slides": [slide]}}


def test_smart_avatar_flag_triggers_smart_positioning(tmp_path, monkeypatch):
    """When slide.smartAvatar is True, the editor coords are ignored and the
    smart positioner analyzes the scene image."""
    img = _make_test_image(tmp_path, dark_column=2)
    assets_dir = tmp_path
    # Make the scene_url resolve to our test image
    project = _slide_with_avatar_and_bg(smart=True)
    project["course"]["slides"][0]["backgroundImage"] = f"/api/projects/p/assets/{img.name}"
    html = generate_single_page_html(project, str(assets_dir), "")
    assert 'data-smart-column="2"' in html


def test_smart_avatar_auto_triggers_when_avatar_has_no_coords(tmp_path):
    """If the avatar has x=0,y=0 (auto-placed default), smart positioning
    kicks in automatically — even without the flag."""
    img = _make_test_image(tmp_path, dark_column=1)
    project = _slide_with_avatar_and_bg(smart=False, avatar_coords=(0, 0, 0, 0))
    project["course"]["slides"][0]["backgroundImage"] = f"/api/projects/p/assets/{img.name}"
    html = generate_single_page_html(project, str(tmp_path), "")
    assert 'data-smart-column="1"' in html


def test_smart_avatar_respects_explicit_editor_coords(tmp_path):
    """When smart flag is OFF and avatar has explicit non-zero coords, use
    those coords — don't override with smart positioning."""
    img = _make_test_image(tmp_path, dark_column=0)
    project = _slide_with_avatar_and_bg(smart=False, avatar_coords=(640, 360, 400, 300))
    project["course"]["slides"][0]["backgroundImage"] = f"/api/projects/p/assets/{img.name}"
    html = generate_single_page_html(project, str(tmp_path), "")
    # No smart column attr
    assert "data-smart-column" not in html
    # Editor coords translate to 640/1280=50%, 360/720=50%
    assert "left:50.00%" in html
    assert "top:50.00%" in html
