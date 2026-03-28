"""
Test HeyGen Voices and Avatar Settings APIs
Tests the new HeyGen voice selector feature for avatar scenes
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test project ID (existing project in database)
TEST_PROJECT_ID = "cb4e0112-3e45-44fe-ab29-304b0ef8f0a0"


class TestHeyGenVoicesAPI:
    """Tests for GET /api/heygen/voices endpoint"""
    
    def test_heygen_voices_all_returns_200(self):
        """GET /api/heygen/voices should return 200 with all voices"""
        response = requests.get(f"{BASE_URL}/api/heygen/voices")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "voices" in data, "Response should contain 'voices' key"
        assert isinstance(data["voices"], list), "voices should be a list"
        assert len(data["voices"]) > 0, "Should return at least one voice"
        
    def test_heygen_voices_structure(self):
        """Each voice should have required fields: voice_id, name, language_code, country_flag, gender"""
        response = requests.get(f"{BASE_URL}/api/heygen/voices")
        assert response.status_code == 200
        
        data = response.json()
        voices = data["voices"]
        
        # Check first voice has all required fields
        first_voice = voices[0]
        required_fields = ["voice_id", "name", "language_code", "country_flag", "gender"]
        for field in required_fields:
            assert field in first_voice, f"Voice should have '{field}' field"
            
    def test_heygen_voices_portuguese_filter(self):
        """GET /api/heygen/voices?language=portuguese should return only Portuguese voices"""
        response = requests.get(f"{BASE_URL}/api/heygen/voices?language=portuguese")
        assert response.status_code == 200
        
        data = response.json()
        voices = data["voices"]
        assert len(voices) > 0, "Should return Portuguese voices"
        
        # All voices should be Portuguese
        for voice in voices:
            lang = voice.get("language", "").lower()
            assert "portuguese" in lang or "brasil" in lang or "portugal" in lang, \
                f"Voice {voice['name']} should be Portuguese, got language: {voice.get('language')}"
                
    def test_heygen_voices_ptbr_available(self):
        """Portuguese voices should include PT-BR voices with correct language_code"""
        response = requests.get(f"{BASE_URL}/api/heygen/voices?language=portuguese")
        assert response.status_code == 200
        
        data = response.json()
        voices = data["voices"]
        
        # Check for PT-BR voices
        ptbr_voices = [v for v in voices if v.get("language_code") == "pt-BR"]
        pt_voices = [v for v in voices if v.get("language_code", "").startswith("pt")]
        
        # Should have at least some Portuguese voices
        assert len(pt_voices) > 0, "Should have Portuguese voices"
        
        # Check country flags
        br_flags = [v for v in voices if v.get("country_flag") == "🇧🇷"]
        assert len(br_flags) > 0, "Should have Brazilian flag voices"
        
    def test_heygen_voices_has_preview_audio(self):
        """Voices should have preview_audio URL"""
        response = requests.get(f"{BASE_URL}/api/heygen/voices?language=portuguese")
        assert response.status_code == 200
        
        data = response.json()
        voices = data["voices"]
        
        # At least some voices should have preview audio
        voices_with_preview = [v for v in voices if v.get("preview_audio")]
        assert len(voices_with_preview) > 0, "Some voices should have preview_audio"


class TestAvatarSettingsAPI:
    """Tests for avatar settings endpoints"""
    
    def test_get_avatar_settings_returns_200(self):
        """GET /api/agent/projects/{id}/avatar-settings should return 200"""
        response = requests.get(f"{BASE_URL}/api/agent/projects/{TEST_PROJECT_ID}/avatar-settings")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "maxScenes" in data, "Response should have maxScenes"
        
    def test_get_avatar_settings_structure(self):
        """Avatar settings should have maxScenes, defaultAvatarId, defaultVoiceId"""
        response = requests.get(f"{BASE_URL}/api/agent/projects/{TEST_PROJECT_ID}/avatar-settings")
        assert response.status_code == 200
        
        data = response.json()
        expected_fields = ["maxScenes", "defaultAvatarId", "defaultVoiceId"]
        for field in expected_fields:
            assert field in data, f"Settings should have '{field}' field"
            
    def test_put_avatar_settings_saves_heygen_voice_id(self):
        """PUT /api/agent/projects/{id}/avatar-settings should save HeyGen voice_id"""
        # First get a real HeyGen voice_id
        voices_response = requests.get(f"{BASE_URL}/api/heygen/voices?language=portuguese")
        assert voices_response.status_code == 200
        voices = voices_response.json()["voices"]
        assert len(voices) > 0, "Need at least one voice to test"
        
        heygen_voice_id = voices[0]["voice_id"]
        
        # Save the voice_id
        payload = {
            "maxScenes": 4,
            "defaultAvatarId": "test-avatar-id",
            "defaultVoiceId": heygen_voice_id
        }
        response = requests.put(
            f"{BASE_URL}/api/agent/projects/{TEST_PROJECT_ID}/avatar-settings",
            json=payload
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data["status"] == "ok"
        assert data["settings"]["defaultVoiceId"] == heygen_voice_id
        
    def test_get_avatar_settings_returns_saved_voice_id(self):
        """GET should return the previously saved HeyGen voice_id"""
        # First save a voice_id
        voices_response = requests.get(f"{BASE_URL}/api/heygen/voices?language=portuguese")
        voices = voices_response.json()["voices"]
        heygen_voice_id = voices[0]["voice_id"]
        
        payload = {
            "maxScenes": 3,
            "defaultAvatarId": None,
            "defaultVoiceId": heygen_voice_id
        }
        requests.put(
            f"{BASE_URL}/api/agent/projects/{TEST_PROJECT_ID}/avatar-settings",
            json=payload
        )
        
        # Now GET and verify
        response = requests.get(f"{BASE_URL}/api/agent/projects/{TEST_PROJECT_ID}/avatar-settings")
        assert response.status_code == 200
        
        data = response.json()
        assert data["defaultVoiceId"] == heygen_voice_id, \
            f"Expected voice_id {heygen_voice_id}, got {data['defaultVoiceId']}"
            
    def test_avatar_settings_nonexistent_project_returns_404(self):
        """GET avatar-settings for non-existent project should return 404"""
        response = requests.get(f"{BASE_URL}/api/agent/projects/nonexistent-project-id/avatar-settings")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"


class TestHeyGenVoicesVsElevenLabs:
    """Verify HeyGen voices are different from ElevenLabs voices"""
    
    def test_heygen_voices_have_different_format_than_elevenlabs(self):
        """HeyGen voices should have language_code and country_flag (ElevenLabs doesn't)"""
        response = requests.get(f"{BASE_URL}/api/heygen/voices?language=portuguese")
        assert response.status_code == 200
        
        data = response.json()
        voices = data["voices"]
        
        # HeyGen voices should have these fields
        for voice in voices[:5]:  # Check first 5
            assert "language_code" in voice, "HeyGen voice should have language_code"
            assert "country_flag" in voice, "HeyGen voice should have country_flag"
            # voice_id format check (HeyGen uses different format than ElevenLabs)
            assert len(voice["voice_id"]) > 10, "voice_id should be a valid ID"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
