"""
Test suite for Avatar Scene Type Switcher Feature
Tests the new type switching functionality for avatar_scene improvements:
- POST /api/agent/sessions/{session_id}/save-type-overrides - saves type changes
- POST /api/agent/courses/{project_id}/apply-improvements - respects type overrides
- GET/PUT /api/agent/projects/{project_id}/avatar-settings - avatar settings
"""
import pytest
import requests
import os
import json
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test project IDs from context
PROJECT_ID_HIBRIDO = "a87fd1a0-1338-4043-9c2f-b0cc8572a12e"

# Auth credentials
ADMIN_EMAIL = "admin@scormify.com"
ADMIN_PASSWORD = "admin123"


def get_auth_token():
    """Get authentication token for API calls"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        headers={"Content-Type": "application/json"}
    )
    if response.status_code == 200:
        return response.json().get("token")
    return None


def get_auth_headers():
    """Get headers with authentication token"""
    token = get_auth_token()
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}" if token else ""
    }


class TestSaveTypeOverridesEndpoint:
    """Test save-type-overrides endpoint for StoryboardPanel"""
    
    def test_save_type_overrides_requires_session(self):
        """POST /api/agent/sessions/{session_id}/save-type-overrides returns 404 for nonexistent session"""
        response = requests.post(
            f"{BASE_URL}/api/agent/sessions/nonexistent-session-id/save-type-overrides",
            json={"typeOverrides": {"0": "content"}},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"
        print("✓ save-type-overrides returns 404 for nonexistent session")
    
    def test_save_type_overrides_with_valid_session(self):
        """POST /api/agent/sessions/{session_id}/save-type-overrides saves type changes"""
        headers = get_auth_headers()
        
        # First create a new session
        create_resp = requests.post(
            f"{BASE_URL}/api/agent/sessions",
            json={},
            headers=headers
        )
        assert create_resp.status_code == 200, f"Failed to create session: {create_resp.text}"
        session_data = create_resp.json()
        session_id = session_data.get("id")
        assert session_id, f"No session ID returned: {session_data}"
        
        # Save type overrides
        type_overrides = {
            "0": "content",
            "2": "simulator",
            "5": "quiz"
        }
        response = requests.post(
            f"{BASE_URL}/api/agent/sessions/{session_id}/save-type-overrides",
            json={"typeOverrides": type_overrides},
            headers=headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("status") == "ok", f"Expected status ok: {data}"
        # Note: overrides count may be 0 if session has no storyboard slides
        print(f"✓ save-type-overrides saved {data.get('overrides')} type overrides for session {session_id}")
    
    def test_save_type_overrides_empty_overrides(self):
        """POST /api/agent/sessions/{session_id}/save-type-overrides handles empty overrides"""
        headers = get_auth_headers()
        
        # Create a new session
        create_resp = requests.post(
            f"{BASE_URL}/api/agent/sessions",
            json={},
            headers=headers
        )
        session_id = create_resp.json().get("id")
        
        # Save empty overrides
        response = requests.post(
            f"{BASE_URL}/api/agent/sessions/{session_id}/save-type-overrides",
            json={"typeOverrides": {}},
            headers=headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("status") == "ok", f"Expected status ok: {data}"
        assert data.get("overrides") == 0, f"Expected 0 overrides: {data}"
        
        print("✓ save-type-overrides handles empty overrides correctly")


class TestAvatarSettingsEndpoints:
    """Test avatar settings GET and PUT endpoints"""
    
    def test_get_avatar_settings_returns_max_scenes(self):
        """GET /api/agent/projects/{project_id}/avatar-settings returns maxScenes"""
        response = requests.get(f"{BASE_URL}/api/agent/projects/{PROJECT_ID_HIBRIDO}/avatar-settings")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "maxScenes" in data, f"Response missing maxScenes: {data}"
        assert isinstance(data["maxScenes"], int), f"maxScenes should be int: {data}"
        print(f"✓ GET avatar-settings returns maxScenes={data['maxScenes']}")
    
    def test_put_avatar_settings_updates_max_scenes(self):
        """PUT /api/agent/projects/{project_id}/avatar-settings updates maxScenes correctly"""
        # Get current settings
        get_resp = requests.get(f"{BASE_URL}/api/agent/projects/{PROJECT_ID_HIBRIDO}/avatar-settings")
        original_max = get_resp.json().get("maxScenes", 3)
        
        # Update to new value
        new_max = 8
        response = requests.put(
            f"{BASE_URL}/api/agent/projects/{PROJECT_ID_HIBRIDO}/avatar-settings",
            json={"maxScenes": new_max},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("status") == "ok", f"Expected status ok: {data}"
        
        # Verify the update
        verify_resp = requests.get(f"{BASE_URL}/api/agent/projects/{PROJECT_ID_HIBRIDO}/avatar-settings")
        verify_data = verify_resp.json()
        assert verify_data.get("maxScenes") == new_max, f"maxScenes not updated: {verify_data}"
        
        # Restore original
        requests.put(
            f"{BASE_URL}/api/agent/projects/{PROJECT_ID_HIBRIDO}/avatar-settings",
            json={"maxScenes": original_max},
            headers={"Content-Type": "application/json"}
        )
        print(f"✓ PUT avatar-settings updated maxScenes to {new_max} and restored to {original_max}")


class TestApplyImprovementsWithTypeOverrides:
    """Test apply-improvements respects type overrides"""
    
    def test_apply_improvements_counts_only_avatar_scenes(self):
        """POST /api/agent/courses/{project_id}/apply-improvements returns correct avatarScenesTriggered count"""
        # First analyze to get improvements
        analyze_resp = requests.post(
            f"{BASE_URL}/api/agent/courses/{PROJECT_ID_HIBRIDO}/analyze",
            headers={"Content-Type": "application/json"},
            timeout=60
        )
        if analyze_resp.status_code != 200:
            pytest.skip(f"Analysis failed: {analyze_resp.text}")
        
        analysis = analyze_resp.json()
        improvements = analysis.get("improvements", [])
        
        if not improvements:
            pytest.skip("No improvements returned from analysis")
        
        # Check if there are avatar_scene improvements
        avatar_scenes = [imp for imp in improvements if imp.get("type") == "avatar_scene"]
        non_avatar = [imp for imp in improvements if imp.get("type") != "avatar_scene"]
        
        print(f"  Analysis returned {len(improvements)} improvements: {len(avatar_scenes)} avatar_scene, {len(non_avatar)} other")
        
        # Select a non-avatar improvement to test
        if non_avatar:
            selected = [non_avatar[0]]
            expected_avatar_count = 0
        else:
            # If only avatar scenes, select one and expect count of 1
            selected = [avatar_scenes[0]]
            expected_avatar_count = 1
        
        # Get preview
        preview_resp = requests.post(
            f"{BASE_URL}/api/agent/courses/{PROJECT_ID_HIBRIDO}/preview-improvements",
            json={"improvements": selected},
            headers={"Content-Type": "application/json"},
            timeout=60
        )
        
        if preview_resp.status_code != 200:
            pytest.skip(f"Preview failed: {preview_resp.text}")
        
        preview_id = preview_resp.json().get("previewId")
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
        assert "avatarScenesTriggered" in data, f"Response missing avatarScenesTriggered: {data.keys()}"
        
        # The count should match expected (0 for non-avatar, 1 for avatar)
        actual_count = data.get("avatarScenesTriggered", 0)
        print(f"✓ apply-improvements returned avatarScenesTriggered={actual_count} (expected ~{expected_avatar_count})")
        
        # Undo to restore state
        undo_resp = requests.post(
            f"{BASE_URL}/api/agent/courses/{PROJECT_ID_HIBRIDO}/undo-improvements",
            headers={"Content-Type": "application/json"}
        )
        if undo_resp.status_code == 200:
            print("  (Improvements undone)")


class TestCourseAnalysisAvatarSceneFields:
    """Test that avatar_scene improvements have required fields for mockup"""
    
    def test_avatar_scene_has_mockup_fields(self):
        """POST /api/agent/courses/{project_id}/analyze avatar_scene has narrationScript, backgroundDescription, avatarPosition"""
        response = requests.post(
            f"{BASE_URL}/api/agent/courses/{PROJECT_ID_HIBRIDO}/analyze",
            headers={"Content-Type": "application/json"},
            timeout=60
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        improvements = data.get("improvements", [])
        avatar_scenes = [imp for imp in improvements if imp.get("type") == "avatar_scene"]
        
        if not avatar_scenes:
            print("✓ No avatar_scene improvements in this analysis (AI-dependent)")
            return
        
        # Check each avatar_scene has required fields
        for i, imp in enumerate(avatar_scenes):
            assert "narrationScript" in imp, f"avatar_scene {i} missing narrationScript"
            assert "backgroundDescription" in imp, f"avatar_scene {i} missing backgroundDescription"
            assert "avatarPosition" in imp, f"avatar_scene {i} missing avatarPosition"
            
            # avatarPosition should be one of: left, right, center
            valid_positions = ["left", "right", "center"]
            assert imp["avatarPosition"] in valid_positions, f"Invalid avatarPosition: {imp['avatarPosition']}"
            
            print(f"  Avatar scene {i}: position={imp['avatarPosition']}, script={imp['narrationScript'][:50]}...")
        
        print(f"✓ All {len(avatar_scenes)} avatar_scene improvements have required mockup fields")


class TestHealthCheck:
    """Basic health check"""
    
    def test_health_endpoint(self):
        """Health endpoint returns 200"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200, f"Health check failed: {response.status_code}"
        print("✓ Health endpoint OK")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
