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
    monkeypatch.setattr(
        whiteboard_store, "validate_whiteboard_file", lambda _path: True
    )

    assert await whiteboard_store.persist_whiteboard_file(
        object(), source.name, source
    )
    assert captured["size"] == 13 * 1024 * 1024
    assert captured["metadata"]["kind"] == "whiteboard"


@pytest.mark.asyncio
async def test_restores_gridfs_whiteboard_before_export(tmp_path, monkeypatch):
    payload = b"durable-whiteboard-content" * 100
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
async def test_rejects_truncated_apng_before_persisting(tmp_path, monkeypatch):
    source = tmp_path / "wb_plan_truncated.png"
    source.write_bytes(b"not-a-real-apng" * 200)

    def bucket_must_not_be_opened(_db):
        raise AssertionError("corrupt media must be rejected before GridFS")

    monkeypatch.setattr(whiteboard_store, "_bucket", bucket_must_not_be_opened)

    assert not await whiteboard_store.persist_whiteboard_file(
        object(), source.name, source
    )


@pytest.mark.asyncio
async def test_does_not_publish_corrupt_apng_restored_from_gridfs(
    tmp_path,
    monkeypatch,
):
    corrupt_payload = b"truncated-apng" * 200
    version = SimpleNamespace(_id="corrupt-gridfs-file")

    class FakeCursor:
        def sort(self, *_args):
            return self

        async def to_list(self, length):
            return [version]

    class FakeDownload:
        def __init__(self):
            self._stream = io.BytesIO(corrupt_payload)

        async def read(self, size):
            return self._stream.read(size)

    class FakeBucket:
        def find(self, _query):
            return FakeCursor()

        async def open_download_stream(self, file_id):
            assert file_id == version._id
            return FakeDownload()

    monkeypatch.setattr(whiteboard_store, "_bucket", lambda _db: FakeBucket())

    destination = tmp_path / "whiteboard" / "wb_plan_corrupt.png"
    assert not await whiteboard_store.restore_whiteboard_file(
        object(), destination.name, destination
    )
    assert not destination.exists()


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


def test_omits_only_missing_whiteboard_from_export_copy():
    project = _project_doc("wb_missing_old.mp4")
    slide = project["course"]["slides"][0]
    slide["elements"].append({
        "id": "regular-image",
        "type": "image",
        "src": "/api/assets/regular.png",
    })

    status = whiteboard_store.omit_missing_whiteboards_from_export(
        project, ["wb_missing_old.mp4"]
    )

    assert status["missing"] == ["wb_missing_old.mp4"]
    assert status["removedElements"] == 1
    assert slide["videoUrl"] is None
    assert [element["id"] for element in slide["elements"]] == ["regular-image"]


@pytest.mark.asyncio
async def test_prepare_export_omits_irrecoverable_whiteboard(tmp_path, monkeypatch):
    project = _project_doc("wb_gone_after_redeploy.mp4")

    async def cannot_restore(_db, _name, _destination):
        return False

    monkeypatch.setattr(
        whiteboard_store, "restore_whiteboard_file", cannot_restore
    )

    status = await whiteboard_store.prepare_whiteboards_for_export(
        project, object(), tmp_path
    )

    assert status["restored"] == []
    assert status["missing"] == ["wb_gone_after_redeploy.mp4"]
    assert project["course"]["slides"][0]["elements"] == []


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
