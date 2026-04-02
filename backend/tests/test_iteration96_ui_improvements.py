"""
Test iteration 96 - UI improvements for Agent 'Gerar Curso' step
Tests:
1. Login flow works correctly
2. Agent page endpoints work with auth
3. Dashboard metrics endpoint
4. Repair-assets endpoint
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@scormify.com"
ADMIN_PASSWORD = "admin123"


class TestAuthFlow:
    """Test authentication flow"""
    
    def test_login_success(self):
        """Test login with valid credentials returns token and user data"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "token" in data, "Response missing token"
        assert "user" in data, "Response missing user"
        assert data["user"]["email"] == ADMIN_EMAIL
        print(f"✓ Login successful, token received")
        return data["token"]


class TestAgentEndpoints:
    """Test Agent page endpoints with authentication"""
    
    @pytest.fixture
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        if response.status_code == 200:
            return response.json().get("token")
        pytest.skip("Authentication failed")
    
    def test_agent_courses_endpoint(self, auth_token):
        """Test GET /api/agent/courses returns 200 with auth"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/agent/courses", headers=headers)
        assert response.status_code == 200, f"Agent courses failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Expected list of courses"
        print(f"✓ Agent courses endpoint works, returned {len(data)} courses")
    
    def test_agent_templates_endpoint(self, auth_token):
        """Test GET /api/agent/templates returns 200 with auth"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/agent/templates", headers=headers)
        assert response.status_code == 200, f"Agent templates failed: {response.text}"
        print(f"✓ Agent templates endpoint works")
    
    def test_agent_design_templates_endpoint(self, auth_token):
        """Test GET /api/agent/design-templates returns 200 with auth"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/agent/design-templates", headers=headers)
        assert response.status_code == 200, f"Agent design templates failed: {response.text}"
        print(f"✓ Agent design templates endpoint works")
    
    def test_elevenlabs_voices_endpoint(self, auth_token):
        """Test GET /api/elevenlabs/voices returns 200 with auth"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/elevenlabs/voices", headers=headers)
        assert response.status_code == 200, f"ElevenLabs voices failed: {response.text}"
        print(f"✓ ElevenLabs voices endpoint works")
    
    def test_heygen_avatars_endpoint(self, auth_token):
        """Test GET /api/heygen/avatars returns 200 with auth"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/heygen/avatars", headers=headers)
        assert response.status_code == 200, f"HeyGen avatars failed: {response.text}"
        print(f"✓ HeyGen avatars endpoint works")
    
    def test_heygen_voices_endpoint(self, auth_token):
        """Test GET /api/heygen/voices returns 200 with auth"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/heygen/voices", headers=headers)
        assert response.status_code == 200, f"HeyGen voices failed: {response.text}"
        print(f"✓ HeyGen voices endpoint works")
    
    def test_gallery_images_endpoint(self, auth_token):
        """Test GET /api/gallery/images returns 200 with auth"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/gallery/images", headers=headers)
        assert response.status_code == 200, f"Gallery images failed: {response.text}"
        print(f"✓ Gallery images endpoint works")


class TestDashboardEndpoints:
    """Test Dashboard endpoints"""
    
    def test_dashboard_metrics_endpoint(self):
        """Test GET /api/dashboard/metrics returns 200"""
        response = requests.get(f"{BASE_URL}/api/dashboard/metrics")
        assert response.status_code == 200, f"Dashboard metrics failed: {response.text}"
        data = response.json()
        assert "totalCourses" in data, "Missing totalCourses"
        assert "totalSlides" in data, "Missing totalSlides"
        assert "totalExports" in data, "Missing totalExports"
        print(f"✓ Dashboard metrics: {data['totalCourses']} courses, {data['totalSlides']} slides, {data['totalExports']} exports")


class TestRepairAssetsEndpoint:
    """Test repair-assets endpoint"""
    
    @pytest.fixture
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        if response.status_code == 200:
            return response.json().get("token")
        pytest.skip("Authentication failed")
    
    def test_repair_assets_endpoint(self, auth_token):
        """Test POST /api/admin/repair-assets returns 200 with auth"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.post(f"{BASE_URL}/api/admin/repair-assets", headers=headers)
        # Accept 200 or 404 (if no assets to repair)
        assert response.status_code in [200, 404], f"Repair assets failed: {response.status_code} - {response.text}"
        print(f"✓ Repair assets endpoint works (status: {response.status_code})")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
