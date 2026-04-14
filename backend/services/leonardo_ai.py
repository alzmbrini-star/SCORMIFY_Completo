"""Leonardo AI image generation service for Scormify."""

import os
import httpx
import asyncio
import logging
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)

LEONARDO_API_KEY = os.environ.get("LEONARDO_API_KEY", "")
LEONARDO_BASE_URL = "https://cloud.leonardo.ai/api/rest/v1"

# Phoenix 1.0 model - high quality
DEFAULT_MODEL_ID = "de7d3faf-762f-48e0-b3b7-9d0ac3a3fcf3"


def _headers():
    return {
        "accept": "application/json",
        "content-type": "application/json",
        "authorization": f"Bearer {LEONARDO_API_KEY}",
    }


async def generate_image(
    prompt: str,
    width: int = 1024,
    height: int = 576,
    num_images: int = 1,
    model_id: str = None,
    style: str = None,
) -> dict:
    """Submit an image generation request to Leonardo AI.
    Returns generation_id for polling."""
    if not LEONARDO_API_KEY:
        raise ValueError("LEONARDO_API_KEY not configured")

    payload = {
        "prompt": prompt,
        "width": width,
        "height": height,
        "num_images": num_images,
        "modelId": model_id or DEFAULT_MODEL_ID,
        "alchemy": True,
    }

    if style:
        payload["presetStyle"] = style

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{LEONARDO_BASE_URL}/generations",
            headers=_headers(),
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()

    gen_id = data.get("sdGenerationJob", {}).get("generationId")
    if not gen_id:
        raise ValueError(f"No generationId returned: {data}")

    logger.info(f"Leonardo generation started: {gen_id}")
    return {"generationId": gen_id, "status": "pending"}


async def poll_generation(generation_id: str, max_wait: int = 120) -> dict:
    """Poll for generation completion. Returns list of image URLs."""
    elapsed = 0
    interval = 5

    async with httpx.AsyncClient(timeout=30) as client:
        while elapsed < max_wait:
            resp = await client.get(
                f"{LEONARDO_BASE_URL}/generations/{generation_id}",
                headers=_headers(),
            )
            resp.raise_for_status()
            data = resp.json()

            gen = data.get("generations_by_pk", {})
            status = gen.get("status")

            if status == "COMPLETE":
                images = gen.get("generated_images", [])
                urls = [img.get("url") for img in images if img.get("url")]
                logger.info(f"Leonardo generation {generation_id} complete: {len(urls)} images")
                return {"status": "complete", "images": urls, "generationId": generation_id}

            if status == "FAILED":
                logger.error(f"Leonardo generation {generation_id} failed")
                return {"status": "failed", "images": [], "generationId": generation_id}

            await asyncio.sleep(interval)
            elapsed += interval

    return {"status": "timeout", "images": [], "generationId": generation_id}


async def generate_and_wait(
    prompt: str,
    width: int = 1024,
    height: int = 576,
    num_images: int = 1,
    model_id: str = None,
    style: str = None,
) -> list:
    """Generate image and wait for completion. Returns list of image URLs."""
    result = await generate_image(prompt, width, height, num_images, model_id, style)
    gen_id = result["generationId"]
    poll_result = await poll_generation(gen_id)

    if poll_result["status"] == "complete":
        return poll_result["images"]
    return []


async def download_image_to_disk(image_url: str, dest_path: str) -> bool:
    """Download a Leonardo image to local disk."""
    try:
        async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
            resp = await client.get(image_url)
            resp.raise_for_status()
            Path(dest_path).parent.mkdir(parents=True, exist_ok=True)
            with open(dest_path, "wb") as f:
                f.write(resp.content)
            return True
    except Exception as e:
        logger.error(f"Failed to download Leonardo image: {e}")
        return False
