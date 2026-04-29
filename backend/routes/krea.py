"""Krea AI image generation routes for Scormify.

Endpoints:
  GET  /api/krea/status                 → is Krea configured?
  GET  /api/krea/models                 → list of curated image models
  POST /api/krea/generate               → submit a new generation (returns job_id)
  GET  /api/krea/jobs/{job_id}          → poll job status + result URLs
  POST /api/krea/jobs/{job_id}/save     → download a generated image into the
                                           project's assets folder (for use
                                           as slide background / image element).
"""
from __future__ import annotations

import os
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx
from fastapi import APIRouter, HTTPException, Request, Depends

from routes.deps import db, PROJECTS_DIR
from routes.auth import require_auth
from routes.projects_common import load_authorized_project
from services import krea_ai

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/krea/status")
async def krea_status(user: dict = Depends(require_auth)):
    """Is Krea configured? Used by the Editor to decide whether to show
    Krea as a provider option."""
    return {
        "configured": krea_ai.is_configured(),
        "models": len(krea_ai.KREA_IMAGE_MODELS),
    }


@router.get("/krea/models")
async def krea_list_models(user: dict = Depends(require_auth)):
    """Public-to-authenticated list of curated image models with metadata."""
    if not krea_ai.is_configured():
        raise HTTPException(503, "Krea AI is not configured. Ask the admin to set KREA_API_KEY.")
    return {"models": krea_ai.KREA_IMAGE_MODELS}


@router.post("/krea/generate")
async def krea_generate(request: Request, user: dict = Depends(require_auth)):
    """Submit a new Krea image generation job.

    Body:
      - modelId: required, one of the IDs in /api/krea/models
      - prompt: required, string
      - width, height: optional (defaults per model)
      - steps: optional override
      - negativePrompt: optional
      - projectId: optional (for usage tracking)
    """
    if not krea_ai.is_configured():
        raise HTTPException(503, "Krea AI is not configured")

    body = await request.json()
    model_id = (body.get("modelId") or "").strip()
    prompt = (body.get("prompt") or "").strip()
    if not prompt:
        raise HTTPException(400, "prompt is required")
    if not model_id:
        raise HTTPException(400, "modelId is required")
    if not krea_ai.get_model_meta(model_id):
        raise HTTPException(400, f"Unknown modelId: {model_id}")

    try:
        job = await krea_ai.submit_generation(
            model_id=model_id,
            prompt=prompt,
            width=int(body.get("width") or 1024),
            height=int(body.get("height") or 576),
            steps=body.get("steps"),
            negative_prompt=body.get("negativePrompt"),
        )
    except httpx.HTTPStatusError as e:
        logger.error(f"Krea API returned {e.response.status_code}: {e.response.text[:300]}")
        raise HTTPException(e.response.status_code, f"Krea API error: {e.response.text[:200]}")
    except Exception as e:
        logger.error(f"Krea submit failed: {e}")
        raise HTTPException(500, str(e))

    # Track in MongoDB for usage / billing visibility
    await db.krea_generations.insert_one({
        "job_id": job["job_id"],
        "modelId": model_id,
        "prompt": prompt,
        "projectId": body.get("projectId"),
        "userId": user.get("user_id") or user.get("id"),
        "companyId": user.get("companyId"),
        "status": job.get("status", "scheduled"),
        "createdAt": datetime.now(timezone.utc).isoformat(),
    })
    return job


@router.get("/krea/jobs/{job_id}")
async def krea_poll(job_id: str, user: dict = Depends(require_auth)):
    """Poll a Krea job. Frontend calls this every 2-3s until status='completed'."""
    if not krea_ai.is_configured():
        raise HTTPException(503, "Krea AI is not configured")
    try:
        data = await krea_ai.get_job(job_id)
    except httpx.HTTPStatusError as e:
        raise HTTPException(e.response.status_code, e.response.text[:200])
    # Update our tracking doc
    await db.krea_generations.update_one(
        {"job_id": job_id},
        {"$set": {
            "status": data.get("status"),
            "completedAt": data.get("completed_at"),
            "resultUrls": (data.get("result") or {}).get("urls", []),
        }},
    )
    return data


@router.post("/krea/jobs/{job_id}/save")
async def krea_save_to_project(job_id: str, request: Request, user: dict = Depends(require_auth)):
    """Download a generated image and save it into the project's assets folder.

    Body: { projectId: str, urlIndex?: int = 0 }
    Returns: { url: "/api/projects/{pid}/assets/{filename}", assetId, filename }
    """
    if not krea_ai.is_configured():
        raise HTTPException(503, "Krea AI is not configured")
    body = await request.json()
    project_id = body.get("projectId")
    if not project_id:
        raise HTTPException(400, "projectId is required")
    # Authorize (raises 404/403 if user can't access)
    await load_authorized_project(project_id, user)
    # Fetch job
    data = await krea_ai.get_job(job_id)
    if data.get("status") != "completed":
        raise HTTPException(400, f"Job not completed yet (status={data.get('status')})")
    urls = (data.get("result") or {}).get("urls") or []
    if not urls:
        raise HTTPException(400, "No images in the completed job")
    idx = int(body.get("urlIndex") or 0)
    if idx < 0 or idx >= len(urls):
        raise HTTPException(400, f"urlIndex out of range (job has {len(urls)} images)")
    image_bytes = await krea_ai.download_image_bytes(urls[idx])
    # Save to assets folder
    assets_dir = Path(PROJECTS_DIR) / project_id / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    asset_id = str(uuid.uuid4())
    filename = f"{asset_id}.png"
    (assets_dir / filename).write_bytes(image_bytes)
    # Compute public URL (matches existing asset URL pattern)
    backend_url = os.environ.get("BASE_URL", "").rstrip("/")
    public_url = f"{backend_url}/api/projects/{project_id}/assets/{filename}" if backend_url else f"/api/projects/{project_id}/assets/{filename}"
    return {
        "url": public_url,
        "assetId": asset_id,
        "filename": filename,
        "jobId": job_id,
    }
