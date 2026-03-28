"""
Test cases for:
1. AI Tutor URL bug fix - tutor apiUrl should use current environment URL in SCORM/HTML exports
2. Fix Simulators button - POST /api/projects/{project_id}/fix-simulators endpoint

These tests verify the fixes implemented in:
- backend/routes/export.py - line 154: Changed to always use _get_external_url() first for tutor apiUrl
- backend/routes/projects.py - line 144: fix_simulators endpoint returning {status, fixed, message}
"""

import pytest
import requests
import os
import zipfile
import io
import json
import re

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://avatar-scenes.preview.emergentagent.com')
TEST_PROJECT_ID = "d3387a1f-6c52-4740-a127-a2e733adf663"  # TestSim project
EXPECTED_TUTOR_URL = "https://avatar-scenes.preview.emergentagent.com"


class TestFixSimulatorsEndpoint:
    """Test the fix-simulators endpoint"""
    
    def test_fix_simulators_endpoint_exists(self):
        """Test that POST /api/projects/{project_id}/fix-simulators endpoint exists and returns proper response"""
        response = requests.post(f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/fix-simulators")
        
        # Should return 200 OK
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Verify response structure
        data = response.json()
        assert "status" in data, "Response should contain 'status' field"
        assert "fixed" in data, "Response should contain 'fixed' field"
        assert "message" in data, "Response should contain 'message' field"
        
        # Verify values
        assert data["status"] == "ok", f"Expected status 'ok', got {data['status']}"
        assert isinstance(data["fixed"], int), f"'fixed' should be an integer, got {type(data['fixed'])}"
        print(f"Fix simulators response: {data}")
    
    def test_fix_simulators_returns_zero_for_no_static_simulators(self):
        """Test that fix-simulators returns fixed=0 when no static simulators exist"""
        response = requests.post(f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/fix-simulators")
        
        assert response.status_code == 200
        data = response.json()
        
        # TestSim project has no static simulators, so fixed should be 0
        assert data["fixed"] == 0, f"Expected fixed=0 for TestSim project, got {data['fixed']}"
        assert "Nenhum simulador estático encontrado" in data["message"] or data["fixed"] == 0
        print(f"Correctly returned: {data['message']}")
    
    def test_fix_simulators_404_for_nonexistent_project(self):
        """Test that fix-simulators returns 404 for non-existent project"""
        fake_project_id = "00000000-0000-0000-0000-000000000000"
        response = requests.post(f"{BASE_URL}/api/projects/{fake_project_id}/fix-simulators")
        
        assert response.status_code == 404, f"Expected 404 for non-existent project, got {response.status_code}"


class TestSCORMExportTutorUrl:
    """Test that SCORM export includes correct tutor apiUrl from current environment"""
    
    def test_scorm_export_returns_download_url(self):
        """Test that SCORM export endpoint works and returns downloadUrl"""
        response = requests.post(f"{BASE_URL}/api/course/{TEST_PROJECT_ID}/export-scorm")
        
        assert response.status_code == 200, f"SCORM export failed: {response.status_code} - {response.text}"
        
        data = response.json()
        assert "downloadUrl" in data, "Response should contain 'downloadUrl'"
        assert "jobId" in data, "Response should contain 'jobId'"
        
        print(f"SCORM export response: jobId={data['jobId']}, downloadUrl={data['downloadUrl']}")
        return data["downloadUrl"]
    
    def test_scorm_export_tutor_url_is_correct(self):
        """Test that SCORM export contains correct tutor apiUrl in course.json"""
        # First, export SCORM
        export_response = requests.post(f"{BASE_URL}/api/course/{TEST_PROJECT_ID}/export-scorm")
        assert export_response.status_code == 200, f"SCORM export failed: {export_response.text}"
        
        download_url = export_response.json()["downloadUrl"]
        
        # Download the SCORM ZIP
        zip_response = requests.get(f"{BASE_URL}{download_url}")
        assert zip_response.status_code == 200, f"Failed to download SCORM ZIP: {zip_response.status_code}"
        
        # Extract and check course.json
        with zipfile.ZipFile(io.BytesIO(zip_response.content)) as zf:
            # Check if course.json exists
            assert "course.json" in zf.namelist(), "course.json not found in SCORM package"
            
            # Read course.json
            course_json_content = zf.read("course.json").decode('utf-8')
            course_data = json.loads(course_json_content)
            
            # Check tutor settings if present
            if "tutorConfig" in course_data and course_data["tutorConfig"]:
                tutor_config = course_data["tutorConfig"]
                if tutor_config.get("enabled"):
                    api_url = tutor_config.get("apiUrl", "")
                    print(f"Tutor apiUrl in SCORM: {api_url}")
                    
                    # Verify it's the current environment URL
                    assert api_url == EXPECTED_TUTOR_URL, \
                        f"Tutor apiUrl should be '{EXPECTED_TUTOR_URL}', got '{api_url}'"
                else:
                    print("Tutor is disabled in course.json")
            else:
                print("No tutorConfig in course.json (tutor may not be enabled)")
    
    def test_scorm_player_js_exists(self):
        """Test that SCORM package contains player.js"""
        export_response = requests.post(f"{BASE_URL}/api/course/{TEST_PROJECT_ID}/export-scorm")
        assert export_response.status_code == 200
        
        download_url = export_response.json()["downloadUrl"]
        zip_response = requests.get(f"{BASE_URL}{download_url}")
        assert zip_response.status_code == 200
        
        with zipfile.ZipFile(io.BytesIO(zip_response.content)) as zf:
            assert "scripts/player.js" in zf.namelist(), "scripts/player.js not found in SCORM package"
            print("SCORM package contains scripts/player.js")


class TestHTMLExportTutorUrl:
    """Test that HTML export includes correct tutor apiUrl from current environment"""
    
    def test_html_export_returns_download_url(self):
        """Test that HTML export endpoint works and returns downloadUrl"""
        response = requests.post(f"{BASE_URL}/api/course/{TEST_PROJECT_ID}/export-html")
        
        assert response.status_code == 200, f"HTML export failed: {response.status_code} - {response.text}"
        
        data = response.json()
        assert "downloadUrl" in data, "Response should contain 'downloadUrl'"
        
        print(f"HTML export response: downloadUrl={data['downloadUrl']}")
        return data["downloadUrl"]
    
    def test_html_export_tutor_url_is_correct(self):
        """Test that HTML export contains correct tutor apiUrl"""
        # First, export HTML
        export_response = requests.post(f"{BASE_URL}/api/course/{TEST_PROJECT_ID}/export-html")
        assert export_response.status_code == 200, f"HTML export failed: {export_response.text}"
        
        download_url = export_response.json()["downloadUrl"]
        
        # Download the HTML file
        html_response = requests.get(f"{BASE_URL}{download_url}")
        assert html_response.status_code == 200, f"Failed to download HTML: {html_response.status_code}"
        
        html_content = html_response.text
        
        # Check for tutor configuration in the HTML
        # The tutor config is embedded in the HTML as JavaScript
        if "tutorConfig" in html_content or "apiUrl" in html_content:
            # Look for apiUrl pattern
            api_url_match = re.search(r'apiUrl["\']?\s*[:=]\s*["\']([^"\']+)["\']', html_content)
            if api_url_match:
                api_url = api_url_match.group(1)
                print(f"Tutor apiUrl in HTML: {api_url}")
                
                # Verify it's the current environment URL
                assert api_url == EXPECTED_TUTOR_URL, \
                    f"Tutor apiUrl should be '{EXPECTED_TUTOR_URL}', got '{api_url}'"
            else:
                print("apiUrl pattern not found in HTML (tutor may not be enabled)")
        else:
            print("No tutor configuration found in HTML export")


class TestExportUrlFunction:
    """Test the _get_external_url function behavior indirectly through exports"""
    
    def test_export_uses_environment_url(self):
        """Verify that exports use the current environment URL, not stale DB values"""
        # This test verifies the fix in export.py line 154
        # The fix prioritizes _get_external_url() over DB settings
        
        # Export SCORM and check the URL
        export_response = requests.post(f"{BASE_URL}/api/course/{TEST_PROJECT_ID}/export-scorm")
        assert export_response.status_code == 200
        
        download_url = export_response.json()["downloadUrl"]
        zip_response = requests.get(f"{BASE_URL}{download_url}")
        assert zip_response.status_code == 200
        
        with zipfile.ZipFile(io.BytesIO(zip_response.content)) as zf:
            course_json_content = zf.read("course.json").decode('utf-8')
            course_data = json.loads(course_json_content)
            
            # If tutor is configured, verify the URL
            if course_data.get("tutorConfig", {}).get("enabled"):
                api_url = course_data["tutorConfig"].get("apiUrl", "")
                
                # The URL should NOT be a stale URL from a previous fork
                # It should be the current environment URL
                assert "preview.emergentagent.com" in api_url, \
                    f"apiUrl should contain current environment domain, got: {api_url}"
                
                # Specifically check it's the expected URL
                assert api_url == EXPECTED_TUTOR_URL, \
                    f"apiUrl should be '{EXPECTED_TUTOR_URL}', got '{api_url}'"
                
                print(f"✓ Export correctly uses environment URL: {api_url}")
            else:
                print("Tutor not enabled - URL check skipped")


class TestProjectEndpoints:
    """Test basic project endpoints to ensure they work"""
    
    def test_get_project(self):
        """Test GET /api/projects/{project_id}"""
        response = requests.get(f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}")
        
        assert response.status_code == 200, f"Failed to get project: {response.status_code}"
        
        data = response.json()
        assert data["id"] == TEST_PROJECT_ID
        assert data["name"] == "TestSim"
        print(f"Project: {data['name']}, ID: {data['id']}")
    
    def test_list_projects(self):
        """Test GET /api/projects"""
        response = requests.get(f"{BASE_URL}/api/projects")
        
        assert response.status_code == 200, f"Failed to list projects: {response.status_code}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"Found {len(data)} projects")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
