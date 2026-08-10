"""OpenAI image generation shared by Editor visual-improvement flows."""

from __future__ import annotations

import base64
import io
import logging
import os
from typing import Optional

from services.llm_config import openai_api_key

logger = logging.getLogger(__name__)


async def generate_openai_image(prompt: str) -> Optional[bytes]:
    """Generate an image and normalize it to an optimized RGB JPEG."""
    key = openai_api_key(allow_legacy=False)
    if not key:
        logger.warning("[openai-image] OPENAI_API_KEY not set")
        return None

    try:
        import httpx
        from openai import AsyncOpenAI
        from PIL import Image

        model = os.environ.get("OPENAI_IMAGE_MODEL", "gpt-image-2").strip() or "gpt-image-2"
        client = AsyncOpenAI(
            api_key=key,
            timeout=float(os.environ.get("OPENAI_IMAGE_TIMEOUT_SECONDS", "180")),
            max_retries=2,
        )
        result = await client.images.generate(
            model=model,
            prompt=prompt,
            size=os.environ.get("OPENAI_IMAGE_SIZE", "1536x1024"),
            quality=os.environ.get("OPENAI_IMAGE_QUALITY", "medium"),
            n=1,
        )
        items = getattr(result, "data", None) or []
        if not items:
            raise RuntimeError("OpenAI returned no image data")

        item = items[0]
        encoded = getattr(item, "b64_json", None)
        if encoded:
            raw = base64.b64decode(encoded)
        else:
            url = getattr(item, "url", None)
            if not url:
                raise RuntimeError("OpenAI returned neither b64_json nor URL")
            async with httpx.AsyncClient(timeout=60) as http:
                response = await http.get(url)
                response.raise_for_status()
                raw = response.content

        image = Image.open(io.BytesIO(raw))
        if image.mode in ("RGBA", "LA", "P"):
            if image.mode == "P":
                image = image.convert("RGBA")
            background = Image.new("RGB", image.size, (255, 255, 255))
            background.paste(image, mask=image.split()[-1] if image.mode == "RGBA" else None)
            image = background
        elif image.mode != "RGB":
            image = image.convert("RGB")

        if max(image.size) > 1600:
            ratio = 1600 / max(image.size)
            image = image.resize(
                (round(image.width * ratio), round(image.height * ratio)),
                Image.Resampling.LANCZOS,
            )
        output = io.BytesIO()
        image.save(output, format="JPEG", quality=88, optimize=True)
        return output.getvalue()
    except Exception as exc:
        logger.exception("[openai-image] generation failed: %s", exc)
        return None
