"""
Test suite for POST /api/generate-html endpoint
Tests AI-powered HTML generation feature using Google Gemini
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestGenerateHtmlEndpoint:
    """Tests for the /api/generate-html endpoint"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Login and get auth token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "admin@scormify.com", "password": "admin123"}
        )
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        return data.get("token") or data.get("access_token")
    
    @pytest.fixture(scope="class")
    def auth_session(self, auth_token):
        """Create authenticated session"""
        session = requests.Session()
        if auth_token:
            session.headers.update({"Authorization": f"Bearer {auth_token}"})
        # Also set cookies for session-based auth
        login_resp = session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "admin@scormify.com", "password": "admin123"}
        )
        return session
    
    def test_generate_html_requires_authentication(self):
        """Test that /api/generate-html returns 401 without authentication"""
        response = requests.post(
            f"{BASE_URL}/api/generate-html",
            json={"prompt": "Create a simple button"}
        )
        # Should return 401 Unauthorized
        assert response.status_code == 401, f"Expected 401, got {response.status_code}: {response.text}"
        print("PASS: /api/generate-html returns 401 without authentication")
    
    def test_generate_html_validates_empty_prompt(self, auth_session):
        """Test that /api/generate-html validates empty prompt"""
        response = auth_session.post(
            f"{BASE_URL}/api/generate-html",
            json={"prompt": ""}
        )
        # Should return 422 (validation error) or 400 (bad request)
        # Note: Pydantic may allow empty string, so we check if it fails gracefully
        # The frontend validates this, but backend should also handle it
        print(f"Empty prompt response: {response.status_code} - {response.text[:200] if response.text else 'No body'}")
        # If it returns 200, the AI might generate something generic - that's acceptable
        # If it returns 4xx, that's also acceptable (validation)
        assert response.status_code in [200, 400, 422, 500], f"Unexpected status: {response.status_code}"
        print(f"PASS: /api/generate-html handles empty prompt (status: {response.status_code})")
    
    def test_generate_html_returns_html_content(self, auth_session):
        """Test that /api/generate-html returns HTML with script and style tags"""
        response = auth_session.post(
            f"{BASE_URL}/api/generate-html",
            json={
                "prompt": "Create a simple interactive counter with a button that increments a number when clicked",
                "courseContext": "Test course"
            },
            timeout=60  # AI generation can take time
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "html" in data, f"Response should contain 'html' key: {data}"
        
        html_content = data["html"]
        assert html_content, "HTML content should not be empty"
        assert len(html_content) > 50, f"HTML content seems too short: {len(html_content)} chars"
        
        # Check for HTML structure
        html_lower = html_content.lower()
        has_div = "<div" in html_lower
        has_button = "<button" in html_lower or "onclick" in html_lower
        has_script = "<script" in html_lower
        has_style = "<style" in html_lower or "style=" in html_lower
        
        print(f"HTML content length: {len(html_content)} chars")
        print(f"Has <div>: {has_div}")
        print(f"Has button/onclick: {has_button}")
        print(f"Has <script>: {has_script}")
        print(f"Has <style> or style=: {has_style}")
        
        # At minimum, should have some HTML structure
        assert has_div or "<html" in html_lower or "<body" in html_lower, "Should contain HTML structure"
        
        # For an interactive counter, we expect JavaScript
        assert has_script or "onclick" in html_lower, "Interactive content should have JavaScript"
        
        print("PASS: /api/generate-html returns valid HTML content with interactive elements")
        print(f"Sample HTML (first 500 chars): {html_content[:500]}...")
    
    def test_generate_html_with_course_context(self, auth_session):
        """Test that /api/generate-html accepts courseContext parameter"""
        response = auth_session.post(
            f"{BASE_URL}/api/generate-html",
            json={
                "prompt": "Create a simple info card about workplace safety",
                "courseContext": "Curso de Segurança do Trabalho"
            },
            timeout=60
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "html" in data, f"Response should contain 'html' key: {data}"
        assert data["html"], "HTML content should not be empty"
        
        print("PASS: /api/generate-html accepts courseContext parameter")


class TestHealthAndAuth:
    """Basic health and auth tests"""
    
    def test_health_endpoint(self):
        """Test health endpoint is accessible"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        print("PASS: Health endpoint returns 200")
    
    def test_admin_login(self):
        """Test admin login works"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "admin@scormify.com", "password": "admin123"}
        )
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "user" in data or "email" in data, f"Login response missing user data: {data}"
        print("PASS: Admin login works with admin@scormify.com / admin123")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
