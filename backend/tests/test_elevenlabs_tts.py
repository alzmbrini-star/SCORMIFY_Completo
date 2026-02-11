"""
ElevenLabs Text-to-Speech API Tests
Tests for TTS integration with ElevenLabs - voices listing and speech generation
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL')

class TestElevenLabsVoices:
    """Tests for GET /api/elevenlabs/voices endpoint"""
    
    def test_list_all_voices(self):
        """Test fetching all available voices"""
        response = requests.get(f"{BASE_URL}/api/elevenlabs/voices")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        # Verify response structure
        assert "voices" in data
        assert "total" in data
        assert "supported_languages" in data
        assert "available_genders" in data
        
        # Verify 21 voices are returned
        voices = data["voices"]
        assert len(voices) == 21, f"Expected 21 voices, got {len(voices)}"
        
        # Verify voice structure
        for voice in voices[:3]:
            assert "voice_id" in voice
            assert "name" in voice
            assert "gender" in voice
            assert "multilingual" in voice
            assert voice["multilingual"] == True, "All voices should be multilingual"
        
        print(f"✅ List all voices: {len(voices)} voices returned")
    
    def test_filter_by_male_gender(self):
        """Test filtering voices by male gender"""
        response = requests.get(f"{BASE_URL}/api/elevenlabs/voices?gender=male")
        assert response.status_code == 200
        
        data = response.json()
        voices = data["voices"]
        
        # Verify all returned voices are male
        for voice in voices:
            assert voice["gender"] == "male", f"Voice {voice['name']} has gender {voice['gender']}, expected male"
        
        # Verify correct count (based on API response)
        assert len(voices) > 0, "Should have male voices"
        print(f"✅ Male filter: {len(voices)} male voices returned")
    
    def test_filter_by_female_gender(self):
        """Test filtering voices by female gender"""
        response = requests.get(f"{BASE_URL}/api/elevenlabs/voices?gender=female")
        assert response.status_code == 200
        
        data = response.json()
        voices = data["voices"]
        
        # Verify all returned voices are female
        for voice in voices:
            assert voice["gender"] == "female", f"Voice {voice['name']} has gender {voice['gender']}, expected female"
        
        assert len(voices) > 0, "Should have female voices"
        print(f"✅ Female filter: {len(voices)} female voices returned")
    
    def test_supported_languages(self):
        """Test that supported languages include Portuguese, English, Spanish"""
        response = requests.get(f"{BASE_URL}/api/elevenlabs/voices")
        assert response.status_code == 200
        
        data = response.json()
        languages = data["supported_languages"]
        
        # Check for the three required languages
        language_codes = [l["code"] for l in languages]
        assert "pt-BR" in language_codes, "Portuguese (Brazil) not in supported languages"
        assert "en" in language_codes, "English not in supported languages"
        assert "es" in language_codes, "Spanish not in supported languages"
        
        print(f"✅ Supported languages: {language_codes}")


class TestElevenLabsGenerateSpeech:
    """Tests for POST /api/elevenlabs/generate-speech endpoint"""
    
    def test_generate_speech_portuguese(self):
        """Test generating speech in Portuguese"""
        payload = {
            "text": "Olá, esta é uma narração de teste em português brasileiro.",
            "voice_id": "pNInz6obpgDQGcFmaJgB",  # Adam voice
            "stability": 0.5,
            "similarity_boost": 0.75
        }
        
        response = requests.post(
            f"{BASE_URL}/api/elevenlabs/generate-speech",
            json=payload
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Verify response structure
        assert data.get("success") == True
        assert "audio_id" in data
        assert "audio_base64" in data
        assert "audio_url" in data
        assert data["audio_base64"].startswith("data:audio/mpeg;base64,")
        
        print(f"✅ Generate Portuguese speech: audio_id={data['audio_id'][:8]}...")
    
    def test_generate_speech_english(self):
        """Test generating speech in English"""
        payload = {
            "text": "Hello, this is a test narration in English.",
            "voice_id": "Xb7hH8MSUJpSbSDYk0k2",  # Alice voice
            "stability": 0.5,
            "similarity_boost": 0.75
        }
        
        response = requests.post(
            f"{BASE_URL}/api/elevenlabs/generate-speech",
            json=payload
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("success") == True
        assert "audio_base64" in data
        
        print(f"✅ Generate English speech: audio_id={data['audio_id'][:8]}...")
    
    def test_generate_speech_spanish(self):
        """Test generating speech in Spanish"""
        payload = {
            "text": "Hola, esta es una narración de prueba en español.",
            "voice_id": "nPczCjzI2devNBz1zQrb",  # Brian voice
            "stability": 0.5,
            "similarity_boost": 0.75
        }
        
        response = requests.post(
            f"{BASE_URL}/api/elevenlabs/generate-speech",
            json=payload
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("success") == True
        assert "audio_base64" in data
        
        print(f"✅ Generate Spanish speech: audio_id={data['audio_id'][:8]}...")
    
    def test_generate_speech_empty_text(self):
        """Test that empty text returns error"""
        payload = {
            "text": "",
            "voice_id": "pNInz6obpgDQGcFmaJgB"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/elevenlabs/generate-speech",
            json=payload
        )
        assert response.status_code == 400, "Empty text should return 400 error"
        print("✅ Empty text validation working")
    
    def test_generate_speech_with_female_voice(self):
        """Test generating speech with a female voice"""
        payload = {
            "text": "Este é um teste com uma voz feminina.",
            "voice_id": "cgSgspJ2msm6clMCkdW9",  # Jessica voice (female)
            "stability": 0.5,
            "similarity_boost": 0.75
        }
        
        response = requests.post(
            f"{BASE_URL}/api/elevenlabs/generate-speech",
            json=payload
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("success") == True
        
        print(f"✅ Generate speech with female voice: audio_id={data['audio_id'][:8]}...")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
