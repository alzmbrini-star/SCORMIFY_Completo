"""Routes for the visual-density analysis feature.

  POST /api/density/analyze            — score a single slide / section
  POST /api/density/suggestions        — score + LLM suggestions for one slide
  POST /api/density/analyze-storyboard — bulk score every section in a storyboard
  POST /api/density/analyze-project    — bulk score every slide in a project
  POST /api/density/generate-image     — render the suggestion's imagePrompt
                                          via Gemini Nano Banana and persist
                                          it as a project asset (used when the
                                          author applies an "infographic" or
                                          "diagram" suggestion that promised
                                          an image but the apply flow alone
                                          only writes the textual rewrite).

All endpoints return shapes compatible with the frontend density UI
(`DensityBadge` + `DensitySuggestionsDialog`).
"""
import os
import logging
import hashlib
import uuid
from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

from routes.deps import db, PROJECTS_DIR
from routes.auth import require_auth
from services.text_density_analyzer import (
    analyze_text_density,
    analyze_slide,
    analyze_storyboard_section,
)
from services.density_suggester import generate_visual_suggestions
from services.gemini_image import generate_simple_image
from services.asset_store import store_asset_async
from services import krea_ai

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/density", tags=["Density"])


class AnalyzeRequest(BaseModel):
    title: Optional[str] = ""
    text: Optional[str] = ""
    bullets: Optional[List[str]] = Field(default_factory=list)
    hasImage: Optional[bool] = False


class StoryboardAnalyzeRequest(BaseModel):
    sections: List[Dict[str, Any]]


class ProjectAnalyzeRequest(BaseModel):
    slides: List[Dict[str, Any]]


@router.post("/analyze")
async def analyze(req: AnalyzeRequest, user: dict = Depends(require_auth)):
    """Score one piece of content. Cheap, deterministic, no LLM."""
    result = analyze_text_density(
        text=req.text or "",
        bullets=req.bullets or [],
        has_image=bool(req.hasImage),
        title=req.title or "",
    )
    return result


@router.post("/suggestions")
async def suggestions(req: AnalyzeRequest, user: dict = Depends(require_auth)):
    """Score + LLM-generated visual alternatives. Slower (~3s) but actionable.
    Always runs the LLM — the frontend uses /analyze for the initial badge
    and only calls this when the author clicks the badge for details."""
    density = analyze_text_density(
        text=req.text or "",
        bullets=req.bullets or [],
        has_image=bool(req.hasImage),
        title=req.title or "",
    )
    sugs = await generate_visual_suggestions(
        title=req.title or "",
        text=req.text or "",
        bullets=req.bullets or [],
        reasons=density["reasons"],
    )
    return {"density": density, "suggestions": sugs}


@router.post("/analyze-storyboard")
async def analyze_storyboard(req: StoryboardAnalyzeRequest, user: dict = Depends(require_auth)):
    """Score every section in a storyboard. Single request → instant badges
    on the storyboard approval screen."""
    out = []
    for idx, section in enumerate(req.sections):
        analysis = analyze_storyboard_section(section)
        out.append({
            "index": idx,
            "title": section.get("title") or section.get("sectionTitle") or f"Secao {idx + 1}",
            **analysis,
        })
    summary = {
        "total": len(out),
        "light": sum(1 for o in out if o["label"] == "light"),
        "medium": sum(1 for o in out if o["label"] == "medium"),
        "heavy": sum(1 for o in out if o["label"] == "heavy"),
    }
    return {"sections": out, "summary": summary}


@router.post("/analyze-project")
async def analyze_project(req: ProjectAnalyzeRequest, user: dict = Depends(require_auth)):
    """Score every slide in a project. Used by GeneratedPanel for the
    post-generation 'Densidade Visual' panel."""
    out = []
    for idx, slide in enumerate(req.slides):
        analysis = analyze_slide(slide)
        out.append({
            "index": idx,
            "slideId": slide.get("id"),
            "title": slide.get("title") or f"Slide {idx + 1}",
            **analysis,
        })
    summary = {
        "total": len(out),
        "light": sum(1 for o in out if o["label"] == "light"),
        "medium": sum(1 for o in out if o["label"] == "medium"),
        "heavy": sum(1 for o in out if o["label"] == "heavy"),
    }
    return {"slides": out, "summary": summary}


class GenerateImageRequest(BaseModel):
    projectId: str
    imagePrompt: str
    # Optional hint for filename — keeps repeat applies idempotent and
    # avoids duplicate assets when the same suggestion is re-applied.
    suggestionId: Optional[str] = None
    # Which image-generation backend to use.
    #   "gemini" (default)  → Gemini Nano Banana via Emergent LLM key
    #                          (~3-6s, no user setup needed, billed to
    #                          Universal Key budget)
    #   "krea"              → Krea AI (user API key required), various
    #                          Flux/Imagen/SeeDream models, ~4-25s, billed
    #                          to the user's Krea account.
    provider: Optional[str] = "gemini"
    # Krea-only: which model from KREA_IMAGE_MODELS. Defaults to flux-1-dev
    # (the fastest, 4s, $0.04) which gives a good price/quality balance for
    # density-suggestion infographics.
    kreaModelId: Optional[str] = "flux-1-dev"
    # Visual style of the generated image. The default ("infographic") is
    # what we shipped first — flat-vector icon-based composition, ideal for
    # density-suggestion diagrams. Other options:
    #   "photorealistic" → studio-grade photography look. Skips the
    #     icon-only rewriting (we WANT visual detail). Best paired with a
    #     photoreal model (Flux 1.1 Pro, Imagen 4) when on Krea.
    #   "3d-illustration" → octane-style 3D render. Good for product
    #     visualizations.
    #   "editorial" → magazine-style editorial photography, neutral
    #     lighting, professional composition.
    imageStyle: Optional[str] = "infographic"
    # Also persist the generated image into the project's company brand
    # library so the author can reuse it across other slides/courses.
    # Requires super_admin (mirrors the upload_asset permission). Falls
    # back silently when the user isn't allowed — the image is still
    # written as a project asset, just not as a company asset.
    saveToLibrary: Optional[bool] = True


# Style → company-asset type mapping. When we persist a density-generated
# image into the company brand library, we need to classify it. Photorealistic
# and editorial shots become "background" candidates (they fill the slide
# well). Infographic and 3D illustrations become "illustration" candidates
# (paired with text). The author can re-categorize via the Brand Library UI
# afterwards.
STYLE_TO_ASSET_TYPE = {
    "infographic": "illustration",
    "photorealistic": "background",
    "editorial": "background",
    "3d-illustration": "illustration",
}


# Style configuration. Each style controls (a) a positive prompt suffix
# that biases the model toward the look the author asked for, (b) a
# negative prompt to suppress the wrong aesthetic, and (c) whether the
# text-stripping rewriting should run. For photorealistic & editorial we
# DON'T strip text instructions because A) the user is asking for a photo
# of a scene, not a labeled diagram, and B) any incidental words in the
# scene (e.g. document headers) being slightly garbled is invisible at
# slide-resolution viewing.
IMAGE_STYLE_CONFIG = {
    "infographic": {
        "label": "Infografico flat",
        "positiveSuffix": "Style: minimalist flat vector illustration, centered hero icon, abstract symbolic composition. Use icons, shapes, arrows, gradients and color coding to convey meaning. Clean modern aesthetic, professional infographic look.",
        "negativeAddon": "photograph, photo, photorealistic, realistic, 3d render, render, depth of field, bokeh",
        "stripText": True,
    },
    "photorealistic": {
        "label": "Fotorrealista",
        "positiveSuffix": "Style: professional editorial photography, photorealistic, highly detailed, natural realistic lighting, shallow depth of field, shot on Canon EOS R5, 50mm lens, f/1.8, ultra sharp, 8k.",
        "negativeAddon": "cartoon, illustration, drawing, painting, anime, infographic, flat design, icon, vector art, low quality, blurry, deformed",
        "stripText": False,
    },
    "3d-illustration": {
        "label": "Ilustracao 3D",
        "positiveSuffix": "Style: high-quality 3D illustration, octane render, ray tracing, soft studio lighting, isometric perspective, vibrant colors, detailed materials and textures, modern corporate aesthetic.",
        "negativeAddon": "photograph, photo, flat design, vector art, infographic, sketch, low poly",
        "stripText": True,
    },
    "editorial": {
        "label": "Editorial corporativo",
        "positiveSuffix": "Style: editorial corporate photography, magazine cover quality, modern professional environment, natural lighting, neutral colors, candid composition, shot on medium format camera.",
        "negativeAddon": "cartoon, illustration, drawing, infographic, flat design, 3d render, low quality, blurry, oversaturated",
        "stripText": False,
    },
}


# Recommended Krea model for each style. When the author picks a style
# the frontend asks "should I auto-switch the Krea model too?" and uses
# this map. The user is always free to override.
STYLE_KREA_MODEL_HINT = {
    "infographic": "flux-1-dev",        # fast, icon-friendly
    "photorealistic": "flux-1.1-pro",   # best photoreal in Flux family
    "3d-illustration": "flux-1.1-pro",  # also handles 3D well
    "editorial": "flux-1.1-pro",        # photorealistic but editorial
}


@router.get("/image-styles")
async def list_image_styles(user: dict = Depends(require_auth)):
    """List the visual styles the author can request for a generated image.

    Each style has a label (pt-BR), a hint for the recommended Krea model
    (the frontend auto-switches if the user is on Krea), and an icon
    keyword for the picker UI.
    """
    return {
        "styles": [
            {"id": "infographic", "label": "Infografico flat", "icon": "LayoutGrid", "recommendedKreaModel": "flux-1-dev"},
            {"id": "photorealistic", "label": "Fotorrealista", "icon": "Camera", "recommendedKreaModel": "flux-1.1-pro"},
            {"id": "3d-illustration", "label": "Ilustracao 3D", "icon": "Box", "recommendedKreaModel": "flux-1.1-pro"},
            {"id": "editorial", "label": "Editorial corporativo", "icon": "Newspaper", "recommendedKreaModel": "flux-1.1-pro"},
        ]
    }


@router.get("/image-providers")
async def list_image_providers(user: dict = Depends(require_auth)):
    """List which image-generation providers are currently usable.

    Frontend uses this to render the provider picker in the density
    suggestions dialog. The Gemini option is always available (uses the
    Emergent Universal Key); Krea only appears if KREA_API_KEY is set
    (user must have configured it in admin settings).
    """
    providers = [
        {
            "id": "gemini",
            "label": "Gemini Nano Banana",
            "description": "Rapido (~5s), ja incluso na chave universal Emergent.",
            "models": [],
            "configured": True,
        },
    ]
    if krea_ai.is_configured():
        providers.append({
            "id": "krea",
            "label": "Krea AI",
            "description": "Mais modelos (Flux, Imagen, SeeDream), maior fidelidade. Cobrado na sua conta Krea.",
            "models": [
                {"id": m["id"], "label": m["label"], "description": m["description"],
                 "approxTimeSeconds": m.get("approxTimeSeconds"),
                 "approxCostUSD": m.get("approxCostUSD"),
                 # textRendering capability — frontend uses this to show
                 # a "✓ texto pt-BR" badge on capable models and a warning
                 # icon on icon-only models.
                 "textRendering": m.get("textRendering", "poor")}
                for m in krea_ai.KREA_IMAGE_MODELS
            ],
            "configured": True,
        })
    return {"providers": providers}


async def _generate_via_krea(prompt: str, model_id: str, negative_prompt: Optional[str] = None) -> Optional[bytes]:
    """Submit a Krea job and poll until completed (or fail fast). Returns
    JPEG bytes or None on failure. Krea is async (submit → poll → download)
    so we wrap that lifecycle here to match the simple bytes-returning
    contract of `generate_simple_image()`.

    The HTTP error categories are tracked for the caller's error message:
      - 402 → Krea account doesn't have access to this model (upgrade plan)
      - 404 → Model path retired or never existed in Krea's catalog
      - 422 → Payload shape mismatch (we pass width/height/steps but some
              models expect aspect_ratio or other parameters)
    """
    import asyncio
    import httpx
    try:
        # 16:9 wide aspect — most density slides put image on the right
        # half of a 1920x780 union, so a roughly 1200x675 image fills it
        # without awkward letterboxing.
        job = await krea_ai.submit_generation(
            model_id=model_id,
            prompt=prompt,
            width=1200,
            height=675,
            negative_prompt=negative_prompt,
        )
        job_id = job.get("job_id")
        if not job_id:
            logger.warning(f"[density.krea] No job_id returned: {job}")
            return None
        # Poll up to 90s (Krea claims 4-25s typical for our default model).
        for _ in range(45):
            await asyncio.sleep(2)
            j = await krea_ai.get_job(job_id)
            status = (j.get("status") or "").lower()
            if status == "completed":
                # Krea returns the URL under one of several shapes depending
                # on the model. The most common (Flux) shape is
                # `result.urls[0]`. We also handle the older `results: [...]`
                # and the flat `image_url` form.
                img_url = None
                result_obj = j.get("result") or {}
                if isinstance(result_obj, dict):
                    urls = result_obj.get("urls") or result_obj.get("images")
                    if isinstance(urls, list) and urls:
                        first = urls[0]
                        img_url = first if isinstance(first, str) else (
                            first.get("url") or first.get("image_url"))
                if not img_url:
                    results = j.get("results") or j.get("outputs") or []
                    if isinstance(results, list) and results:
                        first = results[0]
                        img_url = first if isinstance(first, str) else (
                            first.get("url") or first.get("image_url"))
                if not img_url:
                    img_url = j.get("image_url") or j.get("url")
                if not img_url:
                    logger.warning(f"[density.krea] Job done but no URL: {j}")
                    return None
                raw = await krea_ai.download_image_bytes(img_url)
                # Normalize to optimized JPEG so the file extension (.jpg)
                # matches the bytes and the asset stays small (Krea sends
                # PNG by default which can be 800KB+).
                try:
                    import io
                    from PIL import Image
                    img = Image.open(io.BytesIO(raw))
                    if img.mode in ("RGBA", "LA", "P"):
                        bg = Image.new("RGB", img.size, (255, 255, 255))
                        if img.mode == "P":
                            img = img.convert("RGBA")
                        bg.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
                        img = bg
                    elif img.mode != "RGB":
                        img = img.convert("RGB")
                    if max(img.size) > 1400:
                        ratio = 1400 / max(img.size)
                        img = img.resize(
                            (int(img.width * ratio), int(img.height * ratio)),
                            Image.Resampling.LANCZOS,
                        )
                    out = io.BytesIO()
                    img.save(out, format="JPEG", quality=85, optimize=True)
                    return out.getvalue()
                except Exception as e:
                    logger.warning(f"[density.krea] JPEG normalize failed, keeping raw: {e}")
                    return raw
            if status in ("failed", "cancelled", "error"):
                logger.warning(f"[density.krea] Job {job_id} status={status}")
                return None
        logger.warning(f"[density.krea] Job {job_id} polling timed out")
        return None
    except httpx.HTTPStatusError as e:
        # Re-raise as a specific exception so the route handler can return
        # a useful 4xx with the actual reason instead of a generic 502.
        status_code = e.response.status_code
        if status_code == 402:
            raise KreaUserError(f"Sua conta Krea nao tem acesso ao modelo '{model_id}'. Atualize seu plano ou escolha outro modelo (ex: Flux 1 Dev).")
        if status_code == 404:
            raise KreaUserError(f"O modelo '{model_id}' nao esta disponivel na sua conta Krea. Tente Flux 1 Dev ou troque para Gemini.")
        if status_code == 422:
            raise KreaUserError(f"O modelo '{model_id}' tem parametros incompativeis com esta integracao. Use Flux 1 Dev (compatibilidade total) ou Gemini.")
        logger.error(f"[density.krea] HTTP {status_code}: {e}")
        return None
    except Exception as e:
        logger.error(f"[density.krea] Generation failed: {e}")
        return None


class KreaUserError(Exception):
    """Raised when the Krea API returns a 4xx whose remedy the user needs
    to know (e.g. plan upgrade, wrong model). Propagated to the FastAPI
    route which turns it into a 400 with the human message."""
    pass


@router.post("/generate-image")
async def generate_image_for_suggestion(req: GenerateImageRequest, user: dict = Depends(require_auth)):
    """Generate an illustration for a density suggestion that promised an
    image (e.g. infographic/diagram types).

    Supports two providers (selectable via `provider` field):
      - "gemini" (default): Gemini Nano Banana via Emergent Universal Key.
        Fast (~5s), no user setup, but constrained by the universal key
        budget.
      - "krea": Krea AI (requires KREA_API_KEY env var). Multiple models
        (Flux, Imagen 4, SeeDream, etc) selectable via `kreaModelId`.
        Billed to the user's Krea account.

    Returns: { url, filename, width, height, provider } on success.
    """
    prompt = (req.imagePrompt or "").strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="imagePrompt is required")
    if not req.projectId:
        raise HTTPException(status_code=400, detail="projectId is required")

    # ---- STYLE & LANGUAGE HARDENING ----------------------------------------
    # Three orthogonal concerns shape the final prompt:
    #   (1) `imageStyle` — what does the author WANT the image to look like
    #       (infographic / photorealistic / 3D / editorial).
    #   (2) `textRendering` of the chosen model — CAN it draw legible
    #       words?  Photographic models that can't draw text are still
    #       fine for photorealistic prompts because we don't ask for
    #       labels.
    #   (3) Source `imagePrompt` from the suggestion LLM, which was
    #       authored assuming "infographic with pt-BR labels". We may
    #       need to strip those labels when the model can't draw text
    #       OR keep them when the model can.
    style_id = (req.imageStyle or "infographic").strip().lower()
    style = IMAGE_STYLE_CONFIG.get(style_id) or IMAGE_STYLE_CONFIG["infographic"]

    provider = (req.provider or "gemini").lower().strip()
    text_render_quality = "good"  # gemini handles pt-BR text OK
    if provider == "krea":
        m = krea_ai.get_model(req.kreaModelId or "flux-1-dev")
        text_render_quality = (m or {}).get("textRendering", "poor")

    # The text-stripping rewrite runs when EITHER the style asks for it
    # (infographic / 3D, both flat-vector-ish) AND the model can't render
    # text. Photorealistic & editorial styles never strip — they don't
    # invite labels in the first place.
    should_strip_text = style["stripText"] and text_render_quality == "poor"

    # Negative prompt fed to text-poor models (Flux family). Flux is biased
    # to add labels even when told not to — `negative_prompt` is the only
    # reliable suppression mechanism.
    negative_prompt: Optional[str] = None

    if should_strip_text:
        # Strip any text-rendering instruction the suggester LLM injected
        # (e.g., "Todos os rotulos em portugues") — the model can't draw it
        # legibly anyway. Force ICON-ONLY visuals.
        prompt_lower = prompt.lower()
        # Remove sentences mentioning "rotulos", "legendas", "labels",
        # "palavras", "texto", "titulos" (we add our own constraint).
        for needle in (
            "todos os rotulos",
            "todos os títulos",
            "rotulos em portugues",
            "labels in",
            "with labels",
            "with text",
            "with words",
            "palavras em portugues",
            "legendas em portugues",
            "texto em portugues",
            "nao usar texto em ingles",
            "no usar texto",
        ):
            i = prompt_lower.find(needle)
            if i >= 0:
                # Find sentence boundary backward and forward, drop the sentence.
                start = prompt.rfind(".", 0, i) + 1
                end = prompt.find(".", i)
                end = end + 1 if end >= 0 else len(prompt)
                prompt = (prompt[:start] + prompt[end:]).strip(" .,;")
                prompt_lower = prompt.lower()
        # Rewrite POSITIVE prompt to invite a centered iconic visual rather
        # than a labeled diagram. Flux interprets "diagram with 5 elements"
        # as "draw 5 labeled regions" and will hallucinate text — so we
        # rephrase to suggest a hero icon composition with the style suffix.
        prompt = prompt.rstrip(". ") + ". " + style["positiveSuffix"]
        # NEGATIVE prompt — this is the actual mechanism Flux respects. The
        # positive "no text" instruction alone is unreliable; negative_prompt
        # in Flux training data is consistently suppressed. We add the
        # style-specific aesthetic negatives on top.
        base_negative = (
            "text, letters, words, captions, labels, typography, watermark, "
            "annotations, lettering, characters, alphabet, writing, signature, "
            "logo text, gibberish text, fake text, latin characters, font, "
            "subtitle, heading, paragraph, sentence"
        )
        negative_prompt = base_negative + ", " + style["negativeAddon"]
    else:
        # No text-strip needed. Append the style suffix so the model knows
        # what aesthetic to target, and still apply the style-specific
        # negative prompt (e.g. for photorealistic we want "no cartoon").
        prompt = prompt.rstrip(". ") + ". " + style["positiveSuffix"]
        negative_prompt = style["negativeAddon"]
        # Defense in depth: for text-capable models on infographic-like
        # styles, re-append the pt-BR instruction if the suggester LLM
        # forgot it.
        if style_id in ("infographic",) and not any(
            token in prompt.lower() for token in ("portugues", "português", "pt-br", "brasil")
        ):
            prompt = (
                prompt.rstrip(". ") + ". TODOS os rotulos, titulos, palavras e legendas "
                "DEVEM estar em portugues do Brasil (pt-BR). NAO usar texto em ingles em nenhuma parte da imagem."
            )

    # Confirm the user can write to this project. We reuse the same
    # ownership check the projects routes do — super_admin always passes,
    # otherwise the project must belong to the user's company or be owned
    # by them.
    project = await db.projects.find_one({"id": req.projectId}, {"_id": 0})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    role = (user or {}).get("role")
    if role not in ("super_admin", "admin"):
        # Allow if user owns the project OR shares its company
        if project.get("userId") != user.get("id") and project.get("companyId") != user.get("companyId"):
            raise HTTPException(status_code=403, detail="Forbidden")

    # We pre-resolved `provider` earlier (during language hardening) so we
    # could pick the right prompt strategy. Now branch on it to call the
    # actual generation backend.
    img_bytes: Optional[bytes] = None
    if provider == "krea":
        if not krea_ai.is_configured():
            raise HTTPException(status_code=400, detail="Krea API key not configured. Open admin settings to add KREA_API_KEY.")
        try:
            img_bytes = await _generate_via_krea(prompt, req.kreaModelId or "flux-1-dev", negative_prompt=negative_prompt)
        except KreaUserError as e:
            raise HTTPException(status_code=400, detail=str(e))
        if not img_bytes:
            raise HTTPException(status_code=502, detail="Image generation failed (Krea)")
    else:
        # Default: Gemini Nano Banana via Emergent key. ~3-6s typical.
        img_bytes = await generate_simple_image(prompt)
        if not img_bytes:
            raise HTTPException(status_code=502, detail="Image generation failed (Gemini)")
        provider = "gemini"

    # Deterministic filename keyed on provider + style + prompt + suggestion
    # id keeps re-applies of the same suggestion idempotent (no duplicate
    # gallery clutter). Provider and style are in the seed so switching
    # either produces a different file (so the new image actually shows up).
    seed_src = provider + "|" + style_id + "|" + (req.suggestionId or "") + "|" + prompt
    seed = hashlib.md5(seed_src.encode("utf-8"), usedforsecurity=False).hexdigest()[:10]
    fname = f"density_img_{seed}.jpg"
    fpath = os.path.join(PROJECTS_DIR, req.projectId, "assets", fname)
    os.makedirs(os.path.dirname(fpath), exist_ok=True)
    try:
        with open(fpath, "wb") as f:
            f.write(img_bytes)
    except Exception as e:
        logger.warning(f"[density.generate-image] disk write failed: {e}")

    # Persist to GridFS so it survives container restarts (the K8s preview
    # environment has ephemeral disk).
    try:
        from motor.motor_asyncio import AsyncIOMotorClient
        from routes.deps import mongo_url, db_name
        motor_client = AsyncIOMotorClient(mongo_url)
        _motor_db = motor_client[db_name]
        await store_asset_async(_motor_db, req.projectId, fname, fpath)
    except Exception as e:
        logger.warning(f"[density.generate-image] mongo persist failed: {e}")

    # Optionally persist as a COMPANY brand-library asset so the author can
    # reuse it across other slides and other courses. Requires super_admin
    # (mirrors the manual upload_asset permission). Best-effort: failures
    # here NEVER break the apply flow — the project-level image is already
    # written above and is what the slide actually references.
    company_asset_id: Optional[str] = None
    if req.saveToLibrary and role == "super_admin":
        try:
            from services.asset_store import store_company_asset_async
            from models import CompanyAsset

            company_id = project.get("companyId")
            if company_id:
                # Idempotency: if we already saved THIS exact image to the
                # library (same fname = same provider+style+prompt+suggestionId
                # seed), don't duplicate the meta row. The author would just
                # see two copies of the same image in the library.
                existing = await _motor_db.company_assets_meta.find_one(
                    {"companyId": company_id, "originalFilename": fname},
                    {"_id": 0, "id": 1},
                )
                if existing:
                    company_asset_id = existing.get("id")
                else:
                    asset_id = f"casset_{uuid.uuid4().hex[:12]}"
                    lib_filename = f"{asset_id}.jpg"
                    ok = await store_company_asset_async(_motor_db, company_id, asset_id, lib_filename, fpath)
                    if ok:
                        # Derive metadata from the style and the original prompt
                        # so the brand-library UI can render a useful card.
                        asset_type = STYLE_TO_ASSET_TYPE.get(style_id, "illustration")
                        width = height = None
                        try:
                            from PIL import Image
                            with Image.open(fpath) as im:
                                width, height = im.size
                        except Exception:
                            pass
                        # Description carries the original suggestion prompt
                        # (truncated) so the semantic matcher can rank this
                        # asset for similar future suggestions.
                        src_prompt = (req.imagePrompt or "").strip().replace("\n", " ")
                        description = (
                            f"Imagem gerada via Analise de Densidade ({style_id} / {provider}). "
                            f"Prompt: {src_prompt[:240]}"
                        )
                        meta = CompanyAsset(
                            id=asset_id,
                            companyId=company_id,
                            filename=lib_filename,
                            originalFilename=fname,
                            contentType="image/jpeg",
                            sizeBytes=len(img_bytes),
                            width=width,
                            height=height,
                            type=asset_type,
                            category="content",
                            tags=["ia-densidade", style_id, provider],
                            description=description,
                            createdBy=user.get("id"),
                        ).model_dump()
                        await _motor_db.company_assets_meta.insert_one(meta)
                        company_asset_id = asset_id
                        logger.info(f"[density.generate-image] saved to brand library: {company_id}/{asset_id}")
        except Exception as e:
            logger.warning(f"[density.generate-image] brand-library persist failed: {e}")

    url = f"/api/projects/{req.projectId}/assets/{fname}"
    return {
        "url": url,
        "filename": fname,
        "width": 1200,
        "height": 1200,
        "provider": provider,
        "style": style_id,
        "companyAssetId": company_asset_id,
        "savedToLibrary": bool(company_asset_id),
    }
