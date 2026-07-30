"""Regression tests for protected Bunny Stream iframe URLs."""

from pathlib import Path

from services.single_page_exporter import _render_video_element_inner


BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent


def test_editor_keeps_original_bunny_iframe_url():
    src = (ROOT / "frontend/src/pages/Editor.jsx").read_text(encoding="utf-8")
    start = src.index("// Parse Bunny Stream URL")
    branch = src[start:src.index("// Get slide dimensions", start)]
    assert "embedUrl = parsedUrl" in branch
    assert "libraryId" not in branch
    assert "videoGuid" not in branch


def test_html_exporter_preserves_bunny_url():
    src = (BACKEND / "services/html_exporter.py").read_text(encoding="utf-8")
    assert "iframe.mediadelivery.net" in src
    assert "isBunny" in src
    bunny_branch = src[src.index("}} else if (isBunny)"):]
    bunny_branch = bunny_branch[:bunny_branch.index("}} else {{")]
    assert "src=\"' + embedUrl + '\"" in bunny_branch
    assert "bunnyUrl +=" not in bunny_branch


def test_player_js_preserves_bunny_url_and_fills_element():
    src = (BACKEND / "services/export_assets/player.js").read_text(encoding="utf-8")
    assert "iframe.mediadelivery.net" in src
    assert "isBunny" in src
    idx = src.index("} else if (isBunny)")
    tail = src[idx: idx + 1500]
    assert "iframe.src = embedUrl" in tail
    assert "bunnyUrl +=" not in tail
    assert "position:absolute" in tail


def test_single_page_export_preserves_protected_bunny_query(tmp_path):
    protected = (
        "https://iframe.mediadelivery.net/embed/123/"
        "11111111-2222-3333-4444-555555555555"
        "?token=abc123&expires=1999999999"
    )
    rendered = _render_video_element_inner(
        {"type": "video", "embedUrl": protected},
        "project-1",
        str(tmp_path),
        "",
        0,
    )
    # HTML escaping is expected; browsers decode &amp; back to the same URL.
    assert "token=abc123&amp;expires=1999999999" in rendered
    assert "<iframe" in rendered
    assert "<video " not in rendered
