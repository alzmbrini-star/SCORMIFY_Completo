"""
Test suite for Editor refactoring and Badge Image Upload feature
Tests:
1. Badge image upload endpoint (POST /api/gamification/upload-badge-image)
2. Gamification config endpoints
"""
import pytest
import requests
import os
import base64

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "admin@scormify.com"
TEST_PASSWORD = "admin123"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    })
    if response.status_code == 200:
        data = response.json()
        return data.get("token") or data.get("access_token")
    pytest.skip(f"Authentication failed: {response.status_code} - {response.text}")


@pytest.fixture(scope="module")
def authenticated_session(auth_token):
    """Session with auth header"""
    session = requests.Session()
    session.headers.update({
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json"
    })
    return session


@pytest.fixture(scope="module")
def test_project_id(authenticated_session):
    """Get a test project ID"""
    response = authenticated_session.get(f"{BASE_URL}/api/projects")
    if response.status_code == 200:
        projects = response.json()
        if projects and len(projects) > 0:
            return projects[0].get("id")
    pytest.skip("No projects available for testing")


class TestHealthCheck:
    """Basic health check"""
    
    def test_api_health(self):
        """Test API is healthy"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy"
        print("✓ API health check passed")


class TestBadgeImageUpload:
    """Tests for POST /api/gamification/upload-badge-image"""
    
    def test_upload_badge_image_success(self, auth_token):
        """Test successful badge image upload"""
        # Create a small test PNG image (1x1 pixel red)
        # PNG header + IHDR + IDAT + IEND
        png_data = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg=="
        )
        
        files = {
            'file': ('test_badge.png', png_data, 'image/png')
        }
        headers = {"Authorization": f"Bearer {auth_token}"}
        
        response = requests.post(
            f"{BASE_URL}/api/gamification/upload-badge-image",
            files=files,
            headers=headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "imageUrl" in data, "Response should contain imageUrl"
        
        # Verify it's a base64 data URL
        image_url = data["imageUrl"]
        assert image_url.startswith("data:image/png;base64,"), f"Expected data URL, got: {image_url[:50]}..."
        
        print(f"✓ Badge image upload successful, returned data URL length: {len(image_url)}")
    
    def test_upload_badge_image_jpeg(self, auth_token):
        """Test badge image upload with JPEG"""
        # Minimal JPEG (1x1 pixel)
        jpeg_data = base64.b64decode(
            "/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAn/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8QAFQEBAQAAAAAAAAAAAAAAAAAAAAX/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oADAMBEQCEAwEPwAB//9k="
        )
        
        files = {
            'file': ('test_badge.jpg', jpeg_data, 'image/jpeg')
        }
        headers = {"Authorization": f"Bearer {auth_token}"}
        
        response = requests.post(
            f"{BASE_URL}/api/gamification/upload-badge-image",
            files=files,
            headers=headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "imageUrl" in data
        assert data["imageUrl"].startswith("data:image/jpeg;base64,")
        print("✓ JPEG badge image upload successful")
    
    def test_upload_badge_image_no_auth(self):
        """Test badge image upload without authentication"""
        png_data = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg=="
        )
        
        files = {
            'file': ('test_badge.png', png_data, 'image/png')
        }
        
        response = requests.post(
            f"{BASE_URL}/api/gamification/upload-badge-image",
            files=files
        )
        
        # Should return 401 or 403 without auth
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ Badge upload correctly requires authentication")
    
    def test_upload_badge_image_non_image_file(self, auth_token):
        """Test badge image upload with non-image file"""
        text_data = b"This is not an image"
        
        files = {
            'file': ('test.txt', text_data, 'text/plain')
        }
        headers = {"Authorization": f"Bearer {auth_token}"}
        
        response = requests.post(
            f"{BASE_URL}/api/gamification/upload-badge-image",
            files=files,
            headers=headers
        )
        
        # Should reject non-image files
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("✓ Non-image file correctly rejected")


class TestGamificationConfig:
    """Tests for gamification configuration endpoints"""
    
    def test_get_gamification_defaults(self, authenticated_session):
        """Test GET /api/gamification/defaults"""
        response = authenticated_session.get(f"{BASE_URL}/api/gamification/defaults")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        # Verify structure
        assert "badges" in data, "Response should contain badges"
        assert "quizFeedbackRanges" in data, "Response should contain quizFeedbackRanges"
        assert "scenarioFeedbackRanges" in data, "Response should contain scenarioFeedbackRanges"
        
        # Verify badges have required fields
        if data["badges"]:
            badge = data["badges"][0]
            assert "id" in badge
            assert "name" in badge
            assert "icon" in badge
        
        print(f"✓ Gamification defaults returned {len(data['badges'])} badges")
    
    def test_get_project_gamification(self, authenticated_session, test_project_id):
        """Test GET /api/projects/{project_id}/gamification"""
        response = authenticated_session.get(
            f"{BASE_URL}/api/projects/{test_project_id}/gamification"
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        # Verify structure
        assert "enabled" in data
        assert "badges" in data
        assert "showBadgesAfterQuiz" in data
        
        print(f"✓ Project gamification config retrieved, enabled: {data['enabled']}")
    
    def test_update_project_gamification(self, authenticated_session, test_project_id):
        """Test PUT /api/projects/{project_id}/gamification"""
        # First get current config
        get_response = authenticated_session.get(
            f"{BASE_URL}/api/projects/{test_project_id}/gamification"
        )
        current_config = get_response.json()
        
        # Update config
        updated_config = {
            **current_config,
            "enabled": True,
            "showBadgesAfterQuiz": True,
            "showFinalSummary": True
        }
        
        response = authenticated_session.put(
            f"{BASE_URL}/api/projects/{test_project_id}/gamification",
            json=updated_config
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get("status") == "ok"
        
        print("✓ Project gamification config updated successfully")
    
    def test_get_gamification_icons(self, authenticated_session):
        """Test GET /api/gamification/icons"""
        response = authenticated_session.get(f"{BASE_URL}/api/gamification/icons")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        assert "icons" in data
        assert len(data["icons"]) > 0
        
        # Verify icon structure
        icon = data["icons"][0]
        assert "id" in icon
        assert "name" in icon
        assert "category" in icon
        
        print(f"✓ Gamification icons returned {len(data['icons'])} icons")


class TestProjectsEndpoint:
    """Test projects endpoint to ensure editor can load"""
    
    def test_get_projects(self, authenticated_session):
        """Test GET /api/projects"""
        response = authenticated_session.get(f"{BASE_URL}/api/projects")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        projects = response.json()
        
        assert isinstance(projects, list)
        print(f"✓ Projects endpoint returned {len(projects)} projects")
    
    def test_get_single_project(self, authenticated_session, test_project_id):
        """Test GET /api/projects/{project_id}"""
        response = authenticated_session.get(f"{BASE_URL}/api/projects/{test_project_id}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        project = response.json()
        
        assert "id" in project
        assert "name" in project
        # slides may be nested or named differently
        
        print(f"✓ Single project retrieved: {project['name']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
