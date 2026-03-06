"""HeyGen avatar video generation routes"""
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
import httpx
import asyncio
import os
import uuid
import logging

from routes.deps import (
    db, now_utc, HEYGEN_API_KEY, HEYGEN_BASE_URL, HEYGEN_HEADERS,
    heygen_credits_cache, heygen_sse_subscribers, PROJECTS_DIR, STORAGE_DIR,
    get_project_by_id
)
from routes.auth import require_agent_access, get_current_user
import base64
import re

logger = logging.getLogger("server")

router = APIRouter(tags=["HeyGen"])


@router.get("/heygen/avatars")
async def list_heygen_avatars(limit: int = 200, gender: Optional[str] = None):
    """List available HeyGen avatars with optional gender filter"""
    if not HEYGEN_API_KEY:
        raise HTTPException(status_code=500, detail="HeyGen API key not configured")
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as http_client:
            response = await http_client.get(
                f"{HEYGEN_BASE_URL}/v2/avatars",
                headers=HEYGEN_HEADERS
            )
            
            if response.status_code != 200:
                logger.error(f"HeyGen avatars error: {response.status_code} - {response.text}")
                raise HTTPException(status_code=response.status_code, detail="Failed to fetch avatars from HeyGen")
            
            data = response.json()
            avatars = data.get("data", {}).get("avatars", [])
            
            # Filter by gender if specified
            if gender and gender.lower() != 'all':
                avatars = [a for a in avatars if a.get("gender", "").lower() == gender.lower()]
            
            # Format avatars for frontend
            formatted_avatars = []
            for avatar in avatars[:limit]:
                formatted_avatars.append({
                    "avatar_id": avatar.get("avatar_id"),
                    "avatar_name": avatar.get("avatar_name"),
                    "preview_image_url": avatar.get("preview_image_url"),
                    "preview_video_url": avatar.get("preview_video_url"),
                    "gender": avatar.get("gender"),
                })
            
            # Get unique genders for filter options
            all_genders = list(set(a.get("gender", "unknown") for a in data.get("data", {}).get("avatars", []) if a.get("gender")))
            
            return {
                "avatars": formatted_avatars, 
                "total": len(avatars),
                "available_genders": sorted(all_genders)
            }
    except httpx.RequestError as e:
        logger.error(f"HeyGen request error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to connect to HeyGen: {str(e)}")

@router.get("/heygen/voices")
async def list_heygen_voices(language: Optional[str] = None, gender: Optional[str] = None):
    """List available HeyGen voices with optional language and gender filters"""
    if not HEYGEN_API_KEY:
        raise HTTPException(status_code=500, detail="HeyGen API key not configured")
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as http_client:
            response = await http_client.get(
                f"{HEYGEN_BASE_URL}/v2/voices",
                headers=HEYGEN_HEADERS
            )
            
            if response.status_code != 200:
                logger.error(f"HeyGen voices error: {response.status_code} - {response.text}")
                raise HTTPException(status_code=response.status_code, detail="Failed to fetch voices from HeyGen")
            
            data = response.json()
            all_voices = data.get("data", {}).get("voices", [])
            voices = all_voices.copy()
            
            # Filter by language if specified
            if language and language.lower() != 'all':
                # Support specific language codes like "pt-BR", "pt-PT", "en-US"
                if '-' in language:
                    # Exact match for language code
                    voices = [v for v in voices if v.get("language", "").lower() == language.lower()]
                else:
                    # Partial match (e.g., "portuguese" matches "Portuguese (Brazil)")
                    voices = [v for v in voices if language.lower() in v.get("language", "").lower()]
            
            # Filter by gender if specified
            if gender and gender.lower() != 'all':
                voices = [v for v in voices if v.get("gender", "").lower() == gender.lower()]
            
            # Format voices for frontend
            formatted_voices = []
            for voice in voices:
                lang = voice.get("language", "")
                voice_name = voice.get("name", "")
                # Determine language code and country
                lang_code = ""
                country_flag = ""
                
                # Check if Portuguese and determine variant
                if "portuguese" in lang.lower():
                    # Check voice name for Brazil indicators
                    if "brazil" in voice_name.lower() or "brasil" in voice_name.lower():
                        lang_code = "pt-BR"
                        country_flag = "🇧🇷"
                    elif "portugal" in voice_name.lower():
                        lang_code = "pt-PT"
                        country_flag = "🇵🇹"
                    else:
                        # Default Portuguese to Brazil (most common in LatAm)
                        lang_code = "pt"
                        country_flag = "🇧🇷"
                elif "brazil" in lang.lower() or "brasileiro" in lang.lower():
                    lang_code = "pt-BR"
                    country_flag = "🇧🇷"
                elif "portugal" in lang.lower() or "português" in lang.lower():
                    lang_code = "pt-PT"
                    country_flag = "🇵🇹"
                elif "english" in lang.lower():
                    if "us" in lang.lower() or "american" in lang.lower():
                        lang_code = "en-US"
                        country_flag = "🇺🇸"
                    elif "uk" in lang.lower() or "british" in lang.lower():
                        lang_code = "en-GB"
                        country_flag = "🇬🇧"
                    else:
                        lang_code = "en"
                        country_flag = "🇺🇸"
                elif "spanish" in lang.lower() or "español" in lang.lower():
                    lang_code = "es"
                    country_flag = "🇪🇸"
                elif "french" in lang.lower():
                    lang_code = "fr"
                    country_flag = "🇫🇷"
                elif "german" in lang.lower():
                    lang_code = "de"
                    country_flag = "🇩🇪"
                elif "italian" in lang.lower():
                    lang_code = "it"
                    country_flag = "🇮🇹"
                
                formatted_voices.append({
                    "voice_id": voice.get("voice_id"),
                    "name": voice_name,
                    "language": lang,
                    "language_code": lang_code,
                    "country_flag": country_flag,
                    "gender": voice.get("gender"),
                    "preview_audio": voice.get("preview_audio"),
                    "support_pause": voice.get("support_pause", False),
                })
            
            # Get unique languages for filter options
            language_options = []
            seen_languages = set()
            for v in all_voices:
                lang = v.get("language", "")
                if lang and lang not in seen_languages:
                    seen_languages.add(lang)
                    # Create a simplified label
                    if "brazil" in lang.lower():
                        language_options.append({"value": lang, "label": "🇧🇷 Português (Brasil)", "code": "pt-BR"})
                    elif "portugal" in lang.lower():
                        language_options.append({"value": lang, "label": "🇵🇹 Português (Portugal)", "code": "pt-PT"})
                    elif "english" in lang.lower():
                        if "us" in lang.lower() or "american" in lang.lower():
                            language_options.append({"value": lang, "label": "🇺🇸 English (US)", "code": "en-US"})
                        elif "uk" in lang.lower() or "british" in lang.lower():
                            language_options.append({"value": lang, "label": "🇬🇧 English (UK)", "code": "en-GB"})
                        else:
                            language_options.append({"value": lang, "label": "🇺🇸 English", "code": "en"})
                    elif "spanish" in lang.lower():
                        language_options.append({"value": lang, "label": "🇪🇸 Español", "code": "es"})
                    elif "french" in lang.lower():
                        language_options.append({"value": lang, "label": "🇫🇷 Français", "code": "fr"})
                    elif "german" in lang.lower():
                        language_options.append({"value": lang, "label": "🇩🇪 Deutsch", "code": "de"})
                    elif "italian" in lang.lower():
                        language_options.append({"value": lang, "label": "🇮🇹 Italiano", "code": "it"})
                    else:
                        language_options.append({"value": lang, "label": lang, "code": ""})
            
            # Sort by label
            language_options.sort(key=lambda x: x["label"])
            
            # Get unique genders
            available_genders = list(set(v.get("gender", "unknown") for v in all_voices if v.get("gender")))
            
            return {
                "voices": formatted_voices,
                "total": len(voices),
                "available_languages": language_options,
                "available_genders": sorted(available_genders)
            }
    except httpx.RequestError as e:
        logger.error(f"HeyGen request error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to connect to HeyGen: {str(e)}")


class HeyGenVideoRequest(BaseModel):
    avatar_id: str
    voice_id: str
    script: str
    title: Optional[str] = "Generated Video"
    aspect_ratio: Optional[str] = "16:9"
    transparent_background: Optional[bool] = True  # Default to transparent
    project_id: Optional[str] = None  # Associate video with a project

@router.post("/heygen/generate-video")
async def generate_heygen_video(request: HeyGenVideoRequest):
    """Generate a video using HeyGen API"""
    if not HEYGEN_API_KEY:
        raise HTTPException(status_code=500, detail="HeyGen API key not configured")
    
    if len(request.script) > 5000:
        raise HTTPException(status_code=400, detail="Script exceeds 5000 character limit")
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as http_client:
            
            # For transparent background, try the WebM endpoint first (v1/video.webm)
            if request.transparent_background:
                payload = {
                    "avatar_pose_id": request.avatar_id,
                    "avatar_style": "normal",
                    "input_text": request.script,
                    "voice_id": request.voice_id,
                    "dimension": {
                        "width": 1280 if request.aspect_ratio == "16:9" else 720,
                        "height": 720 if request.aspect_ratio == "16:9" else 1280
                    }
                }
                
                response = await http_client.post(
                    f"{HEYGEN_BASE_URL}/v1/video.webm",
                    headers=HEYGEN_HEADERS,
                    json=payload
                )
                
                # If WebM endpoint fails (avatar not supported), fall back to standard endpoint
                if response.status_code != 200:
                    error_data = response.json()
                    error_code = error_data.get("data", {}).get("error", {}).get("code", "")
                    
                    # Check if it's an avatar compatibility issue
                    if "AVATAR_NOT_FOUND" in str(error_code) or "avatar" in str(error_data).lower():
                        logger.warning("Avatar not compatible with WebM, falling back to standard video")
                        # Fall back to standard endpoint without transparent background
                        request.transparent_background = False
                    else:
                        logger.error(f"HeyGen WebM error: {response.status_code} - {response.text}")
                        error_msg = error_data.get("error", {}).get("message", "")
                        if not error_msg:
                            error_msg = error_data.get("data", {}).get("error", {}).get("message", response.text)
                        raise HTTPException(status_code=response.status_code, detail=f"HeyGen error: {error_msg}")
            
            # Standard video (either requested or fallback from WebM)
            if not request.transparent_background:
                payload = {
                    "video_inputs": [
                        {
                            "character": {
                                "type": "avatar",
                                "avatar_id": request.avatar_id,
                                "avatar_style": "normal"
                            },
                            "voice": {
                                "type": "text",
                                "input_text": request.script,
                                "voice_id": request.voice_id
                            }
                        }
                    ],
                    "dimension": {
                        "width": 1280 if request.aspect_ratio == "16:9" else 720,
                        "height": 720 if request.aspect_ratio == "16:9" else 1280
                    },
                    "title": request.title
                }
                
                response = await http_client.post(
                    f"{HEYGEN_BASE_URL}/v2/video/generate",
                    headers=HEYGEN_HEADERS,
                    json=payload
                )
            
            if response.status_code != 200:
                logger.error(f"HeyGen generate error: {response.status_code} - {response.text}")
                error_data = response.json()
                error_msg = error_data.get("error", {}).get("message", "")
                if not error_msg:
                    error_msg = error_data.get("data", {}).get("error", {}).get("message", response.text)
                raise HTTPException(status_code=response.status_code, detail=f"HeyGen error: {error_msg}")
            
            data = response.json()
            video_id = data.get("data", {}).get("video_id")
            
            if not video_id:
                raise HTTPException(status_code=500, detail="No video ID returned from HeyGen")
            
            # Store video generation request in database
            await db.heygen_videos.insert_one({
                "video_id": video_id,
                "avatar_id": request.avatar_id,
                "voice_id": request.voice_id,
                "script": request.script,
                "title": request.title,
                "status": "processing",
                "transparent": request.transparent_background,
                "project_id": request.project_id,
                "created_at": now_utc()
            })
            
            return {
                "video_id": video_id,
                "status": "processing",
                "message": "Video generation started. Poll status endpoint for updates."
            }
    except httpx.RequestError as e:
        logger.error(f"HeyGen request error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to connect to HeyGen: {str(e)}")

# AI Script Generation (lazy imports for fast startup)

class GenerateScriptRequest(BaseModel):
    topic: str
    style: Optional[str] = "educational"  # educational, conversational, formal, friendly
    duration: Optional[str] = "medium"  # short (30s), medium (1-2min), long (3-5min)
    language: Optional[str] = "português brasileiro"

@router.post("/ai/generate-script")
async def generate_ai_script(request: GenerateScriptRequest):
    """Generate a video script using AI"""
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    emergent_key = os.environ.get('EMERGENT_LLM_KEY', '')
    
    if not emergent_key:
        raise HTTPException(status_code=500, detail="AI key not configured")
    
    # Define duration guidelines
    duration_guide = {
        "short": "30 segundos a 1 minuto (aproximadamente 75-150 palavras)",
        "medium": "1 a 2 minutos (aproximadamente 150-300 palavras)",
        "long": "3 a 5 minutos (aproximadamente 450-750 palavras)"
    }
    
    style_guide = {
        "educational": "tom educativo e didático, explicando conceitos de forma clara",
        "conversational": "tom conversacional e descontraído, como se estivesse falando com um amigo",
        "formal": "tom formal e profissional, adequado para ambientes corporativos",
        "friendly": "tom amigável e acolhedor, criando conexão com o espectador"
    }
    
    try:
        chat = LlmChat(
            api_key=emergent_key,
            session_id=f"script-gen-{uuid.uuid4()}",
            system_message=f"""Você é um roteirista profissional especializado em criar scripts para vídeos com avatares de IA.

Suas diretrizes:
1. Escreva em {request.language}
2. Use {style_guide.get(request.style, style_guide['educational'])}
3. O script deve ter {duration_guide.get(request.duration, duration_guide['medium'])}
4. Escreva de forma natural e fluida, como se fosse uma pessoa real falando
5. Use pausas naturais (vírgulas, pontos) para dar ritmo ao texto
6. Evite jargões técnicos complexos, a menos que sejam explicados
7. Comece com uma saudação ou gancho que prenda a atenção
8. Termine com uma conclusão clara ou call-to-action

IMPORTANTE: Retorne APENAS o script, sem títulos, numeração de cenas ou instruções de direção."""
        ).with_model("openai", "gpt-4o")
        
        user_message = UserMessage(
            text=f"Crie um script de vídeo sobre o seguinte tema:\n\n{request.topic}"
        )
        
        response = await chat.send_message(user_message)
        
        return {
            "script": response,
            "topic": request.topic,
            "style": request.style,
            "duration": request.duration,
            "language": request.language
        }
    except Exception as e:
        logger.error(f"AI script generation error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate script: {str(e)}")

class GenerateNarrationRequest(BaseModel):
    slide_content: Optional[str] = ""
    style: Optional[str] = "educational"
    language: Optional[str] = "português brasileiro"

@router.post("/projects/{project_id}/slides/{slide_id}/generate-narration")
async def generate_slide_narration(project_id: str, slide_id: str, request: GenerateNarrationRequest):
    """Generate 3 narration text options for a slide using Gemini 3 with vision (OCR for images)"""
    from emergentintegrations.llm.chat import LlmChat, UserMessage, FileContent
    emergent_key = os.environ.get('EMERGENT_LLM_KEY', '')
    if not emergent_key:
        raise HTTPException(status_code=500, detail="AI key not configured")

    project = await get_project_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    course = project.get('course', {})
    slides = course.get('slides', [])
    slide = next((s for s in slides if s.get('id') == slide_id), None)
    if not slide:
        raise HTTPException(status_code=404, detail="Slide not found")

    # Collect text content and images from the slide
    text_parts = []
    image_files = []  # list of FileContent for Gemini vision

    # Check for backgroundImage (PPT-imported slides store full slide as image)
    bg_image = slide.get('backgroundImage', '')
    if bg_image and bg_image.startswith('/api/projects/'):
        # Extract file path from URL: /api/projects/{id}/assets/{filename}
        parts = bg_image.split('/assets/')
        if len(parts) == 2:
            local_path = PROJECTS_DIR / project_id / "assets" / parts[1]
            if local_path.exists():
                try:
                    img_data = local_path.read_bytes()
                    ext = local_path.suffix.lower()
                    mime = 'image/png' if ext == '.png' else 'image/jpeg'
                    image_files.append(FileContent(
                        content_type=mime,
                        file_content_base64=base64.b64encode(img_data).decode('utf-8')
                    ))
                    logger.info(f"Loaded background image for vision: {local_path.name}")
                except Exception as e:
                    logger.warning(f"Failed to load background image: {e}")

    # Extract content from elements
    for element in slide.get('elements', []):
        el_type = element.get('type', '')
        # Check both 'content' and 'htmlContent' fields (htmlContent is used by rich text editor)
        raw_content = element.get('content') or element.get('htmlContent') or ''
        if el_type in ('text', 'html') and raw_content:
            # Extract text from HTML
            clean = re.sub(r'<[^>]+>', '', raw_content)
            if clean.strip():
                text_parts.append(clean.strip())
            # Also check for inline images in htmlContent (RTF editor embeds images)
            img_matches = re.findall(r'src="(/api/[^"]+)"', raw_content)
            for img_src in img_matches:
                if img_src.startswith('/api/projects/'):
                    parts = img_src.split('/assets/')
                    if len(parts) == 2:
                        local_path = PROJECTS_DIR / project_id / "assets" / parts[1]
                        if local_path.exists():
                            try:
                                img_data = local_path.read_bytes()
                                ext = local_path.suffix.lower()
                                mime = 'image/png' if ext == '.png' else 'image/jpeg' if ext in ('.jpg', '.jpeg') else 'image/webp'
                                image_files.append(FileContent(
                                    content_type=mime,
                                    file_content_base64=base64.b64encode(img_data).decode('utf-8')
                                ))
                                logger.info(f"Loaded inline image for vision: {local_path.name}")
                            except Exception as e:
                                logger.warning(f"Failed to load inline image: {e}")
                elif img_src.startswith('/api/assets/'):
                    # Global assets path
                    asset_name = img_src.split('/api/assets/')[-1]
                    local_path = STORAGE_DIR / "assets" / asset_name
                    if local_path.exists():
                        try:
                            img_data = local_path.read_bytes()
                            ext = local_path.suffix.lower()
                            mime = 'image/png' if ext == '.png' else 'image/jpeg' if ext in ('.jpg', '.jpeg') else 'image/webp'
                            image_files.append(FileContent(
                                content_type=mime,
                                file_content_base64=base64.b64encode(img_data).decode('utf-8')
                            ))
                            logger.info(f"Loaded global asset image for vision: {asset_name}")
                        except Exception as e:
                            logger.warning(f"Failed to load global asset image: {e}")
        elif el_type == 'image' and element.get('src'):
            src = element['src']
            if src.startswith('/api/projects/'):
                parts = src.split('/assets/')
                if len(parts) == 2:
                    local_path = PROJECTS_DIR / project_id / "assets" / parts[1]
                    if local_path.exists():
                        try:
                            img_data = local_path.read_bytes()
                            ext = local_path.suffix.lower()
                            mime = 'image/png' if ext == '.png' else 'image/jpeg' if ext in ('.jpg', '.jpeg') else 'image/webp'
                            image_files.append(FileContent(
                                content_type=mime,
                                file_content_base64=base64.b64encode(img_data).decode('utf-8')
                            ))
                            logger.info(f"Loaded element image for vision: {local_path.name}")
                        except Exception as e:
                            logger.warning(f"Failed to load element image: {e}")
        elif el_type == 'quiz':
            text_parts.append("[Quiz/Atividade interativa presente no slide]")
        elif el_type == 'video':
            text_parts.append("[Vídeo presente no slide]")

    slide_text = "\n".join(text_parts) if text_parts else ""
    slide_title = slide.get('title', '')
    has_images = len(image_files) > 0

    style_guide = {
        "educational": "educativo e didático, explicando conceitos de forma clara e objetiva",
        "conversational": "conversacional e descontraído, como se estivesse falando com um amigo",
        "formal": "formal e profissional, adequado para ambientes corporativos",
        "friendly": "amigável e acolhedor, criando conexão com o espectador"
    }

    try:
        system_msg = f"""Você é um especialista em criar textos de narração para slides de cursos e apresentações.

Suas diretrizes:
1. Escreva em {request.language}
2. Use tom {style_guide.get(request.style, style_guide['educational'])}
3. O texto deve ser adequado para narração em voz alta (TTS)
4. Escreva de forma natural, fluida e envolvente
5. Use pausas naturais (vírgulas, pontos) para dar ritmo
6. O texto deve complementar e explicar o conteúdo visual do slide
7. Cada opção deve ter entre 2 e 5 frases (ideal para 20-60 segundos de narração)
8. Cada opção deve ter uma abordagem ligeiramente diferente"""

        if has_images:
            system_msg += """
9. IMPORTANTE: Analise atentamente as imagens do slide. Leia todo o texto visível nas imagens (OCR).
10. Use o conteúdo visual e textual das imagens como base principal para a narração."""

        system_msg += """

FORMATO DE RESPOSTA OBRIGATÓRIO:
Retorne exatamente 3 opções, separadas por "---". Cada opção deve conter APENAS o texto de narração, sem numeração, títulos ou marcadores. Exemplo:

Texto da primeira opção aqui...
---
Texto da segunda opção aqui...
---
Texto da terceira opção aqui..."""

        chat = LlmChat(
            api_key=emergent_key,
            session_id=f"narration-gen-{uuid.uuid4()}",
            system_message=system_msg
        ).with_model("gemini", "gemini-3-flash-preview")

        prompt = "Crie 3 opções de texto de narração para o seguinte slide:"
        if slide_title:
            prompt += f"\n\nTítulo do slide: {slide_title}"
        if has_images:
            prompt += "\n\nAs imagens do slide estão anexadas. Leia o conteúdo visual e textual delas para criar a narração."
        if slide_text:
            prompt += f"\n\nTexto extraído do slide:\n{slide_text}"
        if request.slide_content:
            prompt += f"\n\nContexto adicional do usuário: {request.slide_content}"

        user_message = UserMessage(
            text=prompt,
            file_contents=image_files if image_files else None
        )
        response = await chat.send_message(user_message)

        # Parse the 3 options
        options = [opt.strip() for opt in response.split("---") if opt.strip()]

        # Ensure we have exactly 3 options
        if len(options) < 3:
            while len(options) < 3:
                options.append(options[-1] if options else "Narração não disponível.")
        options = options[:3]

        return {
            "options": options,
            "slide_id": slide_id,
            "style": request.style
        }
    except Exception as e:
        logger.error(f"AI narration generation error: {e}")
        raise HTTPException(status_code=500, detail=f"Falha ao gerar narração: {str(e)}")



@router.get("/heygen/video-status/{video_id}")
async def get_heygen_video_status(video_id: str):
    """Check the status of a HeyGen video generation"""
    if not HEYGEN_API_KEY:
        raise HTTPException(status_code=500, detail="HeyGen API key not configured")
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as http_client:
            response = await http_client.get(
                f"{HEYGEN_BASE_URL}/v1/video_status.get",
                headers=HEYGEN_HEADERS,
                params={"video_id": video_id}
            )
            
            if response.status_code != 200:
                logger.error(f"HeyGen status error: {response.status_code} - {response.text}")
                raise HTTPException(status_code=response.status_code, detail="Failed to get video status")
            
            data = response.json()
            video_data = data.get("data", {})
            
            status = video_data.get("status", "unknown")
            video_url = video_data.get("video_url")
            thumbnail_url = video_data.get("thumbnail_url")
            duration = video_data.get("duration")
            
            # Update database
            await db.heygen_videos.update_one(
                {"video_id": video_id},
                {"$set": {
                    "status": status,
                    "video_url": video_url,
                    "thumbnail_url": thumbnail_url,
                    "duration": duration,
                    "updated_at": now_utc()
                }}
            )
            
            return {
                "video_id": video_id,
                "status": status,
                "video_url": video_url,
                "thumbnail_url": thumbnail_url,
                "duration": duration
            }
    except httpx.RequestError as e:
        logger.error(f"HeyGen request error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to connect to HeyGen: {str(e)}")

@router.get("/heygen/videos")
async def list_heygen_videos(project_id: Optional[str] = None):
    """List all generated HeyGen videos, optionally filtered by project"""
    query = {}
    if project_id:
        query["project_id"] = project_id
    
    videos = await db.heygen_videos.find(query).sort("created_at", -1).to_list(100)
    
    formatted_videos = []
    for video in videos:
        formatted_videos.append({
            "video_id": video.get("video_id"),
            "title": video.get("title"),
            "status": video.get("status"),
            "video_url": video.get("video_url"),
            "thumbnail_url": video.get("thumbnail_url"),
            "duration": video.get("duration"),
            "script": video.get("script"),
            "avatar_id": video.get("avatar_id"),
            "voice_id": video.get("voice_id"),
            "project_id": video.get("project_id"),
            "transparent": video.get("transparent"),
            "created_at": video.get("created_at").isoformat() if video.get("created_at") else None
        })
    
    return {"videos": formatted_videos}


@router.get("/heygen/videos/{video_id}/refresh")
async def refresh_heygen_video_status(video_id: str):
    """Refresh video status from HeyGen API and update database"""
    if not HEYGEN_API_KEY:
        raise HTTPException(status_code=500, detail="HeyGen API key not configured")
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as http_client:
            response = await http_client.get(
                f"{HEYGEN_BASE_URL}/v1/video_status.get?video_id={video_id}",
                headers=HEYGEN_HEADERS
            )
            
            if response.status_code != 200:
                logger.error(f"HeyGen status error: {response.status_code} - {response.text}")
                raise HTTPException(status_code=response.status_code, detail="Failed to fetch video status")
            
            data = response.json()
            video_data = data.get("data", {})
            status = video_data.get("status", "unknown")
            video_url = video_data.get("video_url")
            thumbnail_url = video_data.get("thumbnail_url")
            duration = video_data.get("duration")
            
            # Update database with fresh status
            update_data = {"status": status}
            if video_url:
                update_data["video_url"] = video_url
            if thumbnail_url:
                update_data["thumbnail_url"] = thumbnail_url
            if duration:
                update_data["duration"] = duration
            
            await db.heygen_videos.update_one(
                {"video_id": video_id},
                {"$set": update_data}
            )
            
            # Get full video data from database
            video_doc = await db.heygen_videos.find_one({"video_id": video_id})
            
            return {
                "video_id": video_id,
                "status": status,
                "video_url": video_url,
                "thumbnail_url": thumbnail_url,
                "duration": duration,
                "title": video_doc.get("title") if video_doc else None,
                "script": video_doc.get("script") if video_doc else None,
                "project_id": video_doc.get("project_id") if video_doc else None,
                "created_at": video_doc.get("created_at").isoformat() if video_doc and video_doc.get("created_at") else None
            }
    except httpx.RequestError as e:
        logger.error(f"HeyGen request error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to connect to HeyGen: {str(e)}")


@router.delete("/heygen/videos/{video_id}")
async def delete_heygen_video(video_id: str):
    """Delete a video from the library (database only, not from HeyGen)"""
    # Check if video exists
    video_doc = await db.heygen_videos.find_one({"video_id": video_id})
    if not video_doc:
        raise HTTPException(status_code=404, detail="Video not found")
    
    # Delete from database
    result = await db.heygen_videos.delete_one({"video_id": video_id})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=500, detail="Failed to delete video")
    
    logger.info(f"Deleted video {video_id} from library")
    
    return {
        "message": "Video deleted successfully",
        "video_id": video_id
    }


# HeyGen Credits/Quota Check
@router.get("/heygen/credits")
async def get_heygen_credits(force_refresh: bool = False):
    """Check remaining HeyGen API credits/quota (with caching)"""
    if not HEYGEN_API_KEY:
        raise HTTPException(status_code=500, detail="HeyGen API key not configured")
    
    # Check cache first (unless force refresh requested)
    if not force_refresh and heygen_credits_cache["data"] is not None:
        cache_age = (datetime.now(timezone.utc) - heygen_credits_cache["timestamp"]).total_seconds()
        if cache_age < heygen_credits_cache["ttl"]:
            logger.info(f"Returning cached HeyGen credits (age: {cache_age:.1f}s)")
            return heygen_credits_cache["data"]
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as http_client:
            response = await http_client.get(
                f"{HEYGEN_BASE_URL}/v2/user/remaining_quota",
                headers=HEYGEN_HEADERS
            )
            
            if response.status_code != 200:
                logger.error(f"HeyGen credits error: {response.status_code} - {response.text}")
                raise HTTPException(status_code=response.status_code, detail="Failed to fetch credits from HeyGen")
            
            data = response.json()
            quota_data = data.get("data", {})
            
            result = {
                "remaining_quota": quota_data.get("remaining_quota", 0),
                "used_quota": quota_data.get("used_quota"),
                "plan": quota_data.get("plan"),
                "has_credits": quota_data.get("remaining_quota", 0) > 0
            }
            
            # Update cache
            heygen_credits_cache["data"] = result
            heygen_credits_cache["timestamp"] = datetime.now(timezone.utc)
            
            return result
    except httpx.RequestError as e:
        logger.error(f"HeyGen credits request error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to connect to HeyGen: {str(e)}")

# HeyGen Webhook Endpoint
class HeyGenWebhookPayload(BaseModel):
    model_config = ConfigDict(extra="allow")
    event_type: Optional[str] = None
    video_id: Optional[str] = None
    status: Optional[str] = None
    video_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    duration: Optional[float] = None

@router.post("/heygen/webhook")
async def heygen_webhook(request: Request):
    """Receive webhook notifications from HeyGen when video processing completes"""
    try:
        # Get raw body for signature verification if needed
        body = await request.json()
        logger.info(f"HeyGen webhook received: {body}")
        
        # Extract relevant data
        video_id = body.get("video_id") or body.get("data", {}).get("video_id")
        status = body.get("status") or body.get("data", {}).get("status")
        video_url = body.get("video_url") or body.get("data", {}).get("video_url")
        thumbnail_url = body.get("thumbnail_url") or body.get("data", {}).get("thumbnail_url")
        duration = body.get("duration") or body.get("data", {}).get("duration")
        
        if video_id:
            # Update video status in database
            update_data = {
                "webhook_received": True,
                "webhook_received_at": now_utc(),
                "updated_at": now_utc()
            }
            
            if status:
                update_data["status"] = status
            if video_url:
                update_data["video_url"] = video_url
            if thumbnail_url:
                update_data["thumbnail_url"] = thumbnail_url
            if duration:
                update_data["duration"] = duration
            
            result = await db.heygen_videos.update_one(
                {"video_id": video_id},
                {"$set": update_data}
            )
            
            logger.info(f"HeyGen webhook processed: video_id={video_id}, status={status}, matched={result.matched_count}")
            
            # Notify SSE subscribers waiting for this video
            if video_id in heygen_sse_subscribers:
                event_data = {
                    "event": "video_update",
                    "video_id": video_id,
                    "status": status,
                    "video_url": video_url,
                    "thumbnail_url": thumbnail_url,
                    "duration": duration
                }
                for queue in heygen_sse_subscribers[video_id]:
                    try:
                        queue.put_nowait(event_data)
                    except asyncio.QueueFull:
                        pass
                logger.info(f"Notified {len(heygen_sse_subscribers[video_id])} SSE subscribers for video {video_id}")
            
            # Invalidate credits cache after video generation
            heygen_credits_cache["data"] = None
            heygen_credits_cache["timestamp"] = None
            
            return {
                "success": True,
                "video_id": video_id,
                "status": status,
                "message": "Webhook processed successfully"
            }
        else:
            logger.warning(f"HeyGen webhook received without video_id: {body}")
            return {"success": True, "message": "Webhook received but no video_id found"}
            
    except Exception as e:
        logger.error(f"HeyGen webhook error: {e}")
        # Always return 200 to acknowledge receipt (avoid retries)
        return {"success": False, "error": str(e)}

# HeyGen Webhook Configuration Helper
@router.get("/heygen/webhook-url")
async def get_heygen_webhook_url(request: Request):
    """Get the webhook URL to configure in HeyGen dashboard"""
    # Get the base URL from the request or environment
    base_url = os.environ.get('REACT_APP_BACKEND_URL', str(request.base_url).rstrip('/'))
    webhook_url = f"{base_url}/api/heygen/webhook"
    
    return {
        "webhook_url": webhook_url,
        "instructions": [
            "1. Acesse o dashboard da HeyGen",
            "2. Vá em Settings > Webhooks",
            "3. Clique em 'Add Webhook Endpoint'",
            "4. Cole a URL acima no campo 'Endpoint URL'",
            "5. Selecione os eventos: 'video.completed', 'video.failed'",
            "6. Salve as configurações"
        ]
    }

# SSE endpoint for real-time video status updates
@router.get("/heygen/video-events/{video_id}")
async def heygen_video_events(video_id: str, request: Request):
    """Server-Sent Events stream for real-time video status updates.
    The frontend connects to this endpoint to receive webhook notifications without polling."""
    
    async def event_generator():
        queue = asyncio.Queue(maxsize=10)
        
        # Register subscriber
        if video_id not in heygen_sse_subscribers:
            heygen_sse_subscribers[video_id] = []
        heygen_sse_subscribers[video_id].append(queue)
        logger.info(f"SSE subscriber connected for video {video_id}")
        
        try:
            # Send initial connection confirmation
            yield f"data: {json.dumps({'event': 'connected', 'video_id': video_id})}\n\n"
            
            # Check current status from database immediately
            video_doc = await db.heygen_videos.find_one({"video_id": video_id})
            if video_doc:
                current_status = video_doc.get("status", "processing")
                current_url = video_doc.get("video_url")
                yield f"data: {json.dumps({'event': 'current_status', 'video_id': video_id, 'status': current_status, 'video_url': current_url})}\n\n"
                
                # If already completed, close stream
                if current_status in ["completed", "failed", "error"]:
                    yield f"data: {json.dumps({'event': 'final', 'video_id': video_id, 'status': current_status, 'video_url': current_url})}\n\n"
                    return
            
            # Wait for updates from webhook
            timeout_seconds = 900  # 15 minutes max
            start_time = datetime.now(timezone.utc)
            last_api_check = start_time
            api_check_interval = 10  # Check API every 10 seconds if no webhook
            
            while True:
                # Check if client disconnected
                if await request.is_disconnected():
                    logger.info(f"SSE client disconnected for video {video_id}")
                    break
                
                # Check timeout
                elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
                if elapsed > timeout_seconds:
                    yield f"data: {json.dumps({'event': 'timeout', 'video_id': video_id})}\n\n"
                    break
                
                try:
                    # Wait for event with timeout
                    event_data = await asyncio.wait_for(queue.get(), timeout=5.0)
                    yield f"data: {json.dumps(event_data)}\n\n"
                    
                    # If video is done, close the stream
                    if event_data.get("status") in ["completed", "failed", "error"]:
                        break
                        
                except asyncio.TimeoutError:
                    # No webhook received, check API directly as fallback
                    time_since_last_check = (datetime.now(timezone.utc) - last_api_check).total_seconds()
                    
                    if time_since_last_check >= api_check_interval:
                        last_api_check = datetime.now(timezone.utc)
                        
                        # Check status from HeyGen API directly
                        try:
                            async with httpx.AsyncClient() as client:
                                headers = {"X-Api-Key": os.getenv("HEYGEN_API_KEY", "")}
                                resp = await client.get(
                                    f"https://api.heygen.com/v1/video_status.get?video_id={video_id}",
                                    headers=headers,
                                    timeout=10.0
                                )
                                if resp.status_code == 200:
                                    api_data = resp.json().get("data", {})
                                    api_status = api_data.get("status", "processing")
                                    api_video_url = api_data.get("video_url")
                                    
                                    # Update database
                                    if api_status in ["completed", "failed", "error"]:
                                        await db.heygen_videos.update_one(
                                            {"video_id": video_id},
                                            {"$set": {
                                                "status": api_status,
                                                "video_url": api_video_url,
                                                "api_checked_at": now_utc()
                                            }}
                                        )
                                        
                                        yield f"data: {json.dumps({'event': 'status_update', 'video_id': video_id, 'status': api_status, 'video_url': api_video_url})}\n\n"
                                        break
                                    else:
                                        # Send progress update
                                        yield f"data: {json.dumps({'event': 'ping', 'elapsed': int(elapsed), 'status': api_status})}\n\n"
                        except Exception as e:
                            logger.error(f"Error checking HeyGen API: {e}")
                            # Send keepalive ping
                            yield f"data: {json.dumps({'event': 'ping', 'elapsed': int(elapsed)})}\n\n"
                    else:
                        # Just send keepalive
                        yield f"data: {json.dumps({'event': 'ping', 'elapsed': int(elapsed)})}\n\n"
                    
        finally:
            # Unregister subscriber
            if video_id in heygen_sse_subscribers:
                try:
                    heygen_sse_subscribers[video_id].remove(queue)
                    if not heygen_sse_subscribers[video_id]:
                        del heygen_sse_subscribers[video_id]
                except ValueError:
                    pass
            logger.info(f"SSE subscriber disconnected for video {video_id}")
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )
