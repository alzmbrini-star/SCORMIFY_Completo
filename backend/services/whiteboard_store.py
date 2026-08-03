"""Durable storage helpers for rendered Whiteboard media.

Render's local filesystem is ephemeral. Whiteboard outputs can also be much
larger than MongoDB's 16 MB document limit, so new files are stored in a
dedicated GridFS bucket while the legacy collection remains a read fallback.
"""
from __future__ import annotations

import logging
import mimetypes
import re
from pathlib import Path
from typing import Iterable
from uuid import uuid4

from motor.motor_asyncio import AsyncIOMotorGridFSBucket

logger = logging.getLogger(__name__)

WHITEBOARD_BUCKET_NAME = "whiteboard_assets"
LEGACY_ASSET_NAMESPACE = "whiteboard"
_WHITEBOARD_URL_RE = re.compile(
    r"/api/whiteboard/file/(?P<name>wb_[A-Za-z0-9_-]+\.(?:mp4|webm|png))"
)
_WHITEBOARD_NAME_RE = re.compile(r"^wb_[A-Za-z0-9_-]+\.(?:mp4|webm|png)$")
_CHUNK_SIZE = 1024 * 1024
_MIN_MEDIA_BYTES = 1024
_VALIDATION_CACHE: dict[str, tuple[int, int, bool]] = {}


class WhiteboardAssetUnavailableError(RuntimeError):
    """Raised when an export references Whiteboard media that cannot be found."""


def is_valid_whiteboard_name(name: str) -> bool:
    return bool(_WHITEBOARD_NAME_RE.fullmatch(name or ""))


def validate_whiteboard_file(path: str | Path) -> bool:
    """Reject empty/truncated renderer output before it becomes durable.

    FFmpeg can leave a non-empty partial APNG behind when the encoder is
    interrupted.  Browsers may briefly paint its first frame and then replace
    it with the broken-image icon once parsing reaches the truncated tail.  A
    mere ``exists()``/size check therefore is not enough for Whiteboards.
    """
    media = Path(path)
    try:
        if not media.is_file():
            return False
        stat = media.stat()
        cache_key = str(media.resolve())
        signature = (stat.st_size, stat.st_mtime_ns)
        cached = _VALIDATION_CACHE.get(cache_key)
        if cached and cached[:2] == signature:
            return cached[2]
        if stat.st_size < _MIN_MEDIA_BYTES:
            _VALIDATION_CACHE[cache_key] = (*signature, False)
            return False
        lower_name = media.name.lower()
        # Restores are validated while still named
        # ``.wb_plan_x.png.<uuid>.part``; detect that safe temporary form as
        # PNG too instead of relying solely on the final suffix.
        if media.suffix.lower() == ".png" or ".png." in lower_name:
            from PIL import Image

            # ``verify`` walks the PNG chunks and detects a missing/corrupt
            # trailer.  Reopen afterwards because Pillow invalidates the
            # image object after verification, then force the last APNG frame
            # to be decoded as an additional integrity check.
            with Image.open(media) as image:
                image.verify()
            with Image.open(media) as image:
                frames = int(getattr(image, "n_frames", 1) or 1)
                if frames > 1:
                    image.seek(frames - 1)
                image.load()
        if len(_VALIDATION_CACHE) >= 512:
            _VALIDATION_CACHE.clear()
        _VALIDATION_CACHE[cache_key] = (*signature, True)
        return True
    except Exception as exc:
        logger.warning("Invalid Whiteboard media %s: %s", media.name, exc)
        try:
            stat = media.stat()
            _VALIDATION_CACHE[str(media.resolve())] = (
                stat.st_size,
                stat.st_mtime_ns,
                False,
            )
        except OSError:
            pass
        return False


def _names_from_value(value: object) -> Iterable[str]:
    if not isinstance(value, str):
        return ()
    return (match.group("name") for match in _WHITEBOARD_URL_RE.finditer(value))


def extract_whiteboard_names(project_doc: dict) -> list[str]:
    """Return every Whiteboard filename referenced by a project."""
    names: set[str] = set()
    course = (project_doc or {}).get("course") or {}
    for slide in course.get("slides") or []:
        if not isinstance(slide, dict):
            continue
        for field in ("videoUrl", "src", "url"):
            names.update(_names_from_value(slide.get(field)))
        for element in slide.get("elements") or []:
            if not isinstance(element, dict):
                continue
            for field in ("src", "videoUrl", "url", "content"):
                names.update(_names_from_value(element.get(field)))
    return sorted(names)


def missing_local_whiteboard_names(
    project_doc: dict,
    storage_dir: str | Path,
) -> list[str]:
    whiteboard_dir = Path(storage_dir) / "whiteboard"
    return [
        name
        for name in extract_whiteboard_names(project_doc)
        if not (whiteboard_dir / name).is_file()
    ]


def assert_local_whiteboards_available(
    project_doc: dict,
    storage_dir: str | Path,
) -> None:
    """Fail clearly rather than producing a package with broken media links."""
    missing = missing_local_whiteboard_names(project_doc, storage_dir)
    if missing:
        joined = ", ".join(missing)
        raise WhiteboardAssetUnavailableError(
            "Não foi possível exportar porque o Whiteboard do curso não está "
            f"disponível: {joined}. Gere novamente esse Whiteboard no Editor "
            "e tente exportar outra vez."
        )


def _bucket(db) -> AsyncIOMotorGridFSBucket:
    return AsyncIOMotorGridFSBucket(db, bucket_name=WHITEBOARD_BUCKET_NAME)


async def _find_gridfs_versions(bucket, name: str, limit: int = 100):
    cursor = bucket.find({"filename": name}).sort("uploadDate", -1)
    return await cursor.to_list(length=limit)


async def persist_whiteboard_file(db, name: str, source_path: str | Path) -> bool:
    """Persist a rendered Whiteboard in GridFS without a document-size limit."""
    source = Path(source_path)
    if (
        db is None
        or not is_valid_whiteboard_name(name)
        or not validate_whiteboard_file(source)
    ):
        return False

    bucket = _bucket(db)
    content_type = mimetypes.guess_type(name)[0] or "application/octet-stream"
    try:
        old_versions = await _find_gridfs_versions(bucket, name)
        with source.open("rb") as stream:
            await bucket.upload_from_stream(
                name,
                stream,
                metadata={
                    "contentType": content_type,
                    "kind": "whiteboard",
                    "size": source.stat().st_size,
                },
            )
        # Upload first: a failed upload can never erase the last usable copy.
        for old in old_versions:
            try:
                await bucket.delete(old._id)
            except Exception as exc:
                logger.warning(
                    "Could not remove old Whiteboard GridFS version: %s", exc
                )
        logger.info(
            "Whiteboard persisted in GridFS: %s (%d bytes)",
            name,
            source.stat().st_size,
        )
        return True
    except Exception as exc:
        logger.warning("GridFS persist failed for Whiteboard %s: %s", name, exc)

    # Compatibility fallback for installations not yet supporting GridFS.
    # Large files cannot use base64 because of MongoDB's document-size limit.
    if source.stat().st_size <= 12 * 1024 * 1024:
        try:
            from services.asset_store import store_asset_async

            return bool(
                await store_asset_async(
                    db, LEGACY_ASSET_NAMESPACE, name, str(source)
                )
            )
        except Exception as exc:
            logger.warning("Legacy Whiteboard persist failed for %s: %s", name, exc)
    return False


async def restore_whiteboard_file(
    db,
    name: str,
    destination: str | Path,
) -> bool:
    """Restore a Whiteboard from GridFS, falling back to legacy base64 data."""
    destination = Path(destination)
    if destination.is_file():
        return True
    if db is None or not is_valid_whiteboard_name(name):
        return False

    try:
        bucket = _bucket(db)
        versions = await _find_gridfs_versions(bucket, name, limit=1)
        if versions:
            stream = await bucket.open_download_stream(versions[0]._id)
            destination.parent.mkdir(parents=True, exist_ok=True)
            temp_path = destination.with_name(
                f".{destination.name}.{uuid4().hex}.part"
            )
            try:
                with temp_path.open("wb") as output:
                    while True:
                        chunk = await stream.read(_CHUNK_SIZE)
                        if not chunk:
                            break
                        output.write(chunk)
                if not validate_whiteboard_file(temp_path):
                    raise ValueError(
                        f"Whiteboard restaurado do GridFS está corrompido: {name}"
                    )
                temp_path.replace(destination)
            finally:
                if temp_path.exists():
                    temp_path.unlink()
            logger.info("Whiteboard restored from GridFS: %s", name)
            return True
    except Exception as exc:
        logger.warning("GridFS restore failed for Whiteboard %s: %s", name, exc)

    try:
        from services.asset_store import retrieve_asset_async

        data, _content_type = await retrieve_asset_async(
            db, LEGACY_ASSET_NAMESPACE, name
        )
        if data:
            destination.parent.mkdir(parents=True, exist_ok=True)
            temp_path = destination.with_name(
                f".{destination.name}.{uuid4().hex}.part"
            )
            temp_path.write_bytes(data)
            if not validate_whiteboard_file(temp_path):
                temp_path.unlink(missing_ok=True)
                return False
            temp_path.replace(destination)
            logger.info("Whiteboard restored from legacy MongoDB storage: %s", name)
            return True
    except Exception as exc:
        logger.warning("Legacy Whiteboard restore failed for %s: %s", name, exc)
    return False


async def ensure_whiteboards_for_export(
    project_doc: dict,
    db,
    storage_dir: str | Path,
) -> list[str]:
    """Materialize all referenced media locally before an offline export."""
    storage_dir = Path(storage_dir)
    whiteboard_dir = storage_dir / "whiteboard"
    restored: list[str] = []
    for name in extract_whiteboard_names(project_doc):
        destination = whiteboard_dir / name
        if destination.is_file():
            continue
        if await restore_whiteboard_file(db, name, destination):
            restored.append(name)

    assert_local_whiteboards_available(project_doc, storage_dir)
    return restored


def omit_missing_whiteboards_from_export(
    project_doc: dict,
    missing_names: Iterable[str],
) -> dict:
    """Remove irrecoverable Whiteboard references from an export-only copy.

    The caller must never persist this mutated document. This allows the rest
    of a course to be exported after an old Render filesystem was recycled,
    while making the omission explicit in the export result.
    """
    missing = set(missing_names)
    removed_elements = 0
    cleared_slide_fields = 0
    if not missing:
        return {
            "missing": [],
            "removedElements": 0,
            "clearedSlideFields": 0,
        }

    def references_missing(value: object) -> bool:
        return bool(set(_names_from_value(value)) & missing)

    course = (project_doc or {}).get("course") or {}
    for slide in course.get("slides") or []:
        if not isinstance(slide, dict):
            continue
        for field in ("videoUrl", "src", "url"):
            if references_missing(slide.get(field)):
                slide[field] = None
                cleared_slide_fields += 1

        kept_elements = []
        for element in slide.get("elements") or []:
            if not isinstance(element, dict):
                kept_elements.append(element)
                continue
            has_missing_ref = any(
                references_missing(element.get(field))
                for field in ("src", "videoUrl", "url", "content")
            )
            is_media = element.get("type") in ("video", "image")
            if has_missing_ref and (element.get("isWhiteboard") or is_media):
                removed_elements += 1
                continue
            kept_elements.append(element)
        slide["elements"] = kept_elements

    return {
        "missing": sorted(missing),
        "removedElements": removed_elements,
        "clearedSlideFields": cleared_slide_fields,
    }


async def prepare_whiteboards_for_export(
    project_doc: dict,
    db,
    storage_dir: str | Path,
) -> dict:
    """Restore available files and safely omit only irrecoverable references."""
    storage_dir = Path(storage_dir)
    whiteboard_dir = storage_dir / "whiteboard"
    restored: list[str] = []
    for name in extract_whiteboard_names(project_doc):
        destination = whiteboard_dir / name
        if destination.is_file():
            continue
        if await restore_whiteboard_file(db, name, destination):
            restored.append(name)

    missing = missing_local_whiteboard_names(project_doc, storage_dir)
    omission = omit_missing_whiteboards_from_export(project_doc, missing)
    return {
        "restored": restored,
        **omission,
    }
