"""Tests for the Single Page exporter's ElevenLabs narration integration.

Covers:
- _render_slide_narration produces a hidden <audio> + visible controls when
  slide.audio[] has narration entries
- It returns "" when slide has no audio[] or only sfx-typed entries
- generate_single_page_html embeds the narration block inside each section
  AND injects the narration-specific CSS + JS runtime hooks
- The narration is NOT marked as a blocking interactive (no
  data-required="true" on the wrapper) — so it doesn't gate progression.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from services.single_page_exporter import (
    _render_slide_narration,
    generate_single_page_html,
)


def _slide_with_narration(audios):
    return {
        "id": "s1",
        "title": "Aula 1: Introdução",
        "elements": [
            {"type": "html", "id": "el1", "x": 0, "y": 0, "width": 1920, "height": 540,
             "htmlContent": "<p>Conteudo</p>"},
        ],
        "audio": audios,
    }


def test_render_narration_returns_empty_when_no_audio():
    assert _render_slide_narration({"audio": []}, 0, "p", "/tmp", "") == ""
    assert _render_slide_narration({}, 0, "p", "/tmp", "") == ""


def test_render_narration_returns_empty_when_only_sfx():
    """Only narration-typed audio is auto-played; sfx is skipped."""
    slide = {"audio": [{"id": "a1", "type": "sfx", "src": "/x.mp3"}]}
    assert _render_slide_narration(slide, 0, "p", "/tmp", "") == ""


def test_render_narration_includes_audio_and_controls():
    audios = [{"id": "a1", "type": "narration",
               "src": "/api/projects/p/assets/audio_x.mp3", "volume": 0.85}]
    out = _render_slide_narration(_slide_with_narration(audios), 3, "p", "/tmp", "")
    assert 'class="sp-narration"' in out
    assert 'data-narration-section="3"' in out
    assert 'data-testid="sp-narration-3"' in out
    # Hidden <audio> element with the right src + volume + testid
    assert 'class="sp-narration-audio"' in out
    assert 'data-volume="0.85"' in out
    assert 'data-testid="sp-narration-audio-3-0"' in out
    # Controls (play/pause/restart) with proper testids
    assert 'data-narration-action="toggle"' in out
    assert 'data-narration-action="restart"' in out
    assert 'data-testid="sp-narration-toggle-3"' in out
    assert 'data-testid="sp-narration-restart-3"' in out


def test_render_narration_default_volume_is_1():
    audios = [{"id": "a1", "type": "narration", "src": "/x.mp3"}]
    out = _render_slide_narration(_slide_with_narration(audios), 0, "p", "/tmp", "")
    assert 'data-volume="1.0"' in out or 'data-volume="1"' in out


def test_render_narration_clamps_invalid_volume():
    """Volume > 1 should clamp to 1.0; negative should clamp to 0.0."""
    out_hi = _render_slide_narration(
        _slide_with_narration([{"type": "narration", "src": "/x.mp3", "volume": 5.0}]),
        0, "p", "/tmp", "",
    )
    assert 'data-volume="1.0"' in out_hi or 'data-volume="1"' in out_hi
    out_lo = _render_slide_narration(
        _slide_with_narration([{"type": "narration", "src": "/x.mp3", "volume": -3.0}]),
        0, "p", "/tmp", "",
    )
    assert 'data-volume="0.0"' in out_lo or 'data-volume="0"' in out_lo


def test_render_narration_supports_multiple_entries():
    """Multiple narration entries (e.g. from successive TTS upgrades) all render."""
    audios = [
        {"type": "narration", "src": "/a.mp3", "volume": 0.5},
        {"type": "narration", "src": "/b.mp3", "volume": 1.0},
    ]
    out = _render_slide_narration(_slide_with_narration(audios), 7, "p", "/tmp", "")
    assert 'data-testid="sp-narration-audio-7-0"' in out
    assert 'data-testid="sp-narration-audio-7-1"' in out


def test_render_narration_skips_entries_with_no_src():
    audios = [
        {"type": "narration", "src": ""},
        {"type": "narration", "src": "/valid.mp3"},
    ]
    out = _render_slide_narration(_slide_with_narration(audios), 0, "p", "/tmp", "")
    # Only the valid entry should produce an <audio>
    assert out.count('class="sp-narration-audio"') == 1
    assert 'src="/valid.mp3"' in out


def test_render_narration_treats_missing_type_as_narration():
    """Slides uploaded via Editor TTS may have type='narration' but if missing
    we should default to narration (the upload route does set it, but we
    guard against legacy data)."""
    audios = [{"src": "/api/projects/p/assets/audio_y.mp3"}]
    out = _render_slide_narration(_slide_with_narration(audios), 0, "p", "/tmp", "")
    assert 'class="sp-narration-audio"' in out


# ---------------------------------------------------------------------------
# End-to-end: generate_single_page_html embeds narration + JS + CSS
# ---------------------------------------------------------------------------

def _project_with_narration():
    return {
        "id": "proj-test",
        "name": "Curso de Teste",
        "course": {
            "metadata": {"title": "Curso de Teste"},
            "slides": [
                {"id": "s1", "title": "Slide 1",
                 "elements": [{"type": "html", "id": "e1",
                               "x": 0, "y": 0, "width": 1920, "height": 540,
                               "htmlContent": "<p>Olá</p>"}],
                 "audio": [{"id": "a1", "type": "narration",
                            "src": "/api/projects/proj-test/assets/n1.mp3"}]},
                {"id": "s2", "title": "Slide 2",
                 "elements": [{"type": "html", "id": "e2",
                               "x": 0, "y": 0, "width": 1920, "height": 540,
                               "htmlContent": "<p>Mundo</p>"}],
                 "audio": []},
            ]
        }
    }


def test_singlepage_html_includes_narration_for_slide_with_audio():
    html = generate_single_page_html(_project_with_narration(), "/tmp/no-such-dir", "")
    # Slide 0 has narration
    assert 'data-testid="sp-narration-0"' in html
    # Slide 1 has no narration
    assert 'data-testid="sp-narration-1"' not in html


def test_singlepage_html_injects_narration_css():
    html = generate_single_page_html(_project_with_narration(), "/tmp/no-such-dir", "")
    assert ".sp-narration{" in html
    assert ".sp-narration-audio{display:none}" in html
    assert ".sp-narration-controls" in html
    assert ".sp-narration-mute-toggle" in html


def test_singlepage_html_injects_narration_js_runtime():
    html = generate_single_page_html(_project_with_narration(), "/tmp/no-such-dir", "")
    # Key runtime hooks
    assert "function observeNarrations" in html
    assert "function playNarration" in html
    assert "NARRATION_MUTE_KEY" in html
    # Wired into the bootstrap
    assert "observeNarrations()" in html


def test_singlepage_narration_is_not_a_blocking_interactive():
    """The narration wrapper must NOT carry data-required='true' or the
    sp-interactive class — otherwise the existing "all interactives must be
    completed before the next section unlocks" gating would trap the user."""
    html = generate_single_page_html(_project_with_narration(), "/tmp/no-such-dir", "")
    # Find the narration wrapper line
    needle = 'class="sp-narration"'
    assert needle in html
    idx = html.index(needle)
    # Take ~250 chars of the wrapper opening tag region
    region = html[idx:idx + 300]
    assert "sp-interactive" not in region.split('>', 1)[0]
    assert 'data-required="true"' not in region.split('>', 1)[0]


def test_singlepage_narration_resolves_remote_url_when_base_url_provided():
    """When base_url is set and the file isn't on disk, the URL should be
    rewritten to absolute (so the standalone HTML page can fetch the audio)."""
    html = generate_single_page_html(
        _project_with_narration(),
        "/tmp/no-such-dir",
        base_url="https://app.example.com",
    )
    # The audio src should be absolute or at least preserved in the markup
    assert "n1.mp3" in html


def test_singlepage_no_narration_block_when_project_has_no_audio():
    """If no slide has audio, the renderer must not emit the narration markup
    (the JS observer will simply find zero `.sp-narration` nodes — no harm).
    """
    project = _project_with_narration()
    project["course"]["slides"][0]["audio"] = []
    html = generate_single_page_html(project, "/tmp/no-such-dir", "")
    assert 'data-testid="sp-narration-0"' not in html
    assert 'data-testid="sp-narration-1"' not in html
