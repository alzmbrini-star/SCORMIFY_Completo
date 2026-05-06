"""Shared helpers used by the project-route modules (CRUD / slides / media
/ audio / annotations / upload).

This module exists so each specialised route module can stay focused on a
single concern without duplicating the RBAC guard or the PPT background
processor.
"""
import os
import logging
from pathlib import Path

from fastapi import HTTPException

from routes.deps import (
    db, now_utc, get_project_by_id, PROJECTS_DIR, UPLOADS_DIR, jobs, mongo_url
)
from routes.auth import has_role

logger = logging.getLogger("server")


async def resolve_company_id_for_creation(user: dict, requested_company_id: str = None) -> str:
    """Pick the right companyId when creating/updating a project.

    Rules:
      - super_admin: may pass ANY valid companyId in `requested_company_id`
        (used by service-providers who manage multiple client companies).
        If none provided, falls back to user's own companyId.
      - regular admin / user: ALWAYS uses their own companyId — any
        `requested_company_id` from the request body is silently ignored
        (defense in depth — even if the frontend has a tampered payload,
        users can't reattribute projects to other companies).
      - legacy users without companyId: returns None (legacy projects).

    Validates the company exists when super_admin specifies a different one.
    Raises HTTPException(400) if the requested company doesn't exist.
    """
    user_company = user.get("companyId")
    if not has_role(user, "super_admin"):
        return user_company
    # super_admin path
    if not requested_company_id:
        return user_company
    if requested_company_id == user_company:
        return user_company
    # Validate the target company exists
    company = await db.companies.find_one({"id": requested_company_id}, {"_id": 0, "id": 1})
    if not company:
        raise HTTPException(status_code=400, detail=f"Company '{requested_company_id}' not found")
    return requested_company_id


def can_change_project_company(user: dict) -> bool:
    """Only super_admin can re-assign a project to a different company.
    Used by the PUT/PATCH project endpoint when the body contains a
    `companyId` change."""
    return has_role(user, "super_admin")


def can_access_project(user: dict, project: dict) -> bool:
    """Return True if the user can access this project.

    Rules:
      - super_admin: full access
      - anyone else: project's companyId must match user's companyId
      - legacy projects without companyId: only visible to super_admin
        (keeps old orphan data safe from cross-tenant leakage)
    """
    if has_role(user, "super_admin"):
        return True
    user_company = user.get("companyId")
    proj_company = project.get("companyId")
    if not user_company or not proj_company:
        return False
    return user_company == proj_company


async def load_authorized_project(project_id: str, user: dict) -> dict:
    """Load a project by id and raise 404 if it doesn't exist OR the current
    user cannot access it.

    Always prefer this over calling get_project_by_id + manual checks — it
    guarantees both guards are applied and makes it impossible to forget
    the companyId check (which already caused one regression).
    """
    project = await get_project_by_id(project_id)
    if not project or not can_access_project(user, project):
        # 404 (not 403) so callers can't enumerate projects across tenants.
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def process_ppt_upload(job_id: str, file_path: str, project_id: str):
    """Process uploaded PPT file in background using high-fidelity parser.

    Runs in a background task via FastAPI's BackgroundTasks — uses a sync
    MongoClient because it's called from a thread, not the event loop.
    """
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
        sync_db.jobs.update_one(
            {"id": job_id},
            {"$set": {"status": "processing", "progress": 10, "message": "Converting PowerPoint slides to images..."}},
            upsert=True,
        )

        # Sanitize file path - replace problematic characters
        safe_path = Path(file_path)
        if not safe_path.exists():
            # Try alternate safe path (strip non-ASCII from filename)
            import re as _re
            safe_name = _re.sub(r'[^\w\-_. ]', '_', safe_path.name)
            alt_path = safe_path.parent / safe_name
            if alt_path.exists():
                file_path = str(alt_path)
                safe_path = alt_path
                logger.info(f"Using sanitized path: {file_path}")

        # If file is missing (deploy happened), try to recover from MongoDB
        if not safe_path.exists():
            logger.warning(f"PPT file missing from disk, trying to recover from MongoDB: {file_path}")
            recovered = False
            try:
                import base64 as _b64
                ppt_doc = sync_db.ppt_uploads.find_one(
                    {"$or": [{"path": file_path}, {"projectId": project_id}]},
                    {"_id": 0, "data": 1, "fileSize": 1}
                )
                if ppt_doc and ppt_doc.get("data"):
                    # Use a safe recovery path (avoid special characters)
                    recovery_path = UPLOADS_DIR / f"{project_id}_recovered.pptx"
                    recovery_path.parent.mkdir(parents=True, exist_ok=True)
                    decoded = _b64.b64decode(ppt_doc["data"])

                    # Validate file size if we stored it
                    original_size = ppt_doc.get("fileSize", 0)
                    if original_size > 0 and len(decoded) != original_size:
                        logger.error(f"PPT recovery size mismatch: expected={original_size}, got={len(decoded)}. File may be corrupted.")

                    with open(recovery_path, 'wb') as f:
                        f.write(decoded)

                    # Validate the recovered file is a valid PPTX (ZIP format)
                    import zipfile
                    try:
                        with zipfile.ZipFile(recovery_path, 'r') as zf:
                            zf.testzip()
                        logger.info(f"PPT file recovered and validated: {recovery_path} ({len(decoded)} bytes)")
                        file_path = str(recovery_path)
                    except (zipfile.BadZipFile, Exception) as zf_err:
                        logger.error(f"Recovered PPT is not a valid ZIP/PPTX: {zf_err}")
                        recovery_path.unlink(missing_ok=True)
                        raise FileNotFoundError("Arquivo PPT recuperado esta corrompido. Por favor, importe o arquivo novamente.")

                    recovered = True
            except FileNotFoundError:
                raise
            except Exception as recover_err:
                logger.error(f"Failed to recover PPT from MongoDB: {recover_err}")

            if not recovered:
                raise FileNotFoundError("Arquivo PPT nao encontrado. O servidor reiniciou durante o processamento. Por favor, importe o arquivo novamente.")
        else:
            # Validate file on disk is valid before processing
            file_size = safe_path.stat().st_size
            if file_size == 0:
                raise FileNotFoundError("Arquivo PPT esta vazio (0 bytes).")
            logger.info(f"PPT file found on disk: {file_path} ({file_size} bytes)")

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


# Re-export db so the split route modules can write `from routes.projects_common import db`
# instead of adding yet another deps import.
__all__ = [
    "can_access_project",
    "load_authorized_project",
    "resolve_company_id_for_creation",
    "can_change_project_company",
    "process_ppt_upload",
    "db",
    "now_utc",
    "get_project_by_id",
    "PROJECTS_DIR",
    "UPLOADS_DIR",
    "jobs",
    "logger",
]
