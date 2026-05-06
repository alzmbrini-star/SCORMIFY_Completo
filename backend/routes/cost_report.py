"""Cost report routes — aggregate AI usage / project counts per company,
with monetary cost estimates.

Exposed only to super_admin (service-providers managing multiple client
companies). Provides per-company breakdown with USD/BRL estimates so the
user can produce client invoices.

Pricing model:
- Krea: per-model from services.krea_ai.KREA_IMAGE_MODELS[*].approxCostUSD
- Leonardo / Tutor / ElevenLabs / HeyGen: flat rate from DEFAULT_PRICING
- Admin can override any rate via PUT /api/admin/cost-pricing
- USD → BRL conversion via a single configurable rate (default 5.0)
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query

from routes.deps import db
from routes.auth import require_auth

logger = logging.getLogger("server")

router = APIRouter(tags=["Admin"])


# --------------------------------------------------------------------------
# Default pricing (USD per generation/message). Service-provider can override
# via PUT /api/admin/cost-pricing — overrides are stored in MongoDB.
# --------------------------------------------------------------------------
DEFAULT_PRICING_USD: Dict[str, float] = {
    # Image generations
    "leonardo": 0.02,        # avg per Leonardo image
    "krea_default": 0.04,    # fallback when modelId unknown / Krea catalog miss
    # Text / chat
    "tutor": 0.005,          # avg per AI Tutor message (gpt-4o-mini ish)
    # Audio / video
    "elevenlabs": 0.05,      # avg per voiceover (~30-60s)
    "heygen": 0.50,          # avg per avatar video (~1 min)
}
DEFAULT_USD_TO_BRL = 5.0


def _has_super_admin(user: dict) -> bool:
    role = user.get("role") or ""
    return role == "super_admin"


async def _load_pricing() -> Dict[str, Any]:
    """Load the active pricing table — defaults overlaid with admin overrides."""
    pricing = {**DEFAULT_PRICING_USD}
    usd_brl = DEFAULT_USD_TO_BRL
    krea_overrides: Dict[str, float] = {}
    try:
        doc = await db.cost_pricing.find_one({"_id": "active"}, {"_id": 0})
        if doc:
            for k, v in (doc.get("rates") or {}).items():
                if isinstance(v, (int, float)) and v >= 0:
                    pricing[k] = float(v)
            if isinstance(doc.get("usdToBrl"), (int, float)):
                usd_brl = float(doc["usdToBrl"])
            ko = doc.get("kreaOverrides") or {}
            if isinstance(ko, dict):
                for k, v in ko.items():
                    if isinstance(v, (int, float)) and v >= 0:
                        krea_overrides[str(k)] = float(v)
    except Exception:
        pass
    return {"rates": pricing, "usdToBrl": usd_brl, "kreaOverrides": krea_overrides}


def _price_per_krea_model(model_id: str, krea_overrides: Dict[str, float],
                            fallback: float) -> float:
    """Resolve price for a Krea model: admin override > catalog > fallback."""
    if model_id in krea_overrides:
        return krea_overrides[model_id]
    try:
        from services.krea_ai import get_model_meta
        meta = get_model_meta(model_id)
        if meta and isinstance(meta.get("approxCostUSD"), (int, float)):
            return float(meta["approxCostUSD"])
    except Exception:
        pass
    return fallback


# --------------------------------------------------------------------------
# Pricing CRUD — admin can edit override values
# --------------------------------------------------------------------------
@router.get("/admin/cost-pricing")
async def get_pricing(user: dict = Depends(require_auth)):
    """Return the active pricing table (defaults + admin overrides + Krea
    per-model catalog as resolved at this moment)."""
    if not _has_super_admin(user):
        raise HTTPException(403, "Apenas super-admin")
    p = await _load_pricing()
    # Snapshot Krea catalog so the UI shows current per-model prices
    try:
        from services.krea_ai import KREA_IMAGE_MODELS
        krea_catalog = [
            {
                "id": m["id"], "label": m.get("label", m["id"]),
                "tier": m.get("tier", "standard"),
                "default": float(m.get("approxCostUSD", DEFAULT_PRICING_USD["krea_default"])),
                "override": p["kreaOverrides"].get(m["id"]),
                "effective": _price_per_krea_model(m["id"], p["kreaOverrides"],
                                                     DEFAULT_PRICING_USD["krea_default"]),
            }
            for m in KREA_IMAGE_MODELS
        ]
    except Exception:
        krea_catalog = []
    return {
        "rates": p["rates"],
        "usdToBrl": p["usdToBrl"],
        "kreaOverrides": p["kreaOverrides"],
        "kreaCatalog": krea_catalog,
        "defaults": DEFAULT_PRICING_USD,
        "defaultUsdToBrl": DEFAULT_USD_TO_BRL,
    }


@router.put("/admin/cost-pricing")
async def update_pricing(payload: Dict[str, Any], user: dict = Depends(require_auth)):
    """Update pricing overrides. Body shape:
       { "rates": {"leonardo": 0.03, ...}, "usdToBrl": 5.2,
         "kreaOverrides": {"flux-1.1-pro": 0.06, ...} }
    Any field omitted is left unchanged. Negative values are rejected.
    """
    if not _has_super_admin(user):
        raise HTTPException(403, "Apenas super-admin")
    update_doc: Dict[str, Any] = {}
    rates = payload.get("rates")
    if isinstance(rates, dict):
        clean: Dict[str, float] = {}
        for k, v in rates.items():
            if not isinstance(v, (int, float)) or v < 0:
                raise HTTPException(400, f"Preço inválido para '{k}'")
            clean[k] = float(v)
        update_doc["rates"] = clean
    if "usdToBrl" in payload:
        v = payload["usdToBrl"]
        if not isinstance(v, (int, float)) or v <= 0:
            raise HTTPException(400, "Cotação USD→BRL inválida")
        update_doc["usdToBrl"] = float(v)
    krea_o = payload.get("kreaOverrides")
    if isinstance(krea_o, dict):
        clean_k: Dict[str, float] = {}
        for k, v in krea_o.items():
            if not isinstance(v, (int, float)) or v < 0:
                raise HTTPException(400, f"Preço Krea inválido para '{k}'")
            clean_k[str(k)] = float(v)
        update_doc["kreaOverrides"] = clean_k

    if not update_doc:
        raise HTTPException(400, "Nada para atualizar")
    update_doc["updatedAt"] = datetime.now(timezone.utc).isoformat()
    update_doc["updatedBy"] = user.get("user_id")
    await db.cost_pricing.update_one(
        {"_id": "active"},
        {"$set": update_doc},
        upsert=True,
    )
    return await _load_pricing()


# --------------------------------------------------------------------------
# Cost report
# --------------------------------------------------------------------------
@router.get("/admin/cost-report")
async def cost_report(
    user: dict = Depends(require_auth),
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
):
    """Per-company AI usage report with monetary estimates. Super_admin only.

    Aggregates collections by `companyId`, applies the active pricing table,
    and returns counts + USD/BRL totals per integration + grand total.
    """
    if not _has_super_admin(user):
        return {"detail": "Apenas super-admin pode acessar o relatório de custos.",
                 "companies": []}

    pricing = await _load_pricing()
    rates = pricing["rates"]
    usd_brl = pricing["usdToBrl"]
    krea_overrides = pricing["kreaOverrides"]

    date_filter: Dict[str, Any] = {}
    if from_date:
        date_filter["$gte"] = from_date
    if to_date:
        date_filter["$lt"] = to_date
    common_filter = {"createdAt": date_filter} if date_filter else {}

    companies_cursor = db.companies.find({}, {"_id": 0, "id": 1, "name": 1})
    companies_list = await companies_cursor.to_list(length=None)
    company_index = {c["id"]: c.get("name", "") for c in companies_list if c.get("id")}

    async def _count_by_company(collection_name: str) -> Dict[str, int]:
        pipeline: List[Dict[str, Any]] = []
        if common_filter:
            pipeline.append({"$match": common_filter})
        pipeline.append({"$group": {"_id": "$companyId", "count": {"$sum": 1}}})
        try:
            agg = await db[collection_name].aggregate(pipeline).to_list(length=None)
        except Exception as e:
            logger.warning(f"agg failed for {collection_name}: {e}")
            return {}
        return {row["_id"]: row["count"] for row in agg if row.get("_id")}

    # 1) Projects: count + breakdown by source
    projects_pipeline: List[Dict[str, Any]] = []
    if common_filter:
        projects_pipeline.append({"$match": common_filter})
    projects_pipeline.append({
        "$group": {
            "_id": {"companyId": "$companyId", "source": "$source"},
            "count": {"$sum": 1},
        }
    })
    try:
        proj_agg = await db.projects.aggregate(projects_pipeline).to_list(length=None)
    except Exception:
        proj_agg = []
    proj_by_company: Dict[str, Dict[str, int]] = {}
    for row in proj_agg:
        cid = (row.get("_id") or {}).get("companyId")
        src = (row.get("_id") or {}).get("source") or "manual"
        if not cid:
            continue
        proj_by_company.setdefault(cid, {"total": 0})
        proj_by_company[cid][src] = proj_by_company[cid].get(src, 0) + row["count"]
        proj_by_company[cid]["total"] += row["count"]

    # 2) Krea: group by (company, model) — needed for per-model pricing
    krea_pipeline: List[Dict[str, Any]] = []
    if common_filter:
        krea_pipeline.append({"$match": common_filter})
    krea_pipeline.append({
        "$group": {
            "_id": {"companyId": "$companyId", "modelId": "$modelId"},
            "count": {"$sum": 1},
        }
    })
    try:
        krea_agg = await db.krea_generations.aggregate(krea_pipeline).to_list(length=None)
    except Exception:
        krea_agg = []
    krea_by_company: Dict[str, Dict[str, Any]] = {}  # cid → {total, byModel: {id: {count, usd}}, usd}
    for row in krea_agg:
        cid = (row.get("_id") or {}).get("companyId")
        model_id = (row.get("_id") or {}).get("modelId") or "unknown"
        if not cid:
            continue
        count = row["count"]
        price_per = _price_per_krea_model(model_id, krea_overrides,
                                              rates.get("krea_default", DEFAULT_PRICING_USD["krea_default"]))
        usd = count * price_per
        bucket = krea_by_company.setdefault(cid, {"total": 0, "byModel": {}, "usd": 0.0})
        bucket["total"] += count
        bucket["byModel"][model_id] = {
            "count": count,
            "pricePer": price_per,
            "usd": round(usd, 4),
        }
        bucket["usd"] += usd

    leonardo_counts = await _count_by_company("leonardo_generations")
    tutor_counts = await _count_by_company("tutor_logs")

    async def _count_by_project_company(collection_name: str) -> Dict[str, int]:
        try:
            pipeline = []
            if common_filter:
                pipeline.append({"$match": common_filter})
            pipeline += [
                {"$lookup": {
                    "from": "projects", "localField": "projectId",
                    "foreignField": "id", "as": "_project",
                }},
                {"$unwind": {"path": "$_project", "preserveNullAndEmptyArrays": True}},
                {"$group": {"_id": "$_project.companyId", "count": {"$sum": 1}}},
            ]
            agg = await db[collection_name].aggregate(pipeline).to_list(length=None)
            return {row["_id"]: row["count"] for row in agg if row.get("_id")}
        except Exception:
            return {}

    elevenlabs_counts = await _count_by_company("elevenlabs_generations")
    if not elevenlabs_counts:
        elevenlabs_counts = await _count_by_project_company("elevenlabs_generations")
    heygen_counts = await _count_by_company("heygen_jobs")
    if not heygen_counts:
        heygen_counts = await _count_by_project_company("heygen_jobs")

    # 3) Build per-company response with USD/BRL
    all_company_ids = set(company_index.keys())
    all_company_ids.update(proj_by_company.keys())
    all_company_ids.update(krea_by_company.keys())
    all_company_ids.update(leonardo_counts.keys())
    all_company_ids.update(tutor_counts.keys())
    all_company_ids.update(elevenlabs_counts.keys())
    all_company_ids.update(heygen_counts.keys())

    companies_out = []
    for cid in sorted(all_company_ids):
        if not cid:
            continue
        krea = krea_by_company.get(cid, {"total": 0, "byModel": {}, "usd": 0.0})
        leo_n = leonardo_counts.get(cid, 0)
        tut_n = tutor_counts.get(cid, 0)
        ele_n = elevenlabs_counts.get(cid, 0)
        hey_n = heygen_counts.get(cid, 0)

        leo_usd = leo_n * rates.get("leonardo", DEFAULT_PRICING_USD["leonardo"])
        tut_usd = tut_n * rates.get("tutor", DEFAULT_PRICING_USD["tutor"])
        ele_usd = ele_n * rates.get("elevenlabs", DEFAULT_PRICING_USD["elevenlabs"])
        hey_usd = hey_n * rates.get("heygen", DEFAULT_PRICING_USD["heygen"])
        total_usd = krea["usd"] + leo_usd + tut_usd + ele_usd + hey_usd

        companies_out.append({
            "companyId": cid,
            "companyName": company_index.get(cid, "(empresa removida)"),
            "projects": proj_by_company.get(cid, {"total": 0}),
            "krea": {
                "total": krea["total"],
                "usd": round(krea["usd"], 2),
                "brl": round(krea["usd"] * usd_brl, 2),
                "byModel": krea["byModel"],
            },
            "leonardo": {"total": leo_n, "usd": round(leo_usd, 2), "brl": round(leo_usd * usd_brl, 2)},
            "tutor": {"total": tut_n, "usd": round(tut_usd, 2), "brl": round(tut_usd * usd_brl, 2)},
            "elevenlabs": {"total": ele_n, "usd": round(ele_usd, 2), "brl": round(ele_usd * usd_brl, 2)},
            "heygen": {"total": hey_n, "usd": round(hey_usd, 2), "brl": round(hey_usd * usd_brl, 2)},
            "totalUsd": round(total_usd, 2),
            "totalBrl": round(total_usd * usd_brl, 2),
        })

    return {
        "companies": companies_out,
        "from": from_date,
        "to": to_date,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "pricing": {
            "rates": rates,
            "usdToBrl": usd_brl,
            "kreaOverrides": krea_overrides,
        },
    }
