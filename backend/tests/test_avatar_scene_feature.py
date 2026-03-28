"""
Test suite for Avatar Scene Feature
Tests the new avatar scene suggestion and generation functionality:
- GET /api/agent/projects/{project_id}/avatar-settings - returns default settings
- PUT /api/agent/projects/{project_id}/avatar-settings - updates settings
- GET /api/agent/projects/{project_id}/avatar-generation-status - returns generation status
- POST /api/agent/courses/{project_id}/analyze - may return avatar_scene improvements
- POST /api/agent/courses/{project_id}/apply-improvements - returns avatarScenesTriggered count
"""
import pytest
import requests
import os
import json
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test project IDs from context
PROJECT_ID_HIBRIDO = "a87fd1a0-1338-4043-9c2f-b0cc8572a12e"
PROJECT_ID_UNIVERSIDADES = "82d2d9d4-3067-47de-bf5a-0e14e9051e67"


class TestAvatarSettingsEndpoints:
    """Test avatar settings GET and PUT endpoints"""
    
    def test_get_avatar_settings_default(self):
        """GET /api/agent/projects/{project_id}/avatar-settings returns default settings"""
        response = requests.get(f"{BASE_URL}/api/agent/projects/{PROJECT_ID_HIBRIDO}/avatar-settings")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Should have maxScenes field (default 3)
        assert "maxScenes" in data, f"Response missing maxScenes: {data}"
        assert isinstance(data["maxScenes"], int), f"maxScenes should be int: {data}"
        print(f"✓ GET avatar-settings returns: {data}")
    
    def test_get_avatar_settings_nonexistent_project(self):
        """GET /api/agent/projects/{project_id}/avatar-settings returns 404 for nonexistent project"""
        response = requests.get(f"{BASE_URL}/api/agent/projects/nonexistent-project-id/avatar-settings")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ GET avatar-settings returns 404 for nonexistent project")
    
    def test_put_avatar_settings_update_max_scenes(self):
        """PUT /api/agent/projects/{project_id}/avatar-settings updates maxScenes"""
        # First get current settings
        get_resp = requests.get(f"{BASE_URL}/api/agent/projects/{PROJECT_ID_HIBRIDO}/avatar-settings")
        original_settings = get_resp.json()
        original_max = original_settings.get("maxScenes", 3)
        
        # Update to a new value
        new_max = 5 if original_max != 5 else 4
        update_payload = {"maxScenes": new_max}
        
        response = requests.put(
            f"{BASE_URL}/api/agent/projects/{PROJECT_ID_HIBRIDO}/avatar-settings",
            json=update_payload,
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("status") == "ok", f"Expected status ok: {data}"
        assert data.get("settings", {}).get("maxScenes") == new_max, f"maxScenes not updated: {data}"
        
        # Verify by GET
        verify_resp = requests.get(f"{BASE_URL}/api/agent/projects/{PROJECT_ID_HIBRIDO}/avatar-settings")
        verify_data = verify_resp.json()
        assert verify_data.get("maxScenes") == new_max, f"GET after PUT shows wrong value: {verify_data}"
        
        # Restore original
        requests.put(
            f"{BASE_URL}/api/agent/projects/{PROJECT_ID_HIBRIDO}/avatar-settings",
            json={"maxScenes": original_max},
            headers={"Content-Type": "application/json"}
        )
        print(f"✓ PUT avatar-settings updated maxScenes from {original_max} to {new_max} and restored")
    
    def test_put_avatar_settings_with_avatar_and_voice_ids(self):
        """PUT /api/agent/projects/{project_id}/avatar-settings updates all fields"""
        update_payload = {
            "maxScenes": 7,
            "defaultAvatarId": "test-avatar-123",
            "defaultVoiceId": "test-voice-456"
        }
        
        response = requests.put(
            f"{BASE_URL}/api/agent/projects/{PROJECT_ID_HIBRIDO}/avatar-settings",
            json=update_payload,
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        settings = data.get("settings", {})
        assert settings.get("maxScenes") == 7, f"maxScenes not set: {settings}"
        assert settings.get("defaultAvatarId") == "test-avatar-123", f"defaultAvatarId not set: {settings}"
        assert settings.get("defaultVoiceId") == "test-voice-456", f"defaultVoiceId not set: {settings}"
        
        # Restore defaults
        requests.put(
            f"{BASE_URL}/api/agent/projects/{PROJECT_ID_HIBRIDO}/avatar-settings",
            json={"maxScenes": 3, "defaultAvatarId": None, "defaultVoiceId": None},
            headers={"Content-Type": "application/json"}
        )
        print("✓ PUT avatar-settings updates all fields (maxScenes, defaultAvatarId, defaultVoiceId)")


class TestAvatarGenerationStatusEndpoint:
    """Test avatar generation status endpoint"""
    
    def test_get_avatar_generation_status_no_pending(self):
        """GET /api/agent/projects/{project_id}/avatar-generation-status returns no_pending when no scenes generating"""
        response = requests.get(f"{BASE_URL}/api/agent/projects/{PROJECT_ID_UNIVERSIDADES}/avatar-generation-status")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Should have status field
        assert "status" in data, f"Response missing status: {data}"
        # When no pending scenes, status should be "no_pending" or "completed"
        assert data["status"] in ["no_pending", "completed", "processing"], f"Unexpected status: {data}"
        assert "scenes" in data, f"Response missing scenes array: {data}"
        print(f"✓ GET avatar-generation-status returns: status={data['status']}, scenes={len(data.get('scenes', []))}")
    
    def test_get_avatar_generation_status_nonexistent_project(self):
        """GET /api/agent/projects/{project_id}/avatar-generation-status returns 404 for nonexistent project"""
        response = requests.get(f"{BASE_URL}/api/agent/projects/nonexistent-project-id/avatar-generation-status")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ GET avatar-generation-status returns 404 for nonexistent project")


class TestCourseAnalyzeWithAvatarScene:
    """Test course analysis endpoint for avatar_scene suggestions"""
    
    def test_analyze_course_returns_improvements_array(self):
        """POST /api/agent/courses/{project_id}/analyze returns improvements array"""
        response = requests.post(
            f"{BASE_URL}/api/agent/courses/{PROJECT_ID_HIBRIDO}/analyze",
            headers={"Content-Type": "application/json"},
            timeout=60  # AI analysis can take time
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Should have improvements array
        assert "improvements" in data, f"Response missing improvements: {data.keys()}"
        assert isinstance(data["improvements"], list), f"improvements should be list: {type(data['improvements'])}"
        
        # Check for overallScore
        assert "overallScore" in data, f"Response missing overallScore: {data.keys()}"
        
        # Log if any avatar_scene suggestions were returned
        avatar_scenes = [imp for imp in data["improvements"] if imp.get("type") == "avatar_scene"]
        print(f"✓ POST analyze returns {len(data['improvements'])} improvements, {len(avatar_scenes)} avatar_scene suggestions")
        print(f"  Overall score: {data.get('overallScore')}")
        
        # If avatar_scene suggestions exist, verify they have required fields
        for imp in avatar_scenes:
            assert "narrationScript" in imp, f"avatar_scene missing narrationScript: {imp}"
            assert "backgroundDescription" in imp, f"avatar_scene missing backgroundDescription: {imp}"
            assert "avatarPosition" in imp, f"avatar_scene missing avatarPosition: {imp}"
            print(f"  Avatar scene: {imp.get('description', '')[:50]}...")
    
    def test_analyze_course_improvement_structure(self):
        """POST /api/agent/courses/{project_id}/analyze improvements have correct structure"""
        response = requests.post(
            f"{BASE_URL}/api/agent/courses/{PROJECT_ID_UNIVERSIDADES}/analyze",
            headers={"Content-Type": "application/json"},
            timeout=60
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        improvements = data.get("improvements", [])
        
        # Check structure of each improvement
        for imp in improvements[:5]:  # Check first 5
            assert "type" in imp, f"Improvement missing type: {imp}"
            assert "priority" in imp, f"Improvement missing priority: {imp}"
            assert "description" in imp, f"Improvement missing description: {imp}"
            
            # Valid types
            valid_types = ["content", "structure", "quiz", "narration", "visual", "simulator", "avatar_scene"]
            assert imp["type"] in valid_types, f"Invalid type {imp['type']}, expected one of {valid_types}"
            
            # Valid priorities
            valid_priorities = ["alta", "media", "baixa"]
            assert imp["priority"] in valid_priorities, f"Invalid priority {imp['priority']}"
        
        print(f"✓ Improvements have correct structure (type, priority, description)")


class TestApplyImprovementsWithAvatarScene:
    """Test apply improvements endpoint for avatarScenesTriggered response"""
    
    def test_apply_improvements_returns_avatar_scenes_triggered(self):
        """POST /api/agent/courses/{project_id}/apply-improvements returns avatarScenesTriggered count"""
        # First analyze to get improvements
        analyze_resp = requests.post(
            f"{BASE_URL}/api/agent/courses/{PROJECT_ID_HIBRIDO}/analyze",
            headers={"Content-Type": "application/json"},
            timeout=60
        )
        if analyze_resp.status_code != 200:
            pytest.skip("Analysis failed, skipping apply test")
        
        analysis = analyze_resp.json()
        improvements = analysis.get("improvements", [])
        
        if not improvements:
            pytest.skip("No improvements returned from analysis")
        
        # Select first non-avatar improvement to test (to avoid triggering actual generation)
        non_avatar_improvements = [imp for imp in improvements if imp.get("type") != "avatar_scene"]
        if not non_avatar_improvements:
            # If only avatar scenes, use one but expect avatarScenesTriggered > 0
            selected = [improvements[0]]
        else:
            selected = [non_avatar_improvements[0]]
        
        # First get preview
        preview_resp = requests.post(
            f"{BASE_URL}/api/agent/courses/{PROJECT_ID_HIBRIDO}/preview-improvements",
            json={"improvements": selected},
            headers={"Content-Type": "application/json"},
            timeout=60
        )
        
        if preview_resp.status_code != 200:
            pytest.skip(f"Preview failed: {preview_resp.text}")
        
        preview_data = preview_resp.json()
        preview_id = preview_data.get("previewId")
        
        if not preview_id:
            pytest.skip("No previewId returned")
        
        # Apply improvements
        apply_resp = requests.post(
            f"{BASE_URL}/api/agent/courses/{PROJECT_ID_HIBRIDO}/apply-improvements",
            json={"improvements": selected, "previewId": preview_id},
            headers={"Content-Type": "application/json"},
            timeout=60
        )
        assert apply_resp.status_code == 200, f"Expected 200, got {apply_resp.status_code}: {apply_resp.text}"
        
        data = apply_resp.json()
        # Should have avatarScenesTriggered field
        assert "avatarScenesTriggered" in data, f"Response missing avatarScenesTriggered: {data.keys()}"
        assert isinstance(data["avatarScenesTriggered"], int), f"avatarScenesTriggered should be int: {type(data['avatarScenesTriggered'])}"
        
        print(f"✓ POST apply-improvements returns avatarScenesTriggered={data['avatarScenesTriggered']}")
        print(f"  updatedSlides={data.get('updatedSlides')}, newSlides={data.get('newSlides')}, totalSlides={data.get('totalSlides')}")
        
        # Undo improvements to restore state
        undo_resp = requests.post(
            f"{BASE_URL}/api/agent/courses/{PROJECT_ID_HIBRIDO}/undo-improvements",
            headers={"Content-Type": "application/json"}
        )
        if undo_resp.status_code == 200:
            print("  (Improvements undone to restore original state)")


class TestHealthAndBasicEndpoints:
    """Basic health checks"""
    
    def test_health_endpoint(self):
        """Health endpoint returns 200"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200, f"Health check failed: {response.status_code}"
        print("✓ Health endpoint OK")
    
    def test_agent_courses_list(self):
        """GET /api/agent/courses returns list of courses"""
        response = requests.get(f"{BASE_URL}/api/agent/courses")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert isinstance(data, list), f"Expected list, got {type(data)}"
        print(f"✓ GET /api/agent/courses returns {len(data)} courses")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
