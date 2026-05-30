"""Krea AI image generation service.

Krea AI offers a REST API with 40+ image/video/enhancement models.
Auth: `Authorization: Bearer <api_id>:<api_secret>` (concatenated with colon).

Job lifecycle: `scheduled` → `processing` → `completed` (or `failed`/`cancelled`).
Polling: GET /jobs/{job_id} every 2-5 seconds.

Docs: https://docs.krea.ai/api-reference/introduction
"""
from __future__ import annotations

import os
import logging
from typing import Optional, Dict, Any, List

import httpx

logger = logging.getLogger(__name__)

KREA_BASE_URL = "https://api.krea.ai"
# Env var is loaded lazily (each call) so admin settings overrides work.

# Curated model catalog — shown in the Editor's "Generate Image" picker.
# Each entry: path (used in POST /generate/image/{path}) + display metadata.
# The `path` matches the Krea endpoint segment (`provider/model-slug`).
KREA_IMAGE_MODELS: List[Dict[str, Any]] = [
    {
        "id": "krea-1",
        "path": "krea/krea-1",
        "label": "Krea 1 (flagship)",
        "description": "Krea's own flagship model, 4 images per prompt, native 4K",
        "maxWidth": 4096,
        "maxHeight": 4096,
        "defaultSteps": 30,
        "approxCostUSD": 0.08,
        "approxTimeSeconds": 25,
        "tier": "premium",
    },
    {
        "id": "flux-1-dev",
        "path": "bfl/flux-1-dev",
        "label": "Flux 1 Dev (fast)",
        "description": "Fast, balanced image generation — 4 seconds, great for iteration",
        "maxWidth": 1920,
        "maxHeight": 1920,
        "defaultSteps": 28,
        "approxCostUSD": 0.04,
        "approxTimeSeconds": 4,
        "tier": "standard",
        # textRendering: how reliably the model can draw legible words.
        #   "poor" → produces gibberish for non-English words; we must
        #            strip text instructions from the prompt and force
        #            icon-only visuals.
        #   "good" → renders short labels reliably, even in pt-BR.
        #   "excellent" → typography-specialized models (Ideogram, Imagen)
        #            can do paragraphs.
        "textRendering": "poor",
    },
    {
        "id": "flux-1.1-pro",
        "path": "bfl/flux-1.1-pro",
        "label": "Flux 1.1 Pro (photorealistic)",
        "description": "Professional photorealistic quality, excellent for product shots",
        "maxWidth": 1920,
        "maxHeight": 1920,
        "defaultSteps": 28,
        "approxCostUSD": 0.06,
        "approxTimeSeconds": 11,
        "tier": "premium",
        "textRendering": "poor",
    },
    {
        "id": "flux-kontext",
        "path": "bfl/flux-kontext",
        "label": "Flux Kontext (context-aware)",
        "description": "Understands context — ideal for continuing a visual style",
        "maxWidth": 1920,
        "maxHeight": 1920,
        "defaultSteps": 28,
        "approxCostUSD": 0.04,
        "approxTimeSeconds": 5,
        "tier": "standard",
        "textRendering": "poor",
    },
    {
        "id": "imagen-4",
        "path": "google/imagen-4",
        "label": "Imagen 4 (Google)",
        "description": "Google's flagship — excellent text rendering in images",
        "maxWidth": 2048,
        "maxHeight": 2048,
        "defaultSteps": 30,
        "approxCostUSD": 0.04,
        "approxTimeSeconds": 32,
        "tier": "premium",
        "textRendering": "excellent",
    },
    {
        "id": "imagen-4-ultra",
        "path": "google/imagen-4-ultra",
        "label": "Imagen 4 Ultra",
        "description": "Google's top-tier for editorial photography",
        "maxWidth": 2048,
        "maxHeight": 2048,
        "defaultSteps": 30,
        "approxCostUSD": 0.06,
        "approxTimeSeconds": 30,
        "tier": "premium",
        "textRendering": "excellent",
    },
    {
        "id": "nano-banana-2",
        "path": "google/nano-banana-2",
        "label": "Nano Banana 2 (Gemini)",
        "description": "Gemini's image model — fast iterative edits",
        "maxWidth": 1920,
        "maxHeight": 1920,
        "defaultSteps": 20,
        "approxCostUSD": 0.06,
        "approxTimeSeconds": 15,
        "tier": "standard",
        "textRendering": "good",
    },
    {
        "id": "nano-banana-pro",
        "path": "google/nano-banana-pro",
        "label": "Nano Banana Pro",
        "description": "Higher fidelity Gemini image variant",
        "maxWidth": 2048,
        "maxHeight": 2048,
        "defaultSteps": 25,
        "approxCostUSD": 0.15,
        "approxTimeSeconds": 30,
        "tier": "premium",
        "textRendering": "good",
    },
    {
        "id": "chatgpt-image",
        "path": "openai/chatgpt-image",
        "label": "ChatGPT Image (GPT-Image-1)",
        "description": "OpenAI's image model from ChatGPT",
        "maxWidth": 1792,
        "maxHeight": 1792,
        "defaultSteps": 30,
        "approxCostUSD": 0.04,
        "approxTimeSeconds": 60,
        "tier": "standard",
        "textRendering": "good",
    },
    {
        "id": "seedream-5-lite",
        "path": "bytedance/seedream-5-lite",
        "label": "Seedream 5 Lite (ByteDance)",
        "description": "Fast Asian-style image generation",
        "maxWidth": 1920,
        "maxHeight": 1920,
        "defaultSteps": 25,
        "approxCostUSD": 0.04,
        "approxTimeSeconds": 20,
        "tier": "standard",
        "textRendering": "poor",
    },
    {
        "id": "ideogram-3.0",
        "path": "ideogram/ideogram-3.0",
        "label": "Ideogram 3.0 (typography)",
        "description": "Best-in-class for images with readable text",
        "maxWidth": 1920,
        "maxHeight": 1920,
        "defaultSteps": 25,
        "approxCostUSD": 0.06,
        "approxTimeSeconds": 18,
        "tier": "standard",
        "textRendering": "excellent",
    },
]


def get_model(model_id: str) -> Optional[Dict[str, Any]]:
    """Look up a Krea model config by id. Returns None when unknown."""
    for m in KREA_IMAGE_MODELS:
        if m["id"] == model_id:
            return m
    return None


def get_api_key() -> str:
    """Lazy-load API key — allows hot-reload after admin updates.

    Defensive sanitizer (2026-02): strip wrapper quotes/whitespace because
    secrets persisted via the Super Admin UI sometimes land in .env with
    surrounding double quotes — which then carry into the Authorization
    header and trip 403/401 from the upstream provider."""
    raw = os.environ.get("KREA_API_KEY", "").strip()
    if len(raw) >= 2 and ((raw[0] == '"' and raw[-1] == '"') or (raw[0] == "'" and raw[-1] == "'")):
        raw = raw[1:-1].strip()
    return raw


def is_configured() -> bool:
    return bool(get_api_key())


def _auth_headers() -> Dict[str, str]:
    key = get_api_key()
    if not key:
        raise ValueError("KREA_API_KEY not configured")
    return {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


def get_model_meta(model_id: str) -> Optional[Dict[str, Any]]:
    for m in KREA_IMAGE_MODELS:
        if m["id"] == model_id:
            return m
    return None


async def submit_generation(
    model_id: str,
    prompt: str,
    width: int = 1024,
    height: int = 576,
    steps: Optional[int] = None,
    negative_prompt: Optional[str] = None,
    webhook_url: Optional[str] = None,
) -> Dict[str, Any]:
    """Submit a Krea image generation job and return job metadata.

    Returns: {job_id, status, created_at, type, ...}
    Raises: ValueError (bad config), httpx.HTTPStatusError (API error).
    """
    meta = get_model_meta(model_id)
    if not meta:
        raise ValueError(f"Unknown Krea model: {model_id}")
    # Clamp dimensions to model-specific max
    width = max(256, min(int(width), meta.get("maxWidth", 1920)))
    height = max(256, min(int(height), meta.get("maxHeight", 1920)))
    payload: Dict[str, Any] = {
        "prompt": prompt,
        "width": width,
        "height": height,
        "steps": int(steps or meta.get("defaultSteps", 28)),
    }
    if negative_prompt:
        payload["negative_prompt"] = negative_prompt
    headers = _auth_headers()
    if webhook_url:
        headers["X-Webhook-URL"] = webhook_url
    url = f"{KREA_BASE_URL}/generate/image/{meta['path']}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
    logger.info(f"Krea job submitted: {data.get('job_id')} ({model_id})")
    return data


async def get_job(job_id: str) -> Dict[str, Any]:
    """Poll a Krea job's status."""
    headers = _auth_headers()
    url = f"{KREA_BASE_URL}/jobs/{job_id}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url, headers=headers)
        response.raise_for_status()
        return response.json()


async def download_image_bytes(url: str) -> bytes:
    """Download a completed image URL (no auth — URLs are pre-signed)."""
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.get(url)
        r.raise_for_status()
        return r.content
