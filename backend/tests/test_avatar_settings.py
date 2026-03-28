"""
Test Avatar Settings Feature - HeyGen Avatar and ElevenLabs Voice Selectors
Tests the new avatar-settings endpoints and HeyGen/ElevenLabs API integrations
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestHeyGenAvatars:
    """Test HeyGen avatars endpoint"""
    
    def test_heygen_avatars_endpoint_returns_list(self):
        """GET /api/heygen/avatars should return list of avatars"""
        response = requests.get(f"{BASE_URL}/api/heygen/avatars?limit=10")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "avatars" in data, "Response should contain 'avatars' key"
        assert "total" in data, "Response should contain 'total' key"
        
        # Verify avatar structure if avatars exist
        if data["avatars"]:
            avatar = data["avatars"][0]
            assert "avatar_id" in avatar, "Avatar should have avatar_id"
            assert "avatar_name" in avatar, "Avatar should have avatar_name"
            assert "preview_image_url" in avatar, "Avatar should have preview_image_url"
            print(f"PASS: HeyGen avatars endpoint returned {len(data['avatars'])} avatars")
        else:
            print("WARN: No avatars returned - check HeyGen API key")


class TestElevenLabsVoices:
    """Test ElevenLabs voices endpoint"""
    
    def test_elevenlabs_voices_endpoint_returns_list(self):
        """GET /api/elevenlabs/voices should return list of voices"""
        response = requests.get(f"{BASE_URL}/api/elevenlabs/voices")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "voices" in data, "Response should contain 'voices' key"
        assert "total" in data, "Response should contain 'total' key"
        
        # Verify voice structure if voices exist
        if data["voices"]:
            voice = data["voices"][0]
            assert "voice_id" in voice, "Voice should have voice_id"
            assert "name" in voice, "Voice should have name"
            assert "labels" in voice, "Voice should have labels"
            print(f"PASS: ElevenLabs voices endpoint returned {len(data['voices'])} voices")
        else:
            print("WARN: No voices returned - check ElevenLabs API key")


class TestAvatarSettings:
    """Test avatar settings CRUD for projects"""
    
    @pytest.fixture
    def test_project_id(self):
        """Get or create a test project ID"""
        # First, try to get an existing project
        response = requests.get(f"{BASE_URL}/api/projects")
        if response.status_code == 200:
            data = response.json()
            # API returns list directly
            projects = data if isinstance(data, list) else data.get("projects", [])
            if projects:
                return projects[0]["id"]
        
        # If no projects exist, skip the test
        pytest.skip("No projects available for testing avatar settings")
    
    def test_get_avatar_settings_returns_defaults_for_new_project(self, test_project_id):
        """GET /api/agent/projects/{id}/avatar-settings should return defaults (not 404)"""
        response = requests.get(f"{BASE_URL}/api/agent/projects/{test_project_id}/avatar-settings")
        
        # Should NOT return 404 - this was the bug that was fixed
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Should return default values
        assert "maxScenes" in data, "Response should contain maxScenes"
        print(f"PASS: GET avatar-settings returns defaults: {data}")
    
    def test_put_avatar_settings_saves_correctly(self, test_project_id):
        """PUT /api/agent/projects/{id}/avatar-settings should save settings"""
        test_avatar_id = f"test_avatar_{uuid.uuid4().hex[:8]}"
        test_voice_id = f"test_voice_{uuid.uuid4().hex[:8]}"
        
        payload = {
            "maxScenes": 5,
            "defaultAvatarId": test_avatar_id,
            "defaultVoiceId": test_voice_id
        }
        
        response = requests.put(
            f"{BASE_URL}/api/agent/projects/{test_project_id}/avatar-settings",
            json=payload
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("status") == "ok", "Response should have status 'ok'"
        assert data.get("settings", {}).get("defaultAvatarId") == test_avatar_id
        assert data.get("settings", {}).get("defaultVoiceId") == test_voice_id
        print(f"PASS: PUT avatar-settings saved correctly")
    
    def test_get_avatar_settings_returns_saved_values(self, test_project_id):
        """GET /api/agent/projects/{id}/avatar-settings should return saved values"""
        # First save some settings
        test_avatar_id = f"saved_avatar_{uuid.uuid4().hex[:8]}"
        test_voice_id = f"saved_voice_{uuid.uuid4().hex[:8]}"
        
        save_response = requests.put(
            f"{BASE_URL}/api/agent/projects/{test_project_id}/avatar-settings",
            json={
                "maxScenes": 7,
                "defaultAvatarId": test_avatar_id,
                "defaultVoiceId": test_voice_id
            }
        )
        assert save_response.status_code == 200
        
        # Now GET and verify
        get_response = requests.get(f"{BASE_URL}/api/agent/projects/{test_project_id}/avatar-settings")
        assert get_response.status_code == 200
        
        data = get_response.json()
        assert data.get("maxScenes") == 7, f"Expected maxScenes=7, got {data.get('maxScenes')}"
        assert data.get("defaultAvatarId") == test_avatar_id
        assert data.get("defaultVoiceId") == test_voice_id
        print(f"PASS: GET avatar-settings returns saved values correctly")
    
    def test_avatar_settings_for_nonexistent_project_returns_404(self):
        """GET/PUT avatar-settings for non-existent project should return 404"""
        fake_project_id = f"nonexistent_{uuid.uuid4().hex}"
        
        get_response = requests.get(f"{BASE_URL}/api/agent/projects/{fake_project_id}/avatar-settings")
        assert get_response.status_code == 404, f"Expected 404 for non-existent project, got {get_response.status_code}"
        
        put_response = requests.put(
            f"{BASE_URL}/api/agent/projects/{fake_project_id}/avatar-settings",
            json={"maxScenes": 3}
        )
        assert put_response.status_code == 404, f"Expected 404 for non-existent project, got {put_response.status_code}"
        print("PASS: Non-existent project returns 404 correctly")


class TestHealthCheck:
    """Basic health check"""
    
    def test_api_health(self):
        """API should be accessible"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200, f"Health check failed: {response.status_code}"
        print("PASS: API health check")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
