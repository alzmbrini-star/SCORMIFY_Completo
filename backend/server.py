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
    mongo_url = "mongodb://localhost:27017"

# Use longer timeouts for Atlas (remote) connections
is_atlas = "mongodb.net" in mongo_url or "mongodb+srv" in mongo_url
client = AsyncIOMotorClient(
    mongo_url,
    serverSelectionTimeoutMS=30000 if is_atlas else 10000,
    connectTimeoutMS=30000 if is_atlas else 10000,
    socketTimeoutMS=60000 if is_atlas else 30000,
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

# Extra CORS middleware for /tutor/chat — ensures headers survive even if proxy strips them
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response as StarletteResponse

class TutorCorsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if "/tutor/chat" in request.url.path:
            if request.method == "OPTIONS":
                return StarletteResponse(
                    status_code=204,
                    headers={
                        "Access-Control-Allow-Origin": "*",
                        "Access-Control-Allow-Methods": "POST, OPTIONS",
                        "Access-Control-Allow-Headers": "Content-Type, Authorization",
                        "Access-Control-Max-Age": "86400",
                    },
                )
            response = await call_next(request)
            response.headers["Access-Control-Allow-Origin"] = "*"
            response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
            return response
        return await call_next(request)

app.add_middleware(TutorCorsMiddleware)

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
companies_routes.set_db(db)
app.include_router(companies_routes.router, prefix="/api")

from routes import users as users_routes
users_routes.set_db(db)
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
        projects = await db.projects.find({}).to_list(1000)
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



@app.on_event("startup")
async def startup_ensure_ffmpeg():
    """Ensure FFmpeg is available for video export"""
    import shutil
    if not shutil.which('ffmpeg'):
        logger.info("FFmpeg not found, attempting to install...")
        try:
            proc = await asyncio.create_subprocess_exec(
                'apt-get', 'update', '-qq',
                stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL
            )
            await proc.wait()
            proc = await asyncio.create_subprocess_exec(
                'apt-get', 'install', '-y', '-qq', 'ffmpeg',
                stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL
            )
            await proc.wait()
            if shutil.which('ffmpeg'):
                logger.info(f"FFmpeg installed successfully: {shutil.which('ffmpeg')}")
            else:
                logger.warning("FFmpeg installation failed - video export will be unavailable")
        except Exception as e:
            logger.warning(f"FFmpeg auto-install failed (non-fatal): {e}")
    else:
        logger.info(f"FFmpeg available: {shutil.which('ffmpeg')}")


@app.on_event("startup")
async def startup_ensure_admin():
    """Ensure super admin user exists in database"""
    try:
        asyncio.create_task(_run_ensure_admin())
        logger.info("Startup admin check: started in background task")
    except Exception as e:
        logger.warning(f"Startup admin check scheduling failed (non-fatal): {e}")


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
async def startup_persist_local_assets():
    """Persist local assets to MongoDB on startup in background"""
    import threading
    from routes.deps import PROJECTS_DIR, STORAGE_DIR

    def _persist_assets():
        try:
            from services.asset_store import store_asset_sync
            from pymongo import MongoClient

            _is_atlas = "mongodb.net" in mongo_url or "mongodb+srv" in mongo_url
            _timeout = 30000 if _is_atlas else 10000
            _client = MongoClient(
                mongo_url,
                serverSelectionTimeoutMS=_timeout,
                connectTimeoutMS=_timeout,
                socketTimeoutMS=60000 if _is_atlas else 30000,
                retryWrites=True,
                retryReads=True,
            )
            _db = _client[db_name]

            total = 0

            # Get all existing asset keys in one batch query (much faster on Atlas)
            existing_assets = set()
            try:
                for doc in _db.project_assets.find({}, {"_id": 0, "project_id": 1, "filename": 1}):
                    existing_assets.add(f"{doc['project_id']}/{doc['filename']}")
            except Exception as e:
                logger.warning(f"Failed to load existing asset index (non-fatal): {e}")

            bg_temp_dir = PROJECTS_DIR / "bg_temp"
            if bg_temp_dir.exists() and bg_temp_dir.is_dir():
                for asset in bg_temp_dir.iterdir():
                    if asset.is_file() and asset.suffix.lower() in ('.png', '.jpg', '.jpeg', '.gif', '.webp'):
                        key = f"bg_temp/{asset.name}"
                        if key not in existing_assets:
                            store_asset_sync(mongo_url, db_name, "bg_temp", asset.name, str(asset))
                            total += 1

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
                        if key not in existing_assets:
                            store_asset_sync(mongo_url, db_name, project_id, asset.name, str(asset))
                            total += 1

            # Audio migration - batch check
            audio_dir = STORAGE_DIR / "audio"
            audio_migrated = 0
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
                            audio_migrated += 1

            _client.close()
            if total > 0 or audio_migrated > 0:
                logger.info(f"Background asset persistence: saved {total} project assets, {audio_migrated} audio files to MongoDB")
            else:
                logger.info("Background asset persistence: all assets already in MongoDB")
        except Exception as e:
            logger.warning(f"Background asset persistence failed (non-fatal): {e}")

    threading.Thread(target=_persist_assets, daemon=True).start()
    logger.info("Startup asset persistence: started in background thread")


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
