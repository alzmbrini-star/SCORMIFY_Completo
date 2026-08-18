"""Brand Library routes — manages per-company image assets and the visual
Brand Kit (colors/fonts) used by the AI Agent when generating courses.

RBAC: only super_admin can mutate the library (per product decision). All
authenticated users can READ assets so the Editor can preview them.

Storage: file bytes live in GridFS-like `company_assets` collection (base64).
Metadata lives in `company_assets_meta`. Public download URL:
    /api/companies/{company_id}/assets/{asset_id}/file
"""
from fastapi import (
    APIRouter, HTTPException, Request, Depends, UploadFile, File, Form,
)
from fastapi.responses import Response
from typing import Optional, List, Dict, Any
import uuid
import logging
import json
from pathlib import Path
from tempfile import NamedTemporaryFile

from routes.deps import db, now_utc
from routes.auth import require_super_admin, require_auth, has_role
from models import (
    CompanyAsset, CompanyAssetUpdate, BrandKitUpdate,
    COMPANY_ASSET_TYPES, COMPANY_ASSET_CATEGORIES,
)
from services.asset_store import (
    store_company_asset_async,
    retrieve_company_asset_async,
    delete_company_asset_async,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/companies", tags=["BrandLibrary"])


def _public_url(company_id: str, asset_id: str) -> str:
    """The canonical URL the frontend/AI Agent points at for this asset."""
    return f"/api/companies/{company_id}/assets/{asset_id}/file"


async def _require_company(company_id: str) -> dict:
    company = await db.companies.find_one({"id": company_id}, {"_id": 0})
    if not company:
        raise HTTPException(status_code=404, detail="Empresa nao encontrada")
    return company


# ---------------------------------------------------------------------------
# Brand Kit (colors + fonts + logo). Embedded inside the company document.
# ---------------------------------------------------------------------------

@router.get("/{company_id}/brand-kit")
async def get_brand_kit(company_id: str, user: dict = Depends(require_auth)):
    """Return the brand kit for a company. Open to all authenticated users
    because the Editor needs it to render previews using corporate colors."""
    company = await _require_company(company_id)
    # Authorize: super_admin sees any; regular users only their own company.
    # Use has_role() so super_admins whose role lives in the `roles[]` array
    # (newer auth schema) — not the legacy single `role` field — are also
    # correctly granted access.
    if not has_role(user, "super_admin") and user.get("companyId") != company_id:
        raise HTTPException(status_code=403, detail="Acesso negado")
    return company.get("brandKit") or {}


@router.put("/{company_id}/brand-kit")
async def update_brand_kit(
    company_id: str,
    payload: BrandKitUpdate,
    user: dict = Depends(require_super_admin),
):
    """Update company Brand Kit atomically (super_admin only).

    Updating nested fields instead of replacing the whole object preserves
    older settings and avoids a second Mongo round-trip. Empty optional text
    values mean "inherit/default" and are removed from the stored kit.
    """
    company = await _require_company(company_id)
    dump = getattr(payload, "model_dump", None)
    kit = dump(exclude_none=True) if dump else payload.dict(exclude_none=True)
    logger.info(
        "update_brand_kit company=%s saving kit keys=%s logoSize=%r logoPlacement=%r",
        company_id, list(kit.keys()), kit.get("logoSize"), kit.get("logoPlacement"),
    )
    existing_kit = company.get("brandKit")
    set_fields = {"updatedAt": now_utc()}
    unset_fields = {}
    persisted_kit = dict(existing_kit) if isinstance(existing_kit, dict) else {}
    for key, value in kit.items():
        if isinstance(value, str) and not value.strip():
            unset_fields[f"brandKit.{key}"] = ""
            persisted_kit.pop(key, None)
        else:
            set_fields[f"brandKit.{key}"] = value
            persisted_kit[key] = value

    # A few legacy companies have brandKit=null. MongoDB cannot create a
    # dotted child below null, so initialize the complete object in that case.
    if not isinstance(existing_kit, dict):
        update = {"$set": {"brandKit": persisted_kit, "updatedAt": now_utc()}}
    else:
        update = {"$set": set_fields}
        if unset_fields:
            update["$unset"] = unset_fields
    try:
        result = await db.companies.update_one({"id": company_id}, update)
        if not result.matched_count:
            raise HTTPException(status_code=404, detail="Empresa nao encontrada")
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to persist Brand Kit for company=%s", company_id)
        raise HTTPException(
            status_code=500,
            detail="Nao foi possivel salvar a identidade visual no banco de dados.",
        ) from exc
    return {"brandKit": persisted_kit}


# ---------------------------------------------------------------------------
# Asset CRUD
# ---------------------------------------------------------------------------

@router.get("/{company_id}/assets")
async def list_assets(
    company_id: str,
    user: dict = Depends(require_auth),
    type: Optional[str] = None,
    category: Optional[str] = None,
    tag: Optional[str] = None,
    include_inactive: bool = False,
):
    """List brand assets for a company. All authenticated users in the
    company (or super_admin) can read so the Editor can preview imagery."""
    await _require_company(company_id)
    if not has_role(user, "super_admin") and user.get("companyId") != company_id:
        raise HTTPException(status_code=403, detail="Acesso negado")

    query: Dict[str, Any] = {"companyId": company_id}
    if not include_inactive:
        query["isActive"] = {"$ne": False}
    if type:
        query["type"] = type
    if category:
        query["category"] = category
    if tag:
        query["tags"] = {"$in": [tag]}

    rows = await db.company_assets_meta.find(query, {"_id": 0}).sort("createdAt", -1).to_list(1000)
    # Inject the public file URL so the UI/agent doesn't have to know the path
    for r in rows:
        r["url"] = _public_url(company_id, r["id"])
    return {"assets": rows, "total": len(rows)}


@router.post("/{company_id}/assets")
async def upload_asset(
    company_id: str,
    file: UploadFile = File(...),
    type: str = Form("background"),
    category: str = Form("generic"),
    tags: str = Form(""),           # comma-separated
    description: str = Form(""),
    user: dict = Depends(require_super_admin),
):
    """Upload an image into the company brand library. Multipart form.
    `tags` is a comma-separated string for ergonomic curl/Postman usage."""
    await _require_company(company_id)

    # Validate file
    if not file.filename:
        raise HTTPException(status_code=400, detail="Arquivo invalido")
    if file.content_type and not file.content_type.startswith("image"):
        # We're lenient — SVG comes as image/svg+xml; pdf is rejected explicitly
        if "pdf" in (file.content_type or "").lower():
            raise HTTPException(status_code=400, detail="PDF nao aceito; envie PNG, JPG, WEBP ou SVG")

    # Read into a temp file (avoid loading huge images into RAM twice)
    asset_id = f"casset_{uuid.uuid4().hex[:12]}"
    suffix = Path(file.filename).suffix.lower() or ".png"
    safe_filename = f"{asset_id}{suffix}"

    # 10 MB cap — corporate imagery shouldn't need more, and this prevents
    # a malicious large upload from triggering OOM on the worker.
    MAX_BYTES = 10 * 1024 * 1024

    with NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        if len(content) > MAX_BYTES:
            try:
                Path(tmp.name).unlink(missing_ok=True)
            except Exception:
                pass
            raise HTTPException(status_code=413, detail=f"Arquivo maior que {MAX_BYTES // 1024 // 1024}MB")
        tmp.write(content)
        tmp_path = tmp.name

    # Persist bytes in MongoDB (survives K8s pod restarts)
    ok = await store_company_asset_async(db, company_id, asset_id, safe_filename, tmp_path)
    try:
        Path(tmp_path).unlink(missing_ok=True)
    except Exception:
        pass
    if not ok:
        raise HTTPException(status_code=500, detail="Falha ao salvar imagem")

    # Best-effort: extract image dimensions if Pillow is available
    width = height = None
    try:
        from PIL import Image  # type: ignore
        from io import BytesIO
        img = Image.open(BytesIO(content))
        width, height = img.size
    except Exception:
        pass

    # Parse the comma-separated tags into a clean list
    tag_list = [t.strip() for t in (tags or "").split(",") if t.strip()]

    meta = CompanyAsset(
        id=asset_id,
        companyId=company_id,
        filename=safe_filename,
        originalFilename=file.filename,
        contentType=file.content_type or "image/png",
        sizeBytes=len(content),
        width=width,
        height=height,
        type=type,
        category=category,
        tags=tag_list,
        description=description.strip() or None,
        createdBy=user.get("id"),
    ).model_dump()
    await db.company_assets_meta.insert_one(meta)
    # Strip the BSON _id MongoDB writes back
    meta.pop("_id", None)
    meta["url"] = _public_url(company_id, asset_id)
    return meta


@router.patch("/{company_id}/assets/{asset_id}")
async def update_asset(
    company_id: str,
    asset_id: str,
    payload: CompanyAssetUpdate,
    user: dict = Depends(require_super_admin),
):
    """Update brand asset metadata (tags/description/category/type/active)."""
    await _require_company(company_id)
    patch = payload.model_dump(exclude_none=True)
    if not patch:
        raise HTTPException(status_code=400, detail="Sem alteracoes")
    patch["updatedAt"] = now_utc()
    result = await db.company_assets_meta.update_one(
        {"id": asset_id, "companyId": company_id},
        {"$set": patch},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Imagem nao encontrada")
    updated = await db.company_assets_meta.find_one(
        {"id": asset_id, "companyId": company_id}, {"_id": 0}
    )
    if updated:
        updated["url"] = _public_url(company_id, asset_id)
    return updated


@router.delete("/{company_id}/assets/{asset_id}")
async def delete_asset(
    company_id: str,
    asset_id: str,
    user: dict = Depends(require_super_admin),
):
    """Hard-delete a brand asset (file blob + metadata)."""
    await _require_company(company_id)
    meta = await db.company_assets_meta.find_one(
        {"id": asset_id, "companyId": company_id}, {"_id": 0}
    )
    if not meta:
        raise HTTPException(status_code=404, detail="Imagem nao encontrada")
    await delete_company_asset_async(db, company_id, asset_id)
    await db.company_assets_meta.delete_one({"id": asset_id, "companyId": company_id})
    return {"deleted": True, "id": asset_id}


@router.get("/{company_id}/assets/{asset_id}/file")
async def serve_asset(company_id: str, asset_id: str, request: Request):
    """Stream the binary asset back. No auth required — these are corporate
    imagery embedded into exported SCORM packages and Single Page HTML, which
    must remain fetchable from inside an offline LMS player."""
    data, ct = await retrieve_company_asset_async(db, company_id, asset_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Imagem nao encontrada")
    return Response(
        content=data,
        media_type=ct or "image/png",
        headers={"Cache-Control": "public, max-age=3600"},
    )



@router.get("/{company_id}/assets/{asset_id}/analysis")
async def analyze_asset_for_contrast(
    company_id: str,
    asset_id: str,
    user: dict = Depends(require_auth),
):
    """Compute dominant brightness so the frontend can suggest a contrasting
    text color when the author picks this asset as the **course background**.

    Returns:
        {
            "brightness": 0.0-1.0,    # perceived luminance, 0=black, 1=white
            "tone": "dark"|"light",   # broad bucket for UI labels
            "recommendedTextColor": "#FFFFFF" or "#0f172a",
            "recommendedOverlay": "dark" or "light" or "none",
        }
    """
    await _require_company(company_id)
    if not has_role(user, "super_admin") and user.get("companyId") != company_id:
        raise HTTPException(status_code=403, detail="Acesso negado")

    data, _ct = await retrieve_company_asset_async(db, company_id, asset_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Imagem nao encontrada")

    try:
        from PIL import Image  # type: ignore
        from io import BytesIO
        img = Image.open(BytesIO(data)).convert("RGB")
        # Downscale to a tiny thumbnail for fast luminance estimate.
        img.thumbnail((32, 32))
        pixels = list(img.getdata())
        # Standard relative luminance per W3C: 0.2126*R + 0.7152*G + 0.0722*B
        total = sum(
            0.2126 * r + 0.7152 * g + 0.0722 * b
            for r, g, b in pixels
        )
        avg_lum = (total / len(pixels)) / 255.0
    except Exception as e:
        logger.warning(f"asset analysis failed for {company_id}/{asset_id}: {e}")
        # Conservative fallback: assume dark image (so default is light text)
        avg_lum = 0.25

    # Threshold tuned empirically for corporate imagery (slightly darker than
    # 0.5 because text-on-image usually benefits from a darker assumption).
    is_dark = avg_lum < 0.55
    return {
        "brightness": round(avg_lum, 3),
        "tone": "dark" if is_dark else "light",
        # When the image is dark we put light text; when light, dark text.
        "recommendedTextColor": "#FFFFFF" if is_dark else "#0f172a",
        # An overlay reinforces contrast — dark overlay on light img + vice versa.
        # We use "none" for true midtones (0.40-0.65) to let the image speak.
        "recommendedOverlay": (
            "dark" if avg_lum > 0.65 else
            "light" if avg_lum < 0.30 else
            "none"
        ),
    }
