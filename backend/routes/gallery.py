"""AI Image Gallery routes - shared image library per company"""
from fastapi import APIRouter, HTTPException, Request
from typing import Optional
import uuid
import os
import logging
from datetime import datetime, timezone

from routes.deps import db, PROJECTS_DIR
from routes.auth import require_auth, get_current_user

logger = logging.getLogger("server")

router = APIRouter(tags=["Gallery"])


@router.get("/gallery/images")
async def gallery_list_images(request: Request, user: dict = None):
    """List AI-generated images accessible to the current user's company.
    Super admins see all images."""
    current_user = await get_current_user(request)
    if not current_user:
        raise HTTPException(401, "Not authenticated")

    query = {}
    if current_user.get("role") != "super_admin":
        company_id = current_user.get("companyId")
        if company_id:
            query["companyId"] = company_id
        else:
            query["userId"] = current_user.get("user_id")

    images = await db.image_gallery.find(
        query, {"_id": 0}
    ).sort("createdAt", -1).to_list(200)

    # Fire-and-forget: pre-cache missing gallery assets in background
    import asyncio
    asyncio.create_task(_precache_gallery_assets(images))

    return {"images": images, "total": len(images)}


async def _precache_gallery_assets(images: list):
    """Background task: restore missing gallery assets from MongoDB to disk."""
    try:
        from pathlib import Path
        from routes.deps import PROJECTS_DIR
        from services.asset_store import retrieve_asset_async

        missing = []
        for img in images:
            url = img.get("imageUrl", "")
            if url.startswith("/api/projects/"):
                parts = url.split("/")
                if len(parts) >= 6:
                    file_path = PROJECTS_DIR / parts[3] / "assets" / parts[5]
                    if not file_path.exists():
                        missing.append((parts[3], parts[5], file_path))

        if not missing:
            return

        restored = 0
        for project_id, filename, file_path in missing[:5]:
            try:
                data, _ = await retrieve_asset_async(db, project_id, filename)
                if data:
                    file_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(file_path, 'wb') as f:
                        f.write(data)
                    restored += 1
            except Exception:
                pass
        if restored > 0:
            logger.info(f"Gallery pre-cache: restored {restored}/{len(missing)} images")
    except Exception as e:
        logger.warning(f"Gallery pre-cache failed (non-fatal): {e}")


@router.post("/gallery/images")
async def gallery_save_image(data: dict, request: Request):
    """Save an image to the gallery manually."""
    current_user = await get_current_user(request)
    if not current_user:
        raise HTTPException(401, "Not authenticated")

    image_url = data.get("imageUrl", "")
    if not image_url:
        raise HTTPException(400, "imageUrl is required")

    image_doc = {
        "id": str(uuid.uuid4()),
        "imageUrl": image_url,
        "prompt": data.get("prompt", ""),
        "keywords": data.get("keywords", ""),
        "projectId": data.get("projectId", ""),
        "projectName": data.get("projectName", ""),
        "userId": current_user.get("user_id"),
        "companyId": current_user.get("companyId", ""),
        "createdAt": datetime.now(timezone.utc).isoformat(),
    }
    await db.image_gallery.insert_one({**image_doc, "_id": image_doc["id"]})
    return image_doc


@router.delete("/gallery/images/{image_id}")
async def gallery_delete_image(image_id: str, request: Request):
    """Delete an image from the gallery."""
    current_user = await get_current_user(request)
    if not current_user:
        raise HTTPException(401, "Not authenticated")

    image = await db.image_gallery.find_one({"id": image_id}, {"_id": 0})
    if not image:
        raise HTTPException(404, "Image not found")

    # Only owner or super_admin can delete
    if current_user.get("role") != "super_admin" and image.get("userId") != current_user.get("user_id"):
        raise HTTPException(403, "Not authorized to delete this image")

    await db.image_gallery.delete_one({"id": image_id})
    return {"status": "ok", "deleted": image_id}


@router.post("/gallery/cleanup")
async def gallery_cleanup(request: Request):
    """Remove gallery entries whose assets are broken - checks both existence AND data integrity."""
    current_user = await get_current_user(request)
    if not current_user or current_user.get("role") != "super_admin":
        raise HTTPException(403, "Super admin only")

    body = {}
    try:
        body = await request.json()
    except Exception:
        pass
    
    # mode=deep actually verifies data field exists (slower but thorough)
    deep = body.get("deep", True)

    images = await db.image_gallery.find({}, {"_id": 0, "id": 1, "imageUrl": 1}).to_list(500)
    removed = 0
    kept = 0
    errors = []

    for img in images:
        url = img.get("imageUrl", "")
        if not url.startswith("/api/projects/"):
            kept += 1
            continue
        parts = url.split("/")
        if len(parts) >= 6:
            project_id = parts[3]
            filename = parts[5]
            try:
                if deep:
                    # Check document exists AND has non-empty data field
                    doc = await db.project_assets.find_one(
                        {"project_id": project_id, "filename": filename, "data": {"$exists": True, "$ne": ""}},
                        {"_id": 1}
                    )
                else:
                    doc = await db.project_assets.find_one(
                        {"project_id": project_id, "filename": filename},
                        {"_id": 1}
                    )
                if doc:
                    kept += 1
                else:
                    await db.image_gallery.delete_one({"id": img["id"]})
                    removed += 1
            except Exception as e:
                # If query times out, the asset is effectively broken - remove it
                logger.warning(f"Gallery cleanup: timeout checking {filename}, removing entry: {e}")
                await db.image_gallery.delete_one({"id": img["id"]})
                removed += 1
                errors.append(filename)
        else:
            kept += 1

    return {"removed": removed, "kept": kept, "total_before": len(images), "timeout_removed": len(errors)}




async def auto_save_to_gallery(image_url: str, keywords: str, project_id: str, project_name: str, user_id: str, company_id: str):
    """Auto-save a generated image to the gallery (called from other routes)."""
    try:
        # Check if image already exists in gallery
        existing = await db.image_gallery.find_one({"imageUrl": image_url})
        if existing:
            return

        image_doc = {
            "id": str(uuid.uuid4()),
            "imageUrl": image_url,
            "prompt": "",
            "keywords": keywords,
            "projectId": project_id,
            "projectName": project_name,
            "userId": user_id,
            "companyId": company_id,
            "createdAt": datetime.now(timezone.utc).isoformat(),
        }
        await db.image_gallery.insert_one({**image_doc, "_id": image_doc["id"]})
        logger.info(f"Image auto-saved to gallery: {image_url}")
    except Exception as e:
        logger.warning(f"Failed to auto-save image to gallery (non-fatal): {e}")
