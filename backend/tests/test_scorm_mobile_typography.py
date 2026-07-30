"""Regression tests for typography in the standard HTML/SCORM player."""
from pathlib import Path


PLAYER_JS = (
    Path(__file__).resolve().parent.parent
    / "services"
    / "export_assets"
    / "player.js"
)


def test_mobile_html_does_not_override_authored_font_sizes():
    source = PLAYER_JS.read_text(encoding="utf-8")

    assert "p,li{font-size:15px!important" not in source
    assert "span[style*=\"font-size\"]{font-size:inherit!important;}" not in source
    assert "body{font-size:16px!important" not in source


def test_player_keeps_single_proportional_canvas_scale():
    source = PLAYER_JS.read_text(encoding="utf-8")

    assert "var scale = Math.min(scaleX, scaleY);" in source
    assert "container.style.transform = 'scale(' + scale + ')';" in source
    assert "body{padding:12px!important;overflow-x:hidden!important;}" in source
