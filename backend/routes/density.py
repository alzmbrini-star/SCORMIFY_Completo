"""Routes for the visual-density analysis feature.

  POST /api/density/analyze            — score a single slide / section
  POST /api/density/suggestions        — score + LLM suggestions for one slide
  POST /api/density/analyze-storyboard — bulk score every section in a storyboard
  POST /api/density/analyze-project    — bulk score every slide in a project

All endpoints return shapes compatible with the frontend density UI
(`DensityBadge` + `DensitySuggestionsDialog`).
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
import logging

from routes.deps import db
from routes.auth import require_auth
from services.text_density_analyzer import (
    analyze_text_density,
    analyze_slide,
    analyze_storyboard_section,
)
from services.density_suggester import generate_visual_suggestions

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
