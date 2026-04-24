"""Annotation routes: per-slide annotation create/update/delete."""
from fastapi import APIRouter, HTTPException, Depends
import logging

from routes.deps import update_project
from routes.auth import require_auth
from routes.projects_common import load_authorized_project
from models import Annotation, AnnotationCreate

logger = logging.getLogger("server")

router = APIRouter(tags=["Projects - Annotations"])


@router.post("/projects/{project_id}/slides/{slide_id}/annotations")
async def add_annotation(project_id: str, slide_id: str, data: AnnotationCreate, user: dict = Depends(require_auth)):
    """Add annotation to slide"""
    project = await load_authorized_project(project_id, user)
    course = project.get('course', {})
    slides = course.get('slides', [])

    slide_index = next((i for i, s in enumerate(slides) if s.get('id') == slide_id), None)
    if slide_index is None:
        raise HTTPException(status_code=404, detail="Slide not found")

    annotation = Annotation(**data.model_dump())
    annotations = slides[slide_index].get('annotations', [])
    annotations.append(annotation.model_dump())

    slides[slide_index]['annotations'] = annotations
    course['slides'] = slides

    await update_project(project_id, {"course": course})

    return annotation.model_dump()


@router.put("/projects/{project_id}/slides/{slide_id}/annotations/{annotation_id}")
async def update_annotation(project_id: str, slide_id: str, annotation_id: str, update_data: dict, user: dict = Depends(require_auth)):
    """Update annotation (for timeline settings)"""
    project = await load_authorized_project(project_id, user)
    course = project.get('course', {})
    slides = course.get('slides', [])

    slide_index = next((i for i, s in enumerate(slides) if s.get('id') == slide_id), None)
    if slide_index is None:
        raise HTTPException(status_code=404, detail="Slide not found")

    annotations = slides[slide_index].get('annotations', [])
    annotation_index = next((i for i, a in enumerate(annotations) if a.get('id') == annotation_id), None)
    if annotation_index is None:
        raise HTTPException(status_code=404, detail="Annotation not found")

    # Update annotation with new data
    for key, value in update_data.items():
        if value is not None:
            annotations[annotation_index][key] = value

    slides[slide_index]['annotations'] = annotations
    course['slides'] = slides

    await update_project(project_id, {"course": course})

    return annotations[annotation_index]


@router.delete("/projects/{project_id}/slides/{slide_id}/annotations/{annotation_id}")
async def delete_annotation(project_id: str, slide_id: str, annotation_id: str, user: dict = Depends(require_auth)):
    """Delete annotation"""
    project = await load_authorized_project(project_id, user)
    course = project.get('course', {})
    slides = course.get('slides', [])

    slide_index = next((i for i, s in enumerate(slides) if s.get('id') == slide_id), None)
    if slide_index is None:
        raise HTTPException(status_code=404, detail="Slide not found")

    annotations = slides[slide_index].get('annotations', [])
    annotations = [a for a in annotations if a.get('id') != annotation_id]

    slides[slide_index]['annotations'] = annotations
    course['slides'] = slides

    await update_project(project_id, {"course": course})

    return {"message": "Annotation deleted"}
