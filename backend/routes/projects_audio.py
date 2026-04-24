"""Audio routes: per-slide audio narration + project-wide soundtrack (global audio).

Also covers volume and timing (trim) adjustments.
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends
from pathlib import Path
import uuid
import logging
import aiofiles

from routes.deps import db, PROJECTS_DIR, update_project
from routes.auth import require_auth
from routes.projects_common import load_authorized_project

logger = logging.getLogger("server")

router = APIRouter(tags=["Projects - Audio"])


# ---------------------------------------------------------------------------
# Per-slide audio (narration / sfx)
# ---------------------------------------------------------------------------

@router.post("/projects/{project_id}/slides/{slide_id}/audio")
async def upload_slide_audio(
    project_id: str,
    slide_id: str,
    file: UploadFile = File(...),
    audio_type: str = Form("narration"),
    user: dict = Depends(require_auth),
):
    """Upload audio for a slide"""
    project = await load_authorized_project(project_id, user)
    if not file.filename.lower().endswith(('.mp3', '.wav', '.ogg', '.webm')):
        raise HTTPException(status_code=400, detail="Invalid audio format")

    content = await file.read()

    file_id = str(uuid.uuid4())
    ext = Path(file.filename).suffix.lower()
    filename = f"audio_{file_id}{ext}"
    file_path = PROJECTS_DIR / project_id / "assets" / filename
    file_path.parent.mkdir(parents=True, exist_ok=True)

    async with aiofiles.open(file_path, 'wb') as f:
        await f.write(content)

    # Persist in MongoDB for production environments with ephemeral storage
    try:
        from services.asset_store import store_asset_async
        await store_asset_async(db, project_id, filename, str(file_path))
    except Exception as e:
        logger.warning(f"Failed to persist audio in MongoDB (non-fatal): {e}")

    course = project.get('course', {})
    slides = course.get('slides', [])

    slide_index = next((i for i, s in enumerate(slides) if s.get('id') == slide_id), None)
    if slide_index is None:
        raise HTTPException(status_code=404, detail="Slide not found")

    audio_data = {
        "id": file_id,
        "type": audio_type,
        "src": f"/api/projects/{project_id}/assets/{filename}",
        "filename": filename,
        "duration": 0,
        "volume": 1.0
    }

    audio_list = slides[slide_index].get('audio', [])
    audio_list.append(audio_data)
    slides[slide_index]['audio'] = audio_list

    course['slides'] = slides
    await update_project(project_id, {"course": course})

    return audio_data


@router.delete("/projects/{project_id}/slides/{slide_id}/audio/{audio_id}")
async def remove_slide_audio(project_id: str, slide_id: str, audio_id: str, user: dict = Depends(require_auth)):
    """Remove audio from slide"""
    project = await load_authorized_project(project_id, user)
    course = project.get('course', {})
    slides = course.get('slides', [])

    slide_index = next((i for i, s in enumerate(slides) if s.get('id') == slide_id), None)
    if slide_index is None:
        raise HTTPException(status_code=404, detail="Slide not found")

    audio_list = slides[slide_index].get('audio', [])

    audio_to_remove = next((a for a in audio_list if a.get('id') == audio_id), None)
    if not audio_to_remove:
        raise HTTPException(status_code=404, detail="Audio not found")

    if audio_to_remove.get('filename'):
        assets_dir = Path(f"storage/projects/{project_id}/assets")
        audio_path = assets_dir / audio_to_remove['filename']
        if audio_path.exists():
            audio_path.unlink()

    slides[slide_index]['audio'] = [a for a in audio_list if a.get('id') != audio_id]
    course['slides'] = slides

    await update_project(project_id, {"course": course})

    return {"message": "Audio removed from slide"}


@router.put("/projects/{project_id}/slides/{slide_id}/audio/{audio_id}/volume")
async def update_slide_audio_volume(project_id: str, slide_id: str, audio_id: str, volume: float, user: dict = Depends(require_auth)):
    """Update slide audio volume"""
    project = await load_authorized_project(project_id, user)
    course = project.get('course', {})
    slides = course.get('slides', [])

    slide_index = next((i for i, s in enumerate(slides) if s.get('id') == slide_id), None)
    if slide_index is None:
        raise HTTPException(status_code=404, detail="Slide not found")

    audio_list = slides[slide_index].get('audio', [])
    audio_index = next((i for i, a in enumerate(audio_list) if a.get('id') == audio_id), None)
    if audio_index is None:
        raise HTTPException(status_code=404, detail="Audio not found")

    volume = max(0.0, min(1.0, volume))
    audio_list[audio_index]['volume'] = volume
    slides[slide_index]['audio'] = audio_list
    course['slides'] = slides

    await update_project(project_id, {"course": course})

    return audio_list[audio_index]


@router.put("/projects/{project_id}/slides/{slide_id}/audio/{audio_id}/timing")
async def update_slide_audio_timing(project_id: str, slide_id: str, audio_id: str, data: dict, user: dict = Depends(require_auth)):
    """Update slide audio timing (startTime and duration for trimming)"""
    project = await load_authorized_project(project_id, user)
    course = project.get('course', {})
    slides = course.get('slides', [])

    slide_index = next((i for i, s in enumerate(slides) if s.get('id') == slide_id), None)
    if slide_index is None:
        raise HTTPException(status_code=404, detail="Slide not found")

    audio_list = slides[slide_index].get('audio', [])
    audio_index = next((i for i, a in enumerate(audio_list) if a.get('id') == audio_id), None)
    if audio_index is None:
        raise HTTPException(status_code=404, detail="Audio not found")

    # Store original duration if not already stored
    if 'originalDuration' not in audio_list[audio_index]:
        audio_list[audio_index]['originalDuration'] = audio_list[audio_index].get('duration', 10)

    if data.get('startTime') is not None:
        audio_list[audio_index]['startTime'] = max(0, data['startTime'])
    if data.get('duration') is not None:
        audio_list[audio_index]['duration'] = max(0.5, data['duration'])

    slides[slide_index]['audio'] = audio_list
    course['slides'] = slides

    await update_project(project_id, {"course": course})

    return audio_list[audio_index]


# ---------------------------------------------------------------------------
# Global audio (soundtrack for the whole course)
# ---------------------------------------------------------------------------

@router.post("/projects/{project_id}/global-audio")
async def set_global_audio(project_id: str, file: UploadFile = File(...), user: dict = Depends(require_auth)):
    """Set global soundtrack for the course"""
    project = await load_authorized_project(project_id, user)
    if not file.filename.lower().endswith(('.mp3', '.wav', '.ogg')):
        raise HTTPException(status_code=400, detail="Invalid audio format")

    content = await file.read()

    file_id = str(uuid.uuid4())
    ext = Path(file.filename).suffix.lower()
    filename = f"global_audio_{file_id}{ext}"
    file_path = PROJECTS_DIR / project_id / "assets" / filename
    file_path.parent.mkdir(parents=True, exist_ok=True)

    async with aiofiles.open(file_path, 'wb') as f:
        await f.write(content)

    # Persist in MongoDB for production environments with ephemeral storage
    try:
        from services.asset_store import store_asset_async
        await store_asset_async(db, project_id, filename, str(file_path))
    except Exception as e:
        logger.warning(f"Failed to persist global audio in MongoDB (non-fatal): {e}")

    global_audio = {
        "id": file_id,
        "src": f"/api/projects/{project_id}/assets/{filename}",
        "filename": filename,
        "duration": 0,
        "volume": 0.5,
        "loop": True
    }

    course = project.get('course', {})
    course['globalAudio'] = global_audio

    await update_project(project_id, {"course": course})

    return global_audio


@router.delete("/projects/{project_id}/global-audio")
async def remove_global_audio(project_id: str, user: dict = Depends(require_auth)):
    """Remove global audio from project"""
    project = await load_authorized_project(project_id, user)
    course = project.get('course', {})

    if course.get('globalAudio'):
        old_file = course['globalAudio'].get('filename')
        if old_file:
            assets_dir = Path(f"storage/projects/{project_id}/assets")
            old_path = assets_dir / old_file
            if old_path.exists():
                old_path.unlink()

    course['globalAudio'] = None
    await update_project(project_id, {"course": course})

    return {"message": "Global audio removed"}


@router.put("/projects/{project_id}/global-audio/volume")
async def update_global_audio_volume(project_id: str, volume: float, user: dict = Depends(require_auth)):
    """Update global audio volume"""
    project = await load_authorized_project(project_id, user)
    course = project.get('course', {})
    if not course.get('globalAudio'):
        raise HTTPException(status_code=404, detail="No global audio set")

    volume = max(0.0, min(1.0, volume))
    course['globalAudio']['volume'] = volume

    await update_project(project_id, {"course": course})

    return course['globalAudio']
