"""
Shared dependencies for all route modules.
Centralized access to database, paths, and helper functions.
"""
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorGridFSBucket
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
import os
import logging
import asyncio

logger = logging.getLogger("server")

# Storage directories
ROOT_DIR = Path(__file__).parent.parent
STORAGE_DIR = ROOT_DIR / "storage"
UPLOADS_DIR = STORAGE_DIR / "uploads"
PROJECTS_DIR = STORAGE_DIR / "projects"
EXPORTS_DIR = STORAGE_DIR / "exports"

# Ensure directories exist
STORAGE_DIR.mkdir(exist_ok=True)
UPLOADS_DIR.mkdir(exist_ok=True)
PROJECTS_DIR.mkdir(exist_ok=True)
EXPORTS_DIR.mkdir(exist_ok=True)

# Database references (set by server.py at startup)
db = None
exports_bucket = None
mongo_url = ""
db_name = ""

# Job tracking - MongoDB backed (persists across restarts/workers)
jobs: Dict[str, Any] = {}  # Keep as local cache for quick access


async def create_job(job_id: str, data: dict):
    """Create a job in MongoDB and local cache"""
    job_data = {**data, "id": job_id}
    jobs[job_id] = job_data
    if db is not None:
        try:
            await db.jobs.replace_one({"id": job_id}, job_data, upsert=True)
            logger.info(f"Job {job_id} created in MongoDB")
        except Exception as e:
            logger.error(f"Failed to create job {job_id} in MongoDB: {e}")


async def update_job(job_id: str, updates: dict):
    """Update a job in MongoDB and local cache"""
    if job_id in jobs:
        jobs[job_id].update(updates)
    if db is not None:
        try:
            await db.jobs.update_one({"id": job_id}, {"$set": updates}, upsert=True)
        except Exception as e:
            logger.error(f"Failed to update job {job_id} in MongoDB: {e}")


async def get_job(job_id: str) -> Optional[dict]:
    """Get a job from local cache or MongoDB"""
    if job_id in jobs:
        return jobs[job_id]
    if db is not None:
        doc = await db.jobs.find_one({"id": job_id}, {"_id": 0})
        if doc:
            jobs[job_id] = doc  # Cache locally
            return doc
    return None


def update_job_sync(job_id: str, updates: dict):
    """Sync update for use in non-async callbacks (updates cache, DB syncs on next read)"""
    if job_id in jobs:
        jobs[job_id].update(updates)
    # Schedule async DB update
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(_sync_job_to_db(job_id, updates))
    except RuntimeError:
        pass


async def _sync_job_to_db(job_id: str, updates: dict):
    """Background sync job updates to MongoDB"""
    if db is not None:
        try:
            await db.jobs.update_one({"id": job_id}, {"$set": updates}, upsert=True)
        except Exception as e:
            logger.warning(f"Failed to sync job {job_id} to DB: {e}")

# HeyGen config
HEYGEN_API_KEY = os.environ.get('HEYGEN_API_KEY', '')
HEYGEN_BASE_URL = "https://api.heygen.com"
HEYGEN_HEADERS = {
    "X-Api-Key": HEYGEN_API_KEY,
    "Accept": "application/json",
    "Content-Type": "application/json"
}

# ElevenLabs config
ELEVENLABS_API_KEY = os.environ.get('ELEVENLABS_API_KEY', '')

# HeyGen credits cache
heygen_credits_cache: Dict[str, Any] = {
    "data": None,
    "timestamp": None,
    "ttl": 60
}

# SSE Event Store for HeyGen webhook notifications
heygen_sse_subscribers: Dict[str, List[asyncio.Queue]] = {}


def init(database, bucket, _mongo_url: str, _db_name: str):
    """Initialize shared dependencies from server.py"""
    global db, exports_bucket, mongo_url, db_name
    db = database
    exports_bucket = bucket
    mongo_url = _mongo_url
    db_name = _db_name


def now_utc():
    return datetime.now(timezone.utc)


def serialize_doc(doc: dict) -> dict:
    """Serialize MongoDB document for JSON response"""
    if doc is None:
        return None
    doc.pop('_id', None)
    for key, value in doc.items():
        if isinstance(value, datetime):
            doc[key] = value.isoformat()
    return doc


async def get_project_by_id(project_id: str) -> Optional[dict]:
    """Get project from database"""
    doc = await db.projects.find_one({"id": project_id}, {"_id": 0})
    return doc


async def update_project(project_id: str, update_data: dict):
    """Update project in database"""
    update_data['updatedAt'] = now_utc().isoformat()
    await db.projects.update_one({"id": project_id}, {"$set": update_data})
