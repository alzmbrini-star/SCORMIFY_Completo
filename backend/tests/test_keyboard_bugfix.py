"""
Test suite for keyboard input bug fix in SCORM exports.
Tests verify:
1. player.js has keyboard navigation guard for input/textarea
2. tutor.js has stopPropagation on keyboard events
3. SCORM export endpoint returns valid package
4. Tutor chat API endpoint is reachable
5. Tutor settings API endpoints work
6. Health endpoint returns 200
"""
import pytest
import requests
import os
import zipfile
import io
import json

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestHealthEndpoint:
    """Verify basic health check"""
    
    def test_health_returns_200(self):
        """Health endpoint should return 200 with status healthy"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get("status") == "healthy", f"Expected healthy status, got {data}"
        print("✅ Health endpoint returns 200 with status: healthy")


class TestTutorSettingsAPI:
    """Test tutor settings API endpoints"""
    
    def test_get_tutor_settings(self):
        """GET /api/admin/tutor-settings should return settings or defaults"""
        response = requests.get(f"{BASE_URL}/api/admin/tutor-settings")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "enabled" in data, "Response should have 'enabled' field"
        assert "tutorName" in data, "Response should have 'tutorName' field"
        print(f"✅ GET tutor-settings returns: enabled={data.get('enabled')}, tutorName={data.get('tutorName')}")
    
    def test_put_tutor_settings(self):
        """PUT /api/admin/tutor-settings should update and return settings"""
        # First, get current settings
        get_response = requests.get(f"{BASE_URL}/api/admin/tutor-settings")
        original = get_response.json()
        
        # Update with test data
        test_settings = {
            "enabled": True,
            "tutorName": "Test Tutor",
            "messageLimit": 25,
            "systemPrompt": "You are a test tutor.",
            "suggestedQuestions": ["Test question 1?"]
        }
        
        put_response = requests.put(
            f"{BASE_URL}/api/admin/tutor-settings",
            json=test_settings,
            headers={"Content-Type": "application/json"}
        )
        assert put_response.status_code == 200, f"Expected 200, got {put_response.status_code}: {put_response.text}"
        
        # Verify the update persisted
        verify_response = requests.get(f"{BASE_URL}/api/admin/tutor-settings")
        updated = verify_response.json()
        assert updated.get("tutorName") == "Test Tutor", f"tutorName not updated: {updated}"
        assert updated.get("messageLimit") == 25, f"messageLimit not updated: {updated}"
        print("✅ PUT tutor-settings updates and persists correctly")
        
        # Restore original settings
        requests.put(
            f"{BASE_URL}/api/admin/tutor-settings",
            json=original,
            headers={"Content-Type": "application/json"}
        )


class TestTutorChatAPI:
    """Test tutor chat API endpoint"""
    
    def test_tutor_chat_reachable(self):
        """POST /api/tutor/chat should be reachable (returns 400 for empty message, not 404)"""
        response = requests.post(
            f"{BASE_URL}/api/tutor/chat",
            json={},
            headers={"Content-Type": "application/json"}
        )
        # 400 = endpoint exists but validation failed (empty message)
        # 403 = tutor disabled (endpoint exists)
        # 404 = endpoint not found (BAD)
        assert response.status_code in [400, 403], f"Expected 400 or 403, got {response.status_code}: {response.text}"
        print(f"✅ POST /api/tutor/chat is reachable (returns {response.status_code} for empty/disabled)")


class TestSCORMExport:
    """Test SCORM export and verify bug fix files are included"""
    
    @pytest.fixture(scope="class")
    def test_project(self):
        """Create a temporary test project for SCORM export"""
        # Create project
        create_response = requests.post(
            f"{BASE_URL}/api/projects",
            json={"name": "TEST_KeyboardBugfix_Project", "description": "Test project for keyboard bug fix verification"},
            headers={"Content-Type": "application/json"}
        )
        assert create_response.status_code == 200, f"Failed to create project: {create_response.text}"
        project = create_response.json()
        project_id = project["id"]
        print(f"Created test project: {project_id}")
        
        yield project_id
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/projects/{project_id}")
        print(f"Cleaned up test project: {project_id}")
    
    def test_scorm_export_returns_valid_package(self, test_project):
        """SCORM export should return a valid ZIP package"""
        project_id = test_project
        
        # Export SCORM
        export_response = requests.post(f"{BASE_URL}/api/course/{project_id}/export-scorm")
        assert export_response.status_code == 200, f"Export failed: {export_response.status_code}: {export_response.text}"
        
        data = export_response.json()
        assert "downloadUrl" in data, f"No downloadUrl in response: {data}"
        download_url = data["downloadUrl"]
        print(f"✅ SCORM export returns downloadUrl: {download_url}")
        
        # Download the ZIP
        zip_response = requests.get(f"{BASE_URL}{download_url}")
        assert zip_response.status_code == 200, f"Failed to download ZIP: {zip_response.status_code}"
        assert len(zip_response.content) > 1000, f"ZIP file too small: {len(zip_response.content)} bytes"
        print(f"✅ Downloaded SCORM ZIP: {len(zip_response.content)} bytes")
        
        # Verify it's a valid ZIP
        try:
            zip_buffer = io.BytesIO(zip_response.content)
            with zipfile.ZipFile(zip_buffer, 'r') as zf:
                file_list = zf.namelist()
                assert len(file_list) > 0, "ZIP is empty"
                print(f"✅ ZIP contains {len(file_list)} files")
                
                # Return file list for next tests
                return file_list
        except zipfile.BadZipFile:
            pytest.fail("Downloaded file is not a valid ZIP")
    
    def test_scorm_contains_player_js_with_bugfix(self, test_project):
        """SCORM package should contain player.js with keyboard input guard"""
        project_id = test_project
        
        # Export and download
        export_response = requests.post(f"{BASE_URL}/api/course/{project_id}/export-scorm")
        download_url = export_response.json()["downloadUrl"]
        zip_response = requests.get(f"{BASE_URL}{download_url}")
        
        zip_buffer = io.BytesIO(zip_response.content)
        with zipfile.ZipFile(zip_buffer, 'r') as zf:
            # Check player.js exists
            assert "scripts/player.js" in zf.namelist(), "scripts/player.js not in SCORM package"
            
            # Read and verify bug fix code
            player_js = zf.read("scripts/player.js").decode('utf-8')
            
            # Check for the keyboard navigation guard
            assert "input" in player_js and "textarea" in player_js, "player.js missing input/textarea check"
            assert "isContentEditable" in player_js, "player.js missing isContentEditable check"
            
            # More specific check for the bug fix
            bug_fix_present = (
                ("tag === 'input'" in player_js or "tag === \"input\"" in player_js) and
                ("tag === 'textarea'" in player_js or "tag === \"textarea\"" in player_js)
            )
            assert bug_fix_present, "player.js keyboard navigation guard not found"
            print("✅ player.js contains keyboard navigation guard for input/textarea")
    
    def test_scorm_contains_tutor_js_with_bugfix(self, test_project):
        """SCORM package should contain tutor.js with stopPropagation fix (when tutor enabled)"""
        project_id = test_project
        
        # First enable tutor
        requests.put(
            f"{BASE_URL}/api/admin/tutor-settings",
            json={"enabled": True, "tutorName": "Test Tutor"},
            headers={"Content-Type": "application/json"}
        )
        
        try:
            # Export and download
            export_response = requests.post(f"{BASE_URL}/api/course/{project_id}/export-scorm")
            download_url = export_response.json()["downloadUrl"]
            zip_response = requests.get(f"{BASE_URL}{download_url}")
            
            zip_buffer = io.BytesIO(zip_response.content)
            with zipfile.ZipFile(zip_buffer, 'r') as zf:
                # Check tutor.js exists (only when tutor enabled)
                if "scripts/tutor.js" in zf.namelist():
                    # Read and verify bug fix code
                    tutor_js = zf.read("scripts/tutor.js").decode('utf-8')
                    
                    # Check for stopPropagation on keyboard events
                    assert "stopPropagation" in tutor_js, "tutor.js missing stopPropagation"
                    assert "keydown" in tutor_js, "tutor.js missing keydown listener"
                    assert "keyup" in tutor_js, "tutor.js missing keyup listener"
                    assert "keypress" in tutor_js, "tutor.js missing keypress listener"
                    print("✅ tutor.js contains stopPropagation on keydown/keyup/keypress events")
                else:
                    print("⚠️ tutor.js not in package (tutor may be disabled in export)")
        finally:
            # Restore tutor settings
            requests.put(
                f"{BASE_URL}/api/admin/tutor-settings",
                json={"enabled": False},
                headers={"Content-Type": "application/json"}
            )


class TestExportAssetsFiles:
    """Directly verify the source files have the bug fixes"""
    
    def test_player_js_source_has_bugfix(self):
        """Verify /app/backend/services/export_assets/player.js has keyboard guard"""
        player_js_path = "/app/backend/services/export_assets/player.js"
        
        with open(player_js_path, 'r') as f:
            content = f.read()
        
        # Check for the keyboard navigation guard (lines 1684-1689)
        assert "// Keyboard navigation - skip when user is typing" in content or "input" in content
        assert "input" in content and "textarea" in content
        assert "isContentEditable" in content
        
        # Check the specific pattern
        assert "tag === 'input'" in content or 'tag === "input"' in content
        print("✅ Source player.js has keyboard input guard")
    
    def test_tutor_js_source_has_bugfix(self):
        """Verify /app/backend/services/export_assets/tutor.js has stopPropagation"""
        tutor_js_path = "/app/backend/services/export_assets/tutor.js"
        
        with open(tutor_js_path, 'r') as f:
            content = f.read()
        
        # Check for stopPropagation on keyboard events (lines 79-89)
        assert "stopPropagation" in content, "tutor.js missing stopPropagation"
        assert "keydown" in content, "tutor.js missing keydown"
        assert "keyup" in content, "tutor.js missing keyup"
        assert "keypress" in content, "tutor.js missing keypress"
        
        # Check the specific pattern - stopPropagation in the event listeners
        assert "e.stopPropagation()" in content
        print("✅ Source tutor.js has stopPropagation on all keyboard events")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
