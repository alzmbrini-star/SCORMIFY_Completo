"""Project CRUD, slides, elements, media, audio, annotations routes"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, BackgroundTasks, Request
from fastapi.responses import FileResponse
from typing import List, Optional
from pathlib import Path
import uuid
import os
import io
import shutil
import copy
import logging
import aiofiles
import threading

from routes.deps import (
    db, now_utc, serialize_doc, get_project_by_id, update_project,
    PROJECTS_DIR, STORAGE_DIR, UPLOADS_DIR, jobs, mongo_url,
    create_job, update_job, get_job, update_job_sync
)
from models import (
    Project, ProjectCreate, ProjectUpdate, Course, CourseMetadata,
    Slide, SlideCreate, SlideUpdate, SlideElement, ElementCreate, ElementUpdate,
    Animation, Annotation, AnnotationCreate, SlideAudio, GlobalAudio,
    JobStatus, ReorderSlidesRequest
)

logger = logging.getLogger("server")

router = APIRouter(tags=["Projects"])


def process_ppt_upload(job_id: str, file_path: str, project_id: str):
    """Process uploaded PPT file in background using high-fidelity parser"""
    from pymongo import MongoClient
    from services.ppt_image_parser import parse_pptx_high_fidelity
    db_name = os.environ.get("DB_NAME", "scormify")
    _is_atlas = "mongodb.net" in mongo_url or "mongodb+srv" in mongo_url
    sync_client = None
    try:
        jobs[job_id]["status"] = "processing"
        jobs[job_id]["message"] = "Converting PowerPoint slides to images..."
        jobs[job_id]["progress"] = 10
        sync_client = MongoClient(
            mongo_url,
            serverSelectionTimeoutMS=120000 if _is_atlas else 30000,
            connectTimeoutMS=120000 if _is_atlas else 30000,
            socketTimeoutMS=300000 if _is_atlas else 60000,
            retryWrites=True,
            retryReads=True,
        )
        sync_db = sync_client[db_name]
        # Sync job status to MongoDB
        sync_db.jobs.update_one({"id": job_id}, {"$set": {"status": "processing", "progress": 10, "message": "Converting PowerPoint slides to images..."}}, upsert=True)
        
        # If file is missing (deploy happened), try to recover from MongoDB
        if not Path(file_path).exists():
            logger.warning(f"PPT file missing from disk, trying to recover from MongoDB: {file_path}")
            recovered = False
            try:
                import base64 as _b64
                ppt_doc = sync_db.ppt_uploads.find_one(
                    {"$or": [{"path": file_path}, {"projectId": project_id}]},
                    {"data": 1}
                )
                if ppt_doc and ppt_doc.get("data"):
                    Path(file_path).parent.mkdir(parents=True, exist_ok=True)
                    with open(file_path, 'wb') as f:
                        f.write(_b64.b64decode(ppt_doc["data"]))
                    recovered = True
                    logger.info(f"PPT file recovered from MongoDB: {file_path}")
            except Exception as recover_err:
                logger.error(f"Failed to recover PPT from MongoDB: {recover_err}")
            
            if not recovered:
                raise FileNotFoundError(f"Arquivo PPT nao encontrado. O servidor reiniciou durante o processamento. Por favor, importe o arquivo novamente.")
        
        course = parse_pptx_high_fidelity(file_path, project_id, str(PROJECTS_DIR))
        jobs[job_id]["progress"] = 80
        jobs[job_id]["message"] = "Saving course data..."
        sync_db.jobs.update_one({"id": job_id}, {"$set": {"progress": 80, "message": "Saving course data..."}})
        course_dict = course.model_dump()
        course_dict["createdAt"] = course.createdAt.isoformat()
        course_dict["updatedAt"] = course.updatedAt.isoformat()
        sync_db.projects.update_one(
            {"id": project_id},
            {"$set": {"course": course_dict, "status": "ready", "updatedAt": now_utc().isoformat()}}
        )
        jobs[job_id]["status"] = "completed"
        jobs[job_id]["progress"] = 100
        jobs[job_id]["message"] = "Processing complete - slides rendered with high fidelity"
        jobs[job_id]["result"] = {"projectId": project_id}
        sync_db.jobs.update_one({"id": job_id}, {"$set": jobs[job_id]})
        # Cleanup: remove PPT blob from MongoDB (no longer needed)
        try:
            sync_db.ppt_uploads.delete_many({"$or": [{"path": file_path}, {"projectId": project_id}]})
        except Exception:
            pass
    except Exception as e:
        logger.error(f"Error processing PPT: {e}")
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["message"] = str(e)
        try:
            if sync_client:
                sync_db = sync_client[db_name]
                sync_db.jobs.update_one({"id": job_id}, {"$set": {"status": "failed", "message": str(e)}})
        except Exception:
            pass
    finally:
        try:
            os.remove(file_path)
        except OSError:
            pass


@router.get("/projects", response_model=List[dict])
async def list_projects():
    """List all projects"""
    projects = await db.projects.find({}, {"_id": 0}).sort("createdAt", -1).to_list(100)
    return projects

@router.post("/projects", response_model=dict)
async def create_project(data: ProjectCreate):
    """Create a new project"""
    project = Project(
        name=data.name,
        description=data.description
    )
    
    # Set course metadata title to project name
    project.course.metadata.title = data.name
    
    # Create default first slide
    default_slide = Slide(
        title="Slide 1",
        order=0,
        background="#FFFFFF"
    )
    project.course.slides = [default_slide]
    
    project_dict = project.model_dump()
    project_dict['createdAt'] = project.createdAt.isoformat()
    project_dict['updatedAt'] = project.updatedAt.isoformat()
    project_dict['course']['createdAt'] = project.course.createdAt.isoformat()
    project_dict['course']['updatedAt'] = project.course.updatedAt.isoformat()
    project_dict['source'] = 'manual'
    
    await db.projects.insert_one(project_dict)
    
    # Create project directory
    project_dir = PROJECTS_DIR / project.id
    (project_dir / "assets").mkdir(parents=True, exist_ok=True)
    
    return serialize_doc(project_dict)

@router.get("/projects/{project_id}", response_model=dict)
async def get_project(project_id: str):
    """Get project by ID"""
    project = await get_project_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Sanitize any non-string htmlContent (from previous AI bugs)
    needs_fix = False
    for slide in project.get("course", {}).get("slides", []):
        for el in slide.get("elements", []):
            hc = el.get("htmlContent")
            if hc is not None and not isinstance(hc, str):
                import json as _json
                if isinstance(hc, dict):
                    parts = []
                    for k, v in hc.items():
                        if isinstance(v, str):
                            parts.append(f"<p><strong>{k}</strong>: {v}</p>")
                        elif isinstance(v, list):
                            for item in v:
                                if isinstance(item, dict):
                                    label = item.get("label", item.get("title", ""))
                                    desc = item.get("description", item.get("text", ""))
                                    parts.append(f"<p><strong>{label}</strong>: {desc}</p>")
                    el["htmlContent"] = "\n".join(parts) if parts else ""
                else:
                    el["htmlContent"] = str(hc) if hc else ""
                needs_fix = True

    if needs_fix:
        await update_project(project_id, {"course": project["course"]})

    return project


@router.post("/projects/{project_id}/fix-simulators")
async def fix_simulators(project_id: str):
    """Detect and fix static simulators in a course by adding JavaScript interactivity."""
    import re as _re

    project = await get_project_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    slides = project.get("course", {}).get("slides", [])
    fixed_count = 0

    for slide in slides:
        for el in slide.get("elements", []):
            if el.get("type") not in ("html", "text"):
                continue
            hc = el.get("htmlContent", "")
            if not isinstance(hc, str):
                continue

            hc_lower = hc.lower()

            # Detect C-Rate simulator (buttons with C values but no onclick)
            is_crate_sim = ("c-rate" in hc_lower or "simulador" in hc_lower) and ("descarga" in hc_lower or "capacidade" in hc_lower)
            has_js = "onclick" in hc_lower or "<script" in hc_lower or "addEventListener" in hc_lower

            if is_crate_sim and not has_js:
                # Extract capacity if mentioned
                cap_match = _re.search(r'(\d+)\s*Ah', hc)
                capacity = int(cap_match.group(1)) if cap_match else 100

                # Extract C-Rate values from buttons
                crate_matches = _re.findall(r'([\d.]+)C\s*\((\d+)A\)', hc)
                if not crate_matches:
                    crate_matches = [("0.5", "50"), ("1", "100"), ("2", "200")]

                el["htmlContent"] = _build_crate_simulator(capacity, crate_matches)
                fixed_count += 1
                continue

            # Generic simulator detection (buttons without onclick)
            has_buttons = "<button" in hc_lower and "onclick" not in hc_lower
            has_display = "resultado" in hc_lower or "display" in hc_lower or "output" in hc_lower
            if has_buttons and has_display and not has_js:
                # Add basic onclick to buttons
                def _add_onclick(match):
                    btn_html = match.group(0)
                    if "onclick" not in btn_html.lower():
                        btn_html = btn_html.replace("<button", '<button onclick="this.style.opacity=0.7;setTimeout(()=>this.style.opacity=1,200)"', 1)
                    return btn_html

                new_hc = _re.sub(r'<button[^>]*>.*?</button>', _add_onclick, hc, flags=_re.DOTALL | _re.IGNORECASE)
                if new_hc != hc:
                    el["htmlContent"] = new_hc
                    fixed_count += 1

    if fixed_count > 0:
        course = project.get("course", {})
        course["slides"] = slides
        await update_project(project_id, {"course": course})

    return {
        "status": "ok",
        "fixed": fixed_count,
        "message": f"{fixed_count} simulador(es) corrigido(s)" if fixed_count > 0 else "Nenhum simulador estático encontrado"
    }


def _build_crate_simulator(capacity: int, crate_values: list) -> str:
    """Build a fully interactive C-Rate simulator with JavaScript."""
    buttons_html = ""
    for c_val, amps in crate_values:
        buttons_html += f'<button onclick="simulate({c_val}, {amps})" style="padding:12px 24px;border:none;border-radius:10px;background:linear-gradient(135deg,#6366f1,#8b5cf6);color:#fff;font-weight:700;font-size:15px;cursor:pointer;transition:all 0.3s;box-shadow:0 4px 15px rgba(99,102,241,0.4);" onmouseover="this.style.transform=\'translateY(-2px)\';this.style.boxShadow=\'0 6px 20px rgba(99,102,241,0.6)\'" onmouseout="this.style.transform=\'translateY(0)\';this.style.boxShadow=\'0 4px 15px rgba(99,102,241,0.4)\'">{c_val}C ({amps}A)</button>\n'

    return f'''<div style="font-family:'Segoe UI',system-ui,sans-serif;max-width:800px;margin:0 auto;padding:20px;">
  <div style="text-align:center;margin-bottom:24px;">
    <h2 style="color:#e2e8f0;font-size:26px;margin:0 0 8px 0;">Simulador de C-Rate</h2>
    <span style="background:linear-gradient(135deg,#6366f1,#8b5cf6);color:#fff;padding:6px 16px;border-radius:20px;font-size:13px;font-weight:600;">Capacidade: {capacity}Ah</span>
  </div>

  <div style="display:flex;gap:12px;justify-content:center;flex-wrap:wrap;margin-bottom:24px;">
    {buttons_html}
  </div>

  <div id="result-panel" style="background:linear-gradient(135deg,#1e293b,#0f172a);border:1px solid #334155;border-radius:16px;padding:24px;text-align:center;min-height:140px;display:flex;flex-direction:column;align-items:center;justify-content:center;transition:all 0.5s;">
    <div id="result-label" style="color:#94a3b8;font-size:14px;margin-bottom:8px;">Selecione uma taxa C acima</div>
    <div id="result-value" style="color:#22d3ee;font-size:42px;font-weight:800;line-height:1;"></div>
    <div id="result-details" style="color:#94a3b8;font-size:13px;margin-top:12px;"></div>
  </div>

  <div id="bar-container" style="margin-top:20px;display:none;">
    <div style="display:flex;justify-content:space-between;margin-bottom:6px;">
      <span style="color:#94a3b8;font-size:12px;">0%</span>
      <span id="bar-label" style="color:#22d3ee;font-size:12px;font-weight:600;">100%</span>
    </div>
    <div style="background:#1e293b;border-radius:10px;height:20px;overflow:hidden;border:1px solid #334155;">
      <div id="bar-fill" style="height:100%;border-radius:10px;transition:width 1.5s ease-out,background 1s;width:100%;background:linear-gradient(90deg,#22d3ee,#6366f1);"></div>
    </div>
    <div style="display:flex;justify-content:space-between;margin-top:8px;">
      <span style="color:#64748b;font-size:11px;">Descarga Lenta</span>
      <span style="color:#64748b;font-size:11px;">Descarga Rapida</span>
    </div>
  </div>

  <div id="info-box" style="margin-top:20px;background:#1e293b;border-left:4px solid #6366f1;border-radius:0 8px 8px 0;padding:16px;display:none;">
    <p id="info-text" style="color:#cbd5e1;font-size:13px;line-height:1.6;margin:0;"></p>
  </div>

  <script>
    function simulate(cRate, amps) {{
      var capacity = {capacity};
      var hours = capacity / amps;
      var minutes = Math.round(hours * 60);
      var timeStr = hours >= 1 ? hours.toFixed(1) + ' horas' : minutes + ' minutos';

      document.getElementById('result-label').textContent = 'Tempo Estimado de Descarga';
      document.getElementById('result-value').textContent = timeStr;
      document.getElementById('result-details').textContent = 
        'Taxa: ' + cRate + 'C | Corrente: ' + amps + 'A | Capacidade: ' + capacity + 'Ah';

      var panel = document.getElementById('result-panel');
      panel.style.borderColor = '#6366f1';
      panel.style.boxShadow = '0 0 30px rgba(99,102,241,0.2)';

      var barContainer = document.getElementById('bar-container');
      barContainer.style.display = 'block';
      var barFill = document.getElementById('bar-fill');
      var pct = Math.max(10, Math.min(100, (1 / cRate) * 50));
      barFill.style.width = pct + '%';
      document.getElementById('bar-label').textContent = Math.round(pct) + '% eficiencia relativa';

      if (cRate >= 2) {{
        barFill.style.background = 'linear-gradient(90deg,#ef4444,#f97316)';
      }} else if (cRate >= 1) {{
        barFill.style.background = 'linear-gradient(90deg,#f59e0b,#22d3ee)';
      }} else {{
        barFill.style.background = 'linear-gradient(90deg,#22d3ee,#10b981)';
      }}

      var infoBox = document.getElementById('info-box');
      infoBox.style.display = 'block';
      var infoText = document.getElementById('info-text');
      if (cRate <= 0.5) {{
        infoText.innerHTML = '<strong>Taxa Baixa (' + cRate + 'C):</strong> Descarga lenta e controlada. Ideal para maximizar a vida util da bateria. Menor stress termico e quimico nas celulas.';
      }} else if (cRate <= 1) {{
        infoText.innerHTML = '<strong>Taxa Moderada (' + cRate + 'C):</strong> Equilibrio entre desempenho e longevidade. Uso tipico em aplicacoes padrao como veiculos eletricos em condicoes normais.';
      }} else {{
        infoText.innerHTML = '<strong>Taxa Alta (' + cRate + 'C):</strong> Descarga rapida com maior geracao de calor. Reduz a vida util da bateria. Usada em situacoes de alta demanda como aceleracao.';
      }}
    }}
  </script>
</div>'''



@router.put("/projects/{project_id}", response_model=dict)
async def update_project_endpoint(project_id: str, data: ProjectUpdate):
    """Update project"""
    project = await get_project_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    update_data = data.model_dump(exclude_unset=True)
    
    # If project name is being updated, also update course metadata title
    if 'name' in update_data:
        update_data['course.metadata.title'] = update_data['name']
    
    await update_project(project_id, update_data)
    
    return await get_project_by_id(project_id)

@router.delete("/projects/{project_id}")
async def delete_project(project_id: str):
    """Delete project"""
    project = await get_project_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    await db.projects.delete_one({"id": project_id})
    
    # Delete project files
    project_dir = PROJECTS_DIR / project_id
    if project_dir.exists():
        shutil.rmtree(project_dir)
    
    return {"message": "Project deleted"}

# PPT Upload

@router.post("/ppt/upload/init")
async def init_chunked_upload(
    request: Request
):
    """Initialize a chunked PPT upload - returns an upload_id"""
    body = await request.json()
    filename = body.get('filename', 'upload.pptx')
    total_size = body.get('totalSize', 0)
    
    if not filename.lower().endswith(('.ppt', '.pptx')):
        raise HTTPException(status_code=400, detail="Tipo de arquivo invalido. Apenas PPT/PPTX sao permitidos.")
    
    if total_size > 100 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Arquivo muito grande. Tamanho maximo: 100MB.")
    
    upload_id = str(uuid.uuid4())
    upload_path = UPLOADS_DIR / f"chunk_{upload_id}"
    upload_path.mkdir(parents=True, exist_ok=True)
    
    upload_meta = {
        'filename': filename,
        'totalSize': total_size,
        'receivedSize': 0,
        'chunkCount': 0,
        'path': str(upload_path),
    }
    
    # Store in memory AND MongoDB (survives restarts/deploys)
    jobs[f"upload_{upload_id}"] = upload_meta
    try:
        await db.ppt_uploads.update_one(
            {"uploadId": upload_id},
            {"$set": {"uploadId": upload_id, **upload_meta, "createdAt": now_utc().isoformat()}},
            upsert=True,
        )
    except Exception as e:
        logger.warning(f"Failed to persist upload meta to MongoDB (non-fatal): {e}")
    
    logger.info(f"Chunked upload initialized: {upload_id}, file={filename}, size={total_size}")
    return {"uploadId": upload_id}


@router.post("/ppt/upload/chunk/{upload_id}")
async def upload_chunk(
    upload_id: str,
    chunk: UploadFile = File(...),
    chunk_index: int = 0,
):
    """Upload a single chunk of a PPT file"""
    meta_key = f"upload_{upload_id}"
    meta = jobs.get(meta_key)
    
    # If not in memory, try to recover from MongoDB (after deploy/restart)
    if not meta:
        try:
            mongo_meta = await db.ppt_uploads.find_one({"uploadId": upload_id}, {"_id": 0})
            if mongo_meta:
                # Recreate upload directory
                upload_path = Path(mongo_meta.get('path', str(UPLOADS_DIR / f"chunk_{upload_id}")))
                upload_path.mkdir(parents=True, exist_ok=True)
                meta = {
                    'filename': mongo_meta.get('filename', 'upload.pptx'),
                    'totalSize': mongo_meta.get('totalSize', 0),
                    'receivedSize': mongo_meta.get('receivedSize', 0),
                    'chunkCount': mongo_meta.get('chunkCount', 0),
                    'path': str(upload_path),
                }
                jobs[meta_key] = meta
                logger.info(f"Recovered upload state from MongoDB: {upload_id}")
        except Exception as e:
            logger.warning(f"Failed to recover upload state from MongoDB: {e}")
    
    if not meta:
        raise HTTPException(status_code=410, detail="Upload expirado ou servidor reiniciou. Por favor, tente importar o arquivo novamente.")
    
    content = await chunk.read()
    chunk_path = Path(meta['path']) / f"chunk_{chunk_index:04d}"
    async with aiofiles.open(chunk_path, 'wb') as f:
        await f.write(content)
    
    meta['receivedSize'] += len(content)
    meta['chunkCount'] += 1
    
    return {"received": len(content), "totalReceived": meta['receivedSize']}


@router.post("/ppt/upload/complete/{upload_id}")
async def complete_chunked_upload(
    upload_id: str,
    background_tasks: BackgroundTasks,
    project_name: Optional[str] = None,
):
    """Complete a chunked upload and start processing"""
    meta_key = f"upload_{upload_id}"
    meta = jobs.get(meta_key)
    
    # Try to recover from MongoDB if not in memory
    if not meta:
        try:
            mongo_meta = await db.ppt_uploads.find_one({"uploadId": upload_id}, {"_id": 0})
            if mongo_meta:
                meta = {
                    'filename': mongo_meta.get('filename', 'upload.pptx'),
                    'totalSize': mongo_meta.get('totalSize', 0),
                    'receivedSize': mongo_meta.get('receivedSize', 0),
                    'chunkCount': mongo_meta.get('chunkCount', 0),
                    'path': mongo_meta.get('path', str(UPLOADS_DIR / f"chunk_{upload_id}")),
                }
                jobs[meta_key] = meta
        except Exception:
            pass
    
    if not meta:
        raise HTTPException(status_code=410, detail="Upload expirado. Por favor, tente importar novamente.")
    
    filename = meta['filename']
    chunk_dir = Path(meta['path'])
    
    # Reassemble chunks
    project_name = project_name or Path(filename).stem
    final_path = UPLOADS_DIR / f"{upload_id}_{filename}"
    
    chunk_files = sorted(chunk_dir.glob("chunk_*"))
    if not chunk_files:
        raise HTTPException(status_code=400, detail="Nenhum chunk recebido.")
    
    async with aiofiles.open(final_path, 'wb') as out:
        for cf in chunk_files:
            async with aiofiles.open(cf, 'rb') as inp:
                data = await inp.read()
                await out.write(data)
    
    # Cleanup chunk dir and upload metadata
    import shutil
    shutil.rmtree(str(chunk_dir), ignore_errors=True)
    del jobs[meta_key]
    try:
        await db.ppt_uploads.delete_one({"uploadId": upload_id})
    except Exception:
        pass
    
    # Persist assembled PPT file to MongoDB so it survives deploy/restart
    try:
        import base64 as _b64
        async with aiofiles.open(final_path, 'rb') as pf:
            ppt_bytes = await pf.read()
        project_name_for_persist = project_name or Path(filename).stem
        await db.ppt_uploads.update_one(
            {"path": str(final_path)},
            {"$set": {
                "filename": filename,
                "path": str(final_path),
                "data": _b64.b64encode(ppt_bytes).decode('ascii'),
                "createdAt": now_utc().isoformat(),
            }},
            upsert=True,
        )
    except Exception as e:
        logger.warning(f"Failed to persist chunked PPT to MongoDB (non-fatal): {e}")
    
    # Create project
    project = Project(name=project_name)
    project_dict = project.model_dump()
    project_dict['createdAt'] = project.createdAt.isoformat()
    project_dict['updatedAt'] = project.updatedAt.isoformat()
    project_dict['course']['createdAt'] = project.course.createdAt.isoformat()
    project_dict['course']['updatedAt'] = project.course.updatedAt.isoformat()
    project_dict['status'] = 'processing'
    project_dict['source'] = 'ppt'
    
    await db.projects.insert_one(project_dict)
    
    # Create project directory
    project_dir = PROJECTS_DIR / project.id
    (project_dir / "assets").mkdir(parents=True, exist_ok=True)
    
    # Create job
    job_id = str(uuid.uuid4())
    job_data = {
        'id': job_id,
        'status': 'pending',
        'progress': 0,
        'message': 'Upload completo, iniciando processamento...',
        'result': None
    }
    jobs[job_id] = job_data
    await create_job(job_id, job_data)
    
    # Start background processing
    background_tasks.add_task(process_ppt_upload, job_id, str(final_path), project.id)
    
    logger.info(f"Chunked upload complete: {upload_id}, file={filename}, project={project.id}")
    return {
        "jobId": job_id,
        "projectId": project.id,
        "message": "File uploaded, processing started"
    }


@router.post("/ppt/upload")
async def upload_ppt(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    project_name: Optional[str] = None
):
    """Upload and process a PPT/PPTX file"""
    logger.info(f"PPT upload received: filename={file.filename}, content_type={file.content_type}, size_hint={file.size}")
    
    # Validate file type
    if not file.filename.lower().endswith(('.ppt', '.pptx')):
        logger.warning(f"PPT upload rejected: invalid file type: {file.filename}")
        raise HTTPException(status_code=400, detail="Invalid file type. Only PPT/PPTX files are allowed.")
    
    # Validate file size (max 50MB)
    content = await file.read()
    if len(content) > 50 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large. Maximum size is 50MB.")
    
    # Create project
    project_name = project_name or Path(file.filename).stem
    project = Project(name=project_name)
    
    project_dict = project.model_dump()
    project_dict['createdAt'] = project.createdAt.isoformat()
    project_dict['updatedAt'] = project.updatedAt.isoformat()
    project_dict['course']['createdAt'] = project.course.createdAt.isoformat()
    project_dict['course']['updatedAt'] = project.course.updatedAt.isoformat()
    project_dict['status'] = 'processing'
    project_dict['source'] = 'ppt'
    
    await db.projects.insert_one(project_dict)
    
    # Create project directory
    project_dir = PROJECTS_DIR / project.id
    (project_dir / "assets").mkdir(parents=True, exist_ok=True)
    
    # Save uploaded file
    upload_path = UPLOADS_DIR / f"{project.id}_{file.filename}"
    async with aiofiles.open(upload_path, 'wb') as f:
        await f.write(content)
    
    # Persist PPT file to MongoDB so it survives deploy/restart
    try:
        import base64 as _b64
        await db.ppt_uploads.update_one(
            {"projectId": project.id},
            {"$set": {
                "projectId": project.id,
                "filename": file.filename,
                "path": str(upload_path),
                "data": _b64.b64encode(content).decode('ascii'),
                "createdAt": now_utc().isoformat(),
            }},
            upsert=True,
        )
    except Exception as e:
        logger.warning(f"Failed to persist PPT to MongoDB (non-fatal): {e}")
    
    # Create job
    job_id = str(uuid.uuid4())
    jobs[job_id] = {
        'id': job_id,
        'status': 'pending',
        'progress': 0,
        'message': 'Upload received, starting processing...',
        'result': None
    }
    
    # Start background processing
    background_tasks.add_task(process_ppt_upload, job_id, str(upload_path), project.id)
    
    return {
        "jobId": job_id,
        "projectId": project.id,
        "message": "File uploaded, processing started"
    }

@router.get("/job/{job_id}", response_model=JobStatus)
async def get_job_status(job_id: str):
    """Get job status - checks local cache and MongoDB"""
    job = await get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobStatus(**job)

# Course Routes

@router.get("/course/{project_id}")
async def get_course(project_id: str):
    """Get course data for a project"""
    project = await get_project_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project.get('course', {})

@router.post("/course/{project_id}/save")
async def save_course(project_id: str, course_data: dict):
    """Save course data"""
    project = await get_project_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    await update_project(project_id, {"course": course_data})
    return {"message": "Course saved"}

# Slide Routes

@router.post("/projects/{project_id}/slides")
async def create_slide(project_id: str, data: SlideCreate):
    """Add a new slide to the project"""
    project = await get_project_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
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
async def update_slide(project_id: str, slide_id: str, data: SlideUpdate):
    """Update a slide"""
    project = await get_project_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
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
async def delete_slide(project_id: str, slide_id: str):
    """Delete a slide"""
    project = await get_project_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
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
async def duplicate_slide(project_id: str, slide_id: str):
    """Duplicate a slide"""
    project = await get_project_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    course = project.get('course', {})
    slides = course.get('slides', [])
    
    slide_index = next((i for i, s in enumerate(slides) if s.get('id') == slide_id), None)
    if slide_index is None:
        raise HTTPException(status_code=404, detail="Slide not found")
    
    # Deep copy the slide
    import copy
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
async def normalize_slide_dimensions(project_id: str, target_width: int = 1536, target_height: int = 864):
    """Normalize all slides to the same dimensions, scaling elements proportionally"""
    project = await get_project_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    course = project.get('course', {})
    slides = course.get('slides', [])
    
    normalized_count = 0
    
    for slide in slides:
        current_width = slide.get('width', 1536)
        current_height = slide.get('height', 864)
        
        # Skip if already the target dimensions
        if current_width == target_width and current_height == target_height:
            continue
        
        # Calculate scale factors
        scale_x = target_width / current_width
        scale_y = target_height / current_height
        
        # Update slide dimensions
        slide['width'] = target_width
        slide['height'] = target_height
        
        # Scale all elements proportionally
        for element in slide.get('elements', []):
            # Scale position
            if 'x' in element:
                element['x'] = element['x'] * scale_x
            if 'y' in element:
                element['y'] = element['y'] * scale_y
            
            # Scale size
            if 'width' in element:
                element['width'] = element['width'] * scale_x
            if 'height' in element:
                element['height'] = element['height'] * scale_y
        
        # Scale annotations if present
        for annotation in slide.get('annotations', []):
            if 'points' in annotation:
                for point in annotation['points']:
                    if 'x' in point:
                        point['x'] = point['x'] * scale_x
                    if 'y' in point:
                        point['y'] = point['y'] * scale_y
        
        normalized_count += 1
    
    # Save updated course
    course['slides'] = slides
    await update_project(project_id, {"course": course})
    
    return {
        "message": f"Normalized {normalized_count} slides to {target_width}x{target_height}",
        "normalized_count": normalized_count,
        "target_dimensions": {"width": target_width, "height": target_height}
    }

@router.post("/projects/{project_id}/slides/reorder")
async def reorder_slides(project_id: str, data: ReorderSlidesRequest):
    """Reorder slides"""
    project = await get_project_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    course = project.get('course', {})
    slides = course.get('slides', [])
    
    # Create mapping
    slide_map = {s['id']: s for s in slides}
    
    # Reorder based on provided IDs
    new_slides = []
    for i, slide_id in enumerate(data.slideIds):
        if slide_id in slide_map:
            slide = slide_map[slide_id]
            slide['order'] = i
            new_slides.append(slide)
    
    course['slides'] = new_slides
    await update_project(project_id, {"course": course})
    
    return {"message": "Slides reordered"}

# Element Routes

@router.post("/projects/{project_id}/slides/{slide_id}/elements")
async def add_element(project_id: str, slide_id: str, data: ElementCreate):
    """Add element to slide"""
    project = await get_project_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    course = project.get('course', {})
    slides = course.get('slides', [])
    
    slide_index = next((i for i, s in enumerate(slides) if s.get('id') == slide_id), None)
    if slide_index is None:
        raise HTTPException(status_code=404, detail="Slide not found")
    
    element_data = data.model_dump(exclude_unset=True)
    # Ensure style is a dict if not provided
    if 'style' not in element_data or element_data.get('style') is None:
        element_data['style'] = {}
    element = SlideElement(**element_data)
    elements = slides[slide_index].get('elements', [])
    element_dict = element.model_dump()
    element_dict['zIndex'] = len(elements)
    elements.append(element_dict)
    
    slides[slide_index]['elements'] = elements
    course['slides'] = slides
    
    await update_project(project_id, {"course": course})
    
    return element_dict

@router.put("/projects/{project_id}/slides/{slide_id}/elements/{element_id}")
async def update_element(project_id: str, slide_id: str, element_id: str, data: ElementUpdate):
    """Update element"""
    project = await get_project_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
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
    
    slides[slide_index]['elements'] = elements
    course['slides'] = slides
    
    await update_project(project_id, {"course": course})
    
    return elements[elem_index]

@router.delete("/projects/{project_id}/slides/{slide_id}/elements/{element_id}")
async def delete_element(project_id: str, slide_id: str, element_id: str):
    """Delete element"""
    project = await get_project_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    course = project.get('course', {})
    slides = course.get('slides', [])
    
    slide_index = next((i for i, s in enumerate(slides) if s.get('id') == slide_id), None)
    if slide_index is None:
        raise HTTPException(status_code=404, detail="Slide not found")
    
    elements = slides[slide_index].get('elements', [])
    elements = [e for e in elements if e.get('id') != element_id]
    
    slides[slide_index]['elements'] = elements
    course['slides'] = slides
    
    await update_project(project_id, {"course": course})
    
    return {"message": "Element deleted"}

# Media Upload

@router.post("/projects/{project_id}/media")
async def upload_media(project_id: str, file: UploadFile = File(...)):
    """Upload media file (image, audio, video) with automatic image optimization"""
    project = await get_project_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Validate file type
    allowed_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.mp3', '.wav', '.ogg', '.mp4', '.webm'}
    ext = Path(file.filename).suffix.lower()
    if ext not in allowed_extensions:
        raise HTTPException(status_code=400, detail=f"Invalid file type. Allowed: {', '.join(allowed_extensions)}")
    
    # Read and validate size
    content = await file.read()
    original_size = len(content)
    max_size = 100 * 1024 * 1024  # 100MB
    if original_size > max_size:
        raise HTTPException(status_code=400, detail="File too large")
    
    # Optimize images automatically
    image_extensions = {'.png', '.jpg', '.jpeg', '.webp'}
    optimized = False
    final_content = content
    
    if ext in image_extensions:
        try:
            from PIL import Image
            # Open image with Pillow
            img = Image.open(io.BytesIO(content))
            original_width, original_height = img.size
            
            # Only optimize if image is large (> 500KB or dimensions > 1920px)
            should_optimize = original_size > 500 * 1024 or img.width > 1920 or img.height > 1080
            
            if should_optimize:
                # Convert RGBA to RGB for JPEG (remove alpha channel)
                if img.mode == 'RGBA' and ext in {'.jpg', '.jpeg'}:
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    background.paste(img, mask=img.split()[3])
                    img = background
                elif img.mode == 'RGBA':
                    pass  # Keep alpha for PNG/WebP
                elif img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # Calculate max dimensions (Full HD)
                max_width = 1920
                max_height = 1080
                
                # Resize if image is larger than max dimensions
                if img.width > max_width or img.height > max_height:
                    ratio = min(max_width / img.width, max_height / img.height)
                    new_size = (int(img.width * ratio), int(img.height * ratio))
                    img = img.resize(new_size, Image.Resampling.LANCZOS)
                    logger.info(f"Resized image from {original_width}x{original_height} to {new_size[0]}x{new_size[1]}")
                
                # Save optimized image to buffer
                output = io.BytesIO()
                
                if ext == '.png':
                    # For PNG, use optimize and reduce colors if possible
                    img.save(output, format='PNG', optimize=True)
                elif ext == '.webp':
                    # WebP with quality compression
                    img.save(output, format='WEBP', quality=85, method=6)
                else:
                    # JPEG with quality compression
                    img.save(output, format='JPEG', quality=85, optimize=True)
                
                optimized_content = output.getvalue()
                
                # Only use optimized version if it's actually smaller
                if len(optimized_content) < original_size:
                    final_content = optimized_content
                    optimized = True
                    logger.info(f"Image optimized: {original_size} bytes -> {len(final_content)} bytes ({100 - (len(final_content)/original_size*100):.1f}% reduction)")
                else:
                    logger.info(f"Optimization skipped: optimized size ({len(optimized_content)}) >= original ({original_size})")
            
        except Exception as e:
            logger.warning(f"Image optimization failed, using original: {e}")
            # Use original content if optimization fails
    
    # Save file
    file_id = str(uuid.uuid4())
    filename = f"{file_id}{ext}"
    file_path = PROJECTS_DIR / project_id / "assets" / filename
    file_path.parent.mkdir(parents=True, exist_ok=True)
    
    async with aiofiles.open(file_path, 'wb') as f:
        await f.write(final_content)
    
    # Persist in MongoDB for production environments with ephemeral storage
    try:
        from services.asset_store import store_asset_async
        await store_asset_async(db, project_id, filename, str(file_path))
    except Exception as e:
        logger.warning(f"Failed to persist media in MongoDB (non-fatal): {e}")
    
    return {
        "id": file_id,
        "filename": filename,
        "url": f"/api/projects/{project_id}/assets/{filename}",
        "size": len(final_content),
        "originalSize": original_size,
        "optimized": optimized,
        "type": ext[1:]
    }

# Audio Recording

@router.post("/projects/{project_id}/slides/{slide_id}/audio")
async def upload_slide_audio(
    project_id: str,
    slide_id: str,
    file: UploadFile = File(...),
    audio_type: str = Form("narration")
):
    """Upload audio for a slide"""
    project = await get_project_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Validate
    if not file.filename.lower().endswith(('.mp3', '.wav', '.ogg', '.webm')):
        raise HTTPException(status_code=400, detail="Invalid audio format")
    
    content = await file.read()
    
    # Save file
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
    
    # Update slide with audio
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

# Global Audio (Soundtrack)

@router.post("/projects/{project_id}/global-audio")
async def set_global_audio(project_id: str, file: UploadFile = File(...)):
    """Set global soundtrack for the course"""
    project = await get_project_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
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
async def remove_global_audio(project_id: str):
    """Remove global audio from project"""
    project = await get_project_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    course = project.get('course', {})
    
    # Remove global audio file if exists
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
async def update_global_audio_volume(project_id: str, volume: float):
    """Update global audio volume"""
    project = await get_project_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    course = project.get('course', {})
    if not course.get('globalAudio'):
        raise HTTPException(status_code=404, detail="No global audio set")
    
    # Clamp volume between 0 and 1
    volume = max(0.0, min(1.0, volume))
    course['globalAudio']['volume'] = volume
    
    await update_project(project_id, {"course": course})
    
    return course['globalAudio']


@router.delete("/projects/{project_id}/slides/{slide_id}/audio/{audio_id}")
async def remove_slide_audio(project_id: str, slide_id: str, audio_id: str):
    """Remove audio from slide"""
    project = await get_project_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    course = project.get('course', {})
    slides = course.get('slides', [])
    
    slide_index = next((i for i, s in enumerate(slides) if s.get('id') == slide_id), None)
    if slide_index is None:
        raise HTTPException(status_code=404, detail="Slide not found")
    
    audio_list = slides[slide_index].get('audio', [])
    
    # Find and remove audio
    audio_to_remove = next((a for a in audio_list if a.get('id') == audio_id), None)
    if not audio_to_remove:
        raise HTTPException(status_code=404, detail="Audio not found")
    
    # Remove audio file
    if audio_to_remove.get('filename'):
        assets_dir = Path(f"storage/projects/{project_id}/assets")
        audio_path = assets_dir / audio_to_remove['filename']
        if audio_path.exists():
            audio_path.unlink()
    
    # Update slide
    slides[slide_index]['audio'] = [a for a in audio_list if a.get('id') != audio_id]
    course['slides'] = slides
    
    await update_project(project_id, {"course": course})
    
    return {"message": "Audio removed from slide"}


@router.put("/projects/{project_id}/slides/{slide_id}/audio/{audio_id}/volume")
async def update_slide_audio_volume(project_id: str, slide_id: str, audio_id: str, volume: float):
    """Update slide audio volume"""
    project = await get_project_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    course = project.get('course', {})
    slides = course.get('slides', [])
    
    slide_index = next((i for i, s in enumerate(slides) if s.get('id') == slide_id), None)
    if slide_index is None:
        raise HTTPException(status_code=404, detail="Slide not found")
    
    audio_list = slides[slide_index].get('audio', [])
    audio_index = next((i for i, a in enumerate(audio_list) if a.get('id') == audio_id), None)
    if audio_index is None:
        raise HTTPException(status_code=404, detail="Audio not found")
    
    # Clamp volume between 0 and 1
    volume = max(0.0, min(1.0, volume))
    audio_list[audio_index]['volume'] = volume
    slides[slide_index]['audio'] = audio_list
    course['slides'] = slides
    
    await update_project(project_id, {"course": course})
    
    return audio_list[audio_index]


@router.put("/projects/{project_id}/slides/{slide_id}/audio/{audio_id}/timing")
async def update_slide_audio_timing(project_id: str, slide_id: str, audio_id: str, data: dict):
    """Update slide audio timing (startTime and duration for trimming)"""
    project = await get_project_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
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
    
    # Update timing
    if data.get('startTime') is not None:
        audio_list[audio_index]['startTime'] = max(0, data['startTime'])
    if data.get('duration') is not None:
        audio_list[audio_index]['duration'] = max(0.5, data['duration'])
    
    slides[slide_index]['audio'] = audio_list
    course['slides'] = slides
    
    await update_project(project_id, {"course": course})
    
    return audio_list[audio_index]


# Annotations

@router.post("/projects/{project_id}/slides/{slide_id}/annotations")
async def add_annotation(project_id: str, slide_id: str, data: AnnotationCreate):
    """Add annotation to slide"""
    project = await get_project_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
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
async def update_annotation(project_id: str, slide_id: str, annotation_id: str, update_data: dict):
    """Update annotation (for timeline settings)"""
    from models import AnnotationUpdate
    
    project = await get_project_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
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
async def delete_annotation(project_id: str, slide_id: str, annotation_id: str):
    """Delete annotation"""
    project = await get_project_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
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



@router.post("/projects/{project_id}/apply-design-template")
async def apply_design_template_to_project(project_id: str, data: dict):
    """Apply a design template to all slides of an existing project (for manual editor)."""
    from datetime import datetime, timezone
    design_template_id = data.get("designTemplateId", "")
    if not design_template_id:
        raise HTTPException(400, "designTemplateId is required")

    project = await db.projects.find_one({"id": project_id}, {"_id": 0})
    if not project:
        raise HTTPException(404, "Project not found")

    from services.ai_agent import get_design_template_by_id
    design_token = get_design_template_by_id(design_template_id)
    if not design_token:
        raise HTTPException(404, "Design template not found")

    slides = project.get("course", {}).get("slides", [])
    updated = 0

    from routes.agent import _apply_design_token_to_slide
    for slide in slides:
        _apply_design_token_to_slide(slide, design_token)
        updated += 1

    await db.projects.update_one(
        {"id": project_id},
        {"$set": {
            "course.slides": slides,
            "designTemplateId": design_template_id,
            "updatedAt": datetime.now(timezone.utc).isoformat(),
        }}
    )

    return {"status": "ok", "updatedSlides": updated, "templateId": design_template_id, "templateName": design_token["name"]}
