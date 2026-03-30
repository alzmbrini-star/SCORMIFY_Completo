"""
Test HeyGen Test Combination Endpoint
Tests the POST /api/heygen/test-combination endpoint for avatar + voice preview video generation
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Real HeyGen avatar and voice IDs for testing
TEST_AVATAR_ID = "Abigail_expressive_2024112501"
TEST_VOICE_ID = "6872a840c4194f42a7f8ce0aee47660c"


class TestHeyGenTestCombination:
    """Tests for POST /api/heygen/test-combination endpoint"""

    def test_test_combination_success(self):
        """Test successful test combination request returns video_id and status:processing"""
        response = requests.post(
            f"{BASE_URL}/api/heygen/test-combination",
            json={
                "avatar_id": TEST_AVATAR_ID,
                "voice_id": TEST_VOICE_ID
            },
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "video_id" in data, "Response should contain video_id"
        assert "status" in data, "Response should contain status"
        assert data["status"] == "processing", f"Expected status 'processing', got '{data['status']}'"
        assert isinstance(data["video_id"], str), "video_id should be a string"
        assert len(data["video_id"]) > 0, "video_id should not be empty"
        
        print(f"✓ Test combination started successfully: video_id={data['video_id']}")
        
        # Store video_id for status check test
        return data["video_id"]

    def test_test_combination_missing_avatar_id(self):
        """Test that missing avatar_id returns 422 validation error"""
        response = requests.post(
            f"{BASE_URL}/api/heygen/test-combination",
            json={
                "voice_id": TEST_VOICE_ID
            },
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 422, f"Expected 422, got {response.status_code}: {response.text}"
        print("✓ Missing avatar_id correctly returns 422")

    def test_test_combination_missing_voice_id(self):
        """Test that missing voice_id returns 422 validation error"""
        response = requests.post(
            f"{BASE_URL}/api/heygen/test-combination",
            json={
                "avatar_id": TEST_AVATAR_ID
            },
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 422, f"Expected 422, got {response.status_code}: {response.text}"
        print("✓ Missing voice_id correctly returns 422")

    def test_test_combination_empty_body(self):
        """Test that empty request body returns 422 validation error"""
        response = requests.post(
            f"{BASE_URL}/api/heygen/test-combination",
            json={},
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 422, f"Expected 422, got {response.status_code}: {response.text}"
        print("✓ Empty body correctly returns 422")


class TestHeyGenVideoStatus:
    """Tests for GET /api/heygen/video-status/{video_id} endpoint"""

    def test_video_status_valid_id(self):
        """Test video status endpoint with a valid video_id from test-combination"""
        # First create a test combination to get a video_id
        create_response = requests.post(
            f"{BASE_URL}/api/heygen/test-combination",
            json={
                "avatar_id": TEST_AVATAR_ID,
                "voice_id": TEST_VOICE_ID
            },
            headers={"Content-Type": "application/json"}
        )
        
        if create_response.status_code != 200:
            pytest.skip(f"Could not create test video: {create_response.text}")
        
        video_id = create_response.json().get("video_id")
        assert video_id, "No video_id returned from test-combination"
        
        # Now check the status
        status_response = requests.get(
            f"{BASE_URL}/api/heygen/video-status/{video_id}"
        )
        
        assert status_response.status_code == 200, f"Expected 200, got {status_response.status_code}: {status_response.text}"
        
        data = status_response.json()
        assert "video_id" in data, "Response should contain video_id"
        assert "status" in data, "Response should contain status"
        assert data["video_id"] == video_id, "video_id should match"
        # Status can be 'processing', 'pending', 'waiting', 'completed', or 'failed'
        assert data["status"] in ["processing", "pending", "waiting", "completed", "failed"], f"Unexpected status: {data['status']}"
        
        print(f"✓ Video status check successful: video_id={video_id}, status={data['status']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
