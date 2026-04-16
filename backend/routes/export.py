"""Export routes (SCORM, HTML, Video) and asset serving"""
from fastapi import APIRouter, HTTPException, Request, BackgroundTasks
from fastapi.responses import FileResponse
from typing import Optional
from pathlib import Path
from datetime import datetime, timezone
import uuid
import os
import re
import io
import asyncio
import logging

from routes.deps import (
    db, now_utc, get_project_by_id, update_project,
    PROJECTS_DIR, STORAGE_DIR, EXPORTS_DIR, exports_bucket, jobs,
    create_job, update_job, get_job
)
from models import Project

logger = logging.getLogger("server")

router = APIRouter(tags=["Export"])


def _get_external_url(request: Request = None) -> str:
    """Get the external-facing URL for the app.
    Priority: X-Forwarded headers > Referer > BASE_URL > REACT_APP_BACKEND_URL.
    Using request headers ensures production exports use the production URL."""
    from urllib.parse import urlparse
    
    if request:
        # Try 1: X-Forwarded-Host + X-Forwarded-Proto (set by Kubernetes ingress/proxy)
        fwd_host = (request.headers.get('x-forwarded-host') or '').strip()
        fwd_proto = (request.headers.get('x-forwarded-proto') or 'https').strip()
        if fwd_host:
            return f"{fwd_proto}://{fwd_host}"
        
        # Try 2: Referer header (preserved through proxy)
        referer = (request.headers.get('referer') or '').strip()
        if referer and referer.startswith('http'):
            parsed = urlparse(referer)
            if parsed.scheme and parsed.netloc:
                return f"{parsed.scheme}://{parsed.netloc}"
    
    # Try 3: backend .env BASE_URL
    try:
        backend_env = Path(__file__).parent.parent / '.env'
        for line in backend_env.read_text().splitlines():
            if line.startswith('BASE_URL='):
                val = line.split('=', 1)[1].strip().strip('"').strip("'")
                if val:
                    return val
    except Exception:
        pass
    
    # Try 4: frontend .env REACT_APP_BACKEND_URL
    try:
        frontend_env = Path(__file__).parent.parent.parent / 'frontend' / '.env'
        for line in frontend_env.read_text().splitlines():
            if line.startswith('REACT_APP_BACKEND_URL='):
                val = line.split('=', 1)[1].strip().strip('"').strip("'")
                if val:
                    return val
    except Exception:
        pass
    
    # Try 5: os.environ fallback
    return os.environ.get('BASE_URL', '') or os.environ.get('REACT_APP_BACKEND_URL', '')


def _cleanup_old_exports(exports_dir: str, max_age_hours: int = 24):
    import time
    exports_path = Path(exports_dir)
    if not exports_path.exists():
        return
    cutoff = time.time() - max_age_hours * 3600
    removed = 0
    for f in exports_path.iterdir():
        if f.is_file() and f.stat().st_mtime < cutoff:
            try:
                f.unlink()
                removed += 1
            except Exception:
                pass
    if removed:
        logger.info(f"Cleaned up {removed} old export files from {exports_dir}")


async def save_export_to_gridfs(file_path: str, filename: str):
    try:
        cursor = exports_bucket.find({"filename": filename})
        async for grid_file in cursor:
            await exports_bucket.delete(grid_file._id)
        with open(file_path, "rb") as f:
            data = f.read()
        await exports_bucket.upload_from_stream(filename, io.BytesIO(data))
        logger.info(f"Saved export to GridFS: {filename} ({len(data)} bytes)")
    except Exception as e:
        logger.warning(f"GridFS save failed (non-fatal): {e}")


async def get_export_from_gridfs(filename: str, dest_path: str) -> bool:
    try:
        cursor = exports_bucket.find({"filename": filename}, limit=1).sort("uploadDate", -1)
        grid_file = await cursor.next()
        stream = await exports_bucket.open_download_stream(grid_file._id)
        data = await stream.read()
        Path(dest_path).parent.mkdir(parents=True, exist_ok=True)
        with open(dest_path, "wb") as f:
            f.write(data)
        logger.info(f"Restored export from GridFS: {filename} ({len(data)} bytes)")
        return True
    except StopAsyncIteration:
        return False
    except Exception as e:
        logger.warning(f"GridFS retrieve failed: {e}")
        return False


# SCORM Export


@router.post("/course/{project_id}/export-scorm")
async def export_scorm(project_id: str, request: Request, background_tasks: BackgroundTasks):
    """Export project as SCORM 1.2 package"""
    project_doc = await get_project_by_id(project_id)
    if not project_doc:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Create job
    job_id = str(uuid.uuid4())
    job_data = {
        'id': job_id,
        'status': 'processing',
        'progress': 0,
        'message': 'Generating SCORM package...',
        'result': None
    }
    jobs[job_id] = job_data
    await create_job(job_id, job_data)
    
    try:
        # Convert dict to Project model
        project = Project(**project_doc)
        
        # Collect all question IDs from quiz elements in the course
        question_ids = set()
        for slide in project.course.slides:
            for element in slide.elements:
                if element.type == 'quiz' and hasattr(element, 'quizConfig'):
                    quiz_config = element.quizConfig
                    if quiz_config and isinstance(quiz_config, dict):
                        question_ids.update(quiz_config.get('questionIds', []))
        
        # Load questions from database if there are quiz elements
        questions = []
        if question_ids:
            question_docs = await db.questions.find(
                {"id": {"$in": list(question_ids)}},
                {"_id": 0}
            ).to_list(500)
            questions = question_docs
            logger.info(f"Loaded {len(questions)} questions for SCORM export")
        
        # Load tutor settings
        tutor_settings = None
        try:
            settings_doc = await db.settings.find_one({"key": "tutor"}, {"_id": 0})
            if settings_doc and settings_doc.get("enabled"):
                # Always use current environment URL to avoid stale URLs from previous forks
                backend_url = _get_external_url(request) or settings_doc.get('apiUrl', '').strip()
                
                tutor_settings = {
                    'enabled': True,
                    'apiUrl': backend_url,
                    'tutorName': settings_doc.get('tutorName', 'Tutor IA'),
                    'messageLimit': settings_doc.get('messageLimit', 50),
                    'suggestedQuestions': settings_doc.get('suggestedQuestions', []),
                    'courseTopic': project.course.metadata.title or project.name
                }
        except Exception as e:
            logger.warning(f"Tutor settings load failed (non-fatal): {e}")
        
        # Load gamification config
        gamification_settings = None
        try:
            gamification_doc = await db.projects.find_one({"id": project_id}, {"_id": 0, "gamification": 1})
            if gamification_doc and gamification_doc.get("gamification"):
                gamification_settings = gamification_doc["gamification"]
            else:
                # Use defaults if not configured
                from models import DEFAULT_BADGES, DEFAULT_QUIZ_FEEDBACK, DEFAULT_SCENARIO_FEEDBACK
                gamification_settings = {
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
        except Exception as e:
            logger.warning(f"Gamification settings load failed (non-fatal): {e}")

        # Generate package with questions
        # Run in thread pool to avoid blocking the async event loop
        # (export_scorm_package is a CPU+IO intensive synchronous function)
        from services.scorm_exporter import export_scorm_package
        import asyncio
        
        # Use reliable external URL for VLibras proxy
        scorm_backend_url = _get_external_url(request)
        
        zip_path = await asyncio.to_thread(
            export_scorm_package,
            project,
            str(PROJECTS_DIR),
            str(EXPORTS_DIR),
            questions=questions,
            tutor_config=tutor_settings,
            backend_url=scorm_backend_url,
            gamification_config=gamification_settings
        )
        
        # Clean up old exports to prevent disk space exhaustion (keep last 24h)
        try:
            await asyncio.to_thread(_cleanup_old_exports, str(EXPORTS_DIR))
        except Exception as cleanup_err:
            logger.warning(f"Export cleanup failed (non-fatal): {cleanup_err}")
        
        # Persist to GridFS in background (don't block the response)
        export_filename = Path(zip_path).name
        background_tasks.add_task(save_export_to_gridfs, zip_path, export_filename)
        
        jobs[job_id]['status'] = 'completed'
        jobs[job_id]['progress'] = 100
        jobs[job_id]['message'] = 'SCORM package ready'
        jobs[job_id]['result'] = {
            'downloadUrl': f"/api/exports/{export_filename}"
        }
        await update_job(job_id, jobs[job_id])
        
        # Log export for metrics
        try:
            await db.export_logs.insert_one({
                "projectId": project_id,
                "type": "scorm",
                "filename": export_filename,
                "createdAt": datetime.now(timezone.utc).isoformat(),
            })
        except Exception:
            pass
        
        return {
            "jobId": job_id,
            "downloadUrl": f"/api/exports/{export_filename}"
        }
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logger.error(f"SCORM export error: {e}")
        logger.error(f"SCORM export traceback: {error_details}")
        jobs[job_id]['status'] = 'failed'
        jobs[job_id]['message'] = str(e)
        await update_job(job_id, {'status': 'failed', 'message': str(e)})
        raise HTTPException(status_code=500, detail=f"SCORM export failed: {str(e)}")

# HTML Standalone Export

@router.post("/course/{project_id}/export-html")
async def export_html(project_id: str, request: Request, background_tasks: BackgroundTasks):
    """Export project as standalone HTML file"""
    project_doc = await get_project_by_id(project_id)
    if not project_doc:
        raise HTTPException(status_code=404, detail="Project not found")
    
    try:
        from services.html_exporter import generate_standalone_html
        # Get assets directory
        assets_dir = str(PROJECTS_DIR / project_id / "assets")
        
        # Get base URL for external assets
        base_url = _get_external_url(request)
        
        # Collect question IDs from quiz elements
        question_ids = set()
        course_data = project_doc.get('course', {})
        for slide in course_data.get('slides', []):
            for element in slide.get('elements', []):
                if element.get('type') == 'quiz' and element.get('quizConfig'):
                    quiz_config = element.get('quizConfig')
                    if quiz_config and isinstance(quiz_config, dict):
                        question_ids.update(quiz_config.get('questionIds', []))
        
        # Load questions from database if there are quiz elements
        questions = []
        if question_ids:
            question_docs = await db.questions.find(
                {"id": {"$in": list(question_ids)}},
                {"_id": 0}
            ).to_list(500)
            questions = question_docs
            logger.info(f"Loaded {len(questions)} questions for HTML export")
        
        # Load tutor settings for HTML export
        tutor_settings = None
        try:
            settings_doc = await db.settings.find_one({"key": "tutor"}, {"_id": 0})
            if settings_doc and settings_doc.get("enabled"):
                # Use reliable external URL (reads directly from .env files)
                html_backend_url = _get_external_url(request)
                
                # Build course context from slide content
                course_context_parts = []
                for slide in course_data.get('slides', []):
                    slide_title = slide.get('title', '')
                    elements_text = []
                    for el in slide.get('elements', []):
                        if el.get('type') == 'text' and el.get('content'):
                            elements_text.append(el['content'])
                        elif el.get('type') == 'html' and el.get('htmlContent'):
                            import re as re_mod
                            clean = re_mod.sub(r'<[^>]+>', '', el['htmlContent'])
                            if clean.strip():
                                elements_text.append(clean.strip())
                    notes = slide.get('notes', '')
                    libras = slide.get('librasScript', '')
                    parts = [f"Slide: {slide_title}"] if slide_title else []
                    if elements_text:
                        parts.append("Conteudo: " + " | ".join(elements_text))
                    if notes:
                        parts.append(f"Notas: {notes}")
                    if libras:
                        parts.append(f"Narracao: {libras}")
                    if parts:
                        course_context_parts.append("\n".join(parts))
                
                tutor_settings = {
                    'enabled': True,
                    'apiUrl': html_backend_url,
                    'tutorName': settings_doc.get('tutorName', 'Tutor IA'),
                    'messageLimit': settings_doc.get('messageLimit', 50),
                    'suggestedQuestions': settings_doc.get('suggestedQuestions', []),
                    'courseTopic': course_data.get('metadata', {}).get('title', '') or project_doc.get('name', ''),
                    'courseContext': "\n---\n".join(course_context_parts)[:8000]
                }
                
                # Build per-slide contexts for slide-aware tutoring
                per_slide_contexts = []
                for slide in course_data.get('slides', []):
                    elements_text = []
                    for el in slide.get('elements', []):
                        raw = el.get('content') or el.get('htmlContent') or el.get('text') or ''
                        if raw:
                            clean = re.sub(r'<[^>]+>', ' ', raw).strip()
                            clean = re.sub(r'\s+', ' ', clean)
                            if clean:
                                elements_text.append(clean[:500])
                        btn_text = el.get('buttonText')
                        if btn_text:
                            elements_text.append(btn_text)
                    notes = slide.get('notes', '')
                    libras = slide.get('librasScript', '')
                    if notes:
                        elements_text.append(f"Notas: {notes}")
                    if libras:
                        elements_text.append(f"Narracao: {libras}")
                    per_slide_contexts.append(" | ".join(elements_text) if elements_text else '')
                tutor_settings['slideContexts'] = per_slide_contexts
        except Exception as e:
            logger.warning(f"Tutor settings load for HTML export failed (non-fatal): {e}")
        
        # Generate HTML with questions and tutor
        html_content = await generate_standalone_html(
            project_doc,
            assets_dir,
            base_url,
            questions=questions,
            backend_url=base_url,
            tutor_config=tutor_settings
        )
        
        # Save HTML file
        project_name = project_doc.get('name', 'course')
        safe_name = re.sub(r'[^\w\s-]', '', project_name).replace(' ', '_')
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{safe_name}_{timestamp}.html"
        
        html_path = EXPORTS_DIR / filename
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        # Persist to GridFS in background (don't block the response)
        background_tasks.add_task(save_export_to_gridfs, str(html_path), filename)
        
        # Log export for metrics
        try:
            await db.export_logs.insert_one({
                "projectId": project_id,
                "type": "html",
                "filename": filename,
                "createdAt": datetime.now(timezone.utc).isoformat(),
            })
        except Exception:
            pass
        
        return {
            "downloadUrl": f"/api/exports/{filename}",
            "filename": filename,
            "message": "HTML standalone file generated successfully"
        }
        
    except Exception as e:
        logger.error(f"HTML export error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Video Export - Client-Side Approach (generates slide images, frontend creates video)


@router.get("/course/{project_id}/slides-data")
async def get_slides_data(project_id: str, default_duration: float = 5.0):
    """Return raw slide data for client-side rendering with html2canvas.
    Much lighter than export-video-frames (no PIL image generation).
    The browser renders the slides itself, producing WYSIWYG output."""

    project_doc = await get_project_by_id(project_id)
    if not project_doc:
        raise HTTPException(status_code=404, detail="Project not found")

    course = project_doc.get('course', {})
    slides = course.get('slides', [])
    if not slides:
        raise HTTPException(status_code=400, detail="No slides")

    proj_id = project_doc.get('id', '')
    result_slides = []

    for idx, slide in enumerate(slides):
        duration = slide.get('duration', default_duration) or default_duration

        # Resolve asset URLs for background image
        bg_image = slide.get('backgroundImage', '')
        if bg_image and not bg_image.startswith('http'):
            if bg_image.startswith('/api/'):
                pass  # Frontend will prepend apiUrl
            elif bg_image.startswith('assets/'):
                bg_image = f"/api/projects/{proj_id}/assets/{bg_image.replace('assets/', '')}"

        # Resolve element asset URLs
        elements = []
        for el in slide.get('elements', []):
            el_copy = dict(el)
            src = el_copy.get('src', '')
            if src and not src.startswith('http'):
                if src.startswith('/api/'):
                    pass
                elif src.startswith('assets/'):
                    el_copy['src'] = f"/api/projects/{proj_id}/assets/{src.replace('assets/', '')}"
            elements.append(el_copy)

        # Collect video elements for overlay
        video_elements = []
        slide_w = slide.get('width', 1920)
        slide_h = slide.get('height', 1080)
        for el in elements:
            if el.get('type') == 'video' and el.get('src'):
                video_elements.append({
                    'src': el['src'],
                    'x': el.get('x', 0),
                    'y': el.get('y', 0),
                    'width': el.get('width', 200),
                    'height': el.get('height', 200),
                })

        # Collect audio elements
        audio_items = []
        for aud in slide.get('audio', []):
            # Audio source can be in 'src' or 'url' field (legacy format)
            src = aud.get('src', '') or aud.get('url', '')
            if not src:
                continue
            if not src.startswith('http') and not src.startswith('/api/'):
                if src.startswith('assets/'):
                    src = f"/api/projects/{proj_id}/assets/{src.replace('assets/', '')}"
            audio_items.append({
                'src': src,
                'startTime': float(aud.get('startTime', 0)),
                'volume': float(aud.get('volume', 1.0)),
            })

        result_slides.append({
            'index': idx,
            'width': slide_w,
            'height': slide_h,
            'duration': max(2.0, float(duration)),
            'background': slide.get('background', '#FFFFFF'),
            'backgroundImage': bg_image,
            'elements': elements,
            'videoElements': video_elements,
            'audioElements': audio_items,
        })

    # Global audio
    global_audio = None
    ga = course.get('globalAudio', {})
    if ga and ga.get('src'):
        ga_src = ga['src']
        if not ga_src.startswith('http') and not ga_src.startswith('/api/'):
            if ga_src.startswith('assets/'):
                ga_src = f"/api/projects/{proj_id}/assets/{ga_src.replace('assets/', '')}"
        global_audio = {
            'src': ga_src,
            'volume': float(ga.get('volume', 0.5)),
            'loop': ga.get('loop', True),
        }

    return {
        'projectName': project_doc.get('name', 'course'),
        'slides': result_slides,
        'globalAudio': global_audio,
        'totalSlides': len(slides),
    }


@router.post("/course/{project_id}/export-video-frames")
async def export_video_frames(project_id: str, request: Request):
    """Return all slide images as base64 for client-side video generation.
    Also includes video element metadata (HeyGen, YouTube) for overlay.
    This avoids FFmpeg on the server — the browser creates the video using Canvas + MediaRecorder."""
    import base64

    project_doc = await get_project_by_id(project_id)
    if not project_doc:
        raise HTTPException(status_code=404, detail="Project not found")

    body = await request.json()
    default_duration = float(body.get('default_duration', 5.0))

    course = project_doc.get('course', {})
    slides = course.get('slides', [])
    if not slides:
        raise HTTPException(status_code=400, detail="No slides to export")

    try:
        from services.video_exporter import create_slide_base_image
        from PIL import Image
        import tempfile

        canvas_w, canvas_h = 1280, 720
        frames = []

        for idx, slide in enumerate(slides):
            slide_w = slide.get('width', 1920)
            slide_h = slide.get('height', 1080)
            ratio = min(canvas_w / slide_w, canvas_h / slide_h)
            target_w = int(slide_w * ratio)
            target_h = int(slide_h * ratio)
            target_w = target_w if target_w % 2 == 0 else target_w + 1
            target_h = target_h if target_h % 2 == 0 else target_h + 1

            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                tmp_path = tmp.name

            await asyncio.to_thread(
                create_slide_base_image,
                slide, project_doc.get('id', ''), str(PROJECTS_DIR), str(STORAGE_DIR),
                tmp_path, target_w, target_h
            )

            # Pad if needed
            if target_w < canvas_w or target_h < canvas_h:
                img = Image.open(tmp_path)
                canvas = Image.new('RGB', (canvas_w, canvas_h), (0, 0, 0))
                canvas.paste(img, ((canvas_w - target_w) // 2, (canvas_h - target_h) // 2))
                canvas.save(tmp_path)
                img.close()
                canvas.close()

            # Read and encode as base64
            with open(tmp_path, 'rb') as f:
                img_data = base64.b64encode(f.read()).decode('utf-8')

            duration = slide.get('duration', default_duration) or default_duration

            # Collect video elements (HeyGen, YouTube, etc.) for overlay
            video_elements = []
            for el in slide.get('elements', []):
                if el.get('type') == 'video' and el.get('src'):
                    # Scale element coordinates to canvas size
                    ex = el.get('x', 0) * ratio
                    ey = el.get('y', 0) * ratio
                    ew = el.get('width', 200) * ratio
                    eh = el.get('height', 200) * ratio
                    # Center offset (same as image padding)
                    offset_x = (canvas_w - target_w) / 2
                    offset_y = (canvas_h - target_h) / 2
                    video_elements.append({
                        'src': el.get('src', ''),
                        'x': round(ex + offset_x),
                        'y': round(ey + offset_y),
                        'width': round(ew),
                        'height': round(eh),
                        'autoplay': el.get('autoplay', True),
                    })

            frame_data = {
                'index': idx,
                'dataUrl': f"data:image/png;base64,{img_data}",
                'duration': max(2.0, float(duration)),
            }
            if video_elements:
                frame_data['videoElements'] = video_elements

            # Include slide audio (ElevenLabs TTS, recordings, etc.)
            slide_audio = slide.get('audio', [])
            if slide_audio:
                audio_items = []
                for aud in slide_audio:
                    src = aud.get('src', '')
                    if not src:
                        continue
                    # Build full URL for the audio
                    if src.startswith('/api/'):
                        audio_url = src  # Frontend will prepend apiUrl
                    elif src.startswith('assets/'):
                        audio_url = f"/api/projects/{project_doc.get('id', '')}/assets/{src.replace('assets/', '')}"
                    elif src.startswith('http'):
                        audio_url = src
                    else:
                        audio_url = src
                    audio_items.append({
                        'src': audio_url,
                        'startTime': float(aud.get('startTime', 0)),
                        'volume': float(aud.get('volume', 1.0)),
                    })
                if audio_items:
                    frame_data['audioElements'] = audio_items

            # Include global audio if exists (background music)
            if idx == 0:
                global_audio = course.get('globalAudio', {})
                if global_audio and global_audio.get('src'):
                    ga_src = global_audio['src']
                    if ga_src.startswith('/api/'):
                        ga_url = ga_src
                    elif ga_src.startswith('assets/'):
                        ga_url = f"/api/projects/{project_doc.get('id', '')}/assets/{ga_src.replace('assets/', '')}"
                    else:
                        ga_url = ga_src
                    frame_data['globalAudio'] = {
                        'src': ga_url,
                        'volume': float(global_audio.get('volume', 0.5)),
                        'loop': global_audio.get('loop', True),
                    }

            frames.append(frame_data)

            # Cleanup temp file
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

        return {
            'projectName': project_doc.get('name', 'course'),
            'width': canvas_w,
            'height': canvas_h,
            'frames': frames,
            'totalSlides': len(slides),
        }
    except Exception as e:
        logger.error(f"Error generating video frames: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/proxy-video")
async def proxy_video(url: str):
    """Stream-proxy external video URLs (HeyGen, etc.) to bypass CORS restrictions.
    Uses true streaming — no buffering of full video in memory."""
    import httpx
    from starlette.responses import StreamingResponse
    from urllib.parse import urlparse

    if not url or not url.startswith('http'):
        raise HTTPException(status_code=400, detail="Invalid URL")

    # Only allow known video hosts
    allowed_hosts = {'heygen.ai', 'resource2.heygen.ai', 'files2.heygen.ai', 'youtube.com', 'vimeo.com'}
    parsed = urlparse(url)
    host = parsed.hostname or ''
    if not any(host == h or host.endswith('.' + h) for h in allowed_hosts):
        raise HTTPException(status_code=403, detail="Host not allowed")

    try:
        # Use a streaming request — data flows directly to client without buffering
        client = httpx.AsyncClient(timeout=httpx.Timeout(connect=10, read=120, write=10, pool=10), follow_redirects=True)
        req = client.build_request("GET", url)
        resp = await client.send(req, stream=True)

        if resp.status_code != 200:
            await resp.aclose()
            await client.aclose()
            raise HTTPException(status_code=resp.status_code, detail="Upstream error")

        content_type = resp.headers.get('content-type', 'video/mp4')
        content_length = resp.headers.get('content-length')

        response_headers = {
            "Access-Control-Allow-Origin": "*",
            "Cache-Control": "public, max-age=3600",
        }
        if content_length:
            response_headers["Content-Length"] = content_length

        async def stream_and_close():
            try:
                async for chunk in resp.aiter_bytes(chunk_size=65536):
                    yield chunk
            finally:
                await resp.aclose()
                await client.aclose()

        return StreamingResponse(
            stream_and_close(),
            media_type=content_type,
            headers=response_headers,
        )
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Video download timeout")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Video proxy error: {e}")
        raise HTTPException(status_code=500, detail=str(e))



# Legacy Video Export (FFmpeg-based, kept for environments where FFmpeg works)

@router.post("/course/{project_id}/export-video")
async def export_video_endpoint(project_id: str, request: Request, background_tasks: BackgroundTasks):
    """Export project as video (MP4 or WebM).
    Returns jobId INSTANTLY (<100ms) — all heavy work runs in background.
    This prevents Cloudflare/Nginx proxy timeouts (502/504) in production."""

    body = await request.json()
    video_format = body.get('format', 'mp4')
    if video_format not in ('mp4', 'webm'):
        video_format = 'mp4'
    default_duration = float(body.get('default_duration', 5.0))

    # Create job IMMEDIATELY and return — no DB fetch, no FFmpeg check, no imports
    job_id = str(uuid.uuid4())
    job_data = {
        'id': job_id,
        'status': 'processing',
        'progress': 0,
        'message': 'Exportação em fila, preparando...',
        'result': None
    }
    jobs[job_id] = job_data
    # Await MongoDB persistence to ensure job exists before polling starts
    await create_job(job_id, job_data)

    async def run_export():
        """All heavy work happens here — after the HTTP response is already sent.
        Includes global timeout and heartbeat for production resilience."""
        try:
            # Step 1: Import video exporter (may trigger static-ffmpeg download)
            await update_job(job_id, {'message': 'Carregando módulo de vídeo...'})
            try:
                from services.video_exporter import export_video as export_video_func, is_ffmpeg_available
            except Exception as e:
                logger.error(f"Failed to import video_exporter: {e}")
                jobs[job_id]['status'] = 'failed'
                jobs[job_id]['message'] = f"Módulo de vídeo indisponível: {str(e)}"
                await update_job(job_id, {'status': 'failed', 'message': jobs[job_id]['message']})
                return

            # Step 2: Check FFmpeg availability
            if not is_ffmpeg_available():
                jobs[job_id]['status'] = 'failed'
                jobs[job_id]['message'] = 'FFmpeg não disponível. Use exportação SCORM ou HTML.'
                await update_job(job_id, {'status': 'failed', 'message': jobs[job_id]['message']})
                return

            # Step 3: Fetch project from DB
            await update_job(job_id, {'message': 'Carregando projeto...', 'progress': 5})
            project_doc = await get_project_by_id(project_id)
            if not project_doc:
                jobs[job_id]['status'] = 'failed'
                jobs[job_id]['message'] = 'Projeto não encontrado.'
                await update_job(job_id, {'status': 'failed', 'message': jobs[job_id]['message']})
                return

            # Step 4: Run the actual export with global timeout
            def on_progress(progress, message):
                jobs[job_id]['progress'] = progress
                jobs[job_id]['message'] = message
                asyncio.ensure_future(update_job(job_id, {'progress': progress, 'message': message}))

            try:
                output_path = await asyncio.wait_for(
                    export_video_func(
                        project_doc,
                        str(PROJECTS_DIR),
                        str(STORAGE_DIR),
                        str(EXPORTS_DIR),
                        video_format=video_format,
                        default_duration=default_duration,
                        on_progress=on_progress
                    ),
                    timeout=600  # 10 minute max for entire export
                )
            except asyncio.TimeoutError:
                logger.error(f"Video export timed out after 10 minutes for job {job_id}")
                jobs[job_id]['status'] = 'failed'
                jobs[job_id]['message'] = 'Exportação excedeu o limite de 10 minutos. Tente com menos slides.'
                await update_job(job_id, {'status': 'failed', 'message': jobs[job_id]['message']})
                return

            filename = Path(output_path).name
            await save_export_to_gridfs(output_path, filename)
            jobs[job_id]['status'] = 'completed'
            jobs[job_id]['progress'] = 100
            jobs[job_id]['message'] = 'Vídeo exportado com sucesso!'
            jobs[job_id]['result'] = {
                'downloadUrl': f"/api/exports/{filename}",
                'filename': filename
            }
            await update_job(job_id, {
                'status': 'completed',
                'progress': 100,
                'message': 'Vídeo exportado com sucesso!',
                'result': {'downloadUrl': f"/api/exports/{filename}", 'filename': filename}
            })
            logger.info(f"Video job {job_id} completed successfully")
        except BaseException as e:
            # Catch EVERYTHING including CancelledError, SystemExit, KeyboardInterrupt
            logger.error(f"Video export error (BaseException): {type(e).__name__}: {e}")
            try:
                jobs[job_id]['status'] = 'failed'
                jobs[job_id]['message'] = f"Erro na exportação: {type(e).__name__}: {str(e)}"
                await update_job(job_id, {'status': 'failed', 'message': jobs[job_id]['message']})
            except Exception:
                pass  # Last resort - can't even update the job

    # Spawn background task and return IMMEDIATELY
    # Store reference in set to prevent garbage collection of the task
    task = asyncio.create_task(run_export())
    _active_export_tasks.add(task)
    task.add_done_callback(_active_export_tasks.discard)

    return {
        "jobId": job_id,
        "message": f"Exportação de vídeo {video_format.upper()} iniciada"
    }

# Prevent asyncio task garbage collection in production
_active_export_tasks = set()

# Static file serving

@router.get("/projects/{project_id}/assets/{filename}")
async def serve_asset(project_id: str, filename: str):
    """Serve project asset - falls back to MongoDB if local file is missing"""
    file_path = PROJECTS_DIR / project_id / "assets" / filename
    if file_path.exists():
        return FileResponse(file_path)
    
    # Fallback: try to restore from MongoDB (production ephemeral storage)
    if db is not None:
        try:
            from services.asset_store import retrieve_asset_async
            data, content_type = await retrieve_asset_async(db, project_id, filename)
            if data:
                # Cache to filesystem for future requests
                try:
                    file_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(file_path, 'wb') as f:
                        f.write(data)
                    return FileResponse(file_path)
                except Exception:
                    from fastapi.responses import Response
                    return Response(content=data, media_type=content_type)
        except Exception as e:
            logger.warning(f"MongoDB asset fallback failed for {project_id}/{filename}: {e}")
    
    raise HTTPException(status_code=404, detail=f"Asset not found: {filename}")


@router.post("/admin/repair-assets")
async def repair_assets():
    """Scan all local project assets and persist any missing ones to MongoDB."""
    from services.asset_store import store_asset_async
    
    persisted = 0
    errors = 0
    already_in_db = 0
    
    if not PROJECTS_DIR.exists():
        return {"message": "No projects directory found", "persisted": 0}
    
    for project_dir in PROJECTS_DIR.iterdir():
        if not project_dir.is_dir():
            continue
        assets_dir = project_dir / "assets"
        if not assets_dir.exists():
            continue
        project_id = project_dir.name
        for asset_file in assets_dir.iterdir():
            if not asset_file.is_file():
                continue
            existing = await db.project_assets.find_one(
                {"project_id": project_id, "filename": asset_file.name},
                {"_id": 1}
            )
            if existing:
                already_in_db += 1
                continue
            try:
                success = await store_asset_async(db, project_id, asset_file.name, str(asset_file))
                if success:
                    persisted += 1
                else:
                    errors += 1
            except Exception as e:
                errors += 1
                logger.warning(f"Repair: failed to persist {project_id}/{asset_file.name}: {e}")
    
    return {
        "message": f"Repair complete. Persisted {persisted} assets, {already_in_db} already in DB, {errors} errors.",
        "persisted": persisted,
        "already_in_db": already_in_db,
        "errors": errors,
    }


@router.post("/admin/restore-assets")
async def restore_assets_from_mongodb():
    """Force-restore all project assets from MongoDB to local filesystem.
    Useful after a fork or pod restart when local files are missing."""
    import base64 as b64mod
    
    restored = 0
    errors = 0
    already_local = 0
    
    # Get all assets from MongoDB
    cursor = db.project_assets.find({}, {"_id": 0, "project_id": 1, "filename": 1, "data": 1})
    async for doc in cursor:
        pid = doc.get("project_id", "")
        fname = doc.get("filename", "")
        if not pid or not fname or not doc.get("data"):
            continue
        
        if pid == "global":
            fp = STORAGE_DIR / "assets" / fname
        else:
            fp = PROJECTS_DIR / pid / "assets" / fname
        
        if fp.exists():
            already_local += 1
            continue
        
        try:
            fp.parent.mkdir(parents=True, exist_ok=True)
            with open(fp, 'wb') as f:
                f.write(b64mod.b64decode(doc["data"]))
            restored += 1
        except Exception as e:
            errors += 1
            logger.warning(f"Restore failed for {pid}/{fname}: {e}")
    
    return {
        "message": f"Restore complete. Restored {restored} assets, {already_local} already on disk, {errors} errors.",
        "restored": restored,
        "already_local": already_local,
        "errors": errors,
    }


@router.get("/admin/asset-diagnostic")
async def asset_diagnostic():
    """Comprehensive diagnostic for asset storage in production.
    Tests MongoDB connectivity, read/write, and reports asset status."""
    import base64
    from routes.deps import db as route_db, mongo_url as route_mongo_url, db_name as route_db_name
    
    results = {
        "db_status": "unknown",
        "db_name": route_db_name,
        "mongo_url_prefix": route_mongo_url[:30] + "..." if route_mongo_url else "EMPTY",
        "write_test": "not_run",
        "read_test": "not_run",
        "total_assets": 0,
        "sample_projects_with_assets": [],
        "projects_in_db": 0,
        "projects_with_background_images": 0,
        "missing_assets": [],
        "local_files_count": 0,
    }
    
    # 1. Check db connection
    if route_db is None:
        results["db_status"] = "ERROR: db is None"
        return results
    
    try:
        collections = await route_db.list_collection_names()
        results["db_status"] = f"connected ({len(collections)} collections)"
        results["has_project_assets_collection"] = "project_assets" in collections
    except Exception as e:
        results["db_status"] = f"ERROR: {str(e)}"
        return results
    
    # 2. Write test
    test_data = base64.b64encode(b"DIAGNOSTIC_TEST_IMAGE").decode('ascii')
    try:
        await route_db.project_assets.update_one(
            {"project_id": "__diagnostic__", "filename": "test.png"},
            {"$set": {"project_id": "__diagnostic__", "filename": "test.png", "data": test_data, "content_type": "image/png"}},
            upsert=True,
        )
        results["write_test"] = "OK"
    except Exception as e:
        results["write_test"] = f"FAILED: {str(e)}"
    
    # 3. Read test
    try:
        doc = await route_db.project_assets.find_one(
            {"project_id": "__diagnostic__", "filename": "test.png"},
            {"_id": 0, "data": 1}
        )
        if doc and doc.get("data") == test_data:
            results["read_test"] = "OK"
        else:
            results["read_test"] = f"FAILED: doc={doc is not None}, data_match={doc.get('data') == test_data if doc else 'N/A'}"
        # Cleanup
        await route_db.project_assets.delete_one({"project_id": "__diagnostic__", "filename": "test.png"})
    except Exception as e:
        results["read_test"] = f"FAILED: {str(e)}"
    
    # 4. Count total assets
    try:
        results["total_assets"] = await route_db.project_assets.count_documents({})
        # Get sample projects that HAVE assets
        pipeline = [
            {"$group": {"_id": "$project_id", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 10}
        ]
        async for doc in route_db.project_assets.aggregate(pipeline):
            results["sample_projects_with_assets"].append({
                "project_id": doc["_id"],
                "asset_count": doc["count"]
            })
    except Exception as e:
        results["total_assets"] = f"ERROR: {str(e)}"
    
    # 5. Check projects with background images that might 404
    try:
        results["projects_in_db"] = await route_db.projects.count_documents({})
        bg_count = 0
        missing = []
        async for proj in route_db.projects.find(
            {"course.slides.0.backgroundImage": {"$exists": True, "$nin": ["", None]}},
            {"_id": 0, "id": 1, "name": 1, "course.slides.0.backgroundImage": 1}
        ).limit(30):
            bg = proj.get("course", {}).get("slides", [{}])[0].get("backgroundImage", "")
            if bg:
                bg_count += 1
                # Extract project_id and filename from the URL
                # e.g., /api/projects/abc123/assets/slide_001.png
                parts = bg.replace("/api/projects/", "").split("/assets/")
                if len(parts) == 2:
                    asset_pid, asset_fname = parts
                    # Check if this asset exists in MongoDB
                    exists = await route_db.project_assets.find_one(
                        {"project_id": asset_pid, "filename": asset_fname},
                        {"_id": 1}
                    )
                    if not exists:
                        missing.append({
                            "project_id": proj.get("id"),
                            "project_name": proj.get("name", "?")[:40],
                            "bg_url": bg,
                            "asset_project_id": asset_pid,
                            "asset_filename": asset_fname,
                        })
        results["projects_with_background_images"] = bg_count
        results["missing_assets"] = missing[:20]  # Limit to 20
    except Exception as e:
        results["projects_with_background_images"] = f"ERROR: {str(e)}"
    
    # 6. Count local files
    try:
        local_count = 0
        for project_dir in PROJECTS_DIR.iterdir():
            if not project_dir.is_dir():
                continue
            assets_dir = project_dir / "assets"
            if assets_dir.exists():
                local_count += sum(1 for f in assets_dir.iterdir() if f.is_file())
        results["local_files_count"] = local_count
    except Exception as e:
        results["local_files_count"] = f"ERROR: {str(e)}"
    
    return results


@router.get("/admin/asset-diagnostic/{project_id}")
async def asset_diagnostic_project(project_id: str):
    """Check a specific project's assets - what slides reference vs what exists in MongoDB."""
    from routes.deps import db as route_db
    
    results = {
        "project_id": project_id,
        "project_exists": False,
        "slide_count": 0,
        "referenced_assets": [],
        "stored_assets": [],
        "missing": [],
        "found": [],
    }
    
    proj = await route_db.projects.find_one({"id": project_id}, {"_id": 0, "name": 1, "course": 1})
    if not proj:
        return results
    
    results["project_exists"] = True
    results["project_name"] = proj.get("name", "?")
    
    slides = proj.get("course", {}).get("slides", [])
    results["slide_count"] = len(slides)
    
    referenced = set()
    for i, slide in enumerate(slides):
        bg = slide.get("backgroundImage", "")
        if bg and "/assets/" in bg:
            parts = bg.split("/assets/")
            if len(parts) == 2:
                ref_pid = parts[0].replace("/api/projects/", "")
                ref_fname = parts[1]
                referenced.add((ref_pid, ref_fname, f"slide[{i}].backgroundImage"))
        
        for j, el in enumerate(slide.get("elements", [])):
            src = el.get("src", "")
            if src and "/assets/" in src:
                parts = src.split("/assets/")
                if len(parts) == 2:
                    ref_pid = parts[0].replace("/api/projects/", "")
                    ref_fname = parts[1]
                    referenced.add((ref_pid, ref_fname, f"slide[{i}].elements[{j}].src"))
    
    results["referenced_assets"] = [{"project_id": r[0], "filename": r[1], "location": r[2]} for r in referenced]
    
    stored = []
    async for doc in route_db.project_assets.find(
        {"project_id": project_id},
        {"_id": 0, "filename": 1, "content_type": 1}
    ):
        stored.append(doc["filename"])
    results["stored_assets"] = stored
    
    for ref in referenced:
        ref_pid, ref_fname, ref_loc = ref
        exists = await route_db.project_assets.find_one(
            {"project_id": ref_pid, "filename": ref_fname},
            {"_id": 1}
        )
        local_exists = (PROJECTS_DIR / ref_pid / "assets" / ref_fname).exists()
        
        entry = {"project_id": ref_pid, "filename": ref_fname, "location": ref_loc, "in_mongodb": exists is not None, "on_disk": local_exists}
        if exists or local_exists:
            results["found"].append(entry)
        else:
            results["missing"].append(entry)
    
    return results



@router.get("/exports/{filename}")
async def serve_export(filename: str, preview: str = None):
    """Serve exported files (SCORM zip or HTML) with forced download.
    Falls back to MongoDB GridFS if the file is not on local disk."""
    file_path = EXPORTS_DIR / filename
    
    # If not on local disk, try to restore from GridFS
    if not file_path.exists():
        restored = await get_export_from_gridfs(filename, str(file_path))
        if not restored:
            raise HTTPException(status_code=404, detail="File not found")
    
    # Determine media type based on file extension
    if filename.endswith('.html'):
        media_type = 'text/html'
    elif filename.endswith('.zip'):
        media_type = 'application/zip'
    elif filename.endswith('.mp4'):
        media_type = 'video/mp4'
    elif filename.endswith('.webm'):
        media_type = 'video/webm'
    else:
        media_type = 'application/octet-stream'
    
    return FileResponse(file_path, filename=filename, media_type=media_type)