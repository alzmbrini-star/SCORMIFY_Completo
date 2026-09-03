"""Contract tests for the Kling 3.0 integration."""
from __future__ import annotations

import pytest

from services import kling_ai
from routes.kling import _public_job_error, _status_summary


@pytest.mark.asyncio
async def test_text_to_video_uses_current_kling_30_contract(monkeypatch):
    captured = {}

    async def fake_post(path, payload):
        captured["path"] = path
        captured["payload"] = payload
        return {"code": 0, "data": {"id": "task-1", "status": "submitted"}}

    monkeypatch.setattr(kling_ai, "_post", fake_post)
    result = await kling_ai.submit_text_video(
        "Uma animação educativa sobre segurança",
        resolution="1080p",
        aspect_ratio="16:9",
        duration=10,
        audio="native",
        multi_shot=True,
        external_task_id="scormify-scene-1",
    )

    assert result["data"]["id"] == "task-1"
    assert captured["path"] == "/text-to-video/kling-3.0"
    assert captured["payload"]["prompt"].startswith("Uma animação")
    assert captured["payload"]["settings"] == {
        "resolution": "1080p",
        "duration": 10,
        "audio": "native",
        "multi_shot": True,
        "aspect_ratio": "16:9",
    }
    assert captured["payload"]["options"]["watermark_info"] == {"enabled": False}


@pytest.mark.asyncio
async def test_image_to_video_builds_contents_collection(monkeypatch):
    captured = {}

    async def fake_post(path, payload):
        captured["path"] = path
        captured["payload"] = payload
        return {"code": 0, "data": {"id": "task-2", "status": "submitted"}}

    monkeypatch.setattr(kling_ai, "_post", fake_post)
    await kling_ai.submit_image_video(
        "Professor aponta para um diagrama",
        "https://cdn.example.com/first.png",
        last_frame_url="https://cdn.example.com/last.png",
        duration=8,
    )

    assert captured["path"] == "/image-to-video/kling-3.0"
    assert captured["payload"]["contents"] == [
        {"type": "prompt", "text": "Professor aponta para um diagrama"},
        {"type": "first_frame", "url": "https://cdn.example.com/first.png"},
        {"type": "last_frame", "url": "https://cdn.example.com/last.png"},
    ]


@pytest.mark.asyncio
async def test_submit_generation_drops_text_aspect_ratio_for_image_mode(monkeypatch):
    captured = {}

    async def fake_image(prompt, first_frame_url, **kwargs):
        captured.update(kwargs)
        return {"data": {"id": "task-image"}}

    monkeypatch.setattr(kling_ai, "submit_image_video", fake_image)
    await kling_ai.submit_generation(
        prompt="Cena",
        first_frame_url="https://example.com/frame.png",
        aspect_ratio="16:9",
        duration=5,
    )
    assert "aspect_ratio" not in captured


def test_settings_are_bounded_to_supported_values():
    assert kling_ai._settings(
        resolution="invalid",
        aspect_ratio="21:9",
        duration=99,
        audio="voiceover",
    ) == {
        "resolution": "720p",
        "duration": 15,
        "audio": "off",
        "multi_shot": False,
        "aspect_ratio": "16:9",
    }


def test_video_output_selects_video_result():
    task = {
        "outputs": [
            {"type": "audio", "mp3_url": "https://example.com/a.mp3"},
            {"type": "video", "url": "https://example.com/v.mp4", "duration": "5"},
        ]
    }
    assert kling_ai.video_output(task)["url"] == "https://example.com/v.mp4"


def test_kling_response_variants_are_normalized():
    task = kling_ai.submission_task({
        "data": {"task_id": "task-new", "task_status": "completed"}
    })
    assert task["id"] == "task-new"
    assert task["status"] == "succeeded"


def test_video_output_supports_task_result_videos():
    task = {"task_result": {"videos": [{"video_url": "https://example.com/new.mp4"}]}}
    assert kling_ai.video_output(task)["url"] == "https://example.com/new.mp4"


def test_project_status_does_not_report_success_when_one_scene_failed():
    summary = _status_summary([
        {"status": "completed"},
        {"status": "failed"},
    ])
    assert summary == {
        "status": "completed_with_errors",
        "total": 2,
        "completed": 1,
        "failed": 1,
    }


def test_asyncio_internal_error_is_not_exposed_to_author():
    internal = RuntimeError(
        "Task pending got Future pending attached to a different loop at /app/backend/routes/kling.py"
    )
    message = _public_job_error(internal)
    assert "different loop" not in message
    assert "/app/backend" not in message
    assert "Tentar novamente" in message
