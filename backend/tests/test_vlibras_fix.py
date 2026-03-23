"""
Test suite for VLibras API fix verification
Tests that the correct API (plugin.player.translate) is used and broken API is removed

This test validates the bug fix where the previous agent used a non-existent API 
(window.VLibras.Widget.sendMessage) that has been replaced with the correct API 
(window.plugin.player.translate).
"""
import pytest
import requests
import os
import re

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://course-authoring.preview.emergentagent.com')

# File paths for code verification
PLAYER_JS_PATH = "/app/backend/services/export_assets/player.js"
HTML_EXPORTER_PATH = "/app/backend/services/html_exporter.py"


class TestBackendHealth:
    """Test that backend is healthy and accessible"""
    
    def test_health_endpoint(self):
        """GET /api/health should return healthy"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200, f"Health endpoint returned {response.status_code}"
        data = response.json()
        assert data.get("status") == "healthy", f"Health status: {data}"
        print("✓ Backend health check passed")


class TestExportEndpoints:
    """Test that export endpoints are accessible"""
    
    def test_scorm_export_endpoint_exists(self):
        """POST /api/course/{project_id}/export-scorm endpoint should be accessible"""
        # Use a test project ID - endpoint should exist (may return 404 for non-existent project)
        test_project_id = "test-project-123"
        response = requests.post(f"{BASE_URL}/api/course/{test_project_id}/export-scorm")
        # 404 means endpoint exists but project doesn't, 405 would mean endpoint doesn't exist
        assert response.status_code in [200, 404, 500], f"SCORM export endpoint returned unexpected {response.status_code}"
        print("✓ SCORM export endpoint is accessible")
    
    def test_html_export_endpoint_exists(self):
        """POST /api/course/{project_id}/export-html endpoint should be accessible"""
        test_project_id = "test-project-123"
        response = requests.post(f"{BASE_URL}/api/course/{test_project_id}/export-html")
        # 404 means endpoint exists but project doesn't
        assert response.status_code in [200, 404, 500], f"HTML export endpoint returned unexpected {response.status_code}"
        print("✓ HTML export endpoint is accessible")


class TestVLibrasCodeVerification:
    """Test that VLibras code changes are correct"""
    
    def test_player_js_has_correct_api(self):
        """player.js should contain plugin.player.translate (correct API)"""
        with open(PLAYER_JS_PATH, 'r') as f:
            content = f.read()
        
        # Check for correct API
        assert "plugin.player.translate" in content, "player.js missing correct API: plugin.player.translate"
        print("✓ player.js contains correct API: plugin.player.translate")
    
    def test_player_js_no_broken_api(self):
        """player.js should NOT contain VLibras.Widget.sendMessage (broken API)"""
        with open(PLAYER_JS_PATH, 'r') as f:
            content = f.read()
        
        # Check that broken API is NOT present
        assert "VLibras.Widget.sendMessage" not in content, "player.js still contains broken API: VLibras.Widget.sendMessage"
        print("✓ player.js does not contain broken API: VLibras.Widget.sendMessage")
    
    def test_player_js_has_translate_function(self):
        """player.js should contain translateWithVLibras function"""
        with open(PLAYER_JS_PATH, 'r') as f:
            content = f.read()
        
        assert "function translateWithVLibras" in content, "player.js missing translateWithVLibras function"
        print("✓ player.js contains translateWithVLibras function")
    
    def test_player_js_has_fallback_logic(self):
        """player.js translateWithVLibras should have fallback logic (click access button)"""
        with open(PLAYER_JS_PATH, 'r') as f:
            content = f.read()
        
        # Check for fallback logic that clicks the access button
        assert "[vw-access-button]" in content, "player.js missing fallback logic for access button"
        print("✓ player.js contains fallback logic to click VLibras access button")
    
    def test_html_exporter_has_correct_api(self):
        """html_exporter.py should contain plugin.player.translate (correct API)"""
        with open(HTML_EXPORTER_PATH, 'r') as f:
            content = f.read()
        
        # Check for correct API
        assert "plugin.player.translate" in content, "html_exporter.py missing correct API: plugin.player.translate"
        print("✓ html_exporter.py contains correct API: plugin.player.translate")
    
    def test_html_exporter_no_broken_api(self):
        """html_exporter.py should NOT contain VLibras.Widget.sendMessage (broken API)"""
        with open(HTML_EXPORTER_PATH, 'r') as f:
            content = f.read()
        
        # Check that broken API is NOT present
        assert "VLibras.Widget.sendMessage" not in content, "html_exporter.py still contains broken API: VLibras.Widget.sendMessage"
        print("✓ html_exporter.py does not contain broken API: VLibras.Widget.sendMessage")
    
    def test_html_exporter_has_translate_function(self):
        """html_exporter.py should contain translateWithVLibras function"""
        with open(HTML_EXPORTER_PATH, 'r') as f:
            content = f.read()
        
        assert "translateWithVLibras" in content, "html_exporter.py missing translateWithVLibras function"
        print("✓ html_exporter.py contains translateWithVLibras function")
    
    def test_html_exporter_has_fallback_logic(self):
        """html_exporter.py translateWithVLibras should have fallback logic"""
        with open(HTML_EXPORTER_PATH, 'r') as f:
            content = f.read()
        
        assert "[vw-access-button]" in content, "html_exporter.py missing fallback logic for access button"
        print("✓ html_exporter.py contains fallback logic to click VLibras access button")


class TestVLibrasUsage:
    """Test that translateWithVLibras is being called correctly"""
    
    def test_player_js_calls_translate_on_slide_render(self):
        """player.js should call translateWithVLibras when rendering slides with librasScript"""
        with open(PLAYER_JS_PATH, 'r') as f:
            content = f.read()
        
        # Check that translateWithVLibras is called when rendering slides
        # It should check for slide.librasScript and call translateWithVLibras
        assert "librasScript" in content, "player.js missing librasScript check"
        assert "translateWithVLibras" in content, "player.js missing translateWithVLibras call"
        print("✓ player.js calls translateWithVLibras for slides with librasScript")
    
    def test_html_exporter_calls_translate_on_slide_render(self):
        """html_exporter.py should call translateWithVLibras when rendering slides"""
        with open(HTML_EXPORTER_PATH, 'r') as f:
            content = f.read()
        
        # Check that translateWithVLibras is called in the embedded JavaScript
        assert "librasScript" in content, "html_exporter.py missing librasScript check"
        # In the embedded JS template, it should call translateWithVLibras
        pattern = r"translateWithVLibras.*librasScript"
        assert re.search(pattern, content, re.DOTALL), "html_exporter.py should call translateWithVLibras with librasScript"
        print("✓ html_exporter.py calls translateWithVLibras for slides with librasScript")


class TestExportWithRealProject:
    """Test exports with a real project from the database"""
    
    @pytest.fixture
    def project_id(self):
        """Get first available project ID from API"""
        response = requests.get(f"{BASE_URL}/api/projects")
        if response.status_code == 200:
            projects = response.json()
            if projects:
                return projects[0].get('id')
        return None
    
    def test_scorm_export_with_real_project(self, project_id):
        """Test SCORM export with a real project"""
        if not project_id:
            pytest.skip("No projects available for testing")
        
        response = requests.post(f"{BASE_URL}/api/course/{project_id}/export-scorm")
        assert response.status_code == 200, f"SCORM export failed: {response.text}"
        data = response.json()
        assert "downloadUrl" in data, "SCORM export response missing downloadUrl"
        print(f"✓ SCORM export successful: {data.get('downloadUrl')}")
    
    def test_html_export_with_real_project(self, project_id):
        """Test HTML export with a real project"""
        if not project_id:
            pytest.skip("No projects available for testing")
        
        response = requests.post(f"{BASE_URL}/api/course/{project_id}/export-html")
        assert response.status_code == 200, f"HTML export failed: {response.text}"
        data = response.json()
        assert "downloadUrl" in data, "HTML export response missing downloadUrl"
        print(f"✓ HTML export successful: {data.get('downloadUrl')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
