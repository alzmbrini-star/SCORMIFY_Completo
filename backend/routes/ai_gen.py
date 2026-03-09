"""AI text/image generation routes"""
from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
import uuid
import os
import io
import logging
import base64
import json

from routes.deps import db, now_utc, serialize_doc, STORAGE_DIR, PROJECTS_DIR, UPLOADS_DIR

logger = logging.getLogger("server")

router = APIRouter(tags=["AI Generation"])


@router.get("/assets/{filename}")
async def serve_global_asset(filename: str):
    """Serve AI-generated images and other global assets from storage/assets/"""
    asset_path = STORAGE_DIR / "assets" / filename
    if not asset_path.exists():
        raise HTTPException(status_code=404, detail="Asset not found")
    return FileResponse(str(asset_path))


class AITextGenerateRequest(BaseModel):
    prompt: str
    context: Optional[str] = None
    format: str = "html"  # html, plain, markdown

@router.post("/ai/generate-text")
async def generate_text_with_ai(request: AITextGenerateRequest):
    """Generate formatted text content using AI (GPT-4o)"""
    
    emergent_key = os.environ.get('EMERGENT_LLM_KEY')
    if not emergent_key:
        raise HTTPException(status_code=500, detail="AI API key not configured")
    
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
            api_key=emergent_key,
            session_id=f"text-gen-{uuid.uuid4()}",
            system_message=system_message
        ).with_model("openai", "gpt-4o")
        
        # Build the prompt
        full_prompt = f"Gere conteúdo formatado sobre: {request.prompt}"
        if request.context:
            full_prompt += f"\n\nContexto adicional: {request.context}"
        
        # Send message and get response
        user_message = UserMessage(text=full_prompt)
        response = await chat.send_message(user_message)
        
        logger.info(f"AI text generated successfully for prompt: {request.prompt[:50]}...")
        
        return {
            "success": True,
            "content": response,
            "format": request.format
        }
        
    except ImportError:
        logger.error("emergentintegrations library not installed")
        raise HTTPException(status_code=500, detail="AI integration library not available")
    except Exception as e:
        logger.error(f"AI text generation error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate text: {str(e)}")


# AI Image Generation Endpoint
class AIImageGenerateRequest(BaseModel):
    prompt: str
    size: str = "1024x1024"  # 1024x1024, 1792x1024, 1024x1792

@router.post("/ai/generate-image")
async def generate_image_with_ai(request: AIImageGenerateRequest):
    """Generate image using AI (GPT Image 1) with optimization"""
    import base64
    from PIL import Image
    import io
    
    emergent_key = os.environ.get('EMERGENT_LLM_KEY')
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
