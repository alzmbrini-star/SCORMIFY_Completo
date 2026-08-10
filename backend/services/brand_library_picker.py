"""Brand Library Picker — selects images from a company's brand library
that semantically match the context of an AI-generated slide.

Strategy:
  1. List ACTIVE assets for the company, filtered by optional category
     (intro / content / transition / conclusion / etc.) and type
     (background / illustration / icon / logo / cover).
  2. Build a compact catalog string of (id, type, category, tags, description).
  3. Ask the LLM (Emergent universal key, claude-sonnet, cheap+fast) to pick
     the best id for the slide context. Returns just an id (or "none").
  4. Resolve the id back to a public URL the slide can use as
     `backgroundImage` / element src.

Why an LLM instead of cosine similarity?
  - The library is usually small (<200 images per company), so a single LLM
    call is fast and avoids embedding infra.
  - The matcher needs to read pt-BR descriptions and slide titles
    interchangeably — semantic models out-of-the-box do this well.
  - When no asset is a real fit, the LLM can explicitly say "none" so the
    caller falls back to Leonardo (or leaves blank in strict mode).
"""
import asyncio
import json
import logging
import os
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

# Cache the catalog per company per request to avoid re-querying for every
# slide. Lifecycle is process-local; entries expire on next deploy. Good
# enough — companies rarely have more than ~50 brand assets and the catalog
# fits in <5KB.
_catalog_cache: Dict[str, List[Dict[str, Any]]] = {}


async def _load_catalog(db, company_id: str) -> List[Dict[str, Any]]:
    """Fetch active brand assets for a company. Returns slim docs the LLM
    can read without seeing internal fields like createdBy."""
    if company_id in _catalog_cache:
        return _catalog_cache[company_id]
    rows = await db.company_assets_meta.find(
        {"companyId": company_id, "isActive": {"$ne": False}},
        {"_id": 0, "id": 1, "type": 1, "category": 1, "tags": 1, "description": 1},
    ).to_list(500)
    _catalog_cache[company_id] = rows
    return rows


def invalidate_catalog(company_id: str) -> None:
    """Drop the in-memory cache for a company (call when assets change)."""
    _catalog_cache.pop(company_id, None)


def _public_url(company_id: str, asset_id: str) -> str:
    return f"/api/companies/{company_id}/assets/{asset_id}/file"


async def pick_asset_for_slide(
    db,
    company_id: str,
    *,
    slide_title: str = "",
    slide_body: str = "",
    desired_type: str = "background",
    desired_category: Optional[str] = None,
    keyword: str = "",
) -> Optional[Dict[str, Any]]:
    """Choose the best matching brand asset for a slide.

    Args:
        db: Motor async db.
        company_id: which company's library to read.
        slide_title / slide_body: the slide's textual context. Used by the
            LLM to gauge mood/topic.
        desired_type: 'background' / 'illustration' / 'icon' / etc.
            Hard filter — we never pick an icon when a background was asked.
        desired_category: 'intro' / 'content' / 'conclusion' / etc. Soft
            filter: we narrow first; if nothing matches, broaden.
        keyword: if the slide already has an `imageKeywords` field, pass it
            in for a bigger signal.

    Returns:
        {'id', 'url', 'filename', 'contentType', ...} when a match is found,
        otherwise None.
    """
    rows = await _load_catalog(db, company_id)
    if not rows:
        return None

    # Hard filter by type — never serve an icon when a background was asked.
    candidates = [r for r in rows if (r.get("type") or "background") == desired_type]

    # Narrow by category if asked, but only if narrowing leaves at least one
    # candidate; otherwise broaden — empty result is worse than off-category.
    if desired_category:
        narrowed = [r for r in candidates if (r.get("category") or "generic") == desired_category]
        if narrowed:
            candidates = narrowed

    if not candidates:
        return None

    # Single candidate: skip the LLM call entirely.
    if len(candidates) == 1:
        chosen = candidates[0]
        return _build_result(company_id, chosen)

    # Build a compact catalog for the LLM and ask it to pick.
    chosen_id = await _llm_pick_id(
        candidates,
        slide_title=slide_title,
        slide_body=slide_body,
        keyword=keyword,
    )
    if not chosen_id or chosen_id == "none":
        return None
    chosen = next((c for c in candidates if c.get("id") == chosen_id), None)
    if not chosen:
        return None
    return _build_result(company_id, chosen)


def _build_result(company_id: str, asset: Dict[str, Any]) -> Dict[str, Any]:
    """Augment the matched asset record with the URL the caller will use."""
    return {
        "id": asset.get("id"),
        "url": _public_url(company_id, asset.get("id")),
        "type": asset.get("type"),
        "category": asset.get("category"),
        "tags": asset.get("tags") or [],
        "description": asset.get("description"),
        "source": "brand_library",  # provenance tag for debugging/analytics
    }


async def _llm_pick_id(
    candidates: List[Dict[str, Any]],
    *,
    slide_title: str,
    slide_body: str,
    keyword: str,
) -> Optional[str]:
    """Ask Claude (via the Emergent universal key) to pick the best asset.
    Returns the asset id string, or "none", or None on failure (caller treats
    failure as "no match" and falls back)."""
    if not candidates:
        return None

    # Build the catalog payload the LLM will read. Keep IDs short-ish (use the
    # last 8 chars of the casset_xxxx id) so token usage stays low.
    catalog_lines = []
    for c in candidates:
        cid = c.get("id") or ""
        cat = c.get("category") or "generic"
        tags = ", ".join((c.get("tags") or [])[:8])
        desc = (c.get("description") or "")[:140]
        catalog_lines.append(f"- id={cid} | categoria={cat} | tags=[{tags}] | descricao={desc}")
    catalog = "\n".join(catalog_lines)

    context_parts = []
    if slide_title:
        context_parts.append(f"Titulo: {slide_title}")
    if keyword:
        context_parts.append(f"Palavras-chave: {keyword}")
    if slide_body:
        body_short = slide_body[:600]
        context_parts.append(f"Conteudo: {body_short}")
    context = "\n".join(context_parts) or "(sem contexto)"

    prompt = f"""Voce e um assistente que escolhe imagens corporativas para slides de cursos.

Considere o contexto do slide abaixo e o catalogo da empresa, e escolha a imagem que melhor combina semanticamente. Se NENHUMA imagem combinar bem (ex: catalogo de fotos industriais e slide sobre RH), responda exatamente "none".

CONTEXTO DO SLIDE:
{context}

CATALOGO DE IMAGENS DA EMPRESA:
{catalog}

Responda APENAS com o id da imagem escolhida (ex: "casset_abc123def456") ou a string "none". Nenhuma outra palavra, pontuacao ou explicacao."""

    try:
        # Lazy import so this module loads cleanly even when the key isn't set.
        from emergentintegrations.llm.chat import LlmChat, UserMessage  # type: ignore
        key = os.environ.get("OPENAI_API_KEY", "").strip() or os.environ.get("EMERGENT_LLM_KEY", "").strip()
        if not key:
            logger.warning("OPENAI_API_KEY missing — brand library matcher disabled")
            return None
        chat = LlmChat(
            api_key=key,
            session_id=f"brand-library-pick-{candidates[0].get('id')}",
            system_message="Voce e um assistente que escolhe imagens corporativas. Responda APENAS com o id ou 'none'.",
        ).with_model("anthropic", "claude-sonnet-4-5-20250929")
        resp = await chat.send_message(UserMessage(text=prompt))
        if not resp:
            return None
        # The model sometimes returns the id wrapped in quotes/backticks — strip.
        out = str(resp).strip().strip('"').strip("'").strip("`").strip().split()[0]
        if not out or out.lower() in ("none", "nenhuma", "nenhum", "nao"):
            return "none"
        return out
    except Exception as e:
        logger.warning(f"brand library LLM pick failed: {e}")
        return None
