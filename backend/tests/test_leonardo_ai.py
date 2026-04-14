"""
Leonardo AI Image Generation API Tests for Scormify
Tests the 3 Leonardo endpoints:
- POST /api/leonardo/generate - Start image generation
- GET /api/leonardo/status/{id} - Poll for generation status
- POST /api/leonardo/save-to-project - Save image to project assets
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@scormify.com"
ADMIN_PASSWORD = "admin123"

# Known project ID for testing
TEST_PROJECT_ID = "111f5fcd-72eb-4c64-a165-b737a13c2ffb"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for admin user"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    )
    if response.status_code == 200:
        data = response.json()
        return data.get("token") or data.get("access_token")
    pytest.skip(f"Authentication failed: {response.status_code} - {response.text}")


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Headers with authentication"""
    return {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json"
    }


class TestLeonardoGenerateEndpoint:
    """Tests for POST /api/leonardo/generate"""
    
    def test_generate_requires_auth(self):
        """Test that generate endpoint requires authentication"""
        response = requests.post(
            f"{BASE_URL}/api/leonardo/generate",
            json={"prompt": "test image"}
        )
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ Generate endpoint requires authentication")
    
    def test_generate_requires_prompt(self, auth_headers):
        """Test that generate endpoint requires a prompt"""
        response = requests.post(
            f"{BASE_URL}/api/leonardo/generate",
            headers=auth_headers,
            json={}
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("✓ Generate endpoint requires prompt")
    
    def test_generate_empty_prompt_rejected(self, auth_headers):
        """Test that empty prompt is rejected"""
        response = requests.post(
            f"{BASE_URL}/api/leonardo/generate",
            headers=auth_headers,
            json={"prompt": "   "}
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("✓ Empty prompt rejected")
    
    def test_generate_returns_generation_id(self, auth_headers):
        """Test that generate endpoint returns a generationId"""
        response = requests.post(
            f"{BASE_URL}/api/leonardo/generate",
            headers=auth_headers,
            json={
                "prompt": "Modern corporate training room with digital screen, professional lighting",
                "width": 1024,
                "height": 576,
                "numImages": 1,
                "projectId": TEST_PROJECT_ID
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "generationId" in data, f"Response missing generationId: {data}"
        assert data.get("status") == "pending", f"Expected status 'pending', got {data.get('status')}"
        print(f"✓ Generate endpoint returned generationId: {data['generationId']}")
        return data["generationId"]
    
    def test_generate_with_style_preset(self, auth_headers):
        """Test generation with style preset"""
        response = requests.post(
            f"{BASE_URL}/api/leonardo/generate",
            headers=auth_headers,
            json={
                "prompt": "Professional business meeting scene",
                "style": "CINEMATIC",
                "width": 1024,
                "height": 576,
                "numImages": 1
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "generationId" in data
        print(f"✓ Generate with CINEMATIC style returned generationId: {data['generationId']}")


class TestLeonardoStatusEndpoint:
    """Tests for GET /api/leonardo/status/{generation_id}"""
    
    def test_status_requires_auth(self):
        """Test that status endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/leonardo/status/fake-id-123")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ Status endpoint requires authentication")
    
    def test_status_returns_valid_response(self, auth_headers):
        """Test status endpoint with a real generation"""
        # First create a generation
        gen_response = requests.post(
            f"{BASE_URL}/api/leonardo/generate",
            headers=auth_headers,
            json={
                "prompt": "Simple blue gradient background",
                "width": 512,
                "height": 512,
                "numImages": 1
            }
        )
        assert gen_response.status_code == 200
        gen_id = gen_response.json()["generationId"]
        
        # Poll status (just check it returns valid response, don't wait for completion)
        status_response = requests.get(
            f"{BASE_URL}/api/leonardo/status/{gen_id}",
            headers=auth_headers
        )
        assert status_response.status_code == 200, f"Expected 200, got {status_response.status_code}"
        data = status_response.json()
        assert "status" in data, f"Response missing status: {data}"
        assert data["status"] in ["pending", "complete", "failed", "timeout"], f"Invalid status: {data['status']}"
        assert "generationId" in data
        print(f"✓ Status endpoint returned valid response: status={data['status']}")


class TestLeonardoSaveToProjectEndpoint:
    """Tests for POST /api/leonardo/save-to-project"""
    
    def test_save_requires_auth(self):
        """Test that save endpoint requires authentication"""
        response = requests.post(
            f"{BASE_URL}/api/leonardo/save-to-project",
            json={"imageUrl": "https://example.com/image.png", "projectId": TEST_PROJECT_ID}
        )
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ Save endpoint requires authentication")
    
    def test_save_requires_image_url(self, auth_headers):
        """Test that save endpoint requires imageUrl"""
        response = requests.post(
            f"{BASE_URL}/api/leonardo/save-to-project",
            headers=auth_headers,
            json={"projectId": TEST_PROJECT_ID}
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("✓ Save endpoint requires imageUrl")
    
    def test_save_requires_project_id(self, auth_headers):
        """Test that save endpoint requires projectId"""
        response = requests.post(
            f"{BASE_URL}/api/leonardo/save-to-project",
            headers=auth_headers,
            json={"imageUrl": "https://example.com/image.png"}
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("✓ Save endpoint requires projectId")


class TestLeonardoIntegration:
    """Integration tests for full Leonardo workflow"""
    
    def test_full_generation_workflow(self, auth_headers):
        """Test complete workflow: generate -> poll -> verify"""
        # Step 1: Start generation
        gen_response = requests.post(
            f"{BASE_URL}/api/leonardo/generate",
            headers=auth_headers,
            json={
                "prompt": "Abstract colorful geometric pattern for e-learning background",
                "width": 1024,
                "height": 576,
                "numImages": 1,
                "projectId": TEST_PROJECT_ID
            }
        )
        assert gen_response.status_code == 200
        gen_id = gen_response.json()["generationId"]
        print(f"✓ Step 1: Generation started with ID: {gen_id}")
        
        # Step 2: Poll status (just verify endpoint works, don't wait for full completion)
        status_response = requests.get(
            f"{BASE_URL}/api/leonardo/status/{gen_id}",
            headers=auth_headers
        )
        assert status_response.status_code == 200
        status_data = status_response.json()
        print(f"✓ Step 2: Status poll returned: {status_data['status']}")
        
        # Step 3: Verify generation was tracked in database
        # (The generate endpoint stores the generation in leonardo_generations collection)
        assert status_data.get("generationId") == gen_id
        print("✓ Step 3: Generation ID matches in status response")
        
        print("✓ Full workflow test passed (generation started and status polled)")


class TestLeonardoAPIKeyConfiguration:
    """Tests to verify Leonardo API key is configured"""
    
    def test_api_key_configured(self, auth_headers):
        """Test that Leonardo API key is properly configured"""
        # If API key is not configured, the generate endpoint should fail with 500
        # If configured, it should return 200 with generationId
        response = requests.post(
            f"{BASE_URL}/api/leonardo/generate",
            headers=auth_headers,
            json={
                "prompt": "Test image for API key verification",
                "width": 512,
                "height": 512,
                "numImages": 1
            }
        )
        # If we get 200, API key is configured
        # If we get 500 with "LEONARDO_API_KEY not configured", it's not
        if response.status_code == 500:
            error_text = response.text.lower()
            if "api_key" in error_text or "not configured" in error_text:
                pytest.fail("Leonardo API key is not configured in backend .env")
        
        assert response.status_code == 200, f"Unexpected response: {response.status_code} - {response.text}"
        print("✓ Leonardo API key is properly configured")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
