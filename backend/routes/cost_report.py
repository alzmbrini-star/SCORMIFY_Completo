"""Cost report routes — aggregate AI usage / project counts per company.

Exposed only to super_admin (service-providers managing multiple client
companies). Provides per-company breakdown so the user can bill / track
spending across companies.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Query
from typing import Optional, List, Dict, Any

from routes.deps import db
from routes.auth import require_auth

logger = logging.getLogger("server")

router = APIRouter(tags=["Admin"])


def _has_super_admin(user: dict) -> bool:
    role = user.get("role") or ""
    return role == "super_admin"


@router.get("/admin/cost-report")
async def cost_report(
    user: dict = Depends(require_auth),
    from_date: Optional[str] = Query(None, alias="from", description="ISO 8601 date (inclusive)"),
    to_date: Optional[str] = Query(None, alias="to", description="ISO 8601 date (exclusive)"),
):
    """Per-company AI usage report. Super_admin only.

    Aggregates these collections by `companyId`:
    - projects: total courses created (by source: manual / agent / ppt / pdf)
    - krea_generations: # Krea AI image generations
    - leonardo_generations: # Leonardo image generations
    - tutor_logs: # AI Tutor chat messages
    - elevenlabs_generations / heygen_jobs: voice/avatar generations (if tracked)

    Query params:
      ?from=2026-01-01  - inclusive lower bound on createdAt
      ?to=2026-04-30    - exclusive upper bound

    Response shape:
    {
      "companies": [
        {
          "companyId": "...",
          "companyName": "Acme Corp",
          "projects": {"total": 5, "manual": 1, "agent": 3, "ppt": 1},
          "krea": {"total": 12},
          "leonardo": {"total": 5},
          "tutor": {"total": 87},
          "elevenlabs": {"total": 0},
          "heygen": {"total": 0}
        },
        ...
      ],
      "from": "2026-01-01",
      "to": "2026-04-30",
      "generatedAt": "2026-04-29T..."
    }
    """
    if not _has_super_admin(user):
        return {"detail": "Apenas super-admin pode acessar o relatório de custos.",
                 "companies": []}

    # Build createdAt filter
    date_filter: Dict[str, Any] = {}
    if from_date:
        date_filter["$gte"] = from_date
    if to_date:
        date_filter["$lt"] = to_date
    common_filter = {"createdAt": date_filter} if date_filter else {}

    # 1) Get all companies (master list)
    companies_cursor = db.companies.find({}, {"_id": 0, "id": 1, "name": 1})
    companies_list = await companies_cursor.to_list(length=None)
    company_index = {c["id"]: c.get("name", "") for c in companies_list if c.get("id")}

    # Helper: aggregate a collection by companyId, returning {companyId: count}
    async def _count_by_company(collection_name: str, extra_match: dict = None) -> Dict[str, int]:
        match: Dict[str, Any] = {**common_filter}
        if extra_match:
            match.update(extra_match)
        pipeline = []
        if match:
            pipeline.append({"$match": match})
        pipeline.append({
            "$group": {"_id": "$companyId", "count": {"$sum": 1}}
        })
        try:
            agg = await db[collection_name].aggregate(pipeline).to_list(length=None)
        except Exception as e:
            logger.warning(f"cost_report aggregation failed for {collection_name}: {e}")
            return {}
        return {row["_id"]: row["count"] for row in agg if row.get("_id")}

    # 2) Projects: count + breakdown by source
    projects_pipeline: List[Dict[str, Any]] = []
    if common_filter:
        projects_pipeline.append({"$match": common_filter})
    projects_pipeline.append({
        "$group": {
            "_id": {"companyId": "$companyId", "source": "$source"},
            "count": {"$sum": 1}
        }
    })
    try:
        proj_agg = await db.projects.aggregate(projects_pipeline).to_list(length=None)
    except Exception as e:
        logger.warning(f"projects aggregation failed: {e}")
        proj_agg = []
    proj_by_company: Dict[str, Dict[str, int]] = {}
    for row in proj_agg:
        cid = (row.get("_id") or {}).get("companyId")
        src = (row.get("_id") or {}).get("source") or "manual"
        if not cid:
            continue
        proj_by_company.setdefault(cid, {"total": 0})
        proj_by_company[cid][src] = proj_by_company[cid].get(src, 0) + row["count"]
        proj_by_company[cid]["total"] += row["count"]

    # 3) AI generations
    krea_counts = await _count_by_company("krea_generations")
    leonardo_counts = await _count_by_company("leonardo_generations")
    tutor_counts = await _count_by_company("tutor_logs")

    # ElevenLabs / HeyGen: tracked indirectly via projectId. We aggregate by
    # joining through the project's companyId. If those collections don't
    # exist, the helper safely returns {}.
    async def _count_by_project_company(collection_name: str) -> Dict[str, int]:
        try:
            pipeline = []
            if common_filter:
                pipeline.append({"$match": common_filter})
            pipeline += [
                {"$lookup": {
                    "from": "projects",
                    "localField": "projectId",
                    "foreignField": "id",
                    "as": "_project"
                }},
                {"$unwind": {"path": "$_project", "preserveNullAndEmptyArrays": True}},
                {"$group": {
                    "_id": "$_project.companyId",
                    "count": {"$sum": 1}
                }},
            ]
            agg = await db[collection_name].aggregate(pipeline).to_list(length=None)
            return {row["_id"]: row["count"] for row in agg if row.get("_id")}
        except Exception:
            return {}

    elevenlabs_counts = await _count_by_company("elevenlabs_generations")
    if not elevenlabs_counts:
        # Older deployments tracked by projectId only
        elevenlabs_counts = await _count_by_project_company("elevenlabs_generations")
    heygen_counts = await _count_by_company("heygen_jobs")
    if not heygen_counts:
        heygen_counts = await _count_by_project_company("heygen_jobs")

    # 4) Build per-company response
    all_company_ids = set(company_index.keys())
    all_company_ids.update(proj_by_company.keys())
    all_company_ids.update(krea_counts.keys())
    all_company_ids.update(leonardo_counts.keys())
    all_company_ids.update(tutor_counts.keys())
    all_company_ids.update(elevenlabs_counts.keys())
    all_company_ids.update(heygen_counts.keys())

    companies_out = []
    for cid in sorted(all_company_ids):
        if not cid:
            continue
        companies_out.append({
            "companyId": cid,
            "companyName": company_index.get(cid, "(empresa removida)"),
            "projects": proj_by_company.get(cid, {"total": 0}),
            "krea": {"total": krea_counts.get(cid, 0)},
            "leonardo": {"total": leonardo_counts.get(cid, 0)},
            "tutor": {"total": tutor_counts.get(cid, 0)},
            "elevenlabs": {"total": elevenlabs_counts.get(cid, 0)},
            "heygen": {"total": heygen_counts.get(cid, 0)},
        })

    return {
        "companies": companies_out,
        "from": from_date,
        "to": to_date,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
    }
