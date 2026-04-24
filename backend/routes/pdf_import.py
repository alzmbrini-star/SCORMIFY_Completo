"""PDF import routes — chunked upload, extraction preview, repair, Modo Fiel.

Extracted from routes/agent.py to keep the agent module focused on AI
orchestration. These endpoints share the same URL prefixes (/agent/sessions
and /projects) but are all related to importing or rendering PDFs.
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Request, Depends
from typing import Optional
import os
import asyncio
import logging
import re
from pathlib import Path
from datetime import datetime, timezone

from routes.deps import db, PROJECTS_DIR
from routes.auth import require_agent_access, require_auth

logger = logging.getLogger("server")

router = APIRouter(tags=["PDF Import"])

# Track background PDF extraction tasks per session so Modo Fiel can cancel
# them and free the thread pool when the user decides to skip the slow path.
_PDF_EXTRACTION_TASKS: dict = {}


# =============================================================================
# CHUNKED PDF UPLOAD (streams directly to GridFS to avoid OOM on large files)
# =============================================================================

@router.post("/agent/sessions/{session_id}/upload-chunk")
async def agent_upload_chunk(
    session_id: str,
    chunk: UploadFile = File(...),
    uploadId: str = Form(...),
    chunkIndex: int = Form(...),
    totalChunks: int = Form(...),
    fileName: str = Form(...),
    user: dict = Depends(require_agent_access),
):
    """Chunked upload for large files (>5MB) that exceed Cloudflare / nginx
    request-body limits when sent in a single POST.

    The client splits the file into ~5MB chunks and sends them sequentially
    with a shared `uploadId`. Once all chunks arrive, the last request
    reassembles the file and forwards it through the normal upload pipeline
    (same behavior as /upload, including async PDF extraction).

    Returns: {"status": "chunk_received", "received": N, "total": M} until the
    last chunk, then the full upload response.
    """
    s = await db.agent_sessions.find_one({"id": session_id}, {"_id": 0, "id": 1})
    if not s:
        raise HTTPException(404, "Session not found")

    # Sanitize uploadId (must be safe for a filename)
    safe_upload_id = re.sub(r"[^A-Za-z0-9_\-]", "", uploadId)[:64]
    if not safe_upload_id:
        raise HTTPException(400, "Invalid uploadId")

    # Validate chunk indexes
    if chunkIndex < 0 or totalChunks <= 0 or chunkIndex >= totalChunks:
        raise HTTPException(400, "Invalid chunk index")

    # Per-session tmp dir (rooted under /tmp so the container's ephemeral disk
    # is enough). Chunks are small (~5MB) so we don't exceed disk budget.
    tmp_dir = Path("/tmp") / f"upload_{session_id}_{safe_upload_id}"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    chunk_path = tmp_dir / f"chunk_{chunkIndex:04d}"
    try:
        bytes_ = await chunk.read()
        chunk_path.write_bytes(bytes_)
    except Exception as e:
        raise HTTPException(500, f"Erro ao salvar chunk: {e}")

    # How many chunks have we received so far?
    received = sum(1 for p in tmp_dir.iterdir() if p.name.startswith("chunk_"))

    if received < totalChunks:
        return {"status": "chunk_received", "received": received, "total": totalChunks}

    # All chunks received — stream them directly into GridFS one by one,
    # WITHOUT ever holding the full file in memory. This is critical on low-
    # memory production pods where assembling a 30-100MB file in RAM
    # (plus PyPDF2 parsing it) causes OOM → 520 errors.
    import gc as _gc
    parts = sorted(p for p in tmp_dir.iterdir() if p.name.startswith("chunk_"))
    if not parts:
        raise HTTPException(500, "Nenhum chunk encontrado para montar")

    from motor.motor_asyncio import AsyncIOMotorGridFSBucket
    pdf_bucket = AsyncIOMotorGridFSBucket(db, bucket_name="pdf_imports")

    # Stream chunks straight into GridFS
    try:
        upload_stream = pdf_bucket.open_upload_stream(
            filename=f"session_{session_id}.pdf",
            metadata={"session_id": session_id, "file_name": fileName},
        )
        first_part_bytes = b""  # keep only the first ~256KB for PyPDF2 text preview
        PREVIEW_BYTES = 256 * 1024

        for idx, chunk_path in enumerate(parts):
            data = chunk_path.read_bytes()
            await upload_stream.write(data)
            # Keep a small preview for quick text extraction
            if len(first_part_bytes) < PREVIEW_BYTES:
                first_part_bytes += data[:PREVIEW_BYTES - len(first_part_bytes)]
            # Delete the chunk file immediately after writing to free disk
            try:
                chunk_path.unlink()
            except Exception:
                pass
            # Yield and collect every few chunks to keep memory low
            if (idx + 1) % 3 == 0:
                _gc.collect()
                await asyncio.sleep(0)

        await upload_stream.close()
        pdf_gridfs_id = upload_stream._id
    except Exception as e:
        import traceback as _tb
        logger.error(f"[upload-chunk] GridFS streaming failed: {e}\n{_tb.format_exc()}")
        try:
            import shutil as _sh
            _sh.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass
        raise HTTPException(500, f"Erro ao salvar PDF: {str(e)[:180]}")

    # Cleanup
    try:
        import shutil as _sh
        _sh.rmtree(tmp_dir, ignore_errors=True)
    except Exception:
        pass

    # Try a quick text preview from the first chunk (doesn't require the full
    # PDF). If it fails, we leave content_text empty — Modo Fiel will render
    # the pages regardless.
    content_text = ""
    if fileName.lower().endswith(".pdf") and first_part_bytes:
        try:
            from PyPDF2 import PdfReader
            import io as _io
            reader = PdfReader(_io.BytesIO(first_part_bytes), strict=False)
            pages = []
            # Only parse up to 10 pages for the preview (stays cheap)
            for i, page in enumerate(reader.pages):
                if i >= 10:
                    break
                try:
                    t = page.extract_text()
                    if t:
                        pages.append(t)
                except Exception:
                    continue
            content_text = "\n\n".join(pages)[:10000]
        except Exception as e:
            logger.info(f"[upload-chunk] PyPDF2 preview skipped (not critical): {e}")
            content_text = ""

    # Release the preview bytes so they don't linger in memory
    first_part_bytes = None
    _gc.collect()

    # Update the session — mirrors the logic in _agent_upload_content_impl
    set_doc = {
        "contentText": content_text,
        "fileName": fileName,
        "rawFileGridFS": str(pdf_gridfs_id),
        "pdfExtractionStatus": {
            "status": "pdf_ready",
            "message": "PDF recebido. Use Modo Fiel para gerar o curso.",
            "progress": 0,
            "startedAt": datetime.now(timezone.utc).isoformat(),
        },
        "updatedAt": datetime.now(timezone.utc).isoformat(),
    }
    await db.agent_sessions.update_one(
        {"id": session_id},
        {"$set": set_doc},
    )
    return {
        "status": "ok",
        "contentLength": len(content_text),
        "fileName": fileName,
        "pdfReady": True,
    }


# =============================================================================
# BACKGROUND PDF EXTRACTION (legacy — kept for backwards compatibility)
# =============================================================================

async def _background_pdf_extraction(session_id: str, file_bytes: bytes):
    """Run rich PDF extraction (images + OCR) in the background and update
    the session document when done. Runs after the upload HTTP response has
    already been returned to the client, so heavy OCR never triggers a 504/520.
    """
    try:
        from services.pdf_extractor import extract_pdf, payload_to_markdown
        from services.asset_store import store_asset_async

        tmp_project_id = f"pdfimport_{session_id}"
        tmp_assets_dir = PROJECTS_DIR / tmp_project_id / "assets"

        # Progress throttle: update MongoDB at most every ~1.5s to avoid
        # hammering the database while still giving smooth UI progress.
        # We also SERIALIZE updates via an asyncio.Lock so slow Atlas writes
        # don't accumulate orphan tasks and block the event loop.
        import time as _time
        last_update = {"t": 0.0, "pending_msg": None, "pending_pct": None}
        progress_lock = asyncio.Lock()

        async def _flush_progress():
            async with progress_lock:
                if last_update["pending_pct"] is None:
                    return
                pct = last_update["pending_pct"]
                msg = last_update["pending_msg"]
                last_update["pending_pct"] = None
                last_update["pending_msg"] = None
                try:
                    await asyncio.wait_for(
                        db.agent_sessions.update_one(
                            {"id": session_id},
                            {"$set": {
                                "pdfExtractionStatus.progress": pct,
                                "pdfExtractionStatus.message": msg,
                                "updatedAt": datetime.now(timezone.utc).isoformat(),
                            }}
                        ),
                        timeout=5.0,
                    )
                except Exception as e:
                    logger.warning(f"[bg-pdf] progress flush failed: {e}")

        def _progress(pct, msg):
            now = _time.monotonic()
            overall = min(int(pct * 80), 80)
            # Always remember the latest state
            last_update["pending_pct"] = overall
            last_update["pending_msg"] = f"Extraindo {msg}..."
            # Throttle: only flush if 1s passed since last flush, OR we're at 100%
            if now - last_update["t"] < 1.0 and pct < 0.999:
                return
            last_update["t"] = now
            # Schedule a non-blocking flush (create_task OK here because
            # _flush_progress itself has a timeout, so tasks can't pile up).
            try:
                asyncio.create_task(_flush_progress())
            except Exception:
                pass

        extraction = await extract_pdf(file_bytes, tmp_assets_dir, progress_cb=_progress)

        # 80-95%: persist images to MongoDB
        total_assets = len(extraction.get("asset_filenames", []))
        for idx, fname in enumerate(extraction.get("asset_filenames", [])):
            fpath = tmp_assets_dir / fname
            if fpath.exists():
                try:
                    await store_asset_async(db, tmp_project_id, fname, str(fpath))
                except Exception as pe:
                    logger.warning(f"[bg-pdf] asset persist failed {fname}: {pe}")
            if total_assets > 0 and (idx + 1) % 10 == 0:
                pct = 80 + int(15 * (idx + 1) / total_assets)
                try:
                    await db.agent_sessions.update_one(
                        {"id": session_id},
                        {"$set": {
                            "pdfExtractionStatus.progress": pct,
                            "pdfExtractionStatus.message": f"Salvando imagens ({idx+1}/{total_assets})...",
                            "updatedAt": datetime.now(timezone.utc).isoformat(),
                        }}
                    )
                except Exception:
                    pass

        # Update session with rich extraction. Replace the fast PyPDF2 preview
        # with the markdown payload (which includes [IMG:] markers).
        md = payload_to_markdown(extraction)
        await db.agent_sessions.update_one(
            {"id": session_id},
            {"$set": {
                "contentText": md,
                "pdfExtraction": {
                    "tmpProjectId": tmp_project_id,
                    "totalPages": extraction.get("total_pages", 0),
                    "scannedPages": extraction.get("scanned_pages", 0),
                    "imagesExtracted": extraction.get("images_extracted", 0),
                    "assetFilenames": extraction.get("asset_filenames", []),
                },
                "pdfExtractionStatus": {
                    "status": "done",
                    "message": (
                        f"Extracao concluida: {extraction.get('total_pages', 0)} paginas, "
                        f"{extraction.get('images_extracted', 0)} imagens"
                    ),
                    "progress": 100,
                    "finishedAt": datetime.now(timezone.utc).isoformat(),
                },
                "updatedAt": datetime.now(timezone.utc).isoformat(),
            }}
        )
        logger.info(
            f"[bg-pdf] session={session_id} done: "
            f"{extraction.get('total_pages', 0)} pages, "
            f"{extraction.get('images_extracted', 0)} images"
        )
    except Exception as e:
        import traceback as _tb
        logger.error(f"[bg-pdf] session={session_id} failed: {e}\n{_tb.format_exc()}")
        try:
            await db.agent_sessions.update_one(
                {"id": session_id},
                {"$set": {
                    "pdfExtractionStatus": {
                        "status": "error",
                        "message": f"Falha na extracao: {str(e)[:180]}",
                        "progress": 0,
                        "finishedAt": datetime.now(timezone.utc).isoformat(),
                    },
                    "updatedAt": datetime.now(timezone.utc).isoformat(),
                }}
            )
        except Exception:
            pass


# =============================================================================
# PDF PREVIEW (editorial editing of extracted images)
# =============================================================================

def _page_hint_from_filename(fname: str) -> str:
    """Extract 'Pagina N' hint from pdf_pN_imgM.png / pdf_pN_full.png."""
    m = re.match(r"pdf_p(\d+)_", fname)
    return f"Pagina {m.group(1)}" if m else ""


@router.get("/agent/sessions/{session_id}/pdf-preview")
async def agent_pdf_preview(session_id: str, user: dict = Depends(require_agent_access)):
    """Return the PDF extraction preview (chapters + pages + images + user edits)."""
    s = await db.agent_sessions.find_one(
        {"id": session_id},
        {"_id": 0, "pdfExtraction": 1, "pdfPreview": 1, "contentText": 1,
         "fileName": 1, "pdfExtractionStatus": 1, "rawFileGridFS": 1}
    )
    if not s:
        raise HTTPException(404, "Session not found")
    pdf_meta = s.get("pdfExtraction") or {}
    status_info = s.get("pdfExtractionStatus") or {}
    has_pdf_file = bool(s.get("rawFileGridFS"))

    # Still processing in background — let the client poll
    if not pdf_meta.get("tmpProjectId") and status_info.get("status") == "processing":
        return {
            "hasPdf": True,
            "processing": True,
            "fileName": s.get("fileName", ""),
            "statusMessage": status_info.get("message", "Processando..."),
            "progress": status_info.get("progress", 0),
        }

    # PDF was uploaded but extraction produced no images (failed, empty, or
    # fully scanned and OCR gave little/nothing). Keep the panel visible so
    # the user can fall back to Modo Fiel.
    if has_pdf_file and not pdf_meta.get("tmpProjectId"):
        return {
            "hasPdf": True,
            "processing": False,
            "extractionFailed": True,
            "fileName": s.get("fileName", ""),
            "statusMessage": (
                status_info.get("message")
                or "A extracao automatica nao produziu imagens utilizaveis. "
                "Use Modo Fiel para gerar o curso com as paginas do PDF como slides."
            ),
            "images": [],
            "totalPages": status_info.get("totalPages", 0),
        }

    if not pdf_meta.get("tmpProjectId"):
        return {"hasPdf": False}

    tmp_pid = pdf_meta["tmpProjectId"]
    filenames = pdf_meta.get("assetFilenames", [])

    # Load or initialize per-image user preferences
    saved = s.get("pdfPreview") or {}
    image_prefs = saved.get("images", {})
    images = []
    for fname in filenames:
        pref = image_prefs.get(fname, {})
        images.append({
            "filename": fname,
            "url": f"/api/projects/{tmp_pid}/assets/{fname}",
            "included": pref.get("included", True),
            "caption": pref.get("caption", ""),
            "pageHint": _page_hint_from_filename(fname),
        })
    return {
        "hasPdf": True,
        "fileName": s.get("fileName", ""),
        "totalPages": pdf_meta.get("totalPages", 0),
        "scannedPages": pdf_meta.get("scannedPages", 0),
        "imagesExtracted": pdf_meta.get("imagesExtracted", 0),
        "images": images,
    }


@router.post("/agent/sessions/{session_id}/pdf-preview")
async def agent_save_pdf_preview(
    session_id: str, request: Request,
    user: dict = Depends(require_agent_access),
):
    """Save user edits on extracted PDF images before course generation.
    Body: {"images": [{"filename": "...", "included": true, "caption": "..."}, ...]}
    """
    s = await db.agent_sessions.find_one({"id": session_id}, {"_id": 0, "pdfExtraction": 1})
    if not s:
        raise HTTPException(404, "Session not found")
    if not (s.get("pdfExtraction") or {}).get("tmpProjectId"):
        raise HTTPException(400, "No PDF extraction found for this session")

    body = await request.json()
    items = body.get("images", [])
    if not isinstance(items, list):
        raise HTTPException(400, "images must be a list")

    prefs: dict = {}
    excluded = 0
    for it in items:
        fname = it.get("filename")
        if not fname:
            continue
        included = bool(it.get("included", True))
        caption = (it.get("caption") or "").strip()[:200]
        prefs[fname] = {"included": included, "caption": caption}
        if not included:
            excluded += 1

    await db.agent_sessions.update_one(
        {"id": session_id},
        {"$set": {
            "pdfPreview": {"images": prefs, "savedAt": datetime.now(timezone.utc).isoformat()},
            "updatedAt": datetime.now(timezone.utc).isoformat(),
        }}
    )
    return {"status": "ok", "total": len(prefs), "excluded": excluded}


# =============================================================================
# REPAIR PDF IMAGES (retroactive fix for older courses)
# =============================================================================

@router.post("/projects/{project_id}/repair-pdf-images")
async def repair_pdf_images(project_id: str, user: dict = Depends(require_auth)):
    """Retroactively add PDF-extracted images to a project (re-runs the
    page-aware image placement + creates gallery slides if needed)."""
    project = await db.projects.find_one({"id": project_id}, {"_id": 0})
    if not project:
        raise HTTPException(404, "Project not found")
    session_id = project.get("agentSessionId")
    if not session_id:
        raise HTTPException(400, "This project was not generated by the AI agent")

    session = await db.agent_sessions.find_one({"id": session_id}, {"_id": 0})
    if not session:
        raise HTTPException(404, "Original agent session not found")
    pdf_meta = session.get("pdfExtraction") or {}
    if not pdf_meta.get("assetFilenames"):
        return {"status": "noop", "message": "Este projeto nao foi criado a partir de PDF com imagens."}

    # Ensure assets migrated to the real project (idempotent)
    from services.pdf_extractor import (
        migrate_pdf_assets, replace_img_markers_in_slides,
    )
    try:
        await migrate_pdf_assets(db, pdf_meta["tmpProjectId"], project_id, PROJECTS_DIR)
    except Exception as e:
        logger.warning(f"[repair] migrate assets failed (non-fatal): {e}")

    image_prefs = (session.get("pdfPreview") or {}).get("images", {})
    available = set(pdf_meta["assetFilenames"])
    slides = project.get("course", {}).get("slides", [])

    # Remove any previous image elements pointing to pdf_p*_img*/pdf_p*_full.png
    # and any previous auto-generated gallery slides (flag _pdfGallery OR
    # legacy slides titled "Ilustracoes da pagina ..." from older runs),
    # so the operation is idempotent.
    def _is_prev_gallery(s):
        if s.get("_pdfGallery"):
            return True
        title = (s.get("title") or "").strip().lower()
        return title.startswith("ilustracoes da pagina") or title.startswith("ilustrações da página")

    slides = [s for s in slides if not _is_prev_gallery(s)]
    for slide in slides:
        slide["elements"] = [
            el for el in slide.get("elements", [])
            if not (el.get("type") == "image"
                    and isinstance(el.get("src", ""), str)
                    and ("/pdf_p" in el["src"] or el["src"].endswith("_full.png")))
        ]

    inserted = replace_img_markers_in_slides(
        slides, project_id, available,
        image_prefs=image_prefs,
        total_pdf_pages=pdf_meta.get("totalPages"),
    )

    await db.projects.update_one(
        {"id": project_id},
        {"$set": {
            "course.slides": slides,
            "course.updatedAt": datetime.now(timezone.utc).isoformat(),
            "updatedAt": datetime.now(timezone.utc).isoformat(),
        }}
    )
    return {
        "status": "ok",
        "imagesInserted": inserted,
        "totalExtracted": len(available),
        "excluded": sum(1 for p in image_prefs.values() if not p.get("included", True)),
    }


# =============================================================================
# MODO FIEL (Faithful Mode: 1 PDF page = 1 slide background)
# =============================================================================

@router.post("/agent/sessions/{session_id}/generate-faithful-course")
async def agent_generate_faithful_course(
    session_id: str,
    request: Request,
    user: dict = Depends(require_agent_access),
):
    """Faithful mode: 1 PDF page -> 1 slide (page rendered as background).
    Preserves the original PDF's layout, colors, images, fonts and logos
    verbatim. Skips the LLM entirely so there is no rewriting.

    Expects the session to have had a PDF uploaded (via /upload). Optionally
    the body may contain {"title": "..."} to override the course name.
    """
    body = {}
    try:
        body = await request.json()
    except Exception:
        pass

    s = await db.agent_sessions.find_one({"id": session_id}, {"_id": 0})
    if not s:
        raise HTTPException(404, "Session not found")

    # Cancel the normal extraction task (if running) to free up the thread
    # pool. The user chose Modo Fiel — the slow extraction is no longer needed.
    _prev_task = _PDF_EXTRACTION_TASKS.pop(session_id, None)
    if _prev_task and not _prev_task.done():
        try:
            _prev_task.cancel()
            logger.info(f"[faithful] cancelled background extraction for {session_id}")
        except Exception:
            pass
    # Mark the normal extraction as cancelled so the preview panel doesn't
    # keep polling forever.
    try:
        await db.agent_sessions.update_one(
            {"id": session_id},
            {"$set": {
                "pdfExtractionStatus": {
                    "status": "cancelled",
                    "message": "Extracao cancelada pelo usuario (usando Modo Fiel).",
                    "progress": 0,
                    "finishedAt": datetime.now(timezone.utc).isoformat(),
                },
            }}
        )
    except Exception:
        pass

    gridfs_id = s.get("rawFileGridFS")
    if not gridfs_id:
        raise HTTPException(400, "PDF original nao disponivel nesta sessao. Reenvie o arquivo.")

    try:
        from motor.motor_asyncio import AsyncIOMotorGridFSBucket
        from bson import ObjectId
        pdf_bucket = AsyncIOMotorGridFSBucket(db, bucket_name="pdf_imports")
        stream = await pdf_bucket.open_download_stream(ObjectId(gridfs_id))
        pdf_bytes = await stream.read()
    except Exception as e:
        logger.error(f"[faithful] Failed to read PDF from GridFS: {e}")
        raise HTTPException(500, f"Nao foi possivel ler o PDF salvo: {e}")

    title = (body.get("title") or s.get("fileName", "Curso").rsplit(".", 1)[0]).strip()[:160]

    # Background generation to avoid Cloudflare 100s timeout on large PDFs.
    # Build the project stub immediately and return; the heavy rendering
    # happens in a separate task. Frontend polls pdfFaithfulStatus to know
    # when it's done and redirect to the editor.
    from models import Project
    project = Project(name=title, description=f"Curso fiel ao PDF: {s.get('fileName','')}")
    project_dict = project.model_dump()
    project_dict["createdAt"] = project.createdAt.isoformat()
    project_dict["updatedAt"] = project.updatedAt.isoformat()
    project_dict["course"]["createdAt"] = project.course.createdAt.isoformat()
    project_dict["course"]["updatedAt"] = project.course.updatedAt.isoformat()
    project_dict["course"]["metadata"]["title"] = title
    project_dict["course"]["metadata"]["description"] = project.description
    project_dict["course"]["slides"] = []  # filled in background
    project_dict["createdByAgent"] = True
    project_dict["agentSessionId"] = session_id
    project_dict["status"] = "generating"
    project_dict["userId"] = s.get("userId")
    project_dict["companyId"] = s.get("companyId")
    project_dict["importMode"] = "faithful"
    project_dict["faithfulStatus"] = {
        "status": "processing",
        "message": "Renderizando paginas...",
        "progress": 0,
        "startedAt": datetime.now(timezone.utc).isoformat(),
    }
    await db.projects.insert_one(project_dict)

    await db.agent_sessions.update_one(
        {"id": session_id},
        {"$set": {
            "projectId": project.id,
            "faithfulProjectId": project.id,
            "updatedAt": datetime.now(timezone.utc).isoformat(),
        }}
    )

    # Kick off background rendering in a SEPARATE THREAD with its own event
    # loop so it doesn't compete with incoming HTTP requests on the main
    # uvicorn event loop. This is critical for production where Tesseract /
    # PyMuPDF can monopolize the main loop and cause Cloudflare 520s on
    # polling endpoints.
    import threading as _threading

    def _thread_runner():
        # Lower CPU scheduling priority so the uvicorn event loop (which
        # serves /faithful-status polling) is favored by the OS on low-CPU
        # production pods.
        try:
            os.nice(10)
        except Exception:
            pass
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(
                _background_faithful_render(session_id, project.id, pdf_bytes)
            )
        except Exception as e:
            logger.error(f"[bg-faithful-thread] {e}", exc_info=True)
        finally:
            loop.close()

    _threading.Thread(target=_thread_runner, daemon=True, name=f"faithful-{project.id[:8]}").start()

    return {
        "status": "processing",
        "projectId": project.id,
        "message": "O curso fiel esta sendo gerado em segundo plano.",
    }


async def _background_faithful_render(session_id: str, project_id: str, pdf_bytes: bytes):
    """Render the PDF into faithful slides in the background.

    IMPORTANT: this function is expected to run in its OWN asyncio event loop
    (not the main uvicorn loop) via a daemon thread. Because Motor clients
    are bound to a specific event loop, we create a dedicated Motor client
    here and close it at the end.
    """
    from motor.motor_asyncio import AsyncIOMotorClient
    local_client = AsyncIOMotorClient(os.environ['MONGO_URL'])
    local_db = local_client[os.environ['DB_NAME']]
    try:
        from services.pdf_extractor import (
            extract_pdf_faithful, build_faithful_slides,
        )
        from services.asset_store import store_asset_async

        project_dir = PROJECTS_DIR / project_id
        (project_dir / "assets").mkdir(parents=True, exist_ok=True)

        import time as _time
        last_update = {"t": 0.0}

        def _progress(pct, msg):
            now = _time.monotonic()
            if now - last_update["t"] < 1.0 and pct < 0.999:
                return
            last_update["t"] = now
            try:
                asyncio.create_task(local_db.projects.update_one(
                    {"id": project_id},
                    {"$set": {
                        "faithfulStatus.progress": int(pct * 90),
                        "faithfulStatus.message": f"Renderizando {msg}...",
                        "updatedAt": datetime.now(timezone.utc).isoformat(),
                    }}
                ))
            except Exception:
                pass

        extraction = await extract_pdf_faithful(
            pdf_bytes, project_dir / "assets", progress_cb=_progress
        )

        # Persist pages to MongoDB INCREMENTALLY so a crash mid-way doesn't
        # lose all progress (the pod can be restarted and re-render missing
        # pages). (90-99% range)
        total = len(extraction["pages"])
        for i, p in enumerate(extraction["pages"]):
            fpath = project_dir / "assets" / p["filename"]
            if fpath.exists():
                try:
                    await store_asset_async(local_db, project_id, p["filename"], str(fpath))
                except Exception as e:
                    logger.warning(f"[bg-faithful] persist {p['filename']} failed: {e}")
            if total > 0 and (i + 1) % 5 == 0:
                try:
                    await local_db.projects.update_one(
                        {"id": project_id},
                        {"$set": {
                            "faithfulStatus.progress": 90 + int(9 * (i + 1) / total),
                            "faithfulStatus.message": f"Salvando imagens ({i+1}/{total})...",
                        }}
                    )
                except Exception:
                    pass

        slides = build_faithful_slides(extraction["pages"], project_id)

        await local_db.projects.update_one(
            {"id": project_id},
            {"$set": {
                "course.slides": slides,
                "status": "generated",
                "faithfulStatus": {
                    "status": "done",
                    "message": f"Curso fiel criado: {len(slides)} slides.",
                    "progress": 100,
                    "finishedAt": datetime.now(timezone.utc).isoformat(),
                },
                "updatedAt": datetime.now(timezone.utc).isoformat(),
            }}
        )

        await local_db.agent_sessions.update_one(
            {"id": session_id},
            {"$set": {
                "step": "generated",
                "courseProgress": {"message": "Curso fiel criado com sucesso!", "progress": 100},
                "updatedAt": datetime.now(timezone.utc).isoformat(),
            }}
        )
        logger.info(f"[bg-faithful] project {project_id} done: {len(slides)} slides")
    except Exception as e:
        import traceback as _tb
        logger.error(f"[bg-faithful] project={project_id} failed: {e}\n{_tb.format_exc()}")
        try:
            await local_db.projects.update_one(
                {"id": project_id},
                {"$set": {
                    "status": "error",
                    "faithfulStatus": {
                        "status": "error",
                        "message": f"Falha: {str(e)[:180]}",
                        "progress": 0,
                        "finishedAt": datetime.now(timezone.utc).isoformat(),
                    },
                }}
            )
        except Exception:
            pass
    finally:
        try:
            local_client.close()
        except Exception:
            pass


@router.get("/projects/{project_id}/faithful-status")
async def get_faithful_status(project_id: str, user: dict = Depends(require_auth)):
    """Poll endpoint for Modo Fiel background rendering progress.

    Ultra-light: only fetches the `faithfulStatus` field with a short timeout
    so it responds fast even when CPU is busy rendering pages.
    """
    try:
        p = await asyncio.wait_for(
            db.projects.find_one(
                {"id": project_id},
                {"_id": 0, "faithfulStatus": 1}
            ),
            timeout=5.0,
        )
    except asyncio.TimeoutError:
        # Don't fail the polling — return a "still processing" placeholder so
        # the client keeps polling instead of erroring out.
        return {"status": "processing", "progress": -1, "message": "Aguarde..."}
    if not p:
        raise HTTPException(404, "Project not found")
    return p.get("faithfulStatus") or {"status": "done", "progress": 100, "message": ""}
