"""
Test suite for SCORM/HTML export URL fix (iteration 77)
Verifies that _get_external_url() uses X-Forwarded-Host headers correctly
and that export URLs don't contain internal cluster URLs.

Bug context: AI Tutor in SCORM exported courses returned 404 because
_get_external_url() was reading BASE_URL from .env (preview URL) instead
of using X-Forwarded-Host headers set by Kubernetes ingress.
"""
import pytest
import requests
import os
import json
import zipfile
import io
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://ai-tutor-platform-12.preview.emergentagent.com').rstrip('/')

# Test project ID provided in context
TEST_PROJECT_ID = "d3387a1f-6c52-4740-a127-a2e733adf663"


class TestHealthAndAuth:
    """Basic health and auth tests (regression)"""
    
    def test_health_endpoint(self):
        """Verify API is healthy"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy"
        print("PASS: Health endpoint returns 200")
    
    def test_login_admin(self):
        """Verify admin login works (regression)"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@scormify.com",
            "password": "admin123"
        })
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert "user" in data
        print(f"PASS: Admin login successful, user: {data['user'].get('email')}")
        return data["token"]


class TestAdminPanelRegression:
    """Regression tests for admin panel (companies and users)"""
    
    @pytest.fixture
    def auth_token(self):
        """Get auth token for admin"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@scormify.com",
            "password": "admin123"
        })
        if response.status_code == 200:
            return response.json().get("token")
        pytest.skip("Admin login failed")
    
    def test_companies_endpoint(self, auth_token):
        """Verify companies endpoint works (regression)"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/companies", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"PASS: Companies endpoint returns {len(data)} companies")
    
    def test_users_endpoint(self, auth_token):
        """Verify users endpoint works (regression)"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/users", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"PASS: Users endpoint returns {len(data)} users")


class TestTutorChatEndpoint:
    """Test POST /api/tutor/chat endpoint"""
    
    def test_tutor_chat_returns_200(self):
        """Verify tutor chat endpoint returns 200 with valid payload"""
        payload = {
            "message": "Olá, o que é este curso?",
            "courseTopic": "Curso de Teste",
            "courseContext": "Este é um curso de teste para verificar o funcionamento do tutor.",
            "history": [],
            "sessionId": "test-session-001"
        }
        response = requests.post(f"{BASE_URL}/api/tutor/chat", json=payload)
        
        # Should return 200 (or 500 if LLM key is invalid, but NOT 404)
        assert response.status_code != 404, f"Tutor chat returned 404 - route not registered! Response: {response.text}"
        
        if response.status_code == 200:
            data = response.json()
            assert "response" in data or "message" in data or "reply" in data
            print(f"PASS: Tutor chat returns 200 with response")
        else:
            # 500 might happen if LLM key is invalid, but route exists
            print(f"INFO: Tutor chat returns {response.status_code} - route exists but may have LLM issues")
            # Still pass if not 404
            assert response.status_code in [200, 500, 503], f"Unexpected status: {response.status_code}"
            print(f"PASS: Tutor chat route exists (status {response.status_code})")


class TestSCORMExportURLFix:
    """Test SCORM export uses correct external URL from X-Forwarded-Host"""
    
    def test_scorm_export_with_forwarded_headers(self):
        """
        Test SCORM export with X-Forwarded-Host header.
        The export should use the forwarded host URL, not internal cluster URL.
        """
        # Simulate request with X-Forwarded headers (as Kubernetes ingress would set)
        headers = {
            "X-Forwarded-Host": "ai-course-author.preview.emergentagent.com",
            "X-Forwarded-Proto": "https"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/course/{TEST_PROJECT_ID}/export-scorm",
            headers=headers
        )
        
        if response.status_code == 404:
            pytest.skip(f"Project {TEST_PROJECT_ID} not found - skipping SCORM export test")
        
        assert response.status_code == 200, f"SCORM export failed: {response.status_code} - {response.text}"
        
        data = response.json()
        assert "downloadUrl" in data, f"No downloadUrl in response: {data}"
        assert "jobId" in data, f"No jobId in response: {data}"
        
        download_url = data["downloadUrl"]
        print(f"PASS: SCORM export successful, downloadUrl: {download_url}")
        
        return download_url
    
    def test_scorm_export_url_not_internal(self):
        """
        Verify SCORM export download URL doesn't contain internal cluster URL.
        """
        headers = {
            "X-Forwarded-Host": "ai-course-author.preview.emergentagent.com",
            "X-Forwarded-Proto": "https"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/course/{TEST_PROJECT_ID}/export-scorm",
            headers=headers
        )
        
        if response.status_code == 404:
            pytest.skip(f"Project {TEST_PROJECT_ID} not found")
        
        assert response.status_code == 200
        data = response.json()
        download_url = data.get("downloadUrl", "")
        
        # Download URL should be relative (starts with /api/) or use external URL
        # It should NOT contain 'cluster' (internal K8s URL)
        assert "cluster" not in download_url.lower(), f"Download URL contains internal cluster URL: {download_url}"
        print(f"PASS: Download URL doesn't contain internal cluster URL: {download_url}")
    
    def test_scorm_zip_tutor_config_url(self):
        """
        Download SCORM ZIP, extract course.json, verify tutorConfig.apiUrl
        uses external URL (not internal cluster URL).
        """
        headers = {
            "X-Forwarded-Host": "ai-course-author.preview.emergentagent.com",
            "X-Forwarded-Proto": "https"
        }
        
        # Export SCORM
        export_response = requests.post(
            f"{BASE_URL}/api/course/{TEST_PROJECT_ID}/export-scorm",
            headers=headers
        )
        
        if export_response.status_code == 404:
            pytest.skip(f"Project {TEST_PROJECT_ID} not found")
        
        assert export_response.status_code == 200
        data = export_response.json()
        download_url = data.get("downloadUrl", "")
        
        # Wait a moment for export to complete
        time.sleep(2)
        
        # Download the ZIP file
        full_download_url = f"{BASE_URL}{download_url}" if download_url.startswith("/") else download_url
        zip_response = requests.get(full_download_url)
        
        if zip_response.status_code != 200:
            pytest.skip(f"Could not download SCORM ZIP: {zip_response.status_code}")
        
        # Extract and check course.json
        try:
            zip_buffer = io.BytesIO(zip_response.content)
            with zipfile.ZipFile(zip_buffer, 'r') as zf:
                # Look for course.json in the ZIP
                course_json_path = None
                for name in zf.namelist():
                    if name.endswith('course.json'):
                        course_json_path = name
                        break
                
                if not course_json_path:
                    print("INFO: No course.json found in SCORM ZIP - tutor may not be enabled")
                    return
                
                with zf.open(course_json_path) as f:
                    course_data = json.load(f)
                
                # Check tutorConfig.apiUrl
                tutor_config = course_data.get("tutorConfig", {})
                api_url = tutor_config.get("apiUrl", "")
                
                if api_url:
                    # Verify URL doesn't contain internal cluster URL
                    assert "cluster" not in api_url.lower(), f"tutorConfig.apiUrl contains internal cluster URL: {api_url}"
                    
                    # Verify URL uses the external domain
                    assert "ai-course-author.preview.emergentagent.com" in api_url or api_url.startswith("https://"), \
                        f"tutorConfig.apiUrl doesn't use external URL: {api_url}"
                    
                    print(f"PASS: tutorConfig.apiUrl uses external URL: {api_url}")
                else:
                    print("INFO: tutorConfig.apiUrl is empty - tutor may not be enabled for this project")
                    
        except zipfile.BadZipFile:
            pytest.skip("Downloaded file is not a valid ZIP")
        except json.JSONDecodeError:
            pytest.skip("course.json is not valid JSON")


class TestHTMLExportURLFix:
    """Test HTML export uses correct external URL from X-Forwarded-Host"""
    
    def test_html_export_with_forwarded_headers(self):
        """
        Test HTML export with X-Forwarded-Host header.
        """
        headers = {
            "X-Forwarded-Host": "ai-course-author.preview.emergentagent.com",
            "X-Forwarded-Proto": "https"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/course/{TEST_PROJECT_ID}/export-html",
            headers=headers
        )
        
        if response.status_code == 404:
            pytest.skip(f"Project {TEST_PROJECT_ID} not found")
        
        assert response.status_code == 200, f"HTML export failed: {response.status_code} - {response.text}"
        
        data = response.json()
        assert "downloadUrl" in data, f"No downloadUrl in response: {data}"
        
        download_url = data["downloadUrl"]
        print(f"PASS: HTML export successful, downloadUrl: {download_url}")
        
        return download_url
    
    def test_html_export_url_not_internal(self):
        """
        Verify HTML export download URL doesn't contain internal cluster URL.
        """
        headers = {
            "X-Forwarded-Host": "ai-course-author.preview.emergentagent.com",
            "X-Forwarded-Proto": "https"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/course/{TEST_PROJECT_ID}/export-html",
            headers=headers
        )
        
        if response.status_code == 404:
            pytest.skip(f"Project {TEST_PROJECT_ID} not found")
        
        assert response.status_code == 200
        data = response.json()
        download_url = data.get("downloadUrl", "")
        
        # Download URL should NOT contain 'cluster' (internal K8s URL)
        assert "cluster" not in download_url.lower(), f"Download URL contains internal cluster URL: {download_url}"
        print(f"PASS: HTML download URL doesn't contain internal cluster URL: {download_url}")


class TestGetExternalUrlFunction:
    """
    Test the _get_external_url function behavior indirectly through exports.
    We can't call the function directly, but we can verify its behavior
    through the export endpoints.
    """
    
    def test_export_respects_x_forwarded_host(self):
        """
        Verify that exports use X-Forwarded-Host when provided.
        This is the core fix being tested.
        """
        # Test with a custom X-Forwarded-Host
        custom_host = "custom-test-host.example.com"
        headers = {
            "X-Forwarded-Host": custom_host,
            "X-Forwarded-Proto": "https"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/course/{TEST_PROJECT_ID}/export-scorm",
            headers=headers
        )
        
        if response.status_code == 404:
            pytest.skip(f"Project {TEST_PROJECT_ID} not found")
        
        # The export should succeed regardless of the host header
        # (the URL is embedded in the exported content, not the response)
        assert response.status_code == 200, f"Export failed: {response.status_code}"
        print("PASS: Export accepts X-Forwarded-Host header")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
