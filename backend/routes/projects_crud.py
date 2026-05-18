"""Top-level project CRUD + Course + Job + PPT upload + design templates.

Extracted from the old monolithic routes/projects.py. This module holds the
"entry-point" routes: creating/reading/updating/deleting a project and the
PPT upload pipeline that creates projects from PowerPoint files.
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, BackgroundTasks, Request, Depends
from typing import List, Optional
from pathlib import Path
import uuid
import shutil
import logging
import aiofiles

from routes.deps import (
    db, now_utc, serialize_doc, get_project_by_id, update_project,
    PROJECTS_DIR, UPLOADS_DIR, jobs, create_job, get_job
)
from routes.auth import require_auth, has_role
from routes.projects_common import load_authorized_project, process_ppt_upload, resolve_company_id_for_creation, can_change_project_company
from models import (
    Project, ProjectCreate, ProjectUpdate, Slide, JobStatus
)

logger = logging.getLogger("server")

router = APIRouter(tags=["Projects"])


# ---------------------------------------------------------------------------
# Project CRUD
# ---------------------------------------------------------------------------

@router.get("/projects", response_model=List[dict])
async def list_projects(user: dict = Depends(require_auth)):
    """List projects visible to the current user.

    - super_admin: sees ALL projects (including legacy ones without companyId)
    - any other role (company_admin, editor, aprovador, ...): sees only
      projects where companyId == user.companyId.

    Returns a LIGHT projection (only metadata + first slide for thumbnail) so
    the response stays small enough to fit through the production gateway.
    Companies with many heavy projects (slides+inlined media) were hitting
    520 Bad Gateway because the full-document response could exceed
    50+ MB. Frontend (Dashboard.jsx) only needs first slide for the
    SlideMinPreview thumbnail and a slide count.
    """
    pipeline = []
    if not has_role(user, "super_admin"):
        user_company = user.get("companyId")
        if not user_company:
            return []
        pipeline.append({"$match": {"companyId": user_company}})
    pipeline.extend([
        {"$sort": {"createdAt": -1}},
        {"$limit": 500},
        {"$project": {
            "_id": 0,
            "id": 1,
            "name": 1,
            "title": 1,
            "description": 1,
            "tags": 1,
            "createdAt": 1,
            "updatedAt": 1,
            "userId": 1,
            "companyId": 1,
            "source": 1,
            "agentSessionId": 1,
            "createdByAgent": 1,
            "singlePageMode": 1,
            "vlibras": 1,
            "approvalStatus": 1,
            "course": {
                "metadata": "$course.metadata",
                # Only first slide for the thumbnail preview
                "slides": {"$slice": [{"$ifNull": ["$course.slides", []]}, 1]},
                # Total slide count for the badge
                "slidesCount": {"$size": {"$ifNull": ["$course.slides", []]}},
            },
        }},
    ])
    projects = await db.projects.aggregate(pipeline).to_list(500)
    return projects


@router.post("/projects", response_model=dict)
async def create_project(data: ProjectCreate, user: dict = Depends(require_auth)):
    """Create a new project. Automatically tags it with the creator's
    userId and companyId so per-company isolation works downstream.

    Super_admins may pass `companyId` in the body to attribute the project
    to a specific client company (used when service-providers manage
    multiple companies and need cost reporting per company).
    """
    project = Project(name=data.name, description=data.description)
    project.course.metadata.title = data.name
    project.course.slides = [Slide(title="Slide 1", order=0, background="#FFFFFF")]

    project_dict = project.model_dump()
    project_dict['createdAt'] = project.createdAt.isoformat()
    project_dict['updatedAt'] = project.updatedAt.isoformat()
    project_dict['course']['createdAt'] = project.course.createdAt.isoformat()
    project_dict['course']['updatedAt'] = project.course.updatedAt.isoformat()
    project_dict['source'] = 'manual'
    project_dict['userId'] = user.get('user_id')
    project_dict['companyId'] = await resolve_company_id_for_creation(user, data.companyId)

    await db.projects.insert_one(project_dict)

    project_dir = PROJECTS_DIR / project.id
    (project_dir / "assets").mkdir(parents=True, exist_ok=True)

    return serialize_doc(project_dict)


@router.get("/projects/{project_id}", response_model=dict)
async def get_project(project_id: str, user: dict = Depends(require_auth)):
    """Get project by ID. Enforces per-company access isolation."""
    project = await load_authorized_project(project_id, user)

    # Sanitize any non-string htmlContent (from previous AI bugs)
    needs_fix = False
    for slide in project.get("course", {}).get("slides", []):
        for el in slide.get("elements", []):
            hc = el.get("htmlContent")
            if hc is not None and not isinstance(hc, str):
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


@router.put("/projects/{project_id}", response_model=dict)
async def update_project_endpoint(project_id: str, data: ProjectUpdate, user: dict = Depends(require_auth)):
    """Update project. Enforces per-company access isolation.

    Returns a lightweight ack instead of the full project document — projects
    can grow to many MB (slides + base64-inlined media + htmlContent), and
    serialising the whole thing here was causing 502 Bad Gateway in production
    (proxy timeout / response too large). Frontend re-fetches via GET when it
    needs the fresh state.

    `companyId` in the body re-assigns the project to a different company.
    Only super_admin may use this — other roles have it silently dropped.
    """
    await load_authorized_project(project_id, user)
    update_data = data.model_dump(exclude_unset=True)

    # Company re-assignment guard
    if 'companyId' in update_data:
        new_company_id = update_data.get('companyId')
        if not can_change_project_company(user):
            # Silently drop — non-super-admins cannot reattribute projects
            update_data.pop('companyId', None)
        elif new_company_id:
            # Validate target company exists
            company = await db.companies.find_one({"id": new_company_id}, {"_id": 0, "id": 1})
            if not company:
                raise HTTPException(status_code=400, detail=f"Company '{new_company_id}' not found")

    if 'name' in update_data:
        update_data['course.metadata.title'] = update_data['name']

    await update_project(project_id, update_data)

    return {"success": True, "id": project_id, "updated": list(update_data.keys())}


@router.delete("/projects/{project_id}")
async def delete_project(project_id: str, user: dict = Depends(require_auth)):
    """Delete project. Enforces per-company access isolation."""
    await load_authorized_project(project_id, user)
    await db.projects.delete_one({"id": project_id})

    project_dir = PROJECTS_DIR / project_id
    if project_dir.exists():
        shutil.rmtree(project_dir)

    return {"message": "Project deleted"}


# ---------------------------------------------------------------------------
# Static simulator repair (legacy helper for old AI-generated courses)
# ---------------------------------------------------------------------------

@router.post("/projects/{project_id}/fix-simulators")
async def fix_simulators(project_id: str, user: dict = Depends(require_auth)):
    """Detect and fix static simulators in a course by adding JavaScript interactivity."""
    import re as _re

    project = await load_authorized_project(project_id, user)
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
                cap_match = _re.search(r'(\d+)\s*Ah', hc)
                capacity = int(cap_match.group(1)) if cap_match else 100

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


# ---------------------------------------------------------------------------
# Course get/save (legacy endpoints that mirror GET/PUT on /projects)
# ---------------------------------------------------------------------------

@router.get("/course/{project_id}")
async def get_course(project_id: str, user: dict = Depends(require_auth)):
    """Get course data for a project"""
    project = await load_authorized_project(project_id, user)
    return project.get('course', {})


@router.post("/course/{project_id}/save")
async def save_course(project_id: str, course_data: dict, user: dict = Depends(require_auth)):
    """Save course data"""
    await load_authorized_project(project_id, user)
    await update_project(project_id, {"course": course_data})
    return {"message": "Course saved"}


# ---------------------------------------------------------------------------
# Job status (for PPT background processing)
# ---------------------------------------------------------------------------

@router.get("/job/{job_id}", response_model=JobStatus)
async def get_job_status(job_id: str):
    """Get job status - checks local cache and MongoDB"""
    job = await get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobStatus(**job)


# ---------------------------------------------------------------------------
# PPT Upload (chunked + legacy)
# ---------------------------------------------------------------------------

@router.post("/ppt/upload/init")
async def init_chunked_upload(request: Request, user: dict = Depends(require_auth)):
    """Initialize a chunked PPT upload - returns an upload_id"""
    body = await request.json()
    filename = body.get('filename', 'upload.pptx')
    total_size = body.get('totalSize', 0)
    requested_company_id = body.get('companyId')

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
        'userId': user.get('user_id'),
        'companyId': await resolve_company_id_for_creation(user, requested_company_id),
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
                    'userId': mongo_meta.get('userId'),
                    'companyId': mongo_meta.get('companyId'),
                }
                jobs[meta_key] = meta
        except Exception:
            pass

    if not meta:
        raise HTTPException(status_code=410, detail="Upload expirado. Por favor, tente importar novamente.")

    filename = meta['filename']
    chunk_dir = Path(meta['path'])

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

    project = Project(name=project_name)
    project_dict = project.model_dump()
    project_dict['createdAt'] = project.createdAt.isoformat()
    project_dict['updatedAt'] = project.updatedAt.isoformat()
    project_dict['course']['createdAt'] = project.course.createdAt.isoformat()
    project_dict['course']['updatedAt'] = project.course.updatedAt.isoformat()
    project_dict['status'] = 'processing'
    project_dict['source'] = 'ppt'
    project_dict['userId'] = meta.get('userId')
    project_dict['companyId'] = meta.get('companyId')

    await db.projects.insert_one(project_dict)

    project_dir = PROJECTS_DIR / project.id
    (project_dir / "assets").mkdir(parents=True, exist_ok=True)

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
    project_name: Optional[str] = None,
    company_id: Optional[str] = None,
    user: dict = Depends(require_auth),
):
    """Upload and process a PPT/PPTX file (legacy non-chunked flow).
    `company_id` (super_admin only) attributes the project to a specific
    client company; ignored for regular users."""
    logger.info(f"PPT upload received: filename={file.filename}, content_type={file.content_type}, size_hint={file.size}")

    if not file.filename.lower().endswith(('.ppt', '.pptx')):
        logger.warning(f"PPT upload rejected: invalid file type: {file.filename}")
        raise HTTPException(status_code=400, detail="Invalid file type. Only PPT/PPTX files are allowed.")

    content = await file.read()
    if len(content) > 50 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large. Maximum size is 50MB.")

    project_name = project_name or Path(file.filename).stem
    project = Project(name=project_name)

    project_dict = project.model_dump()
    project_dict['createdAt'] = project.createdAt.isoformat()
    project_dict['updatedAt'] = project.updatedAt.isoformat()
    project_dict['course']['createdAt'] = project.course.createdAt.isoformat()
    project_dict['course']['updatedAt'] = project.course.updatedAt.isoformat()
    project_dict['status'] = 'processing'
    project_dict['source'] = 'ppt'
    project_dict['userId'] = user.get('user_id')
    project_dict['companyId'] = await resolve_company_id_for_creation(user, company_id)

    await db.projects.insert_one(project_dict)

    project_dir = PROJECTS_DIR / project.id
    (project_dir / "assets").mkdir(parents=True, exist_ok=True)

    import re as _re_fn
    safe_filename = _re_fn.sub(r'[^\w\-_. ]', '_', file.filename)
    upload_path = UPLOADS_DIR / f"{project.id}_{safe_filename}"
    async with aiofiles.open(upload_path, 'wb') as f:
        await f.write(content)

    # Create job ID early (needed for MongoDB persist)
    job_id = str(uuid.uuid4())

    # Persist PPT file to MongoDB so it survives deploy/restart
    ppt_persisted = False
    for _persist_attempt in range(3):
        try:
            import base64 as _b64
            await db.ppt_uploads.update_one(
                {"projectId": project.id},
                {"$set": {
                    "projectId": project.id,
                    "jobId": job_id,
                    "filename": safe_filename,
                    "path": str(upload_path),
                    "fileSize": len(content),
                    "data": _b64.b64encode(content).decode('ascii'),
                    "createdAt": now_utc().isoformat(),
                }},
                upsert=True,
            )
            ppt_persisted = True
            logger.info(f"PPT file persisted to MongoDB: {project.id}/{safe_filename} ({len(content)} bytes)")
            break
        except Exception as e:
            logger.warning(f"Failed to persist PPT to MongoDB (attempt {_persist_attempt+1}): {e}")
            if _persist_attempt < 2:
                import asyncio as _aio
                await _aio.sleep(2)

    if not ppt_persisted:
        logger.error(f"CRITICAL: PPT file NOT persisted to MongoDB after 3 attempts: {project.id}")
        if len(content) > 12 * 1024 * 1024:
            logger.warning(f"PPT file is {len(content)} bytes - too large for MongoDB BSON limit (16MB). Skipping persist.")

    jobs[job_id] = {
        'id': job_id,
        'status': 'pending',
        'progress': 0,
        'message': 'Upload received, starting processing...',
        'result': None
    }

    background_tasks.add_task(process_ppt_upload, job_id, str(upload_path), project.id)

    return {
        "jobId": job_id,
        "projectId": project.id,
        "message": "File uploaded, processing started"
    }


# ---------------------------------------------------------------------------
# Design template application
# ---------------------------------------------------------------------------
@router.post("/projects/{project_id}/apply-watermark-all")
async def apply_watermark_to_all_slides(project_id: str, user: dict = Depends(require_auth)):
    """Apply the brand-kit logo as a watermark to EVERY slide of the project.

    User-facing trigger: button "Aplicar marca d'agua em TODOS os slides"
    in the Brand Library section of the slide properties panel. Lets the
    author refresh the watermark on an already-generated course without
    regenerating from scratch (which would lose any manual tweaks).

    The actual logic is shared with the generation pipeline via
    `services.ai_agent.apply_brand_logo_to_slides()`, so the result is
    pixel-identical to what `generate_course_from_storyboard()` would
    produce. Idempotent: re-running cleans stale logos first.

    Returns: { appliedCount: int, totalSlides: int }
    """
    from datetime import datetime, timezone
    from services.ai_agent import apply_brand_logo_to_slides

    project = await load_authorized_project(project_id, user)

    # Resolve the brand kit. Priority: project's overriding brandKit (if
    # any) → company.brandKit. If neither has logoUrl, fail fast with a
    # friendly message so the UI can guide the user to the admin settings.
    brand_kit = project.get("brandKit") or {}
    if not brand_kit.get("logoUrl"):
        company_id = project.get("companyId")
        if company_id:
            from routes.deps import db
            company = await db.companies.find_one({"id": company_id}, {"_id": 0, "brandKit": 1})
            if company and company.get("brandKit"):
                brand_kit = company["brandKit"]
    if not brand_kit or not brand_kit.get("logoUrl"):
        raise HTTPException(
            status_code=400,
            detail="Nenhum logo configurado na Brand Kit da empresa. Acesse Admin → Biblioteca de Marca para fazer upload do logo.",
        )

    slides = (project.get("course") or {}).get("slides") or []
    if not slides:
        raise HTTPException(status_code=400, detail="O projeto nao tem slides para aplicar marca d'agua.")

    applied = apply_brand_logo_to_slides(slides, brand_kit)

    # Persist the mutation. We rewrite course.slides + updatedAt so the
    # frontend's autosync picks up the change immediately on reload.
    from routes.deps import db
    await db.projects.update_one(
        {"id": project_id},
        {"$set": {
            "course.slides": slides,
            "updatedAt": datetime.now(timezone.utc).isoformat(),
        }},
    )
    return {"appliedCount": applied, "totalSlides": len(slides)}




@router.post("/projects/{project_id}/apply-design-template")
async def apply_design_template_to_project(project_id: str, data: dict, user: dict = Depends(require_auth)):
    """Apply a design template to all slides of an existing project (for manual editor)."""
    from datetime import datetime, timezone
    design_template_id = data.get("designTemplateId", "")
    if not design_template_id:
        raise HTTPException(400, "designTemplateId is required")

    project = await load_authorized_project(project_id, user)

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
