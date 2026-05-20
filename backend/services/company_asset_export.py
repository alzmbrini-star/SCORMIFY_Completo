"""Pre-extract company brand assets to disk before SCORM/HTML exports.

The exporters resolve URLs synchronously, but GridFS reads are async — so
we must materialize every `/api/companies/<cid>/assets/<aid>/file` URL
referenced by a project into a local file under `assets_dir/_companies/`
before invoking `generate_single_page_html` / scorm exporters.

Once on disk, `_resolve_asset_url` (synchronously) converts those URLs to
data URIs in the final standalone HTML.
"""
from __future__ import annotations

import logging
import mimetypes
import re
from pathlib import Path
from typing import Iterable, Set

logger = logging.getLogger("server")

_COMPANY_ASSET_URL_RE = re.compile(
    r"/api/companies/([^/\s\"']+)/assets/([^/\s\"']+)/file"
)


def _iter_all_strings(obj) -> Iterable[str]:
    """Walk a nested project doc and yield every string value."""
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _iter_all_strings(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            yield from _iter_all_strings(v)


def _collect_company_asset_refs(project_doc: dict) -> Set[tuple]:
    """Return a set of (company_id, asset_id) tuples referenced anywhere
    in the project's slides/elements/styles."""
    found: Set[tuple] = set()
    for s in _iter_all_strings(project_doc):
        for m in _COMPANY_ASSET_URL_RE.finditer(s):
            found.add((m.group(1), m.group(2)))
    return found


def _ext_from_content_type(ct: str) -> str:
    if not ct:
        return "bin"
    ct = ct.split(";")[0].strip().lower()
    guessed = mimetypes.guess_extension(ct) or ""
    return guessed.lstrip(".") or "bin"


async def prepare_company_assets_for_export(project_doc: dict, db, assets_dir: str) -> int:
    """Materialize every referenced company asset under
    `assets_dir/_companies/<asset_id>.<ext>`.

    Returns the count of newly-written files. Existing files are skipped
    (idempotent — safe to call repeatedly).
    """
    refs = _collect_company_asset_refs(project_doc)
    if not refs:
        return 0

    out_dir = Path(assets_dir) / "_companies"
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        from services.asset_store import retrieve_company_asset_async
    except ImportError:
        try:
            from routes.company_assets import retrieve_company_asset_async  # type: ignore
        except Exception as exc:
            logger.warning(f"prepare_company_assets_for_export: helper not found: {exc}")
            return 0

    written = 0
    for company_id, asset_id in refs:
        # Skip if any extension already exists for this asset_id.
        existing = [p for p in out_dir.glob(f"{asset_id}.*") if p.is_file()]
        if existing:
            continue
        try:
            data, content_type = await retrieve_company_asset_async(db, company_id, asset_id)
        except Exception as exc:
            logger.warning(
                f"prepare_company_assets_for_export: fetch {asset_id} failed: {exc}"
            )
            continue
        if not data:
            continue
        ext = _ext_from_content_type(content_type or "")
        # Normalize a few common cases (image/jpeg → jpg, image/svg+xml → svg)
        if ext == "jpe" or ext == "jpeg":
            ext = "jpg"
        if "svg" in (content_type or "").lower():
            ext = "svg"
        target = out_dir / f"{asset_id}.{ext}"
        try:
            target.write_bytes(data)
            written += 1
        except Exception as exc:
            logger.warning(
                f"prepare_company_assets_for_export: write {target} failed: {exc}"
            )
    return written
