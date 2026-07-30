"""Regression coverage for durable Whiteboard media in offline exports."""
from __future__ import annotations

import io
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from models import Course, CourseMetadata, Project, Slide  # noqa: E402
from services.scorm_exporter import export_scorm_package  # noqa: E402
from services.scorm_single_page_exporter import (  # noqa: E402
    export_single_page_scorm_package,
)
from services import whiteboard_store  # noqa: E402


def _project_doc(*names: str) -> dict:
    slides = [
        {
            "id": "slide-1",
            "title": "Whiteboard",
            "videoUrl": (
                f"https://api.example.test/api/whiteboard/file/{names[0]}"
                if names
                else ""
            ),
            "elements": [
                {
                    "id": f"element-{index}",
                    "type": "video",
                    "src": f"/api/whiteboard/file/{name}?v=1",
                    "x": 10,
                    "y": 10,
                    "width": 640,
                    "height": 360,
                }
                for index, name in enumerate(names)
            ],
        }
    ]
    return {
        "id": "whiteboard-persistence-test",
        "userId": "test-user",
        "name": "Whiteboard persistence",
        "course": {
            "metadata": {"title": "Whiteboard persistence", "description": "test"},
            "slides": slides,
        },
    }


def test_extracts_unique_whiteboards_from_slide_and_elements():
    project = _project_doc("wb_alpha.mp4", "wb_plan_beta.png")
    assert whiteboard_store.extract_whiteboard_names(project) == [
        "wb_alpha.mp4",
        "wb_plan_beta.png",
    ]


@pytest.mark.asyncio
async def test_persists_whiteboard_larger_than_legacy_12mb_limit(
    tmp_path,
    monkeypatch,
):
    source = tmp_path / "wb_large.png"
    source.write_bytes(b"x" * (13 * 1024 * 1024))
    captured = {"size": 0}

    class FakeCursor:
        def sort(self, *_args):
            return self

        async def to_list(self, length):
            return []

    class FakeBucket:
        def find(self, _query):
            return FakeCursor()

        async def upload_from_stream(self, _name, stream, metadata=None):
            while True:
                chunk = stream.read(1024 * 1024)
                if not chunk:
                    break
                captured["size"] += len(chunk)
            captured["metadata"] = metadata

        async def delete(self, _file_id):
            raise AssertionError("There are no old versions to delete")

    monkeypatch.setattr(whiteboard_store, "_bucket", lambda _db: FakeBucket())

    assert await whiteboard_store.persist_whiteboard_file(
        object(), source.name, source
    )
    assert captured["size"] == 13 * 1024 * 1024
    assert captured["metadata"]["kind"] == "whiteboard"


@pytest.mark.asyncio
async def test_restores_gridfs_whiteboard_before_export(tmp_path, monkeypatch):
    payload = b"durable-whiteboard-content"
    version = SimpleNamespace(_id="gridfs-file-id")

    class FakeCursor:
        def sort(self, *_args):
            return self

        async def to_list(self, length):
            return [version]

    class FakeDownload:
        def __init__(self):
            self._stream = io.BytesIO(payload)

        async def read(self, size):
            return self._stream.read(size)

    class FakeBucket:
        def find(self, _query):
            return FakeCursor()

        async def open_download_stream(self, file_id):
            assert file_id == version._id
            return FakeDownload()

    monkeypatch.setattr(whiteboard_store, "_bucket", lambda _db: FakeBucket())

    project = _project_doc("wb_restored.mp4")
    restored = await whiteboard_store.ensure_whiteboards_for_export(
        project, object(), tmp_path
    )
    destination = tmp_path / "whiteboard" / "wb_restored.mp4"
    assert restored == ["wb_restored.mp4"]
    assert destination.read_bytes() == payload


@pytest.mark.asyncio
async def test_missing_whiteboard_stops_export_with_actionable_message(tmp_path):
    project = _project_doc("wb_missing_forever.mp4")
    with pytest.raises(
        whiteboard_store.WhiteboardAssetUnavailableError,
        match="Gere novamente",
    ):
        await whiteboard_store.ensure_whiteboards_for_export(
            project, None, tmp_path
        )


def test_traditional_scorm_never_emits_broken_whiteboard_reference(tmp_path):
    project_doc = _project_doc("wb_missing_traditional.mp4")
    project = Project(
        id=project_doc["id"],
        userId=project_doc["userId"],
        name=project_doc["name"],
        course=Course(
            metadata=CourseMetadata(**project_doc["course"]["metadata"]),
            slides=[Slide(**slide) for slide in project_doc["course"]["slides"]],
        ),
    )
    output_dir = tmp_path / "out"
    output_dir.mkdir()

    with pytest.raises(
        whiteboard_store.WhiteboardAssetUnavailableError,
        match="wb_missing_traditional.mp4",
    ):
        export_scorm_package(project, str(tmp_path), str(output_dir))


def test_single_page_scorm_preflight_rejects_missing_whiteboard(tmp_path):
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    with pytest.raises(
        whiteboard_store.WhiteboardAssetUnavailableError,
        match="wb_missing_single_page.mp4",
    ):
        export_single_page_scorm_package(
            _project_doc("wb_missing_single_page.mp4"),
            str(tmp_path),
            str(output_dir),
        )
