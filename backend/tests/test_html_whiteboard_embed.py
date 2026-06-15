"""Regression: HTML exporters must embed Whiteboard assets locally.

Both exporters (traditional `html_exporter.generate_standalone_html` and
single-page `single_page_exporter.generate_single_page_html`) must resolve
`/api/whiteboard/file/wb_*.{mp4,png}` URLs to inlined base64 data URIs so
the resulting standalone HTML works offline / outside the platform.
"""
import asyncio
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from services.html_exporter import generate_standalone_html  # noqa: E402
from services.single_page_exporter import generate_single_page_html  # noqa: E402


WB_DIR = BACKEND_ROOT / "storage" / "whiteboard"


def _pick_existing_files():
    mp4 = next((p for p in WB_DIR.glob("wb_*.mp4")), None)
    png = next((p for p in WB_DIR.glob("wb_*.png")), None)
    return mp4, png


def _make_project_with_wb(mp4_name, png_name):
    slides = []
    if mp4_name:
        slides.append({
            "id": "sl-mp4",
            "title": "WB MP4",
            "backgroundColor": "#fff",
            "elements": [{
                "id": "el-mp4", "type": "video",
                "src": f"/api/whiteboard/file/{mp4_name}",
                "x": 100, "y": 100, "width": 800, "height": 450,
                "isWhiteboard": True,
            }],
        })
    if png_name:
        slides.append({
            "id": "sl-apng",
            "title": "WB APNG",
            "backgroundColor": "#fff",
            "elements": [{
                "id": "el-apng", "type": "image",
                "src": f"/api/whiteboard/file/{png_name}",
                "x": 100, "y": 100, "width": 800, "height": 450,
                "isWhiteboard": True, "isAnimatedPng": True,
            }],
        })
    return {
        "id": "wb_html_test",
        "name": "WB HTML Test",
        "course": {
            "metadata": {"title": "WB HTML", "description": "t"},
            "slides": slides,
        },
    }


def test_traditional_html_embeds_whiteboard():
    mp4_file, png_file = _pick_existing_files()
    assert mp4_file or png_file, "Need at least one whiteboard file in storage"
    project = _make_project_with_wb(
        mp4_file.name if mp4_file else None,
        png_file.name if png_file else None,
    )
    h = asyncio.run(generate_standalone_html(project, "/tmp", "", backend_url=""))
    assert "/api/whiteboard/file/" not in h, "raw whiteboard URL still present"
    if mp4_file:
        assert "data:video/mp4;base64" in h, "MP4 data URI missing"
    if png_file:
        assert "data:image/png;base64" in h, "PNG data URI missing"


def test_single_page_html_embeds_whiteboard():
    mp4_file, png_file = _pick_existing_files()
    assert mp4_file or png_file, "Need at least one whiteboard file in storage"
    project = _make_project_with_wb(
        mp4_file.name if mp4_file else None,
        png_file.name if png_file else None,
    )
    h = generate_single_page_html(project, "/tmp", "")
    assert "/api/whiteboard/file/" not in h, "raw whiteboard URL still present"
    if mp4_file:
        assert "data:video/mp4;base64" in h, "MP4 data URI missing"
    if png_file:
        assert "data:image/png;base64" in h, "PNG data URI missing"
