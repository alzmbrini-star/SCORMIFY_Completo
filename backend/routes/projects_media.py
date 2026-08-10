"""Media upload route.

Single endpoint to upload images/audio/video to a project's assets. Images
are optimised automatically (resize + quality compression) to keep the
final course download small.
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Depends, Body
from pathlib import Path
import asyncio
import uuid
import io
import logging
import aiofiles
import os

from routes.deps import db, PROJECTS_DIR
from routes.auth import require_auth
from routes.projects_common import load_authorized_project

logger = logging.getLogger("server")

router = APIRouter(tags=["Projects - Media"])


def _pdf_page_render_scale(page_width: float, page_height: float) -> float:
    """Choose a sharp raster scale while keeping pathological PDFs bounded."""
    try:
        dpi = min(360, max(144, int(os.environ.get("PDF_PAGE_RENDER_DPI", "240"))))
    except (TypeError, ValueError):
        dpi = 240
    try:
        max_dimension = min(5000, max(1800, int(os.environ.get("PDF_PAGE_MAX_DIMENSION", "3200"))))
    except (TypeError, ValueError):
        max_dimension = 3200
    scale = dpi / 72.0
    largest = max(float(page_width or 1), float(page_height or 1))
    return min(scale, max_dimension / largest)


@router.post("/projects/{project_id}/media")
async def upload_media(project_id: str, file: UploadFile = File(...), user: dict = Depends(require_auth)):
    """Upload media file (image, audio, video) with automatic image optimization."""
    await load_authorized_project(project_id, user)

    allowed_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.mp3', '.wav', '.ogg', '.mp4', '.webm', '.pdf'}
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


@router.post("/projects/{project_id}/pdf-pages")
async def render_pdf_pages(project_id: str, payload: dict = Body(...), user: dict = Depends(require_auth)):
    """Render pages of an uploaded project PDF as PNG images (assets).
    Body: {"filename": "<uuid>.pdf", "pages": "all" | "1-3,5"}. Max 30 pages."""
    await load_authorized_project(project_id, user)
    filename = (payload.get("filename") or "").strip()
    pages_spec = (payload.get("pages") or "all").strip().lower()
    if not filename.endswith('.pdf') or '/' in filename or '..' in filename:
        raise HTTPException(status_code=400, detail="Nome de arquivo PDF inválido")

    pdf_path = PROJECTS_DIR / project_id / "assets" / filename
    if not pdf_path.exists():
        try:
            from services.asset_store import retrieve_asset_async
            data, _ct = await retrieve_asset_async(db, project_id, filename)
            if data:
                pdf_path.parent.mkdir(parents=True, exist_ok=True)
                pdf_path.write_bytes(data)
        except Exception as e:
            logger.warning(f"PDF restore from MongoDB failed: {e}")
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="PDF não encontrado")

    def _render():
        import fitz
        doc = fitz.open(str(pdf_path))
        total = doc.page_count
        if pages_spec in ("all", "todas", ""):
            nums = list(range(1, total + 1))
        else:
            nums = []
            for part in pages_spec.split(","):
                part = part.strip()
                if "-" in part:
                    a, b = part.split("-", 1)
                    nums.extend(range(int(a), int(b) + 1))
                elif part:
                    nums.append(int(part))
            nums = sorted(set(nums))
        nums = [p for p in nums if 1 <= p <= total][:30]
        results = []
        stem = Path(filename).stem
        for p in nums:
            page = doc.load_page(p - 1)
            scale = _pdf_page_render_scale(page.rect.width, page.rect.height)
            pix = page.get_pixmap(
                matrix=fitz.Matrix(scale, scale),
                colorspace=fitz.csRGB,
                alpha=False,
            )
            out_name = f"{stem}_p{p}.png"
            pix.save(str(pdf_path.parent / out_name))
            results.append((p, out_name, pix.width, pix.height))
        doc.close()
        return total, results

    try:
        total, results = await asyncio.to_thread(_render)
    except ValueError:
        raise HTTPException(status_code=400, detail="Formato de páginas inválido. Use 'all' ou ex.: 1-3,5")
    except Exception as e:
        logger.error(f"PDF page render failed: {e}")
        raise HTTPException(status_code=500, detail="Falha ao renderizar páginas do PDF")
    if not results:
        raise HTTPException(status_code=400, detail="Nenhuma página válida selecionada")

    from services.asset_store import store_asset_async
    pages = []
    for p, out_name, width, height in results:
        try:
            await store_asset_async(db, project_id, out_name, str(pdf_path.parent / out_name))
        except Exception as e:
            logger.warning(f"Failed to persist PDF page in MongoDB (non-fatal): {e}")
        pages.append({
            "page": p,
            "url": f"/api/projects/{project_id}/assets/{out_name}",
            "width": width,
            "height": height,
        })
    return {"pageCount": total, "pages": pages}
