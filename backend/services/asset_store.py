"""
Asset Store - Persists binary assets in MongoDB for production environments
where the filesystem is ephemeral (Kubernetes pods).

Assets are stored in a 'project_assets' collection with:
- project_id: str
- filename: str
- data: base64-encoded string
- content_type: str
"""
import base64
import logging
from pathlib import Path
from pymongo import MongoClient

logger = logging.getLogger(__name__)


def _get_content_type(filename: str) -> str:
    """Determine content type from filename extension."""
    ext = Path(filename).suffix.lower()
    ct_map = {
        '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
        '.webp': 'image/webp', '.gif': 'image/gif', '.svg': 'image/svg+xml',
        '.mp3': 'audio/mpeg', '.wav': 'audio/wav', '.ogg': 'audio/ogg',
        '.mp4': 'video/mp4', '.webm': 'video/webm',
    }
    return ct_map.get(ext, 'application/octet-stream')


async def store_asset_async(db, project_id: str, filename: str, file_path: str):
    """Store a file in MongoDB using an existing async motor db connection.
    This is the PREFERRED method for all async contexts (routes, services)."""
    try:
        with open(file_path, 'rb') as f:
            raw_data = f.read()
        
        data_b64 = base64.b64encode(raw_data).decode('ascii')
        content_type = _get_content_type(filename)
        
        result = await db.project_assets.update_one(
            {"project_id": project_id, "filename": filename},
            {"$set": {
                "project_id": project_id,
                "filename": filename,
                "data": data_b64,
                "content_type": content_type,
            }},
            upsert=True
        )
        
        action = "inserted" if result.upserted_id else "updated"
        logger.info(f"Asset {action} in MongoDB: {project_id}/{filename} ({len(raw_data)} bytes)")
        return True
    except Exception as e:
        logger.error(f"Failed to store asset in MongoDB: {project_id}/{filename} - {e}")
        return False


def store_asset_sync(mongo_url: str, db_name: str, project_id: str, filename: str, file_path: str):
    """Store a file in MongoDB (synchronous, for startup/background tasks only)."""
    try:
        with open(file_path, 'rb') as f:
            data = base64.b64encode(f.read()).decode('ascii')

        content_type = _get_content_type(filename)

        is_atlas = "mongodb.net" in mongo_url or "mongodb+srv" in mongo_url
        timeout = 30000 if is_atlas else 10000
        client = MongoClient(mongo_url, serverSelectionTimeoutMS=timeout, connectTimeoutMS=timeout, retryWrites=True)
        db = client[db_name]
        db.project_assets.update_one(
            {"project_id": project_id, "filename": filename},
            {"$set": {
                "project_id": project_id,
                "filename": filename,
                "data": data,
                "content_type": content_type,
            }},
            upsert=True
        )
        client.close()
        logger.info(f"Stored asset in MongoDB (sync): {project_id}/{filename}")
    except Exception as e:
        logger.warning(f"Failed to store asset in MongoDB (sync): {e}")


def retrieve_asset_sync(mongo_url: str, db_name: str, project_id: str, filename: str, dest_path: str) -> bool:
    """Retrieve a file from MongoDB to local filesystem (synchronous).
    Returns True if the file was restored."""
    try:
        is_atlas = "mongodb.net" in mongo_url or "mongodb+srv" in mongo_url
        timeout = 30000 if is_atlas else 10000
        client = MongoClient(mongo_url, serverSelectionTimeoutMS=timeout, connectTimeoutMS=timeout, retryReads=True)
        db = client[db_name]
        doc = db.project_assets.find_one(
            {"project_id": project_id, "filename": filename},
            {"_id": 0}
        )
        client.close()

        if not doc or not doc.get('data'):
            return False

        Path(dest_path).parent.mkdir(parents=True, exist_ok=True)
        with open(dest_path, 'wb') as f:
            f.write(base64.b64decode(doc['data']))

        logger.info(f"Restored asset from MongoDB: {project_id}/{filename}")
        return True
    except Exception as e:
        logger.warning(f"Failed to retrieve asset from MongoDB: {e}")
        return False


async def retrieve_asset_async(db, project_id: str, filename: str) -> tuple:
    """Retrieve asset data and content_type from MongoDB (async).
    Returns (bytes, content_type) or (None, None)."""
    if db is None:
        logger.warning("retrieve_asset_async called with db=None")
        return None, None
    try:
        doc = await db.project_assets.find_one(
            {"project_id": project_id, "filename": filename},
            {"_id": 0}
        )
        if not doc or not doc.get('data'):
            return None, None
        return base64.b64decode(doc['data']), doc.get('content_type', 'application/octet-stream')
    except Exception as e:
        logger.warning(f"Failed async retrieve of asset: {e}")
        return None, None


def restore_project_assets_sync(mongo_url: str, db_name: str, project_id: str, assets_dir: str) -> int:
    """Restore all assets for a project from MongoDB to the local filesystem.
    Returns the number of files restored."""
    try:
        is_atlas = "mongodb.net" in mongo_url or "mongodb+srv" in mongo_url
        timeout = 30000 if is_atlas else 10000
        client = MongoClient(mongo_url, serverSelectionTimeoutMS=timeout, connectTimeoutMS=timeout, retryReads=True)
        db = client[db_name]
        docs = list(db.project_assets.find(
            {"project_id": project_id},
            {"_id": 0, "filename": 1, "data": 1}
        ))
        client.close()

        if not docs:
            return 0

        dest = Path(assets_dir)
        dest.mkdir(parents=True, exist_ok=True)
        restored = 0
        for doc in docs:
            fp = dest / doc['filename']
            if not fp.exists() and doc.get('data'):
                with open(fp, 'wb') as f:
                    f.write(base64.b64decode(doc['data']))
                restored += 1
        return restored
    except Exception as e:
        logger.warning(f"Failed to restore project assets: {e}")
        return 0
