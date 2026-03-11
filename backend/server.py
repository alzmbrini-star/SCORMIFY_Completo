"""
Scormfy API Server - Main entry point
Thin orchestrator that configures FastAPI, CORS, database and includes route modules.
"""
from fastapi import FastAPI, APIRouter
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

# MongoDB connection
mongo_url = os.environ.get('MONGO_URL', '')
db_name = os.environ.get('DB_NAME', 'scormify')
if not mongo_url:
    mongo_url = "mongodb://localhost:27017"

client = AsyncIOMotorClient(
    mongo_url,
    serverSelectionTimeoutMS=10000,
    connectTimeoutMS=10000,
    socketTimeoutMS=30000,
)
db = client[db_name]
logger.info(f"MongoDB client initialized for database: {db_name}")

# GridFS bucket for persistent export storage
exports_bucket = None
if db is not None:
    try:
        exports_bucket = AsyncIOMotorGridFSBucket(db, bucket_name="exports")
    except Exception as e:
        logger.warning(f"GridFS bucket creation failed: {e}")

# Initialize shared dependencies
from routes import deps as deps_module
deps_module.init(db, exports_bucket, mongo_url, db_name)

# Create the main app
app = FastAPI(title="Scormify API", version="2.0.0")

# Register health endpoints FIRST - critical for deployment probes
@app.get("/health")
async def root_health():
    return {"status": "healthy"}

@app.get("/healthz")
async def healthz():
    return {"status": "healthy"}

@app.get("/ready")
async def readyz():
    return {"status": "ready"}

@app.get("/api/health")
async def api_health_direct():
    return {"status": "healthy"}

@app.get("/api/healthz")
async def api_healthz():
    return {"status": "healthy"}

@app.get("/")
async def root():
    return {"status": "running", "app": "Scormify API"}

# Create main API router
api_router = APIRouter(prefix="/api")

@api_router.get("/")
async def api_root():
    return {"message": "Scormify API v2.0"}

# Import and setup auth routes (use set_db pattern for backward compat)
from routes import auth as auth_routes
from routes import companies as companies_routes
from routes import users as users_routes

auth_routes.set_db(db)
companies_routes.set_db(db)
users_routes.set_db(db)

api_router.include_router(auth_routes.router)
api_router.include_router(companies_routes.router)
api_router.include_router(users_routes.router)

# Import and include new route modules (use deps for db access)
from routes.vlibras import router as vlibras_router
from routes.projects import router as projects_router
from routes.export import router as export_router
from routes.heygen import router as heygen_router
from routes.ai_gen import router as ai_gen_router
from routes.questions import router as questions_router
from routes.elevenlabs import router as elevenlabs_router
from routes.admin import router as admin_router
from routes.agent import router as agent_router
from routes.gallery import router as gallery_router
from routes.scenarios import router as scenarios_router

api_router.include_router(vlibras_router)
api_router.include_router(projects_router)
api_router.include_router(export_router)
api_router.include_router(heygen_router)
api_router.include_router(ai_gen_router)
api_router.include_router(questions_router)
api_router.include_router(elevenlabs_router)
api_router.include_router(admin_router)
api_router.include_router(agent_router)
api_router.include_router(gallery_router)
api_router.include_router(scenarios_router)

# Include router
app.include_router(api_router)

# CORS - Allow all origins for cross-domain production deployments
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    max_age=3600,
)


# ============ STARTUP EVENTS ============

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

            _client = MongoClient(mongo_url, serverSelectionTimeoutMS=10000, connectTimeoutMS=10000)
            _db = _client[db_name]

            total = 0

            bg_temp_dir = PROJECTS_DIR / "bg_temp"
            if bg_temp_dir.exists() and bg_temp_dir.is_dir():
                for asset in bg_temp_dir.iterdir():
                    if asset.is_file() and asset.suffix.lower() in ('.png', '.jpg', '.jpeg', '.gif', '.webp'):
                        existing = _db.project_assets.find_one(
                            {"project_id": "bg_temp", "filename": asset.name}, {"_id": 1}
                        )
                        if not existing:
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
                        existing = _db.project_assets.find_one(
                            {"project_id": project_id, "filename": asset.name}, {"_id": 1}
                        )
                        if not existing:
                            store_asset_sync(mongo_url, db_name, project_id, asset.name, str(asset))
                            total += 1

            audio_dir = STORAGE_DIR / "audio"
            audio_migrated = 0
            if audio_dir.exists():
                for audio_file in audio_dir.iterdir():
                    if audio_file.is_file() and audio_file.suffix.lower() in ('.mp3', '.wav', '.ogg'):
                        existing = _db.tts_generations.find_one(
                            {"filename": audio_file.name, "audio_data": {"$exists": True}}, {"_id": 1}
                        )
                        if not existing:
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
    """Check system dependencies in background"""
    import threading
    def _check():
        try:
            from utils.system_deps import ensure_system_dependencies
            ensure_system_dependencies()
        except Exception as e:
            logger.warning(f"System dependency check failed (non-fatal): {e}")
    threading.Thread(target=_check, daemon=True).start()


@app.on_event("shutdown")
async def shutdown_db_client():
    if client is not None:
        client.close()
