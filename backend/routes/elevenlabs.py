"""ElevenLabs Text-to-Speech routes"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
import uuid
import os
import logging
import base64
import aiofiles

from routes.deps import db, now_utc, STORAGE_DIR

logger = logging.getLogger("server")

router = APIRouter(tags=["ElevenLabs"])

ELEVENLABS_API_KEY = os.environ.get('ELEVENLABS_API_KEY', '')


@router.get("/elevenlabs/voices")
async def list_elevenlabs_voices(language: Optional[str] = None, gender: Optional[str] = None):
    if not ELEVENLABS_API_KEY:
        raise HTTPException(status_code=400, detail="ElevenLabs API key not configured")
    try:
        from elevenlabs import ElevenLabs
        client = ElevenLabs(api_key=ELEVENLABS_API_KEY)
        voices_response = client.voices.get_all()
        voices = []
        available_genders = set()
        for voice in voices_response.voices:
            voice_data = {
                "voice_id": voice.voice_id,
                "name": voice.name,
                "description": voice.description or "",
                "preview_url": voice.preview_url,
                "category": voice.category or "premade",
                "labels": voice.labels or {},
                "gender": None,
                "accent": None,
                "age": None,
                "multilingual": True
            }
            if voice.labels:
                voice_data["gender"] = voice.labels.get("gender", "").lower()
                voice_data["accent"] = voice.labels.get("accent", "")
                voice_data["age"] = voice.labels.get("age", "")
                if voice_data["gender"]:
                    available_genders.add(voice_data["gender"])
            if gender:
                if voice_data["gender"] != gender.lower():
                    continue
            voices.append(voice_data)
        voices.sort(key=lambda x: x["name"])
        supported_languages = [
            {"code": "pt-BR", "label": "Portugues (Brasil)"},
            {"code": "en", "label": "English"},
            {"code": "es", "label": "Espanol"}
        ]
        return {
            "voices": voices,
            "total": len(voices),
            "supported_languages": supported_languages,
            "available_genders": sorted(list(available_genders)),
            "note": "All voices support Portuguese, English, and Spanish via eleven_multilingual_v2 model."
        }
    except Exception as e:
        logger.error(f"Error fetching ElevenLabs voices: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching voices: {str(e)}")


class TTSRequest(BaseModel):
    text: str
    voice_id: str
    stability: float = 0.5
    similarity_boost: float = 0.75
    style: float = 0.0
    use_speaker_boost: bool = True


@router.post("/elevenlabs/generate-speech")
async def generate_elevenlabs_speech(request: TTSRequest):
    if not ELEVENLABS_API_KEY:
        raise HTTPException(status_code=400, detail="ElevenLabs API key not configured")
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")
    try:
        from elevenlabs import ElevenLabs
        from elevenlabs.types import VoiceSettings
        client = ElevenLabs(api_key=ELEVENLABS_API_KEY)
        voice_settings = VoiceSettings(
            stability=request.stability,
            similarity_boost=request.similarity_boost,
            style=request.style,
            use_speaker_boost=request.use_speaker_boost
        )
        audio_generator = client.text_to_speech.convert(
            text=request.text,
            voice_id=request.voice_id,
            model_id="eleven_multilingual_v2",
            voice_settings=voice_settings
        )
        audio_data = b""
        for chunk in audio_generator:
            audio_data += chunk
        audio_b64 = base64.b64encode(audio_data).decode()
        audio_id = str(uuid.uuid4())
        filename = f"tts_{audio_id}.mp3"
        audio_path = STORAGE_DIR / "audio" / filename
        audio_path.parent.mkdir(exist_ok=True)
        async with aiofiles.open(audio_path, "wb") as f:
            await f.write(audio_data)
        tts_record = {
            "id": audio_id,
            "voice_id": request.voice_id,
            "text": request.text[:500],
            "filename": filename,
            "file_path": str(audio_path),
            "file_size": len(audio_data),
            "audio_data": base64.b64encode(audio_data).decode(),
            "created_at": now_utc().isoformat()
        }
        await db.tts_generations.insert_one(tts_record)
        return {
            "success": True,
            "audio_id": audio_id,
            "audio_url": f"/api/audio/{filename}",
            "audio_base64": f"data:audio/mpeg;base64,{audio_b64}",
            "text": request.text,
            "voice_id": request.voice_id,
            "file_size": len(audio_data)
        }
    except Exception as e:
        logger.error(f"Error generating TTS: {e}")
        raise HTTPException(status_code=500, detail=f"Error generating speech: {str(e)}")


@router.get("/audio/{filename}")
async def get_audio_file(filename: str):
    audio_path = STORAGE_DIR / "audio" / filename
    if audio_path.exists():
        return FileResponse(audio_path, media_type="audio/mpeg", filename=filename)
    record = await db.tts_generations.find_one({"filename": filename}, {"_id": 0, "audio_data": 1})
    if record and record.get("audio_data"):
        audio_data = base64.b64decode(record["audio_data"])
        audio_path.parent.mkdir(exist_ok=True)
        async with aiofiles.open(audio_path, "wb") as f:
            await f.write(audio_data)
        return FileResponse(audio_path, media_type="audio/mpeg", filename=filename)
    raise HTTPException(status_code=404, detail="Audio file not found")


@router.get("/elevenlabs/voices/recommended")
async def get_recommended_voices():
    if not ELEVENLABS_API_KEY:
        raise HTTPException(status_code=400, detail="ElevenLabs API key not configured")
    try:
        from elevenlabs import ElevenLabs
        client = ElevenLabs(api_key=ELEVENLABS_API_KEY)
        voices_response = client.voices.get_all()
        filters = {
            "pt-BR": {"keywords": ["brazilian", "brazil", "portugues", "portuguese"], "voices": []},
            "en": {"keywords": ["english", "american", "british"], "voices": []},
            "es": {"keywords": ["spanish", "espanol", "latin"], "voices": []},
        }
        for voice in voices_response.voices:
            voice_text = f"{voice.name} {voice.description or ''}".lower()
            accent = (voice.labels or {}).get("accent", "").lower()
            voice_text += f" {accent}"
            gender = (voice.labels or {}).get("gender", "unknown").lower()
            voice_info = {
                "voice_id": voice.voice_id, "name": voice.name,
                "description": voice.description or "", "preview_url": voice.preview_url,
                "gender": gender, "accent": accent
            }
            for lang, data in filters.items():
                if any(kw in voice_text for kw in data["keywords"]):
                    data["voices"].append(voice_info)
        recommended = {}
        for lang, data in filters.items():
            recommended[lang] = {
                "male": [v for v in data["voices"] if v["gender"] == "male"][:5],
                "female": [v for v in data["voices"] if v["gender"] == "female"][:5]
            }
        return {
            "recommended": recommended,
            "languages": [
                {"code": "pt-BR", "label": "Portugues (Brasil)"},
                {"code": "en", "label": "English"},
                {"code": "es", "label": "Espanol"}
            ]
        }
    except Exception as e:
        logger.error(f"Error fetching recommended voices: {e}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
