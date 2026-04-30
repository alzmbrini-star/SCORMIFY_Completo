"""Tests for the kiosk / fullscreen mode in the Single Page export."""
from __future__ import annotations

from services.single_page_exporter import generate_single_page_html


def _project():
    return {
        "id": "p", "name": "Curso",
        "course": {
            "metadata": {"title": "Curso"},
            "slides": [
                {"id": "s1", "title": "Aula 1",
                 "width": 1920, "height": 1080,
                 "backgroundImage": "/api/projects/p/assets/s1.png",
                 "elements": []},
            ]
        }
    }


def test_fullscreen_button_exists_in_header():
    html = generate_single_page_html(_project(), "/tmp/no-such", "")
    assert 'data-testid="sp-fullscreen-btn"' in html
    assert 'aria-label="Modo Tela Cheia"' in html
    # Both expand + shrink icons present (CSS toggles visibility)
    assert "sp-icon-expand" in html
    assert "sp-icon-shrink" in html


def test_fullscreen_css_present():
    html = generate_single_page_html(_project(), "/tmp/no-such", "")
    assert ".sp-fullscreen-btn{" in html
    # Body data-fullscreen toggles all kiosk styles
    assert 'body[data-fullscreen="true"]' in html
    # Header collapses + auto-hides when fullscreen
    assert "sp-header-hidden" in html
    # PPT slides expand to viewport in kiosk mode
    assert 'body[data-fullscreen="true"] .sp-section.sp-aspect-locked' in html


def test_fullscreen_js_runtime_present():
    html = generate_single_page_html(_project(), "/tmp/no-such", "")
    # Functions
    assert "function setFullscreenMode" in html
    assert "function setupFullscreen" in html
    assert "function isInBrowserFullscreen" in html
    assert "function scheduleHeaderAutoHide" in html
    # Vendor-prefixed fullscreen API support
    assert "webkitRequestFullscreen" in html
    assert "mozRequestFullScreen" in html
    # F11 / "f" keyboard shortcut wiring
    assert "ev.key === 'F11'" in html
    # Persistence
    assert "FULLSCREEN_KEY" in html
    assert "sp:fullscreen" in html
    # Bootstrap call
    assert "setupFullscreen()" in html


def test_fullscreen_keyboard_does_not_trigger_in_inputs():
    """Pressing 'f' inside a quiz textarea must NOT toggle kiosk mode."""
    html = generate_single_page_html(_project(), "/tmp/no-such", "")
    # The keydown handler skips toggling when the focused element is an input
    assert "INPUT|TEXTAREA|SELECT" in html


def test_fullscreen_syncs_flag_on_esc_exit():
    """If the user presses Esc to exit browser fullscreen, our internal
    body[data-fullscreen] flag must reset too — otherwise the kiosk CSS stays
    on but the browser is back to windowed mode."""
    html = generate_single_page_html(_project(), "/tmp/no-such", "")
    assert "fullscreenchange" in html
    assert "webkitfullscreenchange" in html


def test_fullscreen_auto_hides_header_after_idle():
    html = generate_single_page_html(_project(), "/tmp/no-such", "")
    assert "scheduleHeaderAutoHide" in html
    # 2.5s idle timeout
    assert "2500" in html


def test_fullscreen_persists_in_sessionstorage():
    html = generate_single_page_html(_project(), "/tmp/no-such", "")
    assert "sessionStorage.setItem(FULLSCREEN_KEY" in html
    assert "sessionStorage.getItem(FULLSCREEN_KEY)" in html
