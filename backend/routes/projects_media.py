"""Media upload route.

Single endpoint to upload images/audio/video to a project's assets. Images
are optimised automatically (resize + quality compression) to keep the
final course download small.
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Depends
from pathlib import Path
import uuid
import io
import logging
import aiofiles

from routes.deps import db, PROJECTS_DIR
from routes.auth import require_auth
from routes.projects_common import load_authorized_project

logger = logging.getLogger("server")

router = APIRouter(tags=["Projects - Media"])


@router.post("/projects/{project_id}/media")
async def upload_media(project_id: str, file: UploadFile = File(...), user: dict = Depends(require_auth)):
    """Upload media file (image, audio, video) with automatic image optimization."""
    await load_authorized_project(project_id, user)

    allowed_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.mp3', '.wav', '.ogg', '.mp4', '.webm'}
    ext = Path(file.filename).suffix.lower()
    if ext not in allowed_extensions:
        raise HTTPException(status_code=400, detail=f"Invalid file type. Allowed: {', '.join(allowed_extensions)}")

    content = await file.read()
    original_size = len(content)
    max_size = 100 * 1024 * 1024  # 100MB
    if original_size > max_size:
        raise HTTPException(status_code=400, detail="File too large")

    # Optimize images automatically
    image_extensions = {'.png', '.jpg', '.jpeg', '.webp'}
    optimized = False
    final_content = content

    if ext in image_extensions:
        try:
            from PIL import Image
            img = Image.open(io.BytesIO(content))
            original_width, original_height = img.size

            # Only optimize if image is large (> 500KB or dimensions > 1920px)
            should_optimize = original_size > 500 * 1024 or img.width > 1920 or img.height > 1080

            if should_optimize:
                # Convert RGBA to RGB for JPEG (remove alpha channel)
                if img.mode == 'RGBA' and ext in {'.jpg', '.jpeg'}:
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    background.paste(img, mask=img.split()[3])
                    img = background
                elif img.mode == 'RGBA':
                    pass  # Keep alpha for PNG/WebP
                elif img.mode != 'RGB':
                    img = img.convert('RGB')

                max_width = 1920
                max_height = 1080

                if img.width > max_width or img.height > max_height:
                    ratio = min(max_width / img.width, max_height / img.height)
                    new_size = (int(img.width * ratio), int(img.height * ratio))
                    img = img.resize(new_size, Image.Resampling.LANCZOS)
                    logger.info(f"Resized image from {original_width}x{original_height} to {new_size[0]}x{new_size[1]}")

                output = io.BytesIO()
                if ext == '.png':
                    img.save(output, format='PNG', optimize=True)
                elif ext == '.webp':
                    img.save(output, format='WEBP', quality=85, method=6)
                else:
                    img.save(output, format='JPEG', quality=85, optimize=True)

                optimized_content = output.getvalue()

                # Only use optimized version if it's actually smaller
                if len(optimized_content) < original_size:
                    final_content = optimized_content
                    optimized = True
                    logger.info(f"Image optimized: {original_size} bytes -> {len(final_content)} bytes ({100 - (len(final_content)/original_size*100):.1f}% reduction)")
                else:
                    logger.info(f"Optimization skipped: optimized size ({len(optimized_content)}) >= original ({original_size})")

        except Exception as e:
            logger.warning(f"Image optimization failed, using original: {e}")

    file_id = str(uuid.uuid4())
    filename = f"{file_id}{ext}"
    file_path = PROJECTS_DIR / project_id / "assets" / filename
    file_path.parent.mkdir(parents=True, exist_ok=True)

    async with aiofiles.open(file_path, 'wb') as f:
        await f.write(final_content)

    # Persist in MongoDB for production environments with ephemeral storage
    try:
        from services.asset_store import store_asset_async
        await store_asset_async(db, project_id, filename, str(file_path))
    except Exception as e:
        logger.warning(f"Failed to persist media in MongoDB (non-fatal): {e}")

    return {
        "id": file_id,
        "filename": filename,
        "url": f"/api/projects/{project_id}/assets/{filename}",
        "size": len(final_content),
        "originalSize": original_size,
        "optimized": optimized,
        "type": ext[1:]
    }
