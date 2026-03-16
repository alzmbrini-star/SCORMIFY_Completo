"""
Scenario routes - CRUD and AI generation for interactive learning scenarios
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import uuid
import asyncio
import logging

from routes.deps import db, now_utc, serialize_doc

logger = logging.getLogger("server")
router = APIRouter(prefix="/scenarios", tags=["Scenarios"])

# In-memory store for generation tasks (lightweight, no extra dependencies)
_generation_tasks: Dict[str, Dict[str, Any]] = {}


# ── Request Models ──

class ScenarioGenerateRequest(BaseModel):
    """Request to generate a scenario via AI"""
    project_id: str
    theme: str
    objectives: str
    audience: str = ""
    complexity: str = "intermediate"  # beginner, intermediate, advanced
    industry: str = ""
    duration_minutes: int = 15
    language: str = "pt-BR"


class ScenarioCreateRequest(BaseModel):
    """Create a scenario manually (or save AI-generated one)"""
    project_id: str
    title: str
    description: str = ""
    context: str = ""
    characters: List[Dict[str, Any]] = []
    learning_objectives: List[str] = []
    competencies_evaluated: List[str] = []
    nodes: List[Dict[str, Any]] = []
    config: Dict[str, Any] = {}


class ScenarioUpdateRequest(BaseModel):
    """Update scenario fields"""
    title: Optional[str] = None
    description: Optional[str] = None
    context: Optional[str] = None
    characters: Optional[List[Dict[str, Any]]] = None
    learning_objectives: Optional[List[str]] = None
    competencies_evaluated: Optional[List[str]] = None
    nodes: Optional[List[Dict[str, Any]]] = None
    config: Optional[Dict[str, Any]] = None


# ── Routes ──

@router.post("/generate")
async def generate_scenario(req: ScenarioGenerateRequest):
    """Start async scenario generation. Returns task_id for polling."""
    task_id = str(uuid.uuid4())

    _generation_tasks[task_id] = {
        "status": "processing",
        "scenario": None,
        "error": None,
    }

    # Run generation in background
    asyncio.ensure_future(_run_generation(task_id, req))

    return {"success": True, "task_id": task_id, "status": "processing"}


async def _run_generation(task_id: str, req: ScenarioGenerateRequest):
    """Background task to generate scenario"""
    from services.scenario_service import generate_scenario_with_ai

    try:
        scenario_data = await generate_scenario_with_ai({
            "theme": req.theme,
            "objectives": req.objectives,
            "audience": req.audience,
            "complexity": req.complexity,
            "industry": req.industry,
            "duration_minutes": req.duration_minutes,
            "language": req.language,
        })

        # Save to database
        scenario_id = str(uuid.uuid4())
        now = now_utc().isoformat()

        doc = {
            "id": scenario_id,
            "project_id": req.project_id,
            "title": scenario_data.get("title", "Cenário sem título"),
            "description": scenario_data.get("description", ""),
            "context": scenario_data.get("context", ""),
            "characters": scenario_data.get("characters", []),
            "learning_objectives": scenario_data.get("learning_objectives", []),
            "competencies_evaluated": scenario_data.get("competencies_evaluated", []),
            "nodes": scenario_data.get("nodes", []),
            "start_node_id": scenario_data["nodes"][0]["id"] if scenario_data.get("nodes") else None,
            "config": {
                "theme": req.theme,
                "objectives": req.objectives,
                "audience": req.audience,
                "complexity": req.complexity,
                "industry": req.industry,
                "duration_minutes": req.duration_minutes,
            },
            "created_at": now,
            "updated_at": now,
        }

        await db.scenarios.insert_one(doc)
        doc.pop("_id", None)

        _generation_tasks[task_id] = {
            "status": "completed",
            "scenario": doc,
            "error": None,
        }
        logger.info(f"Scenario generation task {task_id} completed: {doc['title']}")

    except Exception as e:
        logger.error(f"Scenario generation task {task_id} failed: {e}")
        _generation_tasks[task_id] = {
            "status": "failed",
            "scenario": None,
            "error": str(e),
        }


@router.get("/task/{task_id}")
async def get_generation_status(task_id: str):
    """Poll for scenario generation status"""
    task = _generation_tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task não encontrada")

    result = {"task_id": task_id, "status": task["status"]}

    if task["status"] == "completed":
        result["success"] = True
        result["scenario"] = task["scenario"]
        # Clean up after delivery
        del _generation_tasks[task_id]
    elif task["status"] == "failed":
        result["success"] = False
        result["error"] = task["error"]
        del _generation_tasks[task_id]

    return result


@router.post("")
async def create_scenario(req: ScenarioCreateRequest):
    """Create or save a scenario manually"""
    scenario_id = str(uuid.uuid4())
    now = now_utc().isoformat()

    doc = {
        "id": scenario_id,
        "project_id": req.project_id,
        "title": req.title,
        "description": req.description,
        "context": req.context,
        "characters": req.characters,
        "learning_objectives": req.learning_objectives,
        "competencies_evaluated": req.competencies_evaluated,
        "nodes": req.nodes,
        "start_node_id": req.nodes[0]["id"] if req.nodes else None,
        "config": req.config,
        "created_at": now,
        "updated_at": now,
    }

    await db.scenarios.insert_one(doc)
    doc.pop("_id", None)

    return {"success": True, "scenario": doc}


@router.get("/project/{project_id}")
async def list_scenarios_by_project(project_id: str):
    """List all scenarios for a project"""
    scenarios = await db.scenarios.find(
        {"project_id": project_id}, {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    return scenarios


@router.get("/{scenario_id}")
async def get_scenario(scenario_id: str):
    """Get a single scenario by ID"""
    doc = await db.scenarios.find_one({"id": scenario_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Cenário não encontrado")
    return doc


@router.put("/{scenario_id}")
async def update_scenario(scenario_id: str, req: ScenarioUpdateRequest):
    """Update a scenario"""
    existing = await db.scenarios.find_one({"id": scenario_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Cenário não encontrado")

    update_data = {}
    for field, value in req.model_dump(exclude_none=True).items():
        update_data[field] = value

    if "nodes" in update_data and update_data["nodes"]:
        update_data["start_node_id"] = update_data["nodes"][0]["id"]

    update_data["updated_at"] = now_utc().isoformat()

    await db.scenarios.update_one({"id": scenario_id}, {"$set": update_data})

    updated = await db.scenarios.find_one({"id": scenario_id}, {"_id": 0})
    return {"success": True, "scenario": updated}


@router.delete("/{scenario_id}")
async def delete_scenario(scenario_id: str):
    """Delete a scenario"""
    result = await db.scenarios.delete_one({"id": scenario_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Cenário não encontrado")
    return {"success": True, "message": "Cenário removido"}


@router.post("/{scenario_id}/regenerate")
async def regenerate_scenario(scenario_id: str):
    """Regenerate scenario using its stored config (async with polling)"""
    existing = await db.scenarios.find_one({"id": scenario_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Cenário não encontrado")

    config = existing.get("config", {})
    if not config.get("theme"):
        raise HTTPException(status_code=400, detail="Cenário sem configuração de geração")

    task_id = str(uuid.uuid4())
    _generation_tasks[task_id] = {"status": "processing", "scenario": None, "error": None}

    asyncio.ensure_future(_run_regeneration(task_id, scenario_id, config))

    return {"success": True, "task_id": task_id, "status": "processing"}


async def _run_regeneration(task_id: str, scenario_id: str, config: dict):
    """Background task to regenerate scenario"""
    from services.scenario_service import generate_scenario_with_ai

    try:
        scenario_data = await generate_scenario_with_ai(config)

        update = {
            "title": scenario_data.get("title", ""),
            "description": scenario_data.get("description", ""),
            "context": scenario_data.get("context", ""),
            "characters": scenario_data.get("characters", []),
            "learning_objectives": scenario_data.get("learning_objectives", []),
            "competencies_evaluated": scenario_data.get("competencies_evaluated", []),
            "nodes": scenario_data.get("nodes", []),
            "start_node_id": scenario_data["nodes"][0]["id"] if scenario_data.get("nodes") else None,
            "updated_at": now_utc().isoformat(),
        }

        await db.scenarios.update_one({"id": scenario_id}, {"$set": update})
        updated = await db.scenarios.find_one({"id": scenario_id}, {"_id": 0})

        _generation_tasks[task_id] = {"status": "completed", "scenario": updated, "error": None}
        logger.info(f"Scenario regeneration task {task_id} completed")

    except Exception as e:
        logger.error(f"Scenario regeneration task {task_id} failed: {e}")
        _generation_tasks[task_id] = {"status": "failed", "scenario": None, "error": str(e)}
