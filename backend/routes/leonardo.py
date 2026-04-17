"""Leonardo AI image generation routes for Scormify."""

import os
import uuid
import base64
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request, Depends
from routes.deps import db, PROJECTS_DIR, STORAGE_DIR
from routes.auth import require_auth

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/leonardo/generate")
async def leonardo_generate(request: Request, user: dict = Depends(require_auth)):
    """Start a Leonardo AI image generation. Returns generationId for polling."""
    from services.leonardo_ai import generate_image

    body = await request.json()
    prompt = body.get("prompt", "").strip()
    if not prompt:
        raise HTTPException(400, "Prompt is required")

    width = body.get("width", 1024)
    height = body.get("height", 576)
    num_images = min(body.get("numImages", 1), 4)
    style = body.get("style")
    project_id = body.get("projectId")

    try:
        result = await generate_image(
            prompt=prompt,
            width=width,
            height=height,
            num_images=num_images,
            style=style,
        )
        # Store generation request for tracking
        await db.leonardo_generations.insert_one({
            "generationId": result["generationId"],
            "prompt": prompt,
            "projectId": project_id,
            "userId": user.get("user_id"),
            "width": width,
            "height": height,
            "status": "pending",
            "createdAt": datetime.now(timezone.utc).isoformat(),
        })
        return result
    except Exception as e:
        logger.error(f"Leonardo generation failed: {e}")
        raise HTTPException(500, f"Erro ao gerar imagem: {str(e)[:200]}")


@router.get("/leonardo/status/{generation_id}")
async def leonardo_status(generation_id: str, user: dict = Depends(require_auth)):
    """Poll for generation status and get image URLs."""
    from services.leonardo_ai import poll_generation

    try:
        result = await poll_generation(generation_id, max_wait=10)
        # Update tracking record
        if result["status"] in ("complete", "failed"):
            await db.leonardo_generations.update_one(
                {"generationId": generation_id},
                {"$set": {"status": result["status"], "images": result.get("images", []), "updatedAt": datetime.now(timezone.utc).isoformat()}}
            )
        return result
    except Exception as e:
        logger.error(f"Leonardo poll failed: {e}")
        raise HTTPException(500, f"Erro ao verificar status: {str(e)[:200]}")


@router.post("/leonardo/save-to-project")
async def leonardo_save_to_project(request: Request, user: dict = Depends(require_auth)):
    """Download a Leonardo image and save it to a project's assets."""
    from services.leonardo_ai import download_image_to_disk
    from services.asset_store import store_asset_async

    body = await request.json()
    image_url = body.get("imageUrl")
    project_id = body.get("projectId")
    prompt = body.get("prompt", "")

    if not image_url or not project_id:
        raise HTTPException(400, "imageUrl and projectId are required")

    filename = f"leonardo_{uuid.uuid4().hex[:10]}.png"
    assets_dir = PROJECTS_DIR / project_id / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    dest_path = str(assets_dir / filename)

    success = await download_image_to_disk(image_url, dest_path)
    if not success:
        raise HTTPException(500, "Falha ao baixar imagem do Leonardo")

    # Verify file exists on disk
    from pathlib import Path
    if not Path(dest_path).exists():
        raise HTTPException(500, "Arquivo baixado mas não encontrado no disco")

    # Persist to MongoDB (required for production K8s ephemeral storage)
    try:
        stored = await store_asset_async(db, project_id, filename, dest_path)
        if not stored:
            logger.warning(f"store_asset_async returned False for Leonardo image {filename}")
    except Exception as e:
        logger.warning(f"Failed to persist Leonardo image to MongoDB: {e}")

    asset_url = f"/api/projects/{project_id}/assets/{filename}"

    # Auto-save to AI Image Gallery
    try:
        from routes.gallery import auto_save_to_gallery
        await auto_save_to_gallery(
            image_url=asset_url,
            keywords=f"leonardo: {prompt}" if prompt else "leonardo ai",
            project_id=project_id,
            project_name="",
            user_id=user.get("user_id", ""),
            company_id=user.get("companyId", ""),
        )
    except Exception as e:
        logger.warning(f"Failed to auto-save Leonardo image to gallery: {e}")

    return {"url": asset_url, "filename": filename, "projectId": project_id}
