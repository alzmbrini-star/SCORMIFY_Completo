"""Kling AI video generation client.

Uses the current Kling API 2.0 contract:
  - one API key sent as ``Authorization: Bearer ...``
  - asynchronous text-to-video / image-to-video tasks
  - task results queried through ``GET /tasks?task_ids=...``

Secrets never leave the backend.  Callers receive only task identifiers and
normalized status/result data.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import httpx


DEFAULT_BASE_URL = "https://api-singapore.klingai.com"
ALLOWED_RESOLUTIONS = {"720p", "1080p", "4k"}
ALLOWED_ASPECT_RATIOS = {"16:9", "9:16", "1:1"}
ALLOWED_AUDIO = {"off", "native"}


class KlingAPIError(RuntimeError):
    """Safe, structured error raised for Kling API failures."""

    def __init__(self, message: str, *, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


def _clean_secret(raw: str | None) -> str:
    value = (raw or "").strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        value = value[1:-1].strip()
    return value


def api_key() -> str:
    return _clean_secret(os.environ.get("KLING_API_KEY"))


def base_url() -> str:
    return _clean_secret(os.environ.get("KLING_API_BASE_URL")) or DEFAULT_BASE_URL


def is_configured() -> bool:
    return bool(api_key())


def _headers() -> dict[str, str]:
    key = api_key()
    if not key:
        raise KlingAPIError(
            "Kling AI não está configurado. Cadastre KLING_API_KEY no backend.",
            status_code=503,
        )
    return {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _settings(
    *,
    resolution: str = "720p",
    duration: int = 5,
    audio: str = "off",
    multi_shot: bool = False,
    aspect_ratio: str | None = None,
) -> dict[str, Any]:
    resolution = resolution if resolution in ALLOWED_RESOLUTIONS else "720p"
    audio = audio if audio in ALLOWED_AUDIO else "off"
    duration = max(3, min(15, int(duration or 5)))
    result: dict[str, Any] = {
        "resolution": resolution,
        "duration": duration,
        "audio": audio,
        "multi_shot": bool(multi_shot),
    }
    if aspect_ratio is not None:
        result["aspect_ratio"] = (
            aspect_ratio if aspect_ratio in ALLOWED_ASPECT_RATIOS else "16:9"
        )
    return result


def _options(external_task_id: str | None = None) -> dict[str, Any]:
    options: dict[str, Any] = {"watermark_info": {"enabled": False}}
    if external_task_id:
        options["external_task_id"] = external_task_id[:128]
    return options


async def _post(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(75.0, connect=15.0), follow_redirects=True
        ) as client:
            response = await client.post(
                f"{base_url().rstrip('/')}{path}", headers=_headers(), json=payload
            )
    except httpx.RequestError as exc:
        raise KlingAPIError(f"Falha de conexão com o Kling AI: {exc}") from exc

    if response.status_code >= 400:
        detail = response.text[:400]
        raise KlingAPIError(
            f"Kling AI retornou HTTP {response.status_code}: {detail}",
            status_code=response.status_code if response.status_code < 500 else 502,
        )
    try:
        data = response.json()
    except ValueError as exc:
        raise KlingAPIError("Kling AI retornou uma resposta inválida.") from exc
    if data.get("code") not in (None, 0):
        raise KlingAPIError(
            f"Kling AI recusou a solicitação: {str(data.get('message') or data.get('code'))[:300]}"
        )
    return data


async def submit_text_video(
    prompt: str,
    *,
    resolution: str = "720p",
    aspect_ratio: str = "16:9",
    duration: int = 5,
    audio: str = "off",
    multi_shot: bool = False,
    external_task_id: str | None = None,
) -> dict[str, Any]:
    prompt = (prompt or "").strip()
    if not prompt:
        raise KlingAPIError("O prompt do vídeo Kling é obrigatório.", status_code=400)
    payload = {
        "prompt": prompt[:3072],
        "settings": _settings(
            resolution=resolution,
            aspect_ratio=aspect_ratio,
            duration=duration,
            audio=audio,
            multi_shot=multi_shot,
        ),
        "options": _options(external_task_id),
    }
    return await _post("/text-to-video/kling-3.0", payload)


async def submit_image_video(
    prompt: str,
    first_frame_url: str,
    *,
    last_frame_url: str | None = None,
    resolution: str = "720p",
    duration: int = 5,
    audio: str = "off",
    multi_shot: bool = False,
    external_task_id: str | None = None,
) -> dict[str, Any]:
    prompt = (prompt or "").strip()
    first_frame_url = (first_frame_url or "").strip()
    if not prompt or not first_frame_url:
        raise KlingAPIError(
            "Prompt e imagem inicial são obrigatórios para image-to-video.",
            status_code=400,
        )
    contents = [
        {"type": "prompt", "text": prompt[:3072]},
        {"type": "first_frame", "url": first_frame_url},
    ]
    if last_frame_url:
        contents.append({"type": "last_frame", "url": last_frame_url.strip()})
    payload = {
        "contents": contents,
        "settings": _settings(
            resolution=resolution,
            duration=duration,
            audio=audio,
            multi_shot=multi_shot,
        ),
        "options": _options(external_task_id),
    }
    return await _post("/image-to-video/kling-3.0", payload)


async def submit_generation(**kwargs: Any) -> dict[str, Any]:
    first_frame_url = (kwargs.pop("first_frame_url", None) or "").strip()
    if first_frame_url:
        # Image-to-video keeps the source image's aspect ratio; the current
        # Kling 3.0 endpoint does not accept the text-to-video aspect_ratio.
        kwargs.pop("aspect_ratio", None)
        return await submit_image_video(
            first_frame_url=first_frame_url,
            last_frame_url=kwargs.pop("last_frame_url", None),
            **kwargs,
        )
    kwargs.pop("last_frame_url", None)
    return await submit_text_video(**kwargs)


async def get_task(task_id: str) -> dict[str, Any]:
    if not task_id:
        raise KlingAPIError("task_id é obrigatório.", status_code=400)
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(45.0, connect=15.0), follow_redirects=True
        ) as client:
            response = await client.get(
                f"{base_url().rstrip('/')}/tasks",
                headers=_headers(),
                params={"task_ids": task_id},
            )
    except httpx.RequestError as exc:
        raise KlingAPIError(f"Falha ao consultar o Kling AI: {exc}") from exc
    if response.status_code >= 400:
        raise KlingAPIError(
            f"Kling AI retornou HTTP {response.status_code}: {response.text[:400]}",
            status_code=response.status_code if response.status_code < 500 else 502,
        )
    data = response.json()
    if data.get("code") not in (None, 0):
        raise KlingAPIError(
            f"Kling AI recusou a consulta: {str(data.get('message') or data.get('code'))[:300]}"
        )
    tasks = data.get("data") or []
    if isinstance(tasks, dict):
        tasks = tasks.get("result") or [tasks]
    if not tasks:
        raise KlingAPIError("Tarefa Kling não encontrada.", status_code=404)
    return tasks[0]


def video_output(task: dict[str, Any]) -> dict[str, Any] | None:
    for output in task.get("outputs") or []:
        if output.get("type") == "video" and output.get("url"):
            return output
    return None


async def download_video(url: str, destination: str | Path) -> None:
    """Stream the temporary Kling result to disk before its 30-day expiry."""
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    total = 0
    max_bytes = int(os.environ.get("KLING_MAX_VIDEO_BYTES", 180 * 1024 * 1024))
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(300.0, connect=20.0), follow_redirects=True
        ) as client:
            async with client.stream("GET", url) as response:
                response.raise_for_status()
                with destination.open("wb") as handle:
                    async for chunk in response.aiter_bytes(1024 * 1024):
                        total += len(chunk)
                        if total > max_bytes:
                            raise KlingAPIError(
                                "O vídeo Kling excedeu o limite de armazenamento configurado."
                            )
                        handle.write(chunk)
    except Exception:
        destination.unlink(missing_ok=True)
        raise
