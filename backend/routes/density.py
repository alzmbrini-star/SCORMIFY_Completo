"""Routes for the visual-density analysis feature.

  POST /api/density/analyze            — score a single slide / section
  POST /api/density/suggestions        — score + LLM suggestions for one slide
  POST /api/density/analyze-storyboard — bulk score every section in a storyboard
  POST /api/density/analyze-project    — bulk score every slide in a project
  POST /api/density/generate-image     — render the suggestion's imagePrompt
                                          via Gemini Nano Banana and persist
                                          it as a project asset (used when the
                                          author applies an "infographic" or
                                          "diagram" suggestion that promised
                                          an image but the apply flow alone
                                          only writes the textual rewrite).

All endpoints return shapes compatible with the frontend density UI
(`DensityBadge` + `DensitySuggestionsDialog`).
"""
import os
import logging
import hashlib
from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

from routes.deps import db, PROJECTS_DIR
from routes.auth import require_auth
from services.text_density_analyzer import (
    analyze_text_density,
    analyze_slide,
    analyze_storyboard_section,
)
from services.density_suggester import generate_visual_suggestions
from services.gemini_image import generate_simple_image
from services.asset_store import store_asset_async

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/density", tags=["Density"])


class AnalyzeRequest(BaseModel):
    title: Optional[str] = ""
    text: Optional[str] = ""
    bullets: Optional[List[str]] = Field(default_factory=list)
    hasImage: Optional[bool] = False


class StoryboardAnalyzeRequest(BaseModel):
    sections: List[Dict[str, Any]]


class ProjectAnalyzeRequest(BaseModel):
    slides: List[Dict[str, Any]]


@router.post("/analyze")
async def analyze(req: AnalyzeRequest, user: dict = Depends(require_auth)):
    """Score one piece of content. Cheap, deterministic, no LLM."""
    result = analyze_text_density(
        text=req.text or "",
        bullets=req.bullets or [],
        has_image=bool(req.hasImage),
        title=req.title or "",
    )
    return result


@router.post("/suggestions")
async def suggestions(req: AnalyzeRequest, user: dict = Depends(require_auth)):
    """Score + LLM-generated visual alternatives. Slower (~3s) but actionable.
    Always runs the LLM — the frontend uses /analyze for the initial badge
    and only calls this when the author clicks the badge for details."""
    density = analyze_text_density(
        text=req.text or "",
        bullets=req.bullets or [],
        has_image=bool(req.hasImage),
        title=req.title or "",
    )
    sugs = await generate_visual_suggestions(
        title=req.title or "",
        text=req.text or "",
        bullets=req.bullets or [],
        reasons=density["reasons"],
    )
    return {"density": density, "suggestions": sugs}


@router.post("/analyze-storyboard")
async def analyze_storyboard(req: StoryboardAnalyzeRequest, user: dict = Depends(require_auth)):
    """Score every section in a storyboard. Single request → instant badges
    on the storyboard approval screen."""
    out = []
    for idx, section in enumerate(req.sections):
        analysis = analyze_storyboard_section(section)
        out.append({
            "index": idx,
            "title": section.get("title") or section.get("sectionTitle") or f"Secao {idx + 1}",
            **analysis,
        })
    summary = {
        "total": len(out),
        "light": sum(1 for o in out if o["label"] == "light"),
        "medium": sum(1 for o in out if o["label"] == "medium"),
        "heavy": sum(1 for o in out if o["label"] == "heavy"),
    }
    return {"sections": out, "summary": summary}


@router.post("/analyze-project")
async def analyze_project(req: ProjectAnalyzeRequest, user: dict = Depends(require_auth)):
    """Score every slide in a project. Used by GeneratedPanel for the
    post-generation 'Densidade Visual' panel."""
    out = []
    for idx, slide in enumerate(req.slides):
        analysis = analyze_slide(slide)
        out.append({
            "index": idx,
            "slideId": slide.get("id"),
            "title": slide.get("title") or f"Slide {idx + 1}",
            **analysis,
        })
    summary = {
        "total": len(out),
        "light": sum(1 for o in out if o["label"] == "light"),
        "medium": sum(1 for o in out if o["label"] == "medium"),
        "heavy": sum(1 for o in out if o["label"] == "heavy"),
    }
    return {"slides": out, "summary": summary}


class GenerateImageRequest(BaseModel):
    projectId: str
    imagePrompt: str
    # Optional hint for filename — keeps repeat applies idempotent and
    # avoids duplicate assets when the same suggestion is re-applied.
    suggestionId: Optional[str] = None


@router.post("/generate-image")
async def generate_image_for_suggestion(req: GenerateImageRequest, user: dict = Depends(require_auth)):
    """Generate an illustration for a density suggestion that promised an
    image (e.g. infographic/diagram types).

    Why this endpoint exists: the density suggester returns `imagePrompt`
    + `requiresImage=True` for visual suggestion types, but applying the
    suggestion alone only rewrites the slide text. The author was then
    promised "Inclui imagem" in the UI but received only text — clear UX
    deficit. This endpoint bridges that gap: takes the imagePrompt the LLM
    already produced, renders it via Gemini Nano Banana (Emergent key, free
    for the user), persists the bytes through `store_asset_async` so it
    survives K8s pod restarts, and returns a public URL the frontend can
    add to the slide as a new image element.

    Returns: { url, filename, width, height } on success.
    """
    prompt = (req.imagePrompt or "").strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="imagePrompt is required")
    if not req.projectId:
        raise HTTPException(status_code=400, detail="projectId is required")

    # Confirm the user can write to this project. We reuse the same
    # ownership check the projects routes do — super_admin always passes,
    # otherwise the project must belong to the user's company or be owned
    # by them.
    project = await db.projects.find_one({"id": req.projectId}, {"_id": 0})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    role = (user or {}).get("role")
    if role not in ("super_admin", "admin"):
        # Allow if user owns the project OR shares its company
        if project.get("userId") != user.get("id") and project.get("companyId") != user.get("companyId"):
            raise HTTPException(status_code=403, detail="Forbidden")

    # Generate via Gemini Nano Banana. ~3-6s typical.
    img_bytes = await generate_simple_image(prompt)
    if not img_bytes:
        raise HTTPException(status_code=502, detail="Image generation failed (Gemini)")

    # Deterministic filename keyed on prompt + suggestion id keeps re-applies
    # of the same suggestion idempotent (no duplicate gallery clutter).
    seed_src = (req.suggestionId or "") + "|" + prompt
    seed = hashlib.md5(seed_src.encode("utf-8")).hexdigest()[:10]
    fname = f"density_img_{seed}.jpg"
    fpath = os.path.join(PROJECTS_DIR, req.projectId, "assets", fname)
    os.makedirs(os.path.dirname(fpath), exist_ok=True)
    try:
        with open(fpath, "wb") as f:
            f.write(img_bytes)
    except Exception as e:
        logger.warning(f"[density.generate-image] disk write failed: {e}")

    # Persist to GridFS so it survives container restarts (the K8s preview
    # environment has ephemeral disk).
    try:
        from motor.motor_asyncio import AsyncIOMotorClient
        from routes.deps import mongo_url, db_name
        motor_client = AsyncIOMotorClient(mongo_url)
        _motor_db = motor_client[db_name]
        await store_asset_async(_motor_db, req.projectId, fname, fpath)
    except Exception as e:
        logger.warning(f"[density.generate-image] mongo persist failed: {e}")

    url = f"/api/projects/{req.projectId}/assets/{fname}"
    return {"url": url, "filename": fname, "width": 1200, "height": 1200}
