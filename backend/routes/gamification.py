"""
Gamification routes for badges and feedback configuration
"""
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from typing import Optional
import base64
import uuid
from datetime import datetime, timezone

from routes.deps import db
from routes.auth import require_auth, get_current_user
from models import (
    Badge, BadgeCriteria, FeedbackRange, GamificationConfig,
    DEFAULT_BADGES, DEFAULT_QUIZ_FEEDBACK, DEFAULT_SCENARIO_FEEDBACK, generate_id
)

router = APIRouter()


@router.get("/gamification/defaults")
async def get_default_gamification():
    """Get default badges and feedback ranges"""
    return {
        "badges": [b.model_dump() for b in DEFAULT_BADGES],
        "quizFeedbackRanges": [f.model_dump() for f in DEFAULT_QUIZ_FEEDBACK],
        "scenarioFeedbackRanges": [f.model_dump() for f in DEFAULT_SCENARIO_FEEDBACK],
    }


@router.get("/projects/{project_id}/gamification")
async def get_project_gamification(project_id: str, user: dict = Depends(require_auth)):
    """Get gamification config for a project"""
    project = await db.projects.find_one({"id": project_id}, {"_id": 0, "gamification": 1, "name": 1})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    gamification = project.get("gamification")
    if not gamification:
        # Return defaults if not configured
        return {
            "enabled": True,
            "showBadgesAfterQuiz": True,
            "showBadgesAfterScenario": True,
            "showFinalSummary": True,
            "badges": [b.model_dump() for b in DEFAULT_BADGES],
            "quizFeedbackRanges": [f.model_dump() for f in DEFAULT_QUIZ_FEEDBACK],
            "scenarioFeedbackRanges": [f.model_dump() for f in DEFAULT_SCENARIO_FEEDBACK],
            "completionFeedback": {
                "id": "completion_default",
                "minScore": 0,
                "maxScore": 100,
                "title": "Curso Concluído!",
                "message": "Parabéns por completar o curso!",
                "emoji": "🎓"
            }
        }
    
    return gamification


@router.put("/projects/{project_id}/gamification")
async def update_project_gamification(project_id: str, config: dict, user: dict = Depends(require_auth)):
    """Update gamification config for a project"""
    project = await db.projects.find_one({"id": project_id}, {"_id": 0, "id": 1})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Validate and clean config
    gamification_config = {
        "enabled": config.get("enabled", True),
        "showBadgesAfterQuiz": config.get("showBadgesAfterQuiz", True),
        "showBadgesAfterScenario": config.get("showBadgesAfterScenario", True),
        "showFinalSummary": config.get("showFinalSummary", True),
        "badges": config.get("badges", []),
        "quizFeedbackRanges": config.get("quizFeedbackRanges", []),
        "scenarioFeedbackRanges": config.get("scenarioFeedbackRanges", []),
        "completionFeedback": config.get("completionFeedback"),
        "updatedAt": datetime.now(timezone.utc).isoformat()
    }
    
    await db.projects.update_one(
        {"id": project_id},
        {"$set": {"gamification": gamification_config}}
    )
    
    return {"status": "ok", "message": "Gamification config updated"}


@router.post("/projects/{project_id}/gamification/badges")
async def add_custom_badge(project_id: str, badge: dict, user: dict = Depends(require_auth)):
    """Add a custom badge to a project"""
    project = await db.projects.find_one({"id": project_id}, {"_id": 0, "gamification": 1})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    gamification = project.get("gamification", {})
    badges = gamification.get("badges", [b.model_dump() for b in DEFAULT_BADGES])
    
    # Create new badge with ID
    new_badge = {
        "id": badge.get("id") or generate_id(),
        "name": badge.get("name", "Novo Badge"),
        "description": badge.get("description", ""),
        "icon": badge.get("icon", "award"),
        "iconColor": badge.get("iconColor", "#fbbf24"),
        "customImage": badge.get("customImage"),
        "criteria": badge.get("criteria", {"type": "quiz_score", "threshold": 80, "operator": "gte"}),
        "isDefault": False,
        "createdAt": datetime.now(timezone.utc).isoformat()
    }
    
    badges.append(new_badge)
    gamification["badges"] = badges
    
    await db.projects.update_one(
        {"id": project_id},
        {"$set": {"gamification": gamification}}
    )
    
    return {"status": "ok", "badge": new_badge}


@router.delete("/projects/{project_id}/gamification/badges/{badge_id}")
async def delete_badge(project_id: str, badge_id: str, user: dict = Depends(require_auth)):
    """Delete a badge from a project (only custom badges can be deleted)"""
    project = await db.projects.find_one({"id": project_id}, {"_id": 0, "gamification": 1})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    gamification = project.get("gamification", {})
    badges = gamification.get("badges", [])
    
    # Find and remove badge (only if not default)
    new_badges = []
    deleted = False
    for b in badges:
        if b.get("id") == badge_id:
            if b.get("isDefault"):
                raise HTTPException(status_code=400, detail="Cannot delete default badges")
            deleted = True
        else:
            new_badges.append(b)
    
    if not deleted:
        raise HTTPException(status_code=404, detail="Badge not found")
    
    gamification["badges"] = new_badges
    
    await db.projects.update_one(
        {"id": project_id},
        {"$set": {"gamification": gamification}}
    )
    
    return {"status": "ok", "message": "Badge deleted"}


@router.post("/gamification/upload-badge-image")
async def upload_badge_image(file: UploadFile = File(...), user: dict = Depends(require_auth)):
    """Upload a custom badge image"""
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")
    
    # Read and convert to base64
    content = await file.read()
    if len(content) > 500 * 1024:  # 500KB limit
        raise HTTPException(status_code=400, detail="Image too large (max 500KB)")
    
    base64_image = base64.b64encode(content).decode("utf-8")
    data_url = f"data:{file.content_type};base64,{base64_image}"
    
    return {"imageUrl": data_url}


@router.get("/gamification/icons")
async def get_available_icons():
    """Get list of available predefined icons for badges"""
    return {
        "icons": [
            {"id": "trophy", "name": "Troféu", "category": "achievement"},
            {"id": "award", "name": "Medalha", "category": "achievement"},
            {"id": "star", "name": "Estrela", "category": "achievement"},
            {"id": "medal", "name": "Medalha Militar", "category": "achievement"},
            {"id": "crown", "name": "Coroa", "category": "achievement"},
            {"id": "target", "name": "Alvo", "category": "skill"},
            {"id": "brain", "name": "Cérebro", "category": "skill"},
            {"id": "lightbulb", "name": "Lâmpada", "category": "skill"},
            {"id": "puzzle", "name": "Quebra-cabeça", "category": "skill"},
            {"id": "rocket", "name": "Foguete", "category": "progress"},
            {"id": "flame", "name": "Chama", "category": "progress"},
            {"id": "zap", "name": "Raio", "category": "progress"},
            {"id": "check-circle", "name": "Check", "category": "completion"},
            {"id": "badge", "name": "Distintivo", "category": "completion"},
            {"id": "shield", "name": "Escudo", "category": "completion"},
            {"id": "heart", "name": "Coração", "category": "engagement"},
            {"id": "thumbs-up", "name": "Joinha", "category": "engagement"},
            {"id": "smile", "name": "Sorriso", "category": "engagement"},
        ]
    }
