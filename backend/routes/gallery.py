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
    Super admins see all images. Pre-caches missing assets from MongoDB."""
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

    # Pre-cache: check which gallery images are missing on disk and restore from MongoDB
    # This prevents 53 individual MongoDB fallbacks when the gallery opens
    from pathlib import Path
    from routes.deps import PROJECTS_DIR
    missing_assets = []
    for img in images:
        url = img.get("imageUrl", "")
        if url.startswith("/api/projects/"):
            parts = url.split("/")
            if len(parts) >= 6:
                project_id = parts[3]
                filename = parts[5]
                file_path = PROJECTS_DIR / project_id / "assets" / filename
                if not file_path.exists():
                    missing_assets.append((project_id, filename, file_path))

    # Batch restore up to 20 missing assets (non-blocking best effort)
    if missing_assets:
        from services.asset_store import retrieve_asset_async
        restored = 0
        for project_id, filename, file_path in missing_assets[:20]:
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
            logger.info(f"Gallery pre-cache: restored {restored}/{len(missing_assets)} images from MongoDB")

    return {"images": images, "total": len(images)}


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
