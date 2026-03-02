"""
Test HeyGen Integration for Scormify Agent Flow
Tests: avatars API, voices API, heygen-status endpoint, media-config with heygen
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestHealthEndpoint:
    """Health check endpoint"""
    
    def test_health_endpoint(self):
        """GET /api/health - returns healthy status"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy"
        print("✓ Health endpoint returns healthy status")


class TestHeyGenAvatarsAPI:
    """HeyGen Avatars endpoint tests"""
    
    def test_get_avatars_with_limit(self):
        """GET /api/heygen/avatars?limit=5 - returns list of avatars"""
        response = requests.get(f"{BASE_URL}/api/heygen/avatars?limit=5")
        assert response.status_code == 200
        data = response.json()
        
        # Validate response structure
        assert "avatars" in data
        assert "total" in data
        assert isinstance(data["avatars"], list)
        
        # Check we got 5 or fewer avatars
        assert len(data["avatars"]) <= 5
        
        # Validate avatar structure
        if len(data["avatars"]) > 0:
            avatar = data["avatars"][0]
            assert "avatar_id" in avatar
            assert "avatar_name" in avatar
            assert "preview_image_url" in avatar
            print(f"✓ Got {len(data['avatars'])} avatars, total available: {data['total']}")
            print(f"  Sample avatar: {avatar['avatar_name']}")
        else:
            print("⚠ No avatars returned")
    
    def test_avatars_default_response(self):
        """GET /api/heygen/avatars - default returns up to 200 avatars"""
        response = requests.get(f"{BASE_URL}/api/heygen/avatars")
        assert response.status_code == 200
        data = response.json()
        
        assert "avatars" in data
        assert data["total"] > 0
        print(f"✓ HeyGen API returns {data['total']} total avatars")


class TestHeyGenVoicesAPI:
    """HeyGen Voices endpoint tests"""
    
    def test_get_portuguese_voices(self):
        """GET /api/heygen/voices?language=portuguese - returns Portuguese voices"""
        response = requests.get(f"{BASE_URL}/api/heygen/voices?language=portuguese")
        assert response.status_code == 200
        data = response.json()
        
        # Validate response structure
        assert "voices" in data
        assert isinstance(data["voices"], list)
        
        # Validate we got Portuguese voices
        if len(data["voices"]) > 0:
            voice = data["voices"][0]
            assert "voice_id" in voice
            assert "name" in voice
            assert "gender" in voice
            print(f"✓ Got {len(data['voices'])} Portuguese voices")
            print(f"  Sample voice: {voice['name']} ({voice['gender']})")
        else:
            print("⚠ No Portuguese voices returned")
    
    def test_voices_have_language_info(self):
        """Verify voice response includes language metadata"""
        response = requests.get(f"{BASE_URL}/api/heygen/voices?language=portuguese")
        assert response.status_code == 200
        data = response.json()
        
        # Check voice structure includes language info
        if len(data["voices"]) > 0:
            voice = data["voices"][0]
            assert "language" in voice or "language_code" in voice
            print(f"✓ Voices include language metadata")


class TestHeyGenStatusEndpoint:
    """HeyGen status endpoint for project video status"""
    
    def test_heygen_status_existing_project(self):
        """GET /api/agent/projects/{project_id}/heygen-status - existing project with no heygen"""
        # Test with existing project that has no heygenPending
        project_id = "cebb110f-ced1-4e62-8478-7fb6bd99943d"
        response = requests.get(f"{BASE_URL}/api/agent/projects/{project_id}/heygen-status")
        assert response.status_code == 200
        data = response.json()
        
        # Project exists but has no heygen pending
        assert data.get("status") == "no_heygen"
        assert data.get("videos") == []
        print(f"✓ HeyGen status returns 'no_heygen' for project without pending videos")
    
    def test_heygen_status_nonexistent_project(self):
        """GET /api/agent/projects/{project_id}/heygen-status - non-existent project returns 404"""
        response = requests.get(f"{BASE_URL}/api/agent/projects/nonexistent-project-id/heygen-status")
        assert response.status_code == 404
        print(f"✓ HeyGen status returns 404 for non-existent project")


class TestAgentSessionsAPI:
    """Agent session endpoints"""
    
    def test_create_session(self):
        """POST /api/agent/sessions - creates session"""
        response = requests.post(
            f"{BASE_URL}/api/agent/sessions",
            headers={"Content-Type": "application/json"},
            json={}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "id" in data
        assert data["id"] is not None
        assert len(data["id"]) > 0
        print(f"✓ Session created with ID: {data['id']}")
        
        # Return session ID for later tests
        return data["id"]


class TestAgentMediaConfigAPI:
    """Agent media config endpoint tests"""
    
    def test_media_config_with_heygen_settings(self):
        """POST /api/agent/sessions/{id}/media-config - saves heygen avatar_id and voice_id"""
        # First create a session
        session_response = requests.post(
            f"{BASE_URL}/api/agent/sessions",
            headers={"Content-Type": "application/json"},
            json={}
        )
        assert session_response.status_code == 200
        session_id = session_response.json()["id"]
        
        # Now test media-config endpoint with heygen settings
        media_config = {
            "mediaConfig": {
                "0": {"type": "heygen"},
                "1": {"type": "ai_image"},
                "2": {"type": "heygen"}
            },
            "heygenConfig": {
                "avatarId": "test-avatar-id",
                "voiceId": "test-voice-id"
            }
        }
        
        response = requests.post(
            f"{BASE_URL}/api/agent/sessions/{session_id}/media-config",
            json=media_config
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("status") == "ok"
        assert data.get("configured") == 3  # 3 slides configured
        print(f"✓ Media config saved with {data['configured']} slides configured")
    
    def test_media_config_invalid_session(self):
        """POST /api/agent/sessions/{id}/media-config - invalid session returns 404"""
        response = requests.post(
            f"{BASE_URL}/api/agent/sessions/invalid-session-id/media-config",
            json={"mediaConfig": {}}
        )
        assert response.status_code == 404
        print(f"✓ Media config returns 404 for invalid session")


class TestAgentTemplatesAPI:
    """Agent templates endpoint"""
    
    def test_get_templates_returns_6(self):
        """GET /api/agent/templates - returns 6 templates"""
        response = requests.get(f"{BASE_URL}/api/agent/templates")
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        assert len(data) == 6
        
        # Verify template structure
        template = data[0]
        assert "id" in template
        assert "name" in template
        print(f"✓ Got {len(data)} templates: {[t['id'] for t in data]}")


class TestAgentCoursesAPI:
    """Agent courses endpoint"""
    
    def test_get_agent_courses(self):
        """GET /api/agent/courses - returns agent-created courses"""
        response = requests.get(f"{BASE_URL}/api/agent/courses")
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        print(f"✓ Got {len(data)} agent-created courses")
        
        # Check course structure if any exist
        if len(data) > 0:
            course = data[0]
            assert "id" in course
            assert "name" in course


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
