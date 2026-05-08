"""One-shot data normalization for legacy / PPT-imported projects.

Walks every project in `db.projects` and coerces sloppy numeric fields
(strings like "1280", "1280px", floats stored where ints are expected) to
their canonical types. Preventive cleanup so the schema is consistent
before future Pydantic validators get stricter.

Endpoints:
- POST /api/admin/normalize-numeric-fields?dryRun=true (default)
  → returns a report of what WOULD change without writing anything
- POST /api/admin/normalize-numeric-fields?dryRun=false
  → applies the normalization, returns counts
"""
import re
import logging
from typing import Optional, Tuple
from fastapi import APIRouter, HTTPException, Depends, Query
from datetime import datetime, timezone

from routes.deps import db
from routes.auth import require_auth

logger = logging.getLogger("server")
router = APIRouter(tags=["Admin - Migrations"])


# Fields that should always be int
INT_FIELDS_SLIDE = ("width", "height", "order")
INT_FIELDS_ELEMENT = ()  # element width/height etc are float-ok
# Fields that should be float (accept int)
FLOAT_FIELDS_SLIDE = ("duration",)
FLOAT_FIELDS_ELEMENT = ("x", "y", "width", "height", "rotation", "zIndex")
FLOAT_FIELDS_STYLE = (
    "fontSize", "strokeWidth", "borderRadius", "opacity", "letterSpacing", "lineHeight",
)
FLOAT_FIELDS_AUDIO = ("volume", "duration", "startTime", "endTime")


def _coerce_to_int(v) -> Tuple[Optional[int], bool]:
    """Coerce any value to int. Returns (value, changed_flag)."""
    if v is None:
        return None, False
    if isinstance(v, bool):
        return v, False  # don't touch booleans
    if isinstance(v, int):
        return v, False
    if isinstance(v, float):
        return int(v), True
    if isinstance(v, str):
        m = re.search(r"-?\d+", v)
        if m:
            try:
                return int(m.group()), True
            except (ValueError, OverflowError):
                return None, False
    return None, False


def _coerce_to_float(v) -> Tuple[Optional[float], bool]:
    """Coerce any value to float. Returns (value, changed_flag)."""
    if v is None:
        return None, False
    if isinstance(v, bool):
        return v, False
    if isinstance(v, (int, float)):
        return float(v), isinstance(v, int)  # changed if was int (type widened)
    if isinstance(v, str):
        m = re.search(r"-?\d+(?:\.\d+)?", v)
        if m:
            try:
                return float(m.group()), True
            except (ValueError, OverflowError):
                return None, False
    return None, False


def _normalize_dict_in_place(d: dict, int_keys: tuple, float_keys: tuple) -> int:
    """Walk a dict and coerce specified keys. Returns number of changes."""
    changes = 0
    if not isinstance(d, dict):
        return 0
    for k in int_keys:
        if k in d and d[k] is not None:
            new_v, changed = _coerce_to_int(d[k])
            if changed and new_v is not None:
                d[k] = new_v
                changes += 1
    for k in float_keys:
        if k in d and d[k] is not None:
            new_v, changed = _coerce_to_float(d[k])
            if changed and new_v is not None:
                d[k] = new_v
                changes += 1
    return changes


def _normalize_project_inplace(project: dict) -> dict:
    """Mutate a project document and return a per-section change count.
    The project's `course.slides` tree is normalized."""
    breakdown = {
        "slide_dims": 0,
        "slide_durations": 0,
        "element_pos_size": 0,
        "element_styles": 0,
        "audio_props": 0,
        "annotation_pos": 0,
    }

    course = project.get("course") or {}
    slides = course.get("slides") or []
    if not isinstance(slides, list):
        return breakdown

    for slide in slides:
        if not isinstance(slide, dict):
            continue
        breakdown["slide_dims"] += _normalize_dict_in_place(slide, INT_FIELDS_SLIDE, ())
        breakdown["slide_durations"] += _normalize_dict_in_place(slide, (), FLOAT_FIELDS_SLIDE)

        elements = slide.get("elements") or []
        if isinstance(elements, list):
            for el in elements:
                if not isinstance(el, dict):
                    continue
                breakdown["element_pos_size"] += _normalize_dict_in_place(
                    el, (), FLOAT_FIELDS_ELEMENT
                )
                style = el.get("style")
                if isinstance(style, dict):
                    breakdown["element_styles"] += _normalize_dict_in_place(
                        style, (), FLOAT_FIELDS_STYLE
                    )

        audios = slide.get("audio") or []
        if isinstance(audios, list):
            for a in audios:
                if not isinstance(a, dict):
                    continue
                breakdown["audio_props"] += _normalize_dict_in_place(a, (), FLOAT_FIELDS_AUDIO)

        annotations = slide.get("annotations") or []
        if isinstance(annotations, list):
            for ann in annotations:
                if not isinstance(ann, dict):
                    continue
                breakdown["annotation_pos"] += _normalize_dict_in_place(
                    ann, (), FLOAT_FIELDS_ELEMENT
                )

    return breakdown


@router.post("/admin/normalize-numeric-fields")
async def normalize_numeric_fields(
    dryRun: bool = Query(default=True),
    user: dict = Depends(require_auth),
):
    """One-shot migration: coerce sloppy numeric fields across every
    project in the DB to canonical int/float types.

    Default `dryRun=true` returns a report without writing. Set
    `dryRun=false` to apply.

    Only super_admin or company_admin can run this.
    """
    role = user.get("role", "")
    if role not in ("super_admin", "admin", "company_admin"):
        raise HTTPException(status_code=403, detail="Admin only")

    cursor = db.projects.find({}, {"_id": 0, "id": 1, "name": 1, "course": 1})
    total = 0
    fixed = 0
    aggregate = {
        "slide_dims": 0,
        "slide_durations": 0,
        "element_pos_size": 0,
        "element_styles": 0,
        "audio_props": 0,
        "annotation_pos": 0,
    }
    fixed_projects = []

    async for project in cursor:
        total += 1
        breakdown = _normalize_project_inplace(project)
        project_total = sum(breakdown.values())
        if project_total > 0:
            fixed += 1
            for k, v in breakdown.items():
                aggregate[k] += v
            if len(fixed_projects) < 50:  # cap report size
                fixed_projects.append({
                    "projectId": project.get("id"),
                    "name": (project.get("name") or "")[:80],
                    "totalChanges": project_total,
                    "breakdown": {k: v for k, v in breakdown.items() if v > 0},
                })

            # Apply write if not dry-run
            if not dryRun:
                try:
                    await db.projects.update_one(
                        {"id": project["id"]},
                        {"$set": {
                            "course.slides": project["course"]["slides"],
                            "updatedAt": datetime.now(timezone.utc).isoformat(),
                        }}
                    )
                except Exception as e:
                    logger.error(
                        f"normalize_numeric_fields: write failed for {project.get('id')}: {e}"
                    )

    return {
        "dryRun": dryRun,
        "scanned": total,
        "fixedProjects": fixed,
        "totalFieldsCoerced": sum(aggregate.values()),
        "breakdown": aggregate,
        "sampleProjects": fixed_projects,
        "message": (
            f"DRY RUN: {fixed}/{total} projetos teriam {sum(aggregate.values())} campos corrigidos"
            if dryRun else
            f"OK: {fixed}/{total} projetos atualizados, {sum(aggregate.values())} campos coercidos"
        ),
    }
