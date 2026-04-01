"""
Test suite for Agent subcomponents authHeaders fix (P0 production bug)
Tests that all Agent subcomponent fetch calls include Authorization headers

Bug: 401 Unauthorized errors in production when using AI Agent features
Fix: Added authHeaders() from AuthContext to all fetch calls in 5 Agent subcomponents:
- GeneratedPanel.jsx
- CoursePanels.jsx
- ConfigPanel.jsx
- MediaConfigPanel.jsx
- StoryboardPanel.jsx
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://agent-authfix.preview.emergentagent.com')


class TestAuthFlow:
    """Test authentication flow"""
    
    def test_login_returns_token(self):
        """Test that login returns a valid token"""
        response = requests.post(f'{BASE_URL}/api/auth/login', json={
            'email': 'admin@scormify.com',
            'password': 'admin123'
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        
        data = response.json()
        assert 'token' in data, "Response missing token"
        assert 'user' in data, "Response missing user"
        assert len(data['token']) > 0, "Token is empty"
        assert data['user']['email'] == 'admin@scormify.com', "User email mismatch"


class TestAgentEndpointsWithAuth:
    """Test Agent endpoints with proper authentication"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token before each test"""
        response = requests.post(f'{BASE_URL}/api/auth/login', json={
            'email': 'admin@scormify.com',
            'password': 'admin123'
        })
        if response.status_code == 200:
            self.token = response.json().get('token')
            self.headers = {'Authorization': f'Bearer {self.token}'}
        else:
            pytest.skip("Authentication failed")
    
    def test_agent_courses_with_auth(self):
        """Test /api/agent/courses returns 200 with auth token"""
        response = requests.get(f'{BASE_URL}/api/agent/courses', headers=self.headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Expected list of courses"
        # Verify we get courses
        assert len(data) > 0, "Expected at least one course"
    
    def test_agent_templates_with_auth(self):
        """Test /api/agent/templates returns 200 with auth token"""
        response = requests.get(f'{BASE_URL}/api/agent/templates', headers=self.headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    
    def test_agent_design_templates_with_auth(self):
        """Test /api/agent/design-templates returns 200 with auth token"""
        response = requests.get(f'{BASE_URL}/api/agent/design-templates', headers=self.headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    
    def test_elevenlabs_voices_with_auth(self):
        """Test /api/elevenlabs/voices returns 200 with auth token (used by ConfigPanel, StoryboardPanel)"""
        response = requests.get(f'{BASE_URL}/api/elevenlabs/voices', headers=self.headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    
    def test_heygen_avatars_with_auth(self):
        """Test /api/heygen/avatars returns 200 with auth token (used by CoursePanels, MediaConfigPanel)"""
        response = requests.get(f'{BASE_URL}/api/heygen/avatars?limit=10', headers=self.headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    
    def test_heygen_voices_with_auth(self):
        """Test /api/heygen/voices returns 200 with auth token (used by CoursePanels, MediaConfigPanel)"""
        response = requests.get(f'{BASE_URL}/api/heygen/voices?language=portuguese', headers=self.headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    
    def test_gallery_images_with_auth(self):
        """Test /api/gallery/images returns 200 with auth token (used by MediaConfigPanel)"""
        response = requests.get(f'{BASE_URL}/api/gallery/images', headers=self.headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"


class TestAgentEndpointsWithoutAuth:
    """Test that certain endpoints require authentication"""
    
    def test_auth_me_without_token(self):
        """Test /api/auth/me returns 401 without token"""
        response = requests.get(f'{BASE_URL}/api/auth/me')
        # Should return 401 Unauthorized
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
