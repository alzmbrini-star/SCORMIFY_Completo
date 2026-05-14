"""
Asset Store - Persists binary assets in MongoDB for production environments
where the filesystem is ephemeral (Kubernetes pods).

Assets are stored in a 'project_assets' collection with:
- project_id: str
- filename: str
- data: base64-encoded string
- content_type: str
"""
import asyncio
import base64
import logging
from pathlib import Path
from pymongo import MongoClient

logger = logging.getLogger(__name__)

# Limit concurrent MongoDB asset queries to avoid Atlas M0 timeouts
_asset_semaphore = asyncio.Semaphore(5)


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
    """Store a file in MongoDB (synchronous, for startup/background tasks only).
    NOTE: This creates a new MongoClient per call. For batch operations, use
    the unified startup_asset_sync in server.py which reuses a single client."""
    try:
        with open(file_path, 'rb') as f:
            data = base64.b64encode(f.read()).decode('ascii')

        content_type = _get_content_type(filename)

        is_atlas = "mongodb.net" in mongo_url or "mongodb+srv" in mongo_url
        sel_timeout = 60000 if is_atlas else 10000
        conn_timeout = 60000 if is_atlas else 10000
        sock_timeout = 120000 if is_atlas else 30000
        client = MongoClient(
            mongo_url,
            serverSelectionTimeoutMS=sel_timeout,
            connectTimeoutMS=conn_timeout,
            socketTimeoutMS=sock_timeout,
            retryWrites=True,
        )
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
        sel_timeout = 60000 if is_atlas else 10000
        conn_timeout = 60000 if is_atlas else 10000
        sock_timeout = 120000 if is_atlas else 30000
        client = MongoClient(
            mongo_url,
            serverSelectionTimeoutMS=sel_timeout,
            connectTimeoutMS=conn_timeout,
            socketTimeoutMS=sock_timeout,
            retryReads=True,
        )
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
    Returns (bytes, content_type) or (None, None).
    Uses semaphore to limit concurrent queries and prevent Atlas M0 timeouts."""
    if db is None:
        logger.warning("retrieve_asset_async called with db=None")
        return None, None
    
    async with _asset_semaphore:
        for attempt in range(2):
            try:
                doc = await db.project_assets.find_one(
                    {"project_id": project_id, "filename": filename},
                    {"_id": 0, "data": 1, "content_type": 1}
                )
                if not doc or not doc.get('data'):
                    if attempt == 0:
                        logger.info(f"Asset not in MongoDB: {project_id}/{filename}")
                    return None, None
                data = base64.b64decode(doc['data'])
                logger.info(f"Retrieved asset from MongoDB: {project_id}/{filename} ({len(data)} bytes)")
                return data, doc.get('content_type', 'application/octet-stream')
            except Exception as e:
                logger.warning(f"Failed async retrieve of asset (attempt {attempt+1}): {project_id}/{filename}: {e}")
                if attempt == 0:
                    await asyncio.sleep(2)
        return None, None


def restore_project_assets_sync(mongo_url: str, db_name: str, project_id: str, assets_dir: str) -> int:
    """Restore all assets for a project from MongoDB to the local filesystem.
    Returns the number of files restored."""
    try:
        is_atlas = "mongodb.net" in mongo_url or "mongodb+srv" in mongo_url
        sel_timeout = 60000 if is_atlas else 10000
        conn_timeout = 60000 if is_atlas else 10000
        sock_timeout = 120000 if is_atlas else 30000
        client = MongoClient(
            mongo_url,
            serverSelectionTimeoutMS=sel_timeout,
            connectTimeoutMS=conn_timeout,
            socketTimeoutMS=sock_timeout,
            retryReads=True,
        )
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



# ---------------------------------------------------------------------------
# Company assets (Brand Library) — stored in a separate `company_assets`
# collection so per-project queries don't scan brand imagery and vice-versa.
# Same base64 storage pattern as project_assets: survives K8s pod restarts.
# ---------------------------------------------------------------------------

async def store_company_asset_async(db, company_id: str, asset_id: str, filename: str, file_path: str) -> bool:
    """Persist a Brand Library asset in MongoDB. Keyed by (company_id, asset_id)
    so two assets with the same filename within the same company are still
    distinguishable."""
    try:
        with open(file_path, "rb") as f:
            raw = f.read()
        data_b64 = base64.b64encode(raw).decode("ascii")
        ct = _get_content_type(filename)
        await db.company_assets.update_one(
            {"company_id": company_id, "asset_id": asset_id},
            {"$set": {
                "company_id": company_id,
                "asset_id": asset_id,
                "filename": filename,
                "data": data_b64,
                "content_type": ct,
            }},
            upsert=True,
        )
        logger.info(f"Brand asset stored in MongoDB: {company_id}/{asset_id} ({len(raw)} bytes)")
        return True
    except Exception as e:
        logger.error(f"Failed to store brand asset {company_id}/{asset_id}: {e}")
        return False


async def retrieve_company_asset_async(db, company_id: str, asset_id: str) -> tuple:
    """Fetch a Brand Library asset by (company_id, asset_id). Returns
    (bytes, content_type) or (None, None) when not found."""
    if db is None:
        return None, None
    async with _asset_semaphore:
        try:
            doc = await db.company_assets.find_one(
                {"company_id": company_id, "asset_id": asset_id},
                {"_id": 0, "data": 1, "content_type": 1},
            )
            if not doc or not doc.get("data"):
                return None, None
            return base64.b64decode(doc["data"]), doc.get("content_type", "application/octet-stream")
        except Exception as e:
            logger.warning(f"retrieve_company_asset_async failed for {company_id}/{asset_id}: {e}")
            return None, None


async def delete_company_asset_async(db, company_id: str, asset_id: str) -> bool:
    """Hard-delete a Brand Library asset blob. Caller is responsible for
    removing the metadata document in the `company_assets_meta` collection."""
    if db is None:
        return False
    try:
        await db.company_assets.delete_one({"company_id": company_id, "asset_id": asset_id})
        return True
    except Exception as e:
        logger.warning(f"delete_company_asset_async failed for {company_id}/{asset_id}: {e}")
        return False
