"""Kling AI routes and project-video persistence."""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request

from routes.auth import require_auth
from routes.deps import PROJECTS_DIR, db
from routes.projects_common import load_authorized_project
from services import kling_ai
from services.asset_store import store_asset_async

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Kling AI"])


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_error(exc: Exception) -> HTTPException:
    if isinstance(exc, kling_ai.KlingAPIError):
        return HTTPException(exc.status_code, str(exc))
    logger.exception("Unexpected Kling integration error")
    return HTTPException(500, "Falha inesperada na integração com Kling AI.")


def _absolute_public_url(value: str | None) -> str | None:
    value = (value or "").strip()
    if not value:
        return None
    if value.startswith("/"):
        public_base = (os.environ.get("BASE_URL") or "").strip().rstrip("/")
        return f"{public_base}{value}" if public_base else value
    return value


def _status_summary(results: list[dict]) -> dict:
    completed = sum(1 for row in results if row.get("status") == "completed")
    failed = sum(1 for row in results if row.get("status") == "failed")
    terminal = bool(results) and all(
        row.get("status") in ("completed", "failed") for row in results
    )
    return {
        "status": (
            "all_done" if terminal and failed == 0
            else "completed_with_errors" if terminal
            else "processing"
        ),
        "total": len(results),
        "completed": completed,
        "failed": failed,
    }


@router.get("/kling/status")
async def kling_status(user: dict = Depends(require_auth)):
    return {
        "configured": kling_ai.is_configured(),
        "model": "kling-3.0",
        "maxDuration": 15,
        "supports": ["text-to-video", "image-to-video", "native-audio"],
    }


async def _submit_pending(project_id: str, item: dict, database=None) -> dict:
    store = database if database is not None else db
    project_meta = await store.projects.find_one(
        {"id": project_id}, {"_id": 0, "companyId": 1, "userId": 1}
    ) or {}
    external_id = f"scormify-{project_id[:16]}-{item['slideId'][:16]}-{uuid.uuid4().hex[:8]}"
    response = await kling_ai.submit_generation(
        prompt=item.get("prompt") or item.get("title") or "Educational scene",
        first_frame_url=_absolute_public_url(item.get("firstFrameUrl")),
        last_frame_url=_absolute_public_url(item.get("lastFrameUrl")),
        resolution=item.get("resolution", "720p"),
        aspect_ratio=item.get("aspectRatio", "16:9"),
        duration=item.get("duration", 5),
        audio=item.get("audio", "off"),
        multi_shot=item.get("multiShot", False),
        external_task_id=external_id,
    )
    task = response.get("data") or {}
    task_id = task.get("id")
    if not task_id:
        raise kling_ai.KlingAPIError("Kling AI não retornou o identificador da tarefa.")
    await store.projects.update_one(
        {"id": project_id, "klingPending.slideId": item["slideId"]},
        {"$set": {
            "klingPending.$.taskId": task_id,
            "klingPending.$.externalTaskId": external_id,
            "klingPending.$.status": task.get("status", "submitted"),
            "klingPending.$.submittedAt": _now(),
        }},
    )
    await store.kling_generations.update_one(
        {"taskId": task_id},
        {"$set": {
            "taskId": task_id,
            "externalTaskId": external_id,
            "projectId": project_id,
            "companyId": project_meta.get("companyId"),
            "userId": project_meta.get("userId"),
            "slideId": item["slideId"],
            "prompt": item.get("prompt", ""),
            "status": task.get("status", "submitted"),
            "createdAt": _now(),
        }},
        upsert=True,
    )
    return {"taskId": task_id, "status": task.get("status", "submitted")}


async def submit_project_pending(project_id: str, pending_list: list[dict], database=None) -> None:
    """Submit storyboard jobs in a short-lived background thread.

    Only submission happens here. Long processing is followed by the durable
    polling endpoint, so Render restarts do not lose Kling task identifiers.
    """
    store = database if database is not None else db
    for item in pending_list:
        try:
            await _submit_pending(project_id, item, database=store)
        except Exception as exc:
            logger.error("Kling submit failed for %s: %s", item.get("slideId"), exc)
            await store.projects.update_one(
                {"id": project_id, "klingPending.slideId": item.get("slideId")},
                {"$set": {
                    "klingPending.$.status": "failed",
                    "klingPending.$.error": str(exc)[:300],
                    "klingPending.$.updatedAt": _now(),
                }},
            )


@router.post("/kling/generate")
async def kling_generate(request: Request, user: dict = Depends(require_auth)):
    """Generate Kling video for a slide in an existing project."""
    if not kling_ai.is_configured():
        raise HTTPException(503, "Kling AI não está configurado. Cadastre KLING_API_KEY.")
    body = await request.json()
    project_id = (body.get("projectId") or "").strip()
    slide_id = (body.get("slideId") or "").strip()
    prompt = (body.get("prompt") or "").strip()
    if not project_id or not slide_id or not prompt:
        raise HTTPException(400, "projectId, slideId e prompt são obrigatórios.")
    project = await load_authorized_project(project_id, user)
    if not any(s.get("id") == slide_id for s in project.get("course", {}).get("slides", [])):
        raise HTTPException(404, "Slide não encontrado no projeto.")
    item = {
        "slideId": slide_id,
        "slideIndex": next(
            (i for i, s in enumerate(project.get("course", {}).get("slides", [])) if s.get("id") == slide_id),
            0,
        ),
        "title": body.get("title") or "Vídeo Kling",
        "prompt": prompt[:3072],
        "firstFrameUrl": body.get("firstFrameUrl"),
        "lastFrameUrl": body.get("lastFrameUrl"),
        "resolution": body.get("resolution", "720p"),
        "aspectRatio": body.get("aspectRatio", "16:9"),
        "duration": body.get("duration", 5),
        "audio": body.get("audio", "off"),
        "multiShot": bool(body.get("multiShot", False)),
        "status": "pending",
        "createdAt": _now(),
    }
    await db.projects.update_one(
        {"id": project_id},
        {"$pull": {"klingPending": {"slideId": slide_id}}},
    )
    await db.projects.update_one(
        {"id": project_id},
        {"$push": {"klingPending": item}, "$set": {"updatedAt": _now()}},
    )
    try:
        return await _submit_pending(project_id, item)
    except Exception as exc:
        raise _safe_error(exc)


@router.post("/kling/projects/{project_id}/retry/{slide_id}")
async def kling_retry_failed(
    project_id: str, slide_id: str, user: dict = Depends(require_auth)
):
    """Resubmit only one failed scene, preserving the other generated videos."""
    if not kling_ai.is_configured():
        raise HTTPException(503, "Kling AI não está configurado. Cadastre KLING_API_KEY.")
    project = await load_authorized_project(project_id, user)
    item = next(
        (dict(row) for row in (project.get("klingPending") or []) if row.get("slideId") == slide_id),
        None,
    )
    if not item:
        raise HTTPException(404, "Cena Kling não encontrada no projeto.")
    if item.get("status") == "completed":
        return {"status": "completed", "videoUrl": item.get("videoUrl")}
    item.pop("taskId", None)
    item.pop("externalTaskId", None)
    item.pop("error", None)
    item.pop("providerMessage", None)
    item["status"] = "pending"
    await db.projects.update_one(
        {"id": project_id, "klingPending.slideId": slide_id},
        {
            "$set": {
                "klingPending.$.status": "pending",
                "klingPending.$.updatedAt": _now(),
                "updatedAt": _now(),
            },
            "$unset": {
                "klingPending.$.taskId": "",
                "klingPending.$.externalTaskId": "",
                "klingPending.$.error": "",
                "klingPending.$.providerMessage": "",
            },
        },
    )
    try:
        return await _submit_pending(project_id, item)
    except Exception as exc:
        await db.projects.update_one(
            {"id": project_id, "klingPending.slideId": slide_id},
            {"$set": {
                "klingPending.$.status": "failed",
                "klingPending.$.error": str(exc)[:300],
                "klingPending.$.updatedAt": _now(),
            }},
        )
        raise _safe_error(exc)


async def _replace_placeholder(project_id: str, slide_id: str, public_url: str) -> None:
    project = await db.projects.find_one({"id": project_id}, {"_id": 0, "course.slides": 1})
    if not project:
        return
    slides = project.get("course", {}).get("slides", [])
    for slide_index, slide in enumerate(slides):
        if slide.get("id") != slide_id:
            continue
        for element_index, element in enumerate(slide.get("elements", [])):
            if f'data-kling-slide="{slide_id}"' not in (element.get("htmlContent") or ""):
                continue
            new_element = {
                "id": str(uuid.uuid4()),
                "type": "video",
                "src": public_url,
                "x": element.get("x", 1120),
                "y": element.get("y", 110),
                "width": element.get("width", 740),
                "height": element.get("height", 440),
                "startTime": element.get("startTime", 0),
                "duration": element.get("duration", 5),
                "autoplay": False,
                "controls": True,
                "loop": False,
                "muted": False,
                "objectFit": "cover",
                "provider": "kling",
                "animations": element.get("animations", []),
            }
            await db.projects.update_one(
                {"id": project_id},
                {"$set": {
                    f"course.slides.{slide_index}.elements.{element_index}": new_element,
                    "updatedAt": _now(),
                }},
            )
            return


async def _persist_completed(project_id: str, item: dict, task: dict) -> str:
    output = kling_ai.video_output(task)
    if not output:
        raise kling_ai.KlingAPIError("Tarefa concluída sem URL de vídeo.")
    filename = f"kling_{item['slideId'][:12]}_{uuid.uuid4().hex[:10]}.mp4"
    destination = Path(PROJECTS_DIR) / project_id / "assets" / filename
    await kling_ai.download_video(output["url"], destination)
    stored = await store_asset_async(db, project_id, filename, str(destination))
    if not stored:
        destination.unlink(missing_ok=True)
        raise kling_ai.KlingAPIError("Não foi possível salvar o vídeo Kling permanentemente.")
    public_url = f"/api/projects/{project_id}/assets/{filename}"
    await _replace_placeholder(project_id, item["slideId"], public_url)
    await db.projects.update_one(
        {"id": project_id, "klingPending.taskId": item.get("taskId")},
        {"$set": {
            "klingPending.$.status": "completed",
            "klingPending.$.videoUrl": public_url,
            "klingPending.$.providerUrl": output.get("url"),
            "klingPending.$.durationActual": output.get("duration"),
            "klingPending.$.completedAt": _now(),
            "updatedAt": _now(),
        }},
    )
    await db.kling_generations.update_one(
        {"taskId": item.get("taskId")},
        {"$set": {"status": "completed", "videoUrl": public_url, "completedAt": _now()}},
    )
    return public_url


@router.get("/kling/projects/{project_id}/status")
async def kling_project_status(project_id: str, user: dict = Depends(require_auth)):
    project = await load_authorized_project(project_id, user)
    pending = project.get("klingPending") or []
    if not pending:
        return {"status": "no_kling", "videos": [], "total": 0, "completed": 0}

    results = []
    for original in pending:
        item = dict(original)
        status = item.get("status", "pending")
        task_id = item.get("taskId")
        if not task_id and status == "pending":
            try:
                claim = await db.projects.update_one(
                    {"id": project_id, "klingPending": {"$elemMatch": {"slideId": item.get("slideId"), "status": "pending", "taskId": {"$exists": False}}}},
                    {"$set": {"klingPending.$.status": "submitting", "klingPending.$.updatedAt": _now()}},
                )
                if claim.modified_count:
                    submitted = await _submit_pending(project_id, item)
                    task_id = submitted["taskId"]
                    status = submitted["status"]
            except Exception as exc:
                logger.error("Kling retry submission failed for %s: %s", item.get("slideId"), exc)
                status = "failed"
                await db.projects.update_one(
                    {"id": project_id, "klingPending.slideId": item.get("slideId")},
                    {"$set": {"klingPending.$.status": "failed", "klingPending.$.error": str(exc)[:300]}},
                )
        if task_id and status not in ("completed", "failed", "saving"):
            try:
                task = await kling_ai.get_task(task_id)
                status = task.get("status", status)
                message = task.get("message")
                await db.projects.update_one(
                    {"id": project_id, "klingPending.taskId": task_id},
                    {"$set": {
                        "klingPending.$.status": status,
                        "klingPending.$.providerMessage": message,
                        "klingPending.$.updatedAt": _now(),
                    }},
                )
                if status == "succeeded":
                    # Claim persistence atomically to avoid duplicate downloads
                    claim = await db.projects.update_one(
                        {"id": project_id, "klingPending": {"$elemMatch": {"taskId": task_id, "status": "succeeded"}}},
                        {"$set": {"klingPending.$.status": "saving"}},
                    )
                    if claim.modified_count:
                        item["taskId"] = task_id
                        item["status"] = "saving"
                        await _persist_completed(project_id, item, task)
                        status = "completed"
                elif status == "failed":
                    await db.kling_generations.update_one(
                        {"taskId": task_id},
                        {"$set": {"status": "failed", "error": message, "updatedAt": _now()}},
                    )
            except Exception as exc:
                logger.error("Kling status/persistence failed for %s: %s", task_id, exc)
                status = "failed"
                await db.projects.update_one(
                    {"id": project_id, "klingPending.taskId": task_id},
                    {"$set": {
                        "klingPending.$.status": "failed",
                        "klingPending.$.error": str(exc)[:300],
                        "klingPending.$.updatedAt": _now(),
                    }},
                )
        results.append({
            "slideId": item.get("slideId"),
            "slideIndex": item.get("slideIndex"),
            "title": item.get("title"),
            "taskId": task_id,
            "status": status,
            "videoUrl": item.get("videoUrl"),
            "error": item.get("error"),
            "providerMessage": item.get("providerMessage"),
        })

    # Return the latest persisted state after status transitions.
    latest = await db.projects.find_one({"id": project_id}, {"_id": 0, "klingPending": 1})
    latest_by_slide = {x.get("slideId"): x for x in (latest or {}).get("klingPending", [])}
    for row in results:
        current = latest_by_slide.get(row["slideId"], {})
        row.update({
            "status": current.get("status", row["status"]),
            "videoUrl": current.get("videoUrl", row.get("videoUrl")),
            "error": current.get("error", row.get("error")),
            "providerMessage": current.get("providerMessage", row.get("providerMessage")),
        })
    return {**_status_summary(results), "videos": results}
