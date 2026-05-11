"""Tests for the Tutorial Agent audio narration import path.

When the external Tutorial Agent generates narration audio for a step,
Scormify must:
  1. Download the audio via `step.audio_url` (preferred) or the dedicated
     `/api/v1/tutorials/{id}/steps/{step_id}/audio` fallback.
  2. Persist it in GridFS so it survives K8s pod restarts.
  3. Attach it to `slide.audio[]` as a narration entry — same shape as
     ElevenLabs-generated audio so the Single Page / SCORM exporters
     auto-play it.
  4. Use the `narration` text as the `narrationScript` (so re-generating
     via ElevenLabs later starts from the same source text).
"""
import os
import asyncio
import importlib
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock

import pytest

os.environ.setdefault("TUTORIAL_AGENT_URL", "https://agent.example.com")
os.environ.setdefault("TUTORIAL_AGENT_API_KEY", "test-key")

from routes.tutorial_integration import (
    _step_to_slide,
    _audio_ext_from_content_type,
    _resolve_audio_url,
    _download_step_audio_to_assets,
)


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------

class TestAudioExtension:
    def test_mp3_default(self):
        assert _audio_ext_from_content_type("audio/mpeg") == ".mp3"

    def test_unknown_defaults_to_mp3(self):
        assert _audio_ext_from_content_type("") == ".mp3"
        assert _audio_ext_from_content_type("application/octet-stream") == ".mp3"

    def test_wav(self):
        assert _audio_ext_from_content_type("audio/wav") == ".wav"
        assert _audio_ext_from_content_type("audio/x-wav") == ".wav"

    def test_ogg(self):
        assert _audio_ext_from_content_type("audio/ogg") == ".ogg"

    def test_webm(self):
        assert _audio_ext_from_content_type("audio/webm") == ".webm"


class TestResolveAudioUrl:
    def test_absolute_http_passes_through(self):
        url = "https://cdn.example.com/foo.mp3"
        assert _resolve_audio_url(url) == url

    def test_absolute_http_insecure_passes_through(self):
        url = "http://cdn.example.com/foo.mp3"
        assert _resolve_audio_url(url) == url

    def test_relative_path_prefixed_with_agent_base(self):
        out = _resolve_audio_url("/api/v1/x.mp3")
        assert out.startswith("https://agent.example.com")
        assert out.endswith("/api/v1/x.mp3")

    def test_storage_path_goes_through_files_proxy(self):
        out = _resolve_audio_url("bucket/path/file.mp3")
        assert "/api/files/bucket/path/file.mp3" in out

    def test_empty_returns_empty(self):
        assert _resolve_audio_url("") == ""
        assert _resolve_audio_url(None) == ""


# ---------------------------------------------------------------------------
# Slide attachment
# ---------------------------------------------------------------------------

class TestStepToSlideWithAudio:
    def test_audio_attached_to_slide_audio_array(self):
        audio = {
            "id": "abc",
            "type": "narration",
            "src": "/api/projects/p/assets/audio_x.mp3",
            "filename": "audio_x.mp3",
            "duration": 0,
            "volume": 1.0,
        }
        step = {"action_type": "click", "selector": "Salvar", "narration": "Clique em Salvar para confirmar"}
        slide = _step_to_slide(step, None, 0, audio_data=audio)
        assert isinstance(slide.get("audio"), list)
        assert len(slide["audio"]) == 1
        assert slide["audio"][0]["src"].endswith("audio_x.mp3")
        assert slide["audio"][0]["type"] == "narration"

    def test_audio_omitted_when_none(self):
        step = {"action_type": "click"}
        slide = _step_to_slide(step, None, 0, audio_data=None)
        # No `audio` key at all — keeps the slide doc lean for steps with no audio
        assert "audio" not in slide

    def test_narration_script_uses_explicit_narration(self):
        """When the Agent provides an explicit `narration`, narrationScript should
        match it word-for-word (not the auto-generated description)."""
        narration = "Para gerar o relatorio, primeiro abra o menu de Relatorios"
        step = {"action_type": "click", "selector": "x", "narration": narration}
        slide = _step_to_slide(step, None, 0)
        assert slide["narrationScript"] == narration

    def test_narration_falls_back_to_description_when_blank(self):
        step = {"action_type": "click", "selector": "Confirmar", "narration": ""}
        slide = _step_to_slide(step, None, 0)
        # Falls back to the heuristic description
        assert "Confirmar" in slide["narrationScript"]


# ---------------------------------------------------------------------------
# Audio download pipeline (async, mocked)
# ---------------------------------------------------------------------------

def _audio_bytes(size: int = 5000) -> bytes:
    """A buffer large enough to pass the >200-byte sanity check."""
    return b"ID3\x03\x00\x00\x00\x00" + (b"\x00" * (size - 8))


@pytest.fixture
def patched_store_asset(tmp_path, monkeypatch):
    """Redirect PROJECTS_DIR to a tmp dir and stub store_asset_async so the
    helper runs end-to-end without touching MongoDB or real GridFS."""
    from routes import tutorial_integration as ti
    monkeypatch.setattr(ti, "PROJECTS_DIR", tmp_path)
    stub = AsyncMock(return_value=True)
    monkeypatch.setattr(ti, "store_asset_async", stub)
    return stub


def _make_async_client(*, get_responses):
    """Build a MagicMock impersonating an httpx.AsyncClient where successive
    .get() calls return the responses in order."""
    client = AsyncMock()
    client.__aenter__.return_value = client
    client.__aexit__.return_value = False
    client.get = AsyncMock(side_effect=get_responses)
    return client


def _resp(status: int, content: bytes = b"", content_type: str = "audio/mpeg"):
    r = MagicMock()
    r.status_code = status
    r.content = content
    r.headers = {"content-type": content_type}
    return r


@pytest.mark.asyncio
async def test_audio_downloaded_from_explicit_url(patched_store_asset, monkeypatch):
    """Happy path: step has a usable audio_url → we download it directly."""
    mp3 = _audio_bytes()
    client = _make_async_client(get_responses=[_resp(200, mp3)])
    monkeypatch.setattr("httpx.AsyncClient", lambda **_k: client)

    out = await _download_step_audio_to_assets(
        tutorial_id="t1",
        step_id="step-abc1234567",
        project_id="proj-1",
        audio_url_hint="https://cdn.example.com/x.mp3",
    )
    assert out is not None
    assert out["type"] == "narration"
    assert out["volume"] == 1.0
    assert out["src"].startswith("/api/projects/proj-1/assets/")
    assert out["filename"].endswith(".mp3")
    assert "tutorial_audio_step-abc12" in out["filename"]
    # And the asset was persisted to GridFS
    patched_store_asset.assert_awaited_once()


@pytest.mark.asyncio
async def test_audio_downloaded_via_fallback_endpoint(patched_store_asset, monkeypatch):
    """When audio_url is missing, we try the dedicated /audio endpoint."""
    mp3 = _audio_bytes()
    client = _make_async_client(get_responses=[_resp(200, mp3)])
    monkeypatch.setattr("httpx.AsyncClient", lambda **_k: client)

    out = await _download_step_audio_to_assets(
        tutorial_id="t1",
        step_id="step-xyz0987654",
        project_id="proj-2",
        audio_url_hint=None,
    )
    assert out is not None
    assert out["src"].endswith(".mp3")
    # Confirm we hit the fallback endpoint (path includes /steps/{id}/audio)
    called_with = client.get.call_args
    assert "/steps/step-xyz0987654/audio" in str(called_with)


@pytest.mark.asyncio
async def test_audio_returns_none_when_404(patched_store_asset, monkeypatch):
    """No audio at all → returns None gracefully (no slide.audio populated)."""
    # First call (audio_url) 404 → second call (fallback) also 404
    client = _make_async_client(get_responses=[_resp(404), _resp(404)])
    monkeypatch.setattr("httpx.AsyncClient", lambda **_k: client)

    out = await _download_step_audio_to_assets(
        tutorial_id="t",
        step_id="s1234567",
        project_id="proj-3",
        audio_url_hint="https://example.com/missing.mp3",
    )
    assert out is None
    # No persistence call when nothing was downloaded
    patched_store_asset.assert_not_awaited()


@pytest.mark.asyncio
async def test_audio_tiny_response_rejected(patched_store_asset, monkeypatch):
    """A 50-byte response is almost certainly a JSON error body — reject it."""
    client = _make_async_client(get_responses=[_resp(200, b"err" * 20)])
    monkeypatch.setattr("httpx.AsyncClient", lambda **_k: client)

    out = await _download_step_audio_to_assets(
        tutorial_id="t",
        step_id="s1234567",
        project_id="proj-4",
        audio_url_hint="https://example.com/empty.mp3",
    )
    assert out is None


@pytest.mark.asyncio
async def test_audio_base64_used_when_provided(patched_store_asset, monkeypatch):
    """When the step ships audio_base64 inline, we should use it directly
    and never make a network call."""
    import base64
    mp3 = _audio_bytes()
    b64 = base64.b64encode(mp3).decode("ascii")

    client = _make_async_client(get_responses=[])  # zero calls expected
    monkeypatch.setattr("httpx.AsyncClient", lambda **_k: client)

    out = await _download_step_audio_to_assets(
        tutorial_id="t",
        step_id="step-b64abcde12",
        project_id="proj-5",
        audio_url_hint=None,
        audio_base64=b64,
    )
    assert out is not None
    assert out["filename"].endswith(".mp3")
    # The MagicMock client.get was never invoked
    client.get.assert_not_called()


@pytest.mark.asyncio
async def test_audio_file_written_to_disk(patched_store_asset, monkeypatch, tmp_path):
    """End-to-end: the audio bytes must actually land on disk so the
    /api/projects/{pid}/assets/{filename} URL works."""
    mp3 = _audio_bytes(size=8000)
    client = _make_async_client(get_responses=[_resp(200, mp3, "audio/mpeg")])
    monkeypatch.setattr("httpx.AsyncClient", lambda **_k: client)

    out = await _download_step_audio_to_assets(
        tutorial_id="t",
        step_id="diskcheck-1",
        project_id="proj-disk",
        audio_url_hint="https://cdn.example.com/x.mp3",
    )
    assert out is not None
    on_disk = Path(out["src"].replace("/api/projects/proj-disk/assets/", ""))
    expected_path = tmp_path / "proj-disk" / "assets" / on_disk.name
    assert expected_path.exists()
    assert expected_path.read_bytes() == mp3


@pytest.mark.asyncio
async def test_wav_content_type_yields_wav_extension(patched_store_asset, monkeypatch):
    """If the Agent returns audio/wav, the stored asset must have .wav suffix
    so HTML5 audio tag can pick the right decoder."""
    payload = b"RIFF" + b"\x00" * 5000
    client = _make_async_client(get_responses=[_resp(200, payload, "audio/wav")])
    monkeypatch.setattr("httpx.AsyncClient", lambda **_k: client)

    out = await _download_step_audio_to_assets(
        tutorial_id="t",
        step_id="wavstep-1",
        project_id="proj-wav",
        audio_url_hint="https://cdn.example.com/x.wav",
    )
    assert out is not None
    assert out["filename"].endswith(".wav")
