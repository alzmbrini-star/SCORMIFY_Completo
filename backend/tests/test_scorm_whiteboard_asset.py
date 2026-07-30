"""Regression test for SCORM export of Whiteboard (Hand Writer) assets.

Bug: slides containing a Whiteboard video element (`src` =
`/api/whiteboard/file/wb_*.mp4`) were exported with a broken/red screen
because the SCORM exporter did not copy the rendered MP4/APNG into the
package, and the relative `/api/whiteboard/...` URL doesn't resolve when
the SCORM is opened offline.

This test ensures both MP4 (type=video) and APNG (type=image,
isAnimatedPng=true) whiteboard outputs are copied into `assets/` and the
element `src` is rewritten to the local path.
"""
import os
import json
import shutil
import zipfile
import tempfile
import asyncio
from pathlib import Path
from datetime import datetime

import pytest

# Ensure backend root is on the path so `services` and `models` resolve
import sys
BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from services.scorm_exporter import export_scorm_package
from models import Project, Course, CourseMetadata, Slide  # type: ignore


WB_DIR = BACKEND_ROOT / "storage" / "whiteboard"


def _pick_existing_files():
    """Return one mp4 and (optionally) one png from the whiteboard dir."""
    mp4 = next((p for p in WB_DIR.glob("wb_*.mp4")), None)
    png = next((p for p in WB_DIR.glob("wb_*.png")), None)
    return mp4, png


@pytest.mark.asyncio
async def test_scorm_export_embeds_whiteboard_video_and_apng(tmp_path):
    mp4_file, png_file = _pick_existing_files()
    assert mp4_file is not None, "Need at least one wb_*.mp4 in storage/whiteboard to run this test"

    # Build a minimal project with one slide referencing the whiteboard MP4
    # and (when available) a second slide with an APNG image element.
    elements_slide_1 = [{
        "id": "el-wb-mp4",
        "type": "video",
        "src": f"/api/whiteboard/file/{mp4_file.name}",
        "x": 100, "y": 100, "width": 800, "height": 450,
        "isWhiteboard": True,
        "autoplay": True,
    }]
    slides = [{
        "id": "slide-1",
        "title": "Whiteboard MP4",
        "videoUrl": f"/api/whiteboard/file/{mp4_file.name}",
        "elements": elements_slide_1,
        "backgroundColor": "#d23a1f",
    }]
    if png_file is not None:
        slides.append({
            "id": "slide-2",
            "title": "Whiteboard APNG",
            "elements": [{
                "id": "el-wb-apng",
                "type": "image",
                "src": f"/api/whiteboard/file/{png_file.name}",
                "x": 100, "y": 100, "width": 800, "height": 450,
                "isWhiteboard": True,
                "isAnimatedPng": True,
            }],
            "backgroundColor": "#ffffff",
        })

    project = Project(
        id=f"test_wb_{datetime.utcnow().timestamp():.0f}",
        userId="test-user",
        name="WB Export Test",
        course=Course(
            metadata=CourseMetadata(title="WB Export Test", description="t"),
            slides=[Slide(**s) for s in slides],
        ),
    )

    # Export to tmp dir. We point storage_dir at a clean tmp location so
    # the exporter does NOT pre-copy unrelated project assets — we only
    # want to test the whiteboard rewrite path.
    storage_dir = tmp_path / "storage"
    storage_dir.mkdir()
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    zip_path = export_scorm_package(project, str(storage_dir), str(out_dir))

    assert zip_path and Path(zip_path).exists(), "SCORM zip not produced"

    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        # 1. Whiteboard MP4 was copied into assets/
        assert f"assets/{mp4_file.name}" in names, (
            f"Whiteboard MP4 not embedded. Got: {[n for n in names if 'wb_' in n]}"
        )
        # 2. course.json src must be rewritten to the local relative path
        with zf.open("course.json") as f:
            course_json = json.load(f)
        slide_0 = course_json["slides"][0]
        wb_el = slide_0["elements"][0]
        assert wb_el["src"] == f"assets/{mp4_file.name}", (
            f"Element src not rewritten: {wb_el['src']}"
        )
        assert slide_0["videoUrl"] == f"assets/{mp4_file.name}", (
            f"Slide-level Whiteboard URL not rewritten: {slide_0['videoUrl']}"
        )
        # 3. APNG flow (when available)
        if png_file is not None:
            assert f"assets/{png_file.name}" in names, "Whiteboard APNG not embedded"
            slide_1 = course_json["slides"][1]
            apng_el = slide_1["elements"][0]
            assert apng_el["src"] == f"assets/{png_file.name}", (
                f"APNG src not rewritten: {apng_el['src']}"
            )


if __name__ == "__main__":
    test_scorm_export_embeds_whiteboard_video_and_apng(Path(tempfile.mkdtemp()))
    print("OK")
