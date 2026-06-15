"""HTTP routes for the self-hosted Whiteboard / Hand-writer video
generator. Endpoints:

  POST /api/whiteboard/generate   — render an MP4 from text/title.
  GET  /api/whiteboard/file/{name} — serve the generated MP4.

The generate endpoint accepts a project_id + slide_id so the resulting
video URL is automatically saved to the slide as `videoUrl` (the
existing Slide model already has this field, used by other video
generators like HeyGen)."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from routes.deps import db, now_utc
from routes.auth import require_auth
from services.whiteboard_renderer import (
    OUTPUT_DIR, render_whiteboard_video, list_available_fonts,
)

logger = logging.getLogger("server")
router = APIRouter(prefix="/whiteboard", tags=["Whiteboard"])


class WhiteboardGenerateRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000)
    title: Optional[str] = Field(default=None, max_length=200)
    fontSize: Optional[int] = Field(default=84, ge=40, le=240)
    charsPerSecond: Optional[float] = Field(default=6.0, ge=2.0, le=40.0)
    fontFamily: Optional[str] = Field(default=None, max_length=64)
    transparent: Optional[bool] = Field(default=False)
    # Optional binding — when both are provided, the generated videoUrl
    # is written to the matching slide element so the author doesn't have
    # to manually paste it. When omitted, the URL is just returned.
    projectId: Optional[str] = None
    slideId: Optional[str] = None


@router.post("/generate")
async def generate_whiteboard_video(
    payload: WhiteboardGenerateRequest,
    user: dict = Depends(require_auth),
):
    """Synthesize a whiteboard MP4 and (optionally) bind it to a slide."""
    try:
        rel_url, info = await render_whiteboard_video(
            text=payload.text,
            title=payload.title or None,
            font_size=payload.fontSize or 84,
            chars_per_second=payload.charsPerSecond or 6.0,
            font_family=payload.fontFamily or None,
            transparent=bool(payload.transparent),
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.exception("whiteboard generate failed: %s", e)
        raise HTTPException(500, f"render failed: {e}")

    # Bind to slide if requested.
    if payload.projectId and payload.slideId:
        project = await db.projects.find_one({"id": payload.projectId}, {"_id": 0})
        if project:
            slides = (project.get("course") or {}).get("slides") or []
            slide_idx = next(
                (i for i, s in enumerate(slides) if s.get("id") == payload.slideId),
                None,
            )
            if slide_idx is not None:
                slide = slides[slide_idx]
                elements = slide.get("elements") or []
                # Replace any prior whiteboard element so re-generating
                # the same slide doesn't stack multiple copies.
                elements = [e for e in elements if not (isinstance(e, dict) and e.get("isWhiteboard"))]
                import uuid as _uuid
                # Slide canvas is 1920x820 by default — center the 16:9
                # output at 1280x720 with some breathing room. APNG
                # transparent output is bound as an IMAGE element so it
                # renders via <img>, where APNG plays automatically and
                # preserves alpha. Opaque MP4 stays as a video element.
                is_apng = info.get("format") == "apng"
                if is_apng:
                    new_el = {
                        "id": str(_uuid.uuid4()),
                        "type": "image",
                        "src": rel_url,
                        "x": 320,
                        "y": 50,
                        "width": 1280,
                        "height": 720,
                        "zIndex": len(elements),
                        "isWhiteboard": True,
                        "isAnimatedPng": True,
                        "style": {"backgroundColor": "transparent"},
                    }
                else:
                    new_el = {
                        "id": str(_uuid.uuid4()),
                        "type": "video",
                        "src": rel_url,
                        "x": 320,
                        "y": 50,
                        "width": 1280,
                        "height": 720,
                        "zIndex": len(elements),
                        "isWhiteboard": True,
                        "autoplay": True,
                        "loop": False,
                        "controls": True,
                        "style": {},
                    }
                elements.append(new_el)
                set_fields = {
                    f"course.slides.{slide_idx}.whiteboardMeta": info,
                    f"course.slides.{slide_idx}.elements": elements,
                    "updatedAt": now_utc().isoformat(),
                }
                # Only set `videoUrl` for actual MP4 outputs — APNG is
                # an image and shouldn't be confused with a true video.
                if not is_apng:
                    set_fields[f"course.slides.{slide_idx}.videoUrl"] = rel_url
                await db.projects.update_one(
                    {"id": payload.projectId},
                    {"$set": set_fields},
                )

    return {
        "videoUrl": rel_url,
        **info,
    }


@router.get("/file/{name}")
async def serve_whiteboard_file(name: str):
    """Stream the generated video (MP4 or WebM with alpha) with a long
    cache TTL — same script means CDN-friendly idempotent caching."""
    # Sanitize: name must be wb_<hex>.{mp4|webm|png} to prevent path
    # traversal. .png is used for animated APNG outputs (transparent).
    valid_ext = name.endswith(".mp4") or name.endswith(".webm") or name.endswith(".png")
    ok_name = (
        name.startswith("wb_")
        and valid_ext
        and "/" not in name
        and ".." not in name
    )
    if not ok_name:
        raise HTTPException(404, "invalid name")
    path = OUTPUT_DIR / name
    if not path.exists():
        raise HTTPException(404, "video not found")
    if name.endswith(".webm"):
        media_type = "video/webm"
    elif name.endswith(".png"):
        media_type = "image/apng"
    else:
        media_type = "video/mp4"
    return FileResponse(
        str(path), media_type=media_type,
        headers={"Cache-Control": "public, max-age=2592000, immutable"},
    )


@router.get("/fonts")
async def whiteboard_fonts():
    """Return the catalog of bundled handwriting/marker fonts available
    for the whiteboard renderer."""
    return {"fonts": list_available_fonts()}


@router.get("/health")
async def whiteboard_health():
    """Diagnostic: verifies font + hand asset + ffmpeg binary are ready.

    Crucial for production debugging: hitting this from the browser /
    admin panel tells you instantly whether the K8s pod has the binary
    AND can encode (or whether we'd hit a 500 on first generate)."""
    from services.whiteboard_renderer import (
        HAND_PATH, _resolve_ffmpeg_binary, _resolve_font_path,
    )
    default_font = _resolve_font_path(None)
    info = {
        "fontOk": Path(default_font).exists(),
        "fontPath": str(default_font),
        "availableFonts": [f["id"] for f in list_available_fonts()],
        "handOk": Path(HAND_PATH).exists(),
        "outputDir": str(OUTPUT_DIR),
        "outputDirOk": OUTPUT_DIR.exists(),
    }
    try:
        info["ffmpegPath"] = _resolve_ffmpeg_binary()
        info["ffmpegOk"] = True
    except Exception as e:
        info["ffmpegPath"] = None
        info["ffmpegOk"] = False
        info["ffmpegError"] = str(e)
    return info
