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
from services.html_legacy_normalizer import (
    has_legacy_font,
    normalize_legacy_html,
)

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



@router.post("/admin/normalize-font-tags")
async def normalize_font_tags(
    dryRun: bool = Query(default=True),
    user: dict = Depends(require_auth),
):
    """Walk every project and convert legacy HTML4 `<font color/face/size>`
    markup found in `course.slides[].elements[].htmlContent` into modern
    inline-CSS `<span style="…">` wrappers.

    Why this exists: the React `RichTextEditor` historically called
    `document.execCommand('foreColor', …)` without `styleWithCSS`, which
    on Chromium browsers emits `<font color="X">`. The Aesthetic Analyzer
    needs ONE consistent format to reason about contrast/typography.
    Going forward, the frontend now normalizes at save/paste time; this
    migration cleans the legacy DB rows.

    Default `dryRun=true` reports impact without writing. Only admins.
    Idempotent — safe to re-run.
    """
    role = user.get("role", "")
    if role not in ("super_admin", "admin", "company_admin"):
        raise HTTPException(status_code=403, detail="Admin only")

    scanned = 0
    mutated_projects = 0
    mutated_elements = 0
    sample = []  # cap at 20 for response size

    cursor = db.projects.find({}, {"_id": 0, "id": 1, "name": 1, "course.slides": 1})
    async for project in cursor:
        scanned += 1
        slides = ((project.get("course") or {}).get("slides")) or []
        project_changed_elements = 0

        for slide in slides:
            for el in (slide.get("elements") or []):
                if el.get("type") != "html":
                    continue
                html = el.get("htmlContent") or ""
                if not has_legacy_font(html):
                    continue
                cleaned = normalize_legacy_html(html)
                if cleaned != html:
                    el["htmlContent"] = cleaned
                    project_changed_elements += 1
                    mutated_elements += 1

        if project_changed_elements > 0:
            mutated_projects += 1
            if len(sample) < 20:
                sample.append({
                    "projectId": project.get("id"),
                    "name": (project.get("name") or "")[:80],
                    "elementsCleaned": project_changed_elements,
                })
            if not dryRun:
                try:
                    await db.projects.update_one(
                        {"id": project["id"]},
                        {"$set": {
                            "course.slides": slides,
                            "updatedAt": datetime.now(timezone.utc).isoformat(),
                        }},
                    )
                except Exception as e:
                    logger.error(
                        f"normalize_font_tags: write failed for {project.get('id')}: {e}"
                    )

    return {
        "dryRun": dryRun,
        "scannedProjects": scanned,
        "mutatedProjects": mutated_projects,
        "mutatedElements": mutated_elements,
        "sampleProjects": sample,
        "message": (
            f"DRY RUN: {mutated_projects}/{scanned} projetos teriam "
            f"{mutated_elements} elementos com <font> convertidos para CSS inline"
            if dryRun else
            f"OK: {mutated_projects}/{scanned} projetos limpos, "
            f"{mutated_elements} elementos modernizados"
        ),
    }



@router.post("/admin/cleanup-aesthetic-plates")
async def cleanup_aesthetic_plates(
    dryRun: bool = Query(default=True),
    user: dict = Depends(require_auth),
):
    """Strip every leftover `<style data-aesthetic-fix>` tag AND every
    `data-aesthetic-plate="1"` attribute marker from `htmlContent` in
    every project. Also removes `textBackgroundColor` / `padding` /
    `borderRadius` that the previous plate-injection version added to
    text element styles.

    Why this exists: the v3/v4/v5 plate overlay approach was rejected by
    the user — they want a no-overlay, swap-color-only behavior. This is
    a one-shot cleanup of historical plate artifacts that already landed
    in the DB before the v6 refactor.

    Default `dryRun=true` reports impact without writing. Admin only.
    Idempotent — safe to re-run.
    """
    import re as _re
    role = user.get("role", "")
    if role not in ("super_admin", "admin", "company_admin"):
        raise HTTPException(status_code=403, detail="Admin only")

    style_tag_re = _re.compile(
        r'<style\s+data-aesthetic-fix\s*=\s*[\"\']1[\"\']\s*>[\s\S]*?</style>',
        _re.IGNORECASE,
    )
    plate_attr_re = _re.compile(
        r'\s+data-aesthetic-plate\s*=\s*[\"\']1[\"\']',
        _re.IGNORECASE,
    )

    scanned = 0
    mutated_projects = 0
    mutated_elements = 0
    stripped_styles_total = 0
    sample = []

    cursor = db.projects.find({}, {"_id": 0, "id": 1, "name": 1, "course.slides": 1})
    async for project in cursor:
        scanned += 1
        slides = ((project.get("course") or {}).get("slides")) or []
        project_changed_elements = 0

        for slide in slides:
            for el in (slide.get("elements") or []):
                touched = False
                # 1. Clean htmlContent of plate artifacts
                if el.get("type") == "html":
                    html = el.get("htmlContent") or ""
                    if "data-aesthetic-fix" in html or "data-aesthetic-plate" in html:
                        new_html = style_tag_re.sub("", html)
                        new_html = plate_attr_re.sub("", new_html)
                        if new_html != html:
                            el["htmlContent"] = new_html
                            stripped_styles_total += 1
                            touched = True
                # 2. Clean text element styles of plate-related properties.
                # These keys were auto-set by the previous plate logic on
                # text elements over bgImage slides. They cause an ugly
                # opaque rectangle behind the text in the rendered slide.
                # We match BOTH:
                #   - semi-transparent rgba(...) plates (v4/v5 style)
                #   - SOLID dark hex on HTML elements (v3 style: e.g. textBackgroundColor='#0f172a'
                #     on a type=html element). Solid backgrounds on HTML elements are
                #     ALWAYS the rejected plate behaviour — the htmlContent already
                #     carries its own styling.
                style = el.get("style") or {}
                if isinstance(style, dict):
                    semi_transparent_rgba = _re.compile(
                        r"rgba\s*\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*,\s*0?\.\d+\s*\)",
                        _re.IGNORECASE,
                    )
                    for key in ("textBackgroundColor", "backgroundColor"):
                        v = style.get(key)
                        if not isinstance(v, str):
                            continue
                        is_plate = False
                        if semi_transparent_rgba.search(v):
                            is_plate = True
                        # On HTML elements, ANY non-transparent background was
                        # auto-injected by the legacy plate logic and creates
                        # the ugly opaque rectangle the user complained about.
                        elif el.get("type") == "html" and v.strip().lower() not in ("transparent", "none", "inherit", ""):
                            is_plate = True
                        if is_plate:
                            del style[key]
                            touched = True
                            # Drop padding/borderRadius/textShadow only when
                            # they accompany a removed plate (avoid touching
                            # intentional cosmetic style).
                            for related in ("padding", "borderRadius", "textShadow", "border"):
                                if related in style:
                                    del style[related]
                                    touched = True
                if touched:
                    project_changed_elements += 1
                    mutated_elements += 1

        if project_changed_elements > 0:
            mutated_projects += 1
            if len(sample) < 20:
                sample.append({
                    "projectId": project.get("id"),
                    "name": (project.get("name") or "")[:80],
                    "elementsCleaned": project_changed_elements,
                })
            if not dryRun:
                try:
                    await db.projects.update_one(
                        {"id": project["id"]},
                        {"$set": {
                            "course.slides": slides,
                            "updatedAt": datetime.now(timezone.utc).isoformat(),
                        }},
                    )
                except Exception as e:
                    logger.error(
                        f"cleanup_aesthetic_plates: write failed for {project.get('id')}: {e}"
                    )

    return {
        "dryRun": dryRun,
        "scannedProjects": scanned,
        "mutatedProjects": mutated_projects,
        "mutatedElements": mutated_elements,
        "strippedStyleTags": stripped_styles_total,
        "sampleProjects": sample,
        "message": (
            f"DRY RUN: {mutated_projects}/{scanned} projetos teriam "
            f"{mutated_elements} elementos limpos do overlay estetico"
            if dryRun else
            f"OK: {mutated_projects}/{scanned} projetos limpos, "
            f"{mutated_elements} elementos sem overlay"
        ),
    }



@router.post("/admin/strip-html-container-backgrounds")
async def strip_html_container_backgrounds_migration(
    dryRun: bool = Query(default=True),
    projectId: str = Query(default=""),
    user: dict = Depends(require_auth),
):
    """Strip "island plate" backgrounds from htmlContent wrappers.

    Targets the AI-Agent generated wrapper divs like
    `<div style="width:100%;height:100%;background:#3b82f6">` that paint
    a coloured rectangle behind slide content. When the user changes
    slide.background, those wrappers become disconnected coloured islands
    visually indistinguishable from rejected plate overlays.

    Body params:
      - `dryRun` (default True)
      - `projectId` — optional. When provided, only touches that project.

    Admin only. Idempotent.
    """
    from services.html_container_bg_stripper import strip_html_container_backgrounds

    role = user.get("role", "")
    if role not in ("super_admin", "admin", "company_admin"):
        raise HTTPException(status_code=403, detail="Admin only")

    query: dict = {}
    if projectId:
        query["id"] = projectId

    scanned = 0
    mutated_projects = 0
    mutated_elements = 0
    total_stripped = 0
    sample = []

    cursor = db.projects.find(query, {"_id": 0, "id": 1, "name": 1, "course.slides": 1})
    async for project in cursor:
        scanned += 1
        slides = ((project.get("course") or {}).get("slides")) or []
        project_changed_elements = 0

        for slide in slides:
            slide_bg = (slide.get("background") or "").strip() or None
            for el in (slide.get("elements") or []):
                if el.get("type") != "html":
                    continue
                html = el.get("htmlContent") or ""
                if not html:
                    continue
                new_html, stripped = strip_html_container_backgrounds(html, slide_bg)
                if stripped > 0 and new_html != html:
                    el["htmlContent"] = new_html
                    project_changed_elements += 1
                    mutated_elements += 1
                    total_stripped += stripped

        if project_changed_elements > 0:
            mutated_projects += 1
            if len(sample) < 20:
                sample.append({
                    "projectId": project.get("id"),
                    "name": (project.get("name") or "")[:80],
                    "elementsCleaned": project_changed_elements,
                })
            if not dryRun:
                try:
                    await db.projects.update_one(
                        {"id": project["id"]},
                        {"$set": {
                            "course.slides": slides,
                            "updatedAt": datetime.now(timezone.utc).isoformat(),
                        }},
                    )
                except Exception as e:
                    logger.error(
                        f"strip_html_container_backgrounds: write failed for {project.get('id')}: {e}"
                    )

    return {
        "dryRun": dryRun,
        "scannedProjects": scanned,
        "mutatedProjects": mutated_projects,
        "mutatedElements": mutated_elements,
        "totalContainersStripped": total_stripped,
        "sampleProjects": sample,
        "message": (
            f"DRY RUN: {mutated_projects}/{scanned} projetos teriam "
            f"{mutated_elements} elementos com {total_stripped} backgrounds de container removidos"
            if dryRun else
            f"OK: {mutated_projects}/{scanned} projetos limpos, "
            f"{mutated_elements} elementos com {total_stripped} backgrounds de container removidos"
        ),
    }
