"""AI text/image generation routes"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from typing import Optional
import uuid
import os
import io
import logging
import base64
import json

from routes.deps import db, now_utc, serialize_doc, STORAGE_DIR, PROJECTS_DIR, UPLOADS_DIR
from routes.auth import require_auth

logger = logging.getLogger("server")

router = APIRouter(tags=["AI Generation"])


@router.get("/assets/{filename}")
async def serve_global_asset(filename: str):
    """Serve AI-generated images and other global assets from storage/assets/"""
    asset_path = STORAGE_DIR / "assets" / filename
    if asset_path.exists():
        return FileResponse(str(asset_path))
    
    # Fallback: restore from MongoDB (production - disk is ephemeral)
    try:
        doc = await db.project_assets.find_one(
            {"project_id": "global", "filename": filename},
            {"_id": 0, "data": 1, "content_type": 1}
        )
        if doc and doc.get("data"):
            import base64 as b64mod
            decoded_data = b64mod.b64decode(doc["data"])
            content_type = doc.get("content_type", "application/octet-stream")
            # Try to restore to disk for future requests
            try:
                asset_path.parent.mkdir(parents=True, exist_ok=True)
                with open(asset_path, "wb") as f:
                    f.write(decoded_data)
                logger.info(f"Restored global asset from MongoDB: {filename}")
                return FileResponse(str(asset_path))
            except Exception:
                # If disk write fails, stream directly from memory
                from fastapi.responses import Response
                return Response(content=decoded_data, media_type=content_type)
    except Exception as e:
        logger.warning(f"MongoDB fallback failed for global asset {filename}: {e}")
    
    raise HTTPException(status_code=404, detail="Asset not found")


class AITextGenerateRequest(BaseModel):
    prompt: str = Field(min_length=3, max_length=4000)
    context: Optional[str] = Field(default=None, max_length=8000)
    format: str = "html"  # html, plain, markdown


def _text_generation_credentials() -> tuple[str, str]:
    """Use the same OpenAI secret already configured for the Tutor IA."""
    api_key = (
        os.environ.get("OPENAI_API_KEY", "").strip()
        or os.environ.get("EMERGENT_LLM_KEY", "").strip()
    )
    model = (
        os.environ.get("OPENAI_TEXT_MODEL", "").strip()
        or os.environ.get("OPENAI_TUTOR_MODEL", "").strip()
        or "gpt-4o"
    )
    return api_key, model


def _clean_generated_html(value: object) -> str:
    """Remove common Markdown wrappers while preserving the generated HTML."""
    text = str(value or "").strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].strip().lower() in ("```", "```html"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def _friendly_text_generation_error(exc: Exception) -> tuple[int, str]:
    error = str(exc).lower()
    if (
        "insufficient_quota" in error
        or "budget has been exceeded" in error
        or ("billing" in error and "quota" in error)
    ):
        return 503, (
            "O saldo ou limite de uso da conta OpenAI foi atingido. "
            "Verifique Billing e Usage na plataforma OpenAI."
        )
    if "rate limit" in error or "429" in error:
        return 429, (
            "A OpenAI está recebendo muitas solicitações. "
            "Aguarde alguns segundos e tente novamente."
        )
    if "invalid api key" in error or "unauthorized" in error or "401" in error:
        return 503, (
            "A chave OpenAI configurada parece inválida. "
            "Verifique OPENAI_API_KEY no ambiente seguro do Render."
        )
    return 502, (
        "Não foi possível gerar o texto com IA agora. "
        "Tente novamente em alguns instantes."
    )


@router.post("/ai/generate-text")
async def generate_text_with_ai(
    request: AITextGenerateRequest,
    _user: dict = Depends(require_auth),
):
    """Generate formatted educational content with the configured OpenAI key."""

    api_key, model = _text_generation_credentials()
    prompt_text = request.prompt.strip()
    if not prompt_text:
        raise HTTPException(
            status_code=400,
            detail="Descreva o texto que deseja gerar.",
        )
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail=(
                "A geração de texto ainda não possui uma chave OpenAI "
                "configurada. Cadastre OPENAI_API_KEY no backend do Render."
            ),
        )
    
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        
        # System message for text generation
        system_message = """Você é um assistente especializado em criar conteúdo educacional formatado em HTML.

Regras:
1. SEMPRE responda em português brasileiro
2. Use tags HTML para formatação: <h1>, <h2>, <h3>, <p>, <strong>, <em>, <ul>, <ol>, <li>, <table>, <tr>, <td>, <th>
3. Crie conteúdo bem estruturado com títulos, parágrafos e listas quando apropriado
4. Use tabelas para dados comparativos ou estruturados
5. Seja conciso mas informativo
6. NÃO inclua tags <html>, <head> ou <body> - apenas o conteúdo interno
7. NÃO use markdown, apenas HTML puro

Exemplo de resposta formatada:
<h2>Título do Tópico</h2>
<p>Parágrafo introdutório explicando o conceito.</p>
<h3>Subtópico</h3>
<ul>
  <li><strong>Item 1:</strong> Descrição do item</li>
  <li><strong>Item 2:</strong> Descrição do item</li>
</ul>"""

        # Initialize chat with GPT-4o
        chat = LlmChat(
            api_key=api_key,
            session_id=f"text-gen-{uuid.uuid4()}",
            system_message=system_message
        ).with_model("openai", model)
        
        # Build the prompt
        full_prompt = f"Gere conteúdo formatado sobre: {prompt_text}"
        if request.context:
            full_prompt += f"\n\nContexto adicional: {request.context}"
        
        # Send message and get response
        user_message = UserMessage(text=full_prompt)
        response = _clean_generated_html(await chat.send_message(user_message))
        if not response:
            raise RuntimeError("empty response from OpenAI")
        
        logger.info(f"AI text generated successfully for prompt: {request.prompt[:50]}...")
        
        return {
            "success": True,
            "content": response,
            "format": request.format
        }
        
    except HTTPException:
        raise
    except ImportError:
        logger.error("emergentintegrations library not installed")
        raise HTTPException(
            status_code=500,
            detail="A integração de IA não está disponível no servidor.",
        )
    except Exception as e:
        logger.error(f"AI text generation error: {e}")
        status_code, detail = _friendly_text_generation_error(e)
        raise HTTPException(status_code=status_code, detail=detail)


# AI Image Generation Endpoint
class AIImageGenerateRequest(BaseModel):
    prompt: str
    size: str = "1024x1024"  # 1024x1024, 1792x1024, 1024x1792

@router.post("/ai/generate-image")
async def generate_image_with_ai(request: AIImageGenerateRequest):
    """Generate image using AI (GPT Image 1) with optimization"""
    from PIL import Image
    
    emergent_key = os.environ.get('OPENAI_API_KEY', '').strip() or os.environ.get('EMERGENT_LLM_KEY', '').strip()
    if not emergent_key:
        raise HTTPException(status_code=500, detail="AI API key not configured")
    
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage as UM
        
        logger.info(f"Generating image with Gemini Nano Banana, prompt: {request.prompt[:50]}...")
        
        chat = LlmChat(
            api_key=emergent_key,
            session_id=f"img_{uuid.uuid4().hex[:8]}",
            system_message="You are an image generator.",
        ).with_model("gemini", "gemini-3-pro-image-preview").with_params(modalities=["image", "text"])
        
        text_resp, gen_images = await chat.send_message_multimodal_response(UM(text=request.prompt))
        
        if not gen_images or len(gen_images) == 0:
            raise HTTPException(status_code=500, detail="No image was generated")
        
        # Decode base64 image data
        raw_image_data = base64.b64decode(gen_images[0]['data'])
        
        # Optimize the image - convert to JPEG with compression
        original_image = Image.open(io.BytesIO(raw_image_data))
        
        # Convert RGBA to RGB if necessary (JPEG doesn't support transparency)
        if original_image.mode in ('RGBA', 'LA', 'P'):
            # Create white background
            background = Image.new('RGB', original_image.size, (255, 255, 255))
            if original_image.mode == 'P':
                original_image = original_image.convert('RGBA')
            background.paste(original_image, mask=original_image.split()[-1] if original_image.mode == 'RGBA' else None)
            original_image = background
        elif original_image.mode != 'RGB':
            original_image = original_image.convert('RGB')
        
        # Resize if image is too large (max 1200px on longest side for web)
        max_size = 1200
        if max(original_image.size) > max_size:
            ratio = max_size / max(original_image.size)
            new_size = (int(original_image.width * ratio), int(original_image.height * ratio))
            original_image = original_image.resize(new_size, Image.Resampling.LANCZOS)
            logger.info(f"Resized image from original to {new_size}")
        
        # Save as optimized JPEG
        optimized_buffer = io.BytesIO()
        original_image.save(optimized_buffer, format='JPEG', quality=80, optimize=True)
        optimized_data = optimized_buffer.getvalue()
        
        # Log size comparison
        original_size = len(raw_image_data)
        optimized_size = len(optimized_data)
        compression_ratio = (1 - optimized_size / original_size) * 100
        logger.info(f"Image optimized: {original_size/1024:.1f}KB -> {optimized_size/1024:.1f}KB ({compression_ratio:.1f}% reduction)")
        
        # Convert to base64
        image_base64 = base64.b64encode(optimized_data).decode('utf-8')
        
        # Save to storage and return URL
        image_id = str(uuid.uuid4())
        image_filename = f"{image_id}.jpg"  # Changed to .jpg
        
        # Use the general storage assets directory
        assets_dir = STORAGE_DIR / "assets"
        assets_dir.mkdir(exist_ok=True)
        image_path = assets_dir / image_filename
        
        with open(image_path, "wb") as f:
            f.write(optimized_data)
        
        # Also persist to MongoDB for production (disk is ephemeral in containers)
        try:
            await db.project_assets.update_one(
                {"project_id": "global", "filename": image_filename},
                {"$set": {
                    "project_id": "global",
                    "filename": image_filename,
                    "content_type": "image/jpeg",
                    "data": optimized_data,
                }},
                upsert=True
            )
            logger.info(f"AI image persisted to MongoDB: {image_filename}")
        except Exception as e:
            logger.warning(f"Failed to persist AI image to MongoDB (non-fatal): {e}")
        
        logger.info(f"Image generated successfully: {image_filename}")
        
        return {
            "success": True,
            "imageUrl": f"/api/assets/{image_filename}",
            "imageBase64": f"data:image/jpeg;base64,{image_base64}"
        }
        
    except ImportError as e:
        logger.error(f"emergentintegrations library error: {e}")
        raise HTTPException(status_code=500, detail="AI image integration library not available")
    except Exception as e:
        logger.error(f"AI image generation error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate image: {str(e)}")


@router.post("/migrate-asset-urls")
async def migrate_asset_urls():
    """
    Migrate all absolute asset URLs to relative URLs in the database.
    This fixes issues when the domain changes between sessions (e.g., after a fork).
    Handles both global (/api/assets/) and project-specific (/api/projects/{id}/assets/) URLs.
    Also normalizes image element src attributes.
    """
    import re
    
    migrated_count = 0
    projects = await db.projects.find({}).to_list(1000)
    
    for project in projects:
        updated = False
        course = project.get('course', {})
        slides = course.get('slides', [])
        
        for slide in slides:
            elements = slide.get('elements', [])
            for element in elements:
                # Fix HTML elements with embedded image URLs
                if element.get('type') == 'html' and element.get('htmlContent'):
                    html_content = element['htmlContent']
                    
                    # Strip domain from /api/assets/ URLs
                    new_content = re.sub(
                        r'https?://[^/\s"\']+/api/assets/',
                        '/api/assets/',
                        html_content
                    )
                    # Strip domain from /api/projects/ URLs
                    new_content = re.sub(
                        r'https?://[^/\s"\']+/api/projects/',
                        '/api/projects/',
                        new_content
                    )
                    
                    if new_content != html_content:
                        element['htmlContent'] = new_content
                        updated = True
                        migrated_count += 1
                
                # Fix image element src attributes
                src = element.get('src', '')
                if src and src.startswith('http') and '/api/' in src:
                    new_src = re.sub(r'https?://[^/\s"\']+(/api/.*)', r'\1', src)
                    if new_src != src:
                        element['src'] = new_src
                        updated = True
                        migrated_count += 1
            
            # Fix slide background images
            bg = slide.get('backgroundImage', '')
            if bg and bg.startswith('http') and '/api/' in bg:
                new_bg = re.sub(r'https?://[^/\s"\']+(/api/.*)', r'\1', bg)
                if new_bg != bg:
                    slide['backgroundImage'] = new_bg
                    updated = True
                    migrated_count += 1
        
        if updated:
            await db.projects.update_one(
                {'id': project['id']},
                {'$set': {'course': course}}
            )
            logger.info(f"Migrated {migrated_count} URLs in project {project.get('name', project['id'])}")
    
    return {
        "success": True,
        "message": f"Migrated {migrated_count} elements with asset URLs",
        "migrated_count": migrated_count
    }


# ============================================
# Quiz Generator Endpoints
