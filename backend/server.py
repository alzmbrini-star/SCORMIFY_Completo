"""
Scormfy API Server - Main entry point
Thin orchestrator that configures FastAPI, CORS, database and includes route modules.
"""
import sys
print("[STARTUP] server.py: Loading imports...", flush=True)
from fastapi import FastAPI, APIRouter, Request
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorGridFSBucket
import os
import re
import logging
from pathlib import Path
from datetime import datetime, timezone
import asyncio
import base64

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env', override=False)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
logger.info("Starting Scormify API server...")
print("[STARTUP] server.py: Configuring MongoDB...", flush=True)

# MongoDB connection
mongo_url = os.environ.get('MONGO_URL', '')
db_name = os.environ.get('DB_NAME', 'scormify')
if not mongo_url:
    raise RuntimeError("MONGO_URL environment variable is required")

# Use longer timeouts for Atlas (remote) connections
is_atlas = "mongodb.net" in mongo_url or "mongodb+srv" in mongo_url
client = AsyncIOMotorClient(
    mongo_url,
    serverSelectionTimeoutMS=60000 if is_atlas else 10000,
    connectTimeoutMS=60000 if is_atlas else 10000,
    socketTimeoutMS=120000 if is_atlas else 30000,
    maxPoolSize=20,
    retryWrites=True,
    retryReads=True,
)
db = client[db_name]
exports_bucket = AsyncIOMotorGridFSBucket(db, bucket_name="exports")

print("[STARTUP] server.py: Creating FastAPI app...", flush=True)

# Create FastAPI app
app = FastAPI(title="Scormify API")

# CORS configuration - always allow all origins (SCORM tutor needs cross-origin access)
cors_origins_str = os.environ.get("CORS_ORIGINS", "*")
origins = [o.strip() for o in cors_origins_str.split(",") if o.strip()] if cors_origins_str and cors_origins_str != "*" else ["*"]
if not origins:
    origins = ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=86400,
)

# Health endpoints - defined FIRST to ensure immediate availability
@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.get("/healthz")
async def health_check_k8s():
    return {"status": "healthy"}

@app.get("/ready")
async def readiness_check():
    return {"status": "ready"}

# Also register health at /api/health for deployment systems that use the /api prefix
@app.get("/api/health")
async def health_check_api():
    return {"status": "healthy"}

@app.get("/api/healthz")
async def health_check_api_k8s():
    return {"status": "healthy"}

print("[STARTUP] server.py: Loading route modules...", flush=True)

# Root route
@app.get("/")
async def root():
    return {"name": "Scormify API", "status": "running"}

# Initialize shared dependencies
from routes import deps as deps_module
deps_module.init(db, exports_bucket, mongo_url, db_name)

# Import and mount route modules
from routes import auth as auth_routes
auth_routes.set_db(db)
app.include_router(auth_routes.router, prefix="/api")

from routes import projects as projects_routes
app.include_router(projects_routes.router, prefix="/api")

from routes import export as export_routes
app.include_router(export_routes.router, prefix="/api")

from routes import gamification as gamification_routes
app.include_router(gamification_routes.router, prefix="/api")

from routes import agent as agent_routes
app.include_router(agent_routes.router, prefix="/api")

from routes import ai_gen as ai_gen_routes
app.include_router(ai_gen_routes.router, prefix="/api")

from routes import admin as admin_routes
app.include_router(admin_routes.router, prefix="/api")

from routes import companies as companies_routes
app.include_router(companies_routes.router, prefix="/api")

from routes import users as users_routes
app.include_router(users_routes.router, prefix="/api")

from routes import elevenlabs as elevenlabs_routes
app.include_router(elevenlabs_routes.router, prefix="/api")

from routes import gallery as gallery_routes
app.include_router(gallery_routes.router, prefix="/api")

from routes import heygen as heygen_routes
app.include_router(heygen_routes.router, prefix="/api")

from routes import questions as questions_routes
app.include_router(questions_routes.router, prefix="/api")

from routes import scenarios as scenarios_routes
app.include_router(scenarios_routes.router, prefix="/api")

from routes import vlibras as vlibras_routes
app.include_router(vlibras_routes.router, prefix="/api")

from routes import leonardo as leonardo_routes
app.include_router(leonardo_routes.router, prefix="/api")

from routes import aesthetics as aesthetics_routes
app.include_router(aesthetics_routes.router, prefix="/api")


from routes import notifications as notifications_routes
app.include_router(notifications_routes.router, prefix="/api")


print("[STARTUP] server.py: Routes loaded. Setting up startup events...", flush=True)

# ---- STARTUP EVENTS (all non-blocking background tasks) ----

@app.on_event("startup")
async def startup_migrate_urls():
    """Auto-migrate absolute asset URLs to relative on startup"""
    try:
        asyncio.create_task(_run_migrate_urls())
        logger.info("Startup URL migration: started in background task")
    except Exception as e:
        logger.warning(f"Startup URL migration scheduling failed (non-fatal): {e}")


async def _run_migrate_urls():
    if db is None:
        return
    try:
        migrated_count = 0
        # Use projection to avoid loading full course data into memory
        projects = await db.projects.find(
            {},
            {"_id": 0, "id": 1, "course.slides.elements.type": 1, "course.slides.elements.htmlContent": 1, "course.slides.elements.src": 1, "course.slides.backgroundImage": 1}
        ).to_list(1000)
        for project in projects:
            updated = False
            course = project.get('course', {})
            for slide in course.get('slides', []):
                for element in slide.get('elements', []):
                    if element.get('type') == 'html' and element.get('htmlContent'):
                        html = element['htmlContent']
                        if not isinstance(html, str):
                            continue
                        new_html = re.sub(r'https?://[^/\s"\']+/api/assets/', '/api/assets/', html)
                        new_html = re.sub(r'https?://[^/\s"\']+/api/projects/', '/api/projects/', new_html)
                        if new_html != html:
                            element['htmlContent'] = new_html
                            updated = True
                            migrated_count += 1
                    src = element.get('src', '')
                    if src and src.startswith('http') and '/api/' in src:
                        new_src = re.sub(r'https?://[^/\s"\']+(/api/.*)', r'\1', src)
                        if new_src != src:
                            element['src'] = new_src
                            updated = True
                            migrated_count += 1
                bg = slide.get('backgroundImage', '')
                if bg and bg.startswith('http') and '/api/' in bg:
                    new_bg = re.sub(r'https?://[^/\s"\']+(/api/.*)', r'\1', bg)
                    if new_bg != bg:
                        slide['backgroundImage'] = new_bg
                        updated = True
                        migrated_count += 1
            if updated:
                await db.projects.update_one({'id': project['id']}, {'$set': {'course': course}})
        if migrated_count > 0:
            logger.info(f"Startup URL migration: fixed {migrated_count} absolute URLs to relative")
        else:
            logger.info("Startup URL migration: no absolute URLs found, all clean")
    except Exception as e:
        logger.warning(f"Startup URL migration failed (non-fatal): {e}")



# NOTE: FFmpeg startup removed — video export now runs client-side (Canvas + MediaRecorder).
# The legacy video_exporter.py is only used for create_slide_base_image (PIL-based, no FFmpeg needed).


@app.on_event("startup")
async def startup_create_indexes():
    """Create MongoDB indexes for production performance."""
    try:
        # Deduplicate project_assets before creating index (handles legacy duplicates)
        pipeline = [
            {"$group": {"_id": {"project_id": "$project_id", "filename": "$filename"}, "count": {"$sum": 1}, "ids": {"$push": "$_id"}}},
            {"$match": {"count": {"$gt": 1}}}
        ]
        async for dup in db.project_assets.aggregate(pipeline):
            # Keep first, delete rest
            ids_to_remove = dup["ids"][1:]
            if ids_to_remove:
                await db.project_assets.delete_many({"_id": {"$in": ids_to_remove}})
        
        await db.project_assets.create_index(
            [("project_id", 1), ("filename", 1)],
            unique=True,
            background=True,
        )
        await db.image_gallery.create_index([("companyId", 1), ("createdAt", -1)], background=True)
        await db.agent_sessions.create_index([("id", 1)], unique=True, background=True)
        logger.info("MongoDB indexes ensured")
    except Exception as e:
        logger.warning(f"Index creation failed (non-fatal): {e}")


@app.on_event("startup")
async def startup_ensure_admin():
    """Ensure super admin user exists in database"""
    try:
        asyncio.create_task(_run_ensure_admin())
        logger.info("Startup admin check: started in background task")
    except Exception as e:
        logger.warning(f"Startup admin check scheduling failed (non-fatal): {e}")



@app.on_event("startup")
async def startup_migrate_roles():
    """Migrate legacy single-role 'role' field to multi-role 'roles' array."""
    try:
        migrated = 0
        async for user in db.users.find({"roles": {"$exists": False}}, {"_id": 0, "user_id": 1, "role": 1}):
            legacy_role = user.get("role", "editor")
            await db.users.update_one(
                {"user_id": user["user_id"]},
                {"$set": {"roles": [legacy_role]}}
            )
            migrated += 1
        if migrated > 0:
            logger.info(f"Roles migration: converted {migrated} users from single role to multi-role")
    except Exception as e:
        logger.warning(f"Roles migration failed (non-fatal): {e}")



@app.on_event("startup")
async def startup_recover_stalled_ppt_jobs():
    """Recover PPT processing jobs that were interrupted by a deploy/restart"""
    try:
        asyncio.create_task(_recover_stalled_ppt_jobs())
        logger.info("Startup PPT recovery: started in background task")
    except Exception as e:
        logger.warning(f"Startup PPT recovery scheduling failed (non-fatal): {e}")


async def _recover_stalled_ppt_jobs():
    """Find PPT uploads in MongoDB that have stalled jobs and restart processing."""
    if db is None:
        return
    try:
        await asyncio.sleep(10)  # Wait for server to be ready
        
        # Find stalled jobs (status=processing or pending, with PPT data in ppt_uploads)
        stalled_uploads = await db.ppt_uploads.find(
            {"data": {"$exists": True}},
            {"_id": 0, "projectId": 1, "jobId": 1, "filename": 1, "path": 1}
        ).to_list(50)
        
        if not stalled_uploads:
            return
        
        recovered = 0
        for upload in stalled_uploads:
            project_id = upload.get("projectId")
            job_id = upload.get("jobId")
            file_path = upload.get("path", "")
            
            if not project_id:
                continue
            
            # Check if the job is actually stalled (not completed)
            if job_id:
                job = await db.jobs.find_one({"id": job_id}, {"_id": 0, "status": 1})
                if job and job.get("status") == "completed":
                    # Job already completed, clean up the upload data
                    await db.ppt_uploads.delete_one({"projectId": project_id})
                    continue
            
            # Check if project exists and is still in 'processing' state
            project = await db.projects.find_one({"id": project_id}, {"_id": 0, "status": 1})
            if not project or project.get("status") != "processing":
                # Project completed or doesn't exist, clean up
                await db.ppt_uploads.delete_one({"projectId": project_id})
                continue
            
            # This is a stalled job - recover the PPT file and restart processing
            logger.info(f"Recovering stalled PPT job: project={project_id}, job={job_id}")
            
            try:
                import base64 as _b64
                ppt_doc = await db.ppt_uploads.find_one(
                    {"projectId": project_id},
                    {"_id": 0, "data": 1, "path": 1}
                )
                if ppt_doc and ppt_doc.get("data"):
                    # Restore file to disk
                    restore_path = Path(file_path) if file_path else (UPLOADS_DIR / f"{project_id}_recovered.pptx")
                    restore_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(restore_path, 'wb') as f:
                        f.write(_b64.b64decode(ppt_doc["data"]))
                    
                    # Create/update job
                    if not job_id:
                        job_id = str(uuid.uuid4())
                    
                    from routes.projects import process_ppt_upload, jobs
                    jobs[job_id] = {
                        'id': job_id,
                        'status': 'pending',
                        'progress': 0,
                        'message': 'Recuperando processamento interrompido...',
                        'result': None
                    }
                    await db.jobs.update_one(
                        {"id": job_id},
                        {"$set": jobs[job_id]},
                        upsert=True
                    )
                    
                    # Start processing in background thread (same as normal flow)
                    import threading
                    def _run_ppt():
                        process_ppt_upload(job_id, str(restore_path), project_id)
                    t = threading.Thread(target=_run_ppt, daemon=True)
                    t.start()
                    recovered += 1
                    logger.info(f"Restarted stalled PPT processing: project={project_id}")
            except Exception as e:
                logger.error(f"Failed to recover stalled PPT job for project {project_id}: {e}")
        
        if recovered > 0:
            logger.info(f"Startup PPT recovery: restarted {recovered} stalled jobs")
    except Exception as e:
        logger.warning(f"Startup PPT recovery failed (non-fatal): {e}")


async def _run_ensure_admin():
    if db is None:
        return
    import bcrypt
    try:
        admin_email = "admin@scormify.com"
        existing_admin = await db.users.find_one({"email": admin_email})
        if not existing_admin:
            logger.info("Creating default super admin user...")
            password_hash = bcrypt.hashpw("admin123".encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            await db.users.insert_one({
                "user_id": "user_superadmin001",
                "email": admin_email,
                "name": "Super Admin",
                "picture": None,
                "companyId": None,
                "role": "super_admin",
                "passwordHash": password_hash,
                "isActive": True,
                "createdAt": datetime.now(timezone.utc),
                "updatedAt": datetime.now(timezone.utc)
            })
            logger.info("Super admin user created successfully")
        else:
            logger.info("Super admin user already exists")
    except Exception as e:
        logger.warning(f"Failed to ensure admin user (non-fatal): {e}")


@app.on_event("startup")
async def startup_asset_sync():
    """
    Unified asset sync on startup:
    1. RESTORE: MongoDB -> local disk (needed after deploy/fork when disk is empty)
    2. PERSIST: local disk -> MongoDB (needed when new files exist locally but not in DB)
    
    Uses a SINGLE MongoClient with Atlas-optimized timeouts to avoid the timeout storm
    that happened when store_asset_sync created a new connection per asset.
    """
    import threading
    from routes.deps import PROJECTS_DIR, STORAGE_DIR

    def _asset_sync():
        try:
            from pymongo import MongoClient
            from services.asset_store import _get_content_type
            import time

            _is_atlas = "mongodb.net" in mongo_url or "mongodb+srv" in mongo_url

            _client = MongoClient(
                mongo_url,
                serverSelectionTimeoutMS=30000,
                connectTimeoutMS=30000,
                socketTimeoutMS=60000,
                maxPoolSize=2,
                retryWrites=True,
                retryReads=True,
            )
            _db = _client[db_name]
            _persist_throttle = 0.5 if _is_atlas else 0

            # ── PHASE 1: INDEX (single query instead of per-project) ──
            total_restored = 0
            all_assets_index = []
            try:
                time.sleep(5)  # Let Atlas connections warm up and indexes build
                
                # Single lightweight query for ALL asset metadata (no binary data)
                all_assets_index = list(_db.project_assets.find(
                    {},
                    {"_id": 0, "project_id": 1, "filename": 1},
                ).batch_size(500))
                
                project_ids = set(doc.get("project_id", "") for doc in all_assets_index)
                logger.info(f"Asset sync: found {len(project_ids)} projects in MongoDB")
                
                total_in_mongo = len(all_assets_index)
                local_exists = sum(1 for doc in all_assets_index
                    if (PROJECTS_DIR / doc.get("project_id","") / "assets" / doc.get("filename","")).exists()
                    or (doc.get("project_id") == "global" and (STORAGE_DIR / "assets" / doc.get("filename","")).exists())
                )
                logger.info(f"Asset sync: {total_in_mongo} assets indexed, {local_exists} already on disk, {total_in_mongo - local_exists} will be served on-demand from MongoDB")
            except Exception as e:
                logger.warning(f"Asset sync INDEX phase failed (non-fatal): {e}")

            # Restore audio files
            audio_restored = 0
            try:
                audio_dir = STORAGE_DIR / "audio"
                audio_filenames = list(_db.tts_generations.find(
                    {"audio_data": {"$exists": True}},
                    {"_id": 0, "filename": 1}
                ))
                missing_audio = []
                for adoc in audio_filenames:
                    fname = adoc.get("filename", "")
                    if fname:
                        afp = audio_dir / fname
                        if not afp.exists():
                            missing_audio.append((fname, afp))

                if missing_audio:
                    logger.info(f"Asset sync: {len(missing_audio)} audio files missing, restoring...")
                    for fname, afp in missing_audio:
                        try:
                            adoc = _db.tts_generations.find_one(
                                {"filename": fname},
                                {"_id": 0, "audio_data": 1}
                            )
                            if adoc and adoc.get("audio_data"):
                                afp.parent.mkdir(parents=True, exist_ok=True)
                                with open(afp, "wb") as f:
                                    f.write(base64.b64decode(adoc["audio_data"]))
                                audio_restored += 1
                        except Exception as e:
                            logger.warning(f"Audio restore failed for {fname}: {e}")
            except Exception as e:
                logger.warning(f"Audio restore phase failed (non-fatal): {e}")

            if total_restored > 0 or audio_restored > 0:
                logger.info(f"Asset sync RESTORE complete: {total_restored} assets, {audio_restored} audio files restored from MongoDB")

            # ── PHASE 2: PERSIST (disk -> MongoDB) ──
            # Uses the SAME _db connection (no new MongoClient per asset!)
            total_persisted = 0
            try:
                # Build set of existing asset keys from the index we already fetched
                existing_keys = set()
                for doc in all_assets_index:
                    existing_keys.add(f"{doc['project_id']}/{doc['filename']}")

                # Collect files to persist
                files_to_persist = []

                bg_temp_dir = PROJECTS_DIR / "bg_temp"
                if bg_temp_dir.exists() and bg_temp_dir.is_dir():
                    for asset in bg_temp_dir.iterdir():
                        if asset.is_file() and asset.suffix.lower() in ('.png', '.jpg', '.jpeg', '.gif', '.webp'):
                            key = f"bg_temp/{asset.name}"
                            if key not in existing_keys:
                                files_to_persist.append(("bg_temp", asset.name, str(asset)))

                for project_dir in PROJECTS_DIR.iterdir():
                    if not project_dir.is_dir() or project_dir.name == "bg_temp":
                        continue
                    assets_dir = project_dir / "assets"
                    if not assets_dir.exists():
                        continue
                    project_id = project_dir.name
                    for asset in assets_dir.iterdir():
                        if asset.is_file() and asset.suffix.lower() in (
                            '.png', '.jpg', '.jpeg', '.mp3', '.wav', '.ogg',
                            '.webm', '.mp4', '.gif', '.webp', '.svg'
                        ):
                            key = f"{project_id}/{asset.name}"
                            if key not in existing_keys:
                                files_to_persist.append((project_id, asset.name, str(asset)))

                if files_to_persist:
                    logger.info(f"Asset sync: {len(files_to_persist)} new local files to persist to MongoDB...")
                    failed_persists = []
                    for idx, (pid, fname, fpath) in enumerate(files_to_persist):
                        try:
                            file_size = Path(fpath).stat().st_size
                            if file_size > 10 * 1024 * 1024:  # Skip files > 10MB (Atlas timeout risk)
                                logger.warning(f"Asset too large for Atlas persist ({file_size} bytes), skipping: {pid}/{fname}")
                                continue
                            with open(fpath, 'rb') as f:
                                data_b64 = base64.b64encode(f.read()).decode('ascii')
                            _db.project_assets.update_one(
                                {"project_id": pid, "filename": fname},
                                {"$set": {
                                    "project_id": pid,
                                    "filename": fname,
                                    "data": data_b64,
                                    "content_type": _get_content_type(fname),
                                }},
                                upsert=True
                            )
                            total_persisted += 1
                            if _persist_throttle:
                                time.sleep(_persist_throttle)
                        except Exception as e:
                            failed_persists.append((pid, fname, fpath))
                            logger.warning(f"Asset persist failed for {pid}/{fname}: {e}")
                    
                    # Retry failed persists once
                    if failed_persists:
                        logger.info(f"Asset sync: retrying {len(failed_persists)} failed persists...")
                        time.sleep(5)
                        for pid, fname, fpath in failed_persists:
                            try:
                                if not Path(fpath).exists():
                                    continue
                                with open(fpath, 'rb') as f:
                                    data_b64 = base64.b64encode(f.read()).decode('ascii')
                                _db.project_assets.update_one(
                                    {"project_id": pid, "filename": fname},
                                    {"$set": {
                                        "project_id": pid,
                                        "filename": fname,
                                        "data": data_b64,
                                        "content_type": _get_content_type(fname),
                                    }},
                                    upsert=True
                                )
                                total_persisted += 1
                            except Exception as e:
                                logger.warning(f"Asset persist retry failed for {pid}/{fname}: {e}")
                else:
                    logger.info("Asset sync: no new local files to persist")
            except Exception as e:
                logger.warning(f"Asset sync PERSIST phase failed (non-fatal): {e}")

            # Persist audio files
            audio_persisted = 0
            try:
                audio_dir = STORAGE_DIR / "audio"
                if audio_dir.exists():
                    existing_audio = set()
                    try:
                        for doc in _db.tts_generations.find(
                            {"audio_data": {"$exists": True}},
                            {"_id": 0, "filename": 1}
                        ):
                            existing_audio.add(doc.get('filename', ''))
                    except Exception:
                        pass

                    for audio_file in audio_dir.iterdir():
                        if audio_file.is_file() and audio_file.suffix.lower() in ('.mp3', '.wav', '.ogg'):
                            if audio_file.name not in existing_audio:
                                try:
                                    with open(audio_file, 'rb') as f:
                                        audio_data = f.read()
                                    _db.tts_generations.update_one(
                                        {"filename": audio_file.name},
                                        {"$set": {
                                            "filename": audio_file.name,
                                            "audio_data": base64.b64encode(audio_data).decode(),
                                            "file_size": len(audio_data),
                                            "type": "narration",
                                            "migrated_at": datetime.now(timezone.utc).isoformat()
                                        }},
                                        upsert=True
                                    )
                                    audio_persisted += 1
                                except Exception as e:
                                    logger.warning(f"Audio persist failed for {audio_file.name}: {e}")
            except Exception as e:
                logger.warning(f"Audio persist phase failed (non-fatal): {e}")

            _client.close()

            if total_persisted > 0 or audio_persisted > 0:
                logger.info(f"Asset sync PERSIST complete: {total_persisted} assets, {audio_persisted} audio files saved to MongoDB")

            logger.info(f"Asset sync DONE: restored={total_restored}+{audio_restored}, persisted={total_persisted}+{audio_persisted}")
        except Exception as e:
            logger.warning(f"Asset sync failed (non-fatal): {e}")

    threading.Thread(target=_asset_sync, daemon=True).start()
    logger.info("Startup asset sync: started in background thread")


@app.on_event("startup")
async def startup_check_system_deps():
    """Check system dependencies in background - SKIP in production to avoid slow startup"""
    # Skip heavy system installs in production containers
    if os.environ.get("SKIP_SYSTEM_DEPS", "").lower() in ("1", "true", "yes"):
        logger.info("System dependency check: SKIPPED (SKIP_SYSTEM_DEPS=1)")
        return
    import threading
    def _check():
        try:
            from utils.system_deps import ensure_system_dependencies
            ensure_system_dependencies()
        except Exception as e:
            logger.warning(f"System dependency check failed (non-fatal): {e}")
    threading.Thread(target=_check, daemon=True).start()


@app.on_event("shutdown")
async def shutdown():
    """Clean up resources on shutdown"""
    if client is not None:
        client.close()

print("[STARTUP] server.py: Ready to accept connections.", flush=True)


# ── CORS for /api/tutor/chat ──
# The production proxy does NOT inject any CORS headers, so the backend must
# provide them. Previously the backend ended up emitting two values
# ("*" from CORSMiddleware + "<origin>" from a custom wrapper) and the browser
# rejected with "contains multiple values".
#
# Solution: an ASGI wrapper that intercepts ONLY the OPTIONS preflight for
# /api/tutor/chat and returns a 204 with a reflected origin. For POST we let the
# response pass through untouched so the global CORSMiddleware (allow_origins=*)
# is the sole source of Access-Control-Allow-Origin.
from starlette.types import ASGIApp, Receive, Scope, Send


class _TutorCorsASGI:
    def __init__(self, inner: ASGIApp):
        self.inner = inner

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if (
            scope["type"] != "http"
            or scope.get("method") != "OPTIONS"
            or "/tutor/chat" not in scope.get("path", "")
        ):
            await self.inner(scope, receive, send)
            return

        origin = b"*"
        for key, val in scope.get("headers", []):
            if key == b"origin":
                origin = val
                break

        await send({
            "type": "http.response.start",
            "status": 204,
            "headers": [
                (b"access-control-allow-origin", origin),
                (b"access-control-allow-methods", b"POST, OPTIONS"),
                (b"access-control-allow-headers", b"Content-Type, Authorization"),
                (b"access-control-max-age", b"86400"),
                (b"vary", b"Origin"),
                (b"content-length", b"0"),
            ],
        })
        await send({"type": "http.response.body", "body": b""})


app = _TutorCorsASGI(app)
