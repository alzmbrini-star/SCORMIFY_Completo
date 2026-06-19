"""Regression test for the SCORM/HTML initial loading overlay (2026-02).

A SCORM package on an LMS with narrow bandwidth used to show the first
slide's broken-image flash before the player JS could finish wiring
up the asset paths. We now ship a fixed full-viewport loading overlay
that:
  - Renders BEFORE any slide markup, so the user never sees broken UI.
  - Tracks `<img>` / `<video>` loading on the first slide and animates
    a progress bar.
  - Hides automatically when assets settle OR after a 15 s safety net.

These tests verify the overlay markup + behavioural hooks are emitted
in both the standalone HTML export and the SCORM single-page zip.
"""
import asyncio
import io
import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.html_exporter import generate_standalone_html  # noqa: E402


def _course():
    return {
        "id": "p1", "name": "Loader Test", "enableVlibras": False,
        "course": {
            "metadata": {"title": "Loader Test"},
            "slides": [{
                "id": "s1", "title": "S", "width": 1280, "height": 720,
                "background": "#fff", "duration": 5,
                "elements": [{
                    "id": "e1", "type": "image",
                    "src": "https://example.com/img.png",
                    "x": 0, "y": 0, "width": 400, "height": 200,
                }],
                "annotations": [],
            }],
        },
    }


def _html():
    return asyncio.run(generate_standalone_html(
        project=_course(),
        assets_dir="/tmp",
        base_url="",
        questions=None,
        backend_url="",
        tutor_config=None,
    ))


def test_loader_overlay_is_emitted():
    html = _html()
    # Overlay container + testid.
    assert 'id="scormify-loader"' in html
    assert 'data-testid="scorm-initial-loader"' in html
    # ARIA support for screen readers.
    assert 'role="status"' in html
    assert 'aria-label="Carregando curso"' in html
    # Title in Portuguese (matches Scormify product language).
    assert "Carregando curso" in html


def test_loader_appears_before_slide_markup():
    """Overlay HTML must come BEFORE the player-container div so the
    overlay paints first even if the rest of the document is slow."""
    html = _html()
    loader_idx = html.find('id="scormify-loader"')
    player_idx = html.find('id="player-container"')
    assert loader_idx > 0 and player_idx > 0
    assert loader_idx < player_idx, (
        "loader overlay must be in the document BEFORE the player "
        "container (otherwise it can't cover the broken-image flash)"
    )


def test_loader_has_progress_hooks():
    html = _html()
    # Progress UI nodes.
    assert 'id="scormify-loader-bar"' in html
    assert 'id="scormify-loader-percent"' in html
    # JS waits for <img> and <video> assets on the first slide.
    assert "querySelectorAll('img')" in html
    assert "querySelectorAll('video')" in html
    # Safety timeout (15 s) to never block the user forever.
    assert "setTimeout(hide, 15000)" in html


def test_scorm_single_page_zip_contains_loader():
    """Generating the actual SCORM zip must ship the loader inside
    index.html (it's a slice of the same HTML generator)."""
    from services.scorm_single_page_exporter import export_single_page_scorm_package

    with tempfile.TemporaryDirectory() as tmp:
        out = export_single_page_scorm_package(
            project_doc=_course(),
            storage_dir=tmp,
            output_dir=tmp,
            backend_url="",
        )
        with zipfile.ZipFile(out) as z:
            assert "index.html" in z.namelist()
            with z.open("index.html") as f:
                content = f.read().decode("utf-8")
        # Loader must be present in the SCORM bundle too.
        assert 'id="scormify-loader"' in content
        assert "Carregando curso" in content
