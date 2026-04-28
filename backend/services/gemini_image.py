"""Helper to generate an image via Gemini Nano Banana (Emergent LLM key).

Used both by the manual /api/ai/generate-image endpoint and by the agent's
"imagem_simples" improvement type. Returns optimized JPEG bytes.
"""
import os
import io
import base64
import uuid
import logging
from typing import Optional

logger = logging.getLogger("server")


async def generate_simple_image(prompt: str) -> Optional[bytes]:
    """Generate an image via Gemini Nano Banana and return optimized JPEG bytes.

    Returns None on failure (caller should log + skip).
    """
    emergent_key = os.environ.get("EMERGENT_LLM_KEY")
    if not emergent_key:
        logger.warning("[gemini-image] EMERGENT_LLM_KEY not set")
        return None

    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage as UM
        from PIL import Image

        chat = (
            LlmChat(
                api_key=emergent_key,
                session_id=f"img_{uuid.uuid4().hex[:8]}",
                system_message="You are an image generator.",
            )
            .with_model("gemini", "gemini-3-pro-image-preview")
            .with_params(modalities=["image", "text"])
        )

        _, gen_images = await chat.send_message_multimodal_response(UM(text=prompt))
        if not gen_images:
            logger.warning("[gemini-image] No image returned")
            return None

        raw = base64.b64decode(gen_images[0]["data"])
        img = Image.open(io.BytesIO(raw))

        # Convert RGBA -> RGB so JPEG works
        if img.mode in ("RGBA", "LA", "P"):
            bg = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode == "P":
                img = img.convert("RGBA")
            bg.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
            img = bg
        elif img.mode != "RGB":
            img = img.convert("RGB")

        # Cap dimensions
        if max(img.size) > 1200:
            ratio = 1200 / max(img.size)
            img = img.resize(
                (int(img.width * ratio), int(img.height * ratio)),
                Image.Resampling.LANCZOS,
            )

        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=80, optimize=True)
        return buf.getvalue()
    except Exception as e:
        logger.error(f"[gemini-image] generation failed: {e}")
        return None
