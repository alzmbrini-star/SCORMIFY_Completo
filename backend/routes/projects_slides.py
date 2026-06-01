"""Slide and element routes.

Covers: create/update/delete slide, duplicate, reorder, normalize dimensions,
plus element CRUD (add/update/delete) within a slide.
"""
from fastapi import APIRouter, HTTPException, Depends
import uuid
import copy
import logging

from routes.deps import update_project, db, now_utc
from routes.auth import require_auth
from routes.projects_common import load_authorized_project
from models import (
    Slide, SlideCreate, SlideUpdate, SlideElement, ElementCreate, ElementUpdate,
    ReorderSlidesRequest
)

logger = logging.getLogger("server")

router = APIRouter(tags=["Projects - Slides"])


@router.post("/projects/{project_id}/slides")
async def create_slide(project_id: str, data: SlideCreate, user: dict = Depends(require_auth)):
    """Add a new slide to the project"""
    project = await load_authorized_project(project_id, user)
    course = project.get('course', {})
    slides = course.get('slides', [])

    # Get dimensions from first slide if not provided, to maintain consistency
    first_slide = slides[0] if slides else None
    slide_width = data.width or (first_slide.get('width') if first_slide else 1280)
    slide_height = data.height or (first_slide.get('height') if first_slide else 720)

    new_slide = Slide(
        title=data.title,
        background=data.background,
        width=slide_width,
        height=slide_height,
        order=len(slides)
    )

    slides.append(new_slide.model_dump())
    course['slides'] = slides

    await update_project(project_id, {"course": course})

    return new_slide.model_dump()


@router.put("/projects/{project_id}/slides/{slide_id}")
async def update_slide(project_id: str, slide_id: str, data: SlideUpdate, user: dict = Depends(require_auth)):
    """Update a slide"""
    project = await load_authorized_project(project_id, user)
    course = project.get('course', {})
    slides = course.get('slides', [])

    slide_index = next((i for i, s in enumerate(slides) if s.get('id') == slide_id), None)
    if slide_index is None:
        raise HTTPException(status_code=404, detail="Slide not found")

    update_data = data.model_dump(exclude_unset=True)
    slides[slide_index].update(update_data)
    course['slides'] = slides

    await update_project(project_id, {"course": course})

    return slides[slide_index]


@router.delete("/projects/{project_id}/slides/{slide_id}")
async def delete_slide(project_id: str, slide_id: str, user: dict = Depends(require_auth)):
    """Delete a slide"""
    project = await load_authorized_project(project_id, user)
    course = project.get('course', {})
    slides = course.get('slides', [])

    slides = [s for s in slides if s.get('id') != slide_id]

    # Re-order slides
    for i, slide in enumerate(slides):
        slide['order'] = i

    course['slides'] = slides
    await update_project(project_id, {"course": course})

    return {"message": "Slide deleted"}


@router.post("/projects/{project_id}/slides/{slide_id}/duplicate")
async def duplicate_slide(project_id: str, slide_id: str, user: dict = Depends(require_auth)):
    """Duplicate a slide"""
    project = await load_authorized_project(project_id, user)
    course = project.get('course', {})
    slides = course.get('slides', [])

    slide_index = next((i for i, s in enumerate(slides) if s.get('id') == slide_id), None)
    if slide_index is None:
        raise HTTPException(status_code=404, detail="Slide not found")

    # Deep copy the slide
    new_slide = copy.deepcopy(slides[slide_index])
    new_slide['id'] = str(uuid.uuid4())
    new_slide['title'] = f"{new_slide.get('title', 'Slide')} (copy)"
    new_slide['order'] = slide_index + 1

    # Insert after original
    slides.insert(slide_index + 1, new_slide)

    # Re-order subsequent slides
    for i in range(slide_index + 2, len(slides)):
        slides[i]['order'] = i

    course['slides'] = slides
    await update_project(project_id, {"course": course})

    return new_slide


@router.post("/projects/{project_id}/normalize-dimensions")
async def normalize_slide_dimensions(project_id: str, target_width: int = 1536, target_height: int = 864, user: dict = Depends(require_auth)):
    """Normalize all slides to the same dimensions, scaling elements proportionally"""
    project = await load_authorized_project(project_id, user)
    course = project.get('course', {})
    slides = course.get('slides', [])

    normalized_count = 0

    for slide in slides:
        current_width = slide.get('width', 1536)
        current_height = slide.get('height', 864)

        if current_width == target_width and current_height == target_height:
            continue

        scale_x = target_width / current_width
        scale_y = target_height / current_height

        slide['width'] = target_width
        slide['height'] = target_height

        for element in slide.get('elements', []):
            if 'x' in element:
                element['x'] = element['x'] * scale_x
            if 'y' in element:
                element['y'] = element['y'] * scale_y
            if 'width' in element:
                element['width'] = element['width'] * scale_x
            if 'height' in element:
                element['height'] = element['height'] * scale_y

        for annotation in slide.get('annotations', []):
            if 'points' in annotation:
                for point in annotation['points']:
                    if 'x' in point:
                        point['x'] = point['x'] * scale_x
                    if 'y' in point:
                        point['y'] = point['y'] * scale_y

        normalized_count += 1

    course['slides'] = slides
    await update_project(project_id, {"course": course})

    return {
        "message": f"Normalized {normalized_count} slides to {target_width}x{target_height}",
        "normalized_count": normalized_count,
        "target_dimensions": {"width": target_width, "height": target_height}
    }


@router.post("/projects/{project_id}/slides/reorder")
async def reorder_slides(project_id: str, data: ReorderSlidesRequest, user: dict = Depends(require_auth)):
    """Reorder slides"""
    project = await load_authorized_project(project_id, user)
    course = project.get('course', {})
    slides = course.get('slides', [])

    slide_map = {s['id']: s for s in slides}

    new_slides = []
    for i, slide_id in enumerate(data.slideIds):
        if slide_id in slide_map:
            slide = slide_map[slide_id]
            slide['order'] = i
            new_slides.append(slide)

    course['slides'] = new_slides
    await update_project(project_id, {"course": course})

    return {"message": "Slides reordered"}


# ---------------------------------------------------------------------------
# Element CRUD (within a slide)
# ---------------------------------------------------------------------------

@router.post("/projects/{project_id}/slides/{slide_id}/elements")
async def add_element(project_id: str, slide_id: str, data: ElementCreate, user: dict = Depends(require_auth)):
    """Add element to slide"""
    project = await load_authorized_project(project_id, user)
    course = project.get('course', {})
    slides = course.get('slides', [])

    slide_index = next((i for i, s in enumerate(slides) if s.get('id') == slide_id), None)
    if slide_index is None:
        raise HTTPException(status_code=404, detail="Slide not found")

    element_data = data.model_dump(exclude_unset=True)
    if 'style' not in element_data or element_data.get('style') is None:
        element_data['style'] = {}
    element = SlideElement(**element_data)
    elements = slides[slide_index].get('elements', [])
    element_dict = element.model_dump()
    element_dict['zIndex'] = len(elements)
    elements.append(element_dict)

    # Granular update (see update_element rationale).
    await db.projects.update_one(
        {"id": project_id},
        {"$set": {
            f"course.slides.{slide_index}.elements": elements,
            "updatedAt": now_utc().isoformat(),
        }},
    )

    return element_dict


@router.put("/projects/{project_id}/slides/{slide_id}/elements/{element_id}")
async def update_element(project_id: str, slide_id: str, element_id: str, data: ElementUpdate, user: dict = Depends(require_auth)):
    """Update element.

    Uses a granular `$set` on the specific array index so we never resend
    the whole course document to MongoDB on every keystroke save. Critical
    for projects with Faithful Mode (slides carrying multi-MB base64 PNGs)
    where the legacy full-course $set was causing 502 Bad Gateway in
    production (request > 100s Cloudflare timeout)."""
    project = await load_authorized_project(project_id, user)
    course = project.get('course', {})
    slides = course.get('slides', [])

    slide_index = next((i for i, s in enumerate(slides) if s.get('id') == slide_id), None)
    if slide_index is None:
        raise HTTPException(status_code=404, detail="Slide not found")

    elements = slides[slide_index].get('elements', [])
    elem_index = next((i for i, e in enumerate(elements) if e.get('id') == element_id), None)
    if elem_index is None:
        raise HTTPException(status_code=404, detail="Element not found")

    update_data = data.model_dump(exclude_unset=True)
    elements[elem_index].update(update_data)

    # Granular update — only the element + updatedAt. Mongo's positional
    # dotted-path $set keeps the request payload small (<= 1MB even for
    # heavy htmlContent) and lets Atlas finish in <100ms.
    await db.projects.update_one(
        {"id": project_id},
        {"$set": {
            f"course.slides.{slide_index}.elements.{elem_index}": elements[elem_index],
            "updatedAt": now_utc().isoformat(),
        }},
    )

    return elements[elem_index]


@router.delete("/projects/{project_id}/slides/{slide_id}/elements/{element_id}")
async def delete_element(project_id: str, slide_id: str, element_id: str, user: dict = Depends(require_auth)):
    """Delete element"""
    project = await load_authorized_project(project_id, user)
    course = project.get('course', {})
    slides = course.get('slides', [])

    slide_index = next((i for i, s in enumerate(slides) if s.get('id') == slide_id), None)
    if slide_index is None:
        raise HTTPException(status_code=404, detail="Slide not found")

    elements = slides[slide_index].get('elements', [])
    elements = [e for e in elements if e.get('id') != element_id]

    # Granular update (see update_element rationale).
    await db.projects.update_one(
        {"id": project_id},
        {"$set": {
            f"course.slides.{slide_index}.elements": elements,
            "updatedAt": now_utc().isoformat(),
        }},
    )

    return {"message": "Element deleted"}
