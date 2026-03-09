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
    PROJECTS_DIR, STORAGE_DIR, EXPORTS_DIR, exports_bucket, jobs
)
from models import Project

logger = logging.getLogger("server")

router = APIRouter(tags=["Export"])


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
    jobs[job_id] = {
        'id': job_id,
        'status': 'processing',
        'progress': 0,
        'message': 'Generating SCORM package...',
        'result': None
    }
    
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
                # Use BASE_URL from env as primary source (always the correct external URL)
                # Request headers may contain internal cluster URLs that are unreachable externally
                backend_url = os.environ.get('BASE_URL', '').strip()
                if not backend_url:
                    # Fallback: read from frontend .env
                    try:
                        env_path = Path(__file__).parent.parent / "frontend" / ".env"
                        for line in env_path.read_text().splitlines():
                            if line.startswith("REACT_APP_BACKEND_URL="):
                                backend_url = line.split("=", 1)[1].strip()
                                break
                    except Exception:
                        pass
                
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

        # Generate package with questions
        # Run in thread pool to avoid blocking the async event loop
        # (export_scorm_package is a CPU+IO intensive synchronous function)
        from services.scorm_exporter import export_scorm_package
        import asyncio
        
        # Use BASE_URL from env for VLibras proxy (always the correct external URL)
        scorm_backend_url = os.environ.get('BASE_URL', '').strip()
        if not scorm_backend_url:
            try:
                env_path = Path(__file__).parent.parent / "frontend" / ".env"
                for line in env_path.read_text().splitlines():
                    if line.startswith("REACT_APP_BACKEND_URL="):
                        scorm_backend_url = line.split("=", 1)[1].strip()
                        break
            except Exception:
                pass
        
        zip_path = await asyncio.to_thread(
            export_scorm_package,
            project,
            str(PROJECTS_DIR),
            str(EXPORTS_DIR),
            questions=questions,
            tutor_config=tutor_settings,
            backend_url=scorm_backend_url
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
        base_url = os.environ.get('REACT_APP_BACKEND_URL', '')
        
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
                # Use BASE_URL from env as primary source (always the correct external URL)
                html_backend_url = os.environ.get('BASE_URL', '').strip() or base_url or ''
                
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

# Video Export

@router.post("/course/{project_id}/export-video")
async def export_video_endpoint(project_id: str, request: Request, background_tasks: BackgroundTasks):
    """Export project as video (MP4 or WebM)"""
    from services.video_exporter import export_video as export_video_func, is_ffmpeg_available
    # Check if video export is available
    if not is_ffmpeg_available():
        raise HTTPException(
            status_code=503,
            detail="A exportação de vídeo não está disponível neste ambiente. FFmpeg não está instalado. Use exportação SCORM ou HTML como alternativa."
        )
    
    project_doc = await get_project_by_id(project_id)
    if not project_doc:
        raise HTTPException(status_code=404, detail="Project not found")

    body = await request.json()
    video_format = body.get('format', 'mp4')
    if video_format not in ('mp4', 'webm'):
        video_format = 'mp4'
    default_duration = float(body.get('default_duration', 5.0))

    # Create job for tracking
    job_id = str(uuid.uuid4())
    jobs[job_id] = {
        'id': job_id,
        'status': 'processing',
        'progress': 0,
        'message': 'Iniciando exportação de vídeo...',
        'result': None
    }

    async def run_export():
        try:
            def on_progress(progress, message):
                jobs[job_id]['progress'] = progress
                jobs[job_id]['message'] = message

            output_path = await export_video_func(
                project_doc,
                str(PROJECTS_DIR),
                str(STORAGE_DIR),
                str(EXPORTS_DIR),
                video_format=video_format,
                default_duration=default_duration,
                on_progress=on_progress
            )

            filename = Path(output_path).name
            # Persist to GridFS
            await save_export_to_gridfs(output_path, filename)
            jobs[job_id]['status'] = 'completed'
            jobs[job_id]['progress'] = 100
            jobs[job_id]['message'] = 'Vídeo exportado com sucesso!'
            jobs[job_id]['result'] = {
                'downloadUrl': f"/api/exports/{filename}",
                'filename': filename
            }
        except Exception as e:
            logger.error(f"Video export error: {e}")
            jobs[job_id]['status'] = 'failed'
            jobs[job_id]['message'] = f"Erro na exportação: {str(e)}"

    # Run in background
    asyncio.create_task(run_export())

    return {
        "jobId": job_id,
        "message": f"Exportação de vídeo {video_format.upper()} iniciada"
    }

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
                # Restore to filesystem for future requests
                file_path.parent.mkdir(parents=True, exist_ok=True)
                with open(file_path, 'wb') as f:
                    f.write(data)
                logger.info(f"Restored asset from MongoDB: {project_id}/{filename}")
                return FileResponse(file_path)
        except Exception as e:
            logger.warning(f"MongoDB asset fallback failed: {e}")
    
    raise HTTPException(status_code=404, detail="File not found")

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
    else:
        media_type = 'application/octet-stream'
    
    return FileResponse(file_path, filename=filename, media_type=media_type)