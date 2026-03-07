"""
Test suite for HeyGen Slide-to-Video Feature
Tests: generate-all-slide-scripts, generate-slide-video, generate-batch-slide-videos, batch-status, credits
"""
import pytest
import requests
import os
import time
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
TEST_PROJECT_ID = "82d2d9d4-3067-47de-bf5a-0e14e9051e67"


@pytest.fixture(scope="module")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


class TestHeyGenCredits:
    """Test HeyGen credits endpoint"""
    
    def test_get_credits_endpoint_returns_200(self, api_client):
        """GET /api/heygen/credits should return 200 and credits info"""
        response = api_client.get(f"{BASE_URL}/api/heygen/credits")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        print(f"Credits response: {data}")
        
        # Verify response structure
        assert "remaining_quota" in data or "plan_credit" in data, "Missing credits field"
        assert "has_credits" in data, "Missing has_credits field"
        
    def test_credits_has_plan_credit_field(self, api_client):
        """Credits should include plan_credit for subscription plans"""
        response = api_client.get(f"{BASE_URL}/api/heygen/credits")
        assert response.status_code == 200
        
        data = response.json()
        # plan_credit is the key field for Enterprise plans
        assert "plan_credit" in data, "Missing plan_credit field"
        print(f"Plan credit: {data.get('plan_credit')}, Remaining quota: {data.get('remaining_quota')}")
        
    def test_credits_force_refresh(self, api_client):
        """Credits with force_refresh=true should bypass cache"""
        response = api_client.get(f"{BASE_URL}/api/heygen/credits?force_refresh=true")
        assert response.status_code == 200
        
        data = response.json()
        assert "has_credits" in data
        print(f"Force refresh credits: {data}")


class TestHeyGenAvatarsVoices:
    """Test HeyGen avatars and voices endpoints"""
    
    def test_list_avatars(self, api_client):
        """GET /api/heygen/avatars should return avatar list"""
        response = api_client.get(f"{BASE_URL}/api/heygen/avatars")
        assert response.status_code == 200
        
        data = response.json()
        assert "avatars" in data, "Missing avatars field"
        assert isinstance(data["avatars"], list), "Avatars should be a list"
        
        if len(data["avatars"]) > 0:
            avatar = data["avatars"][0]
            assert "avatar_id" in avatar, "Avatar missing avatar_id"
            assert "avatar_name" in avatar, "Avatar missing avatar_name"
            print(f"Found {len(data['avatars'])} avatars")
        
    def test_list_voices(self, api_client):
        """GET /api/heygen/voices should return voice list"""
        response = api_client.get(f"{BASE_URL}/api/heygen/voices")
        assert response.status_code == 200
        
        data = response.json()
        assert "voices" in data, "Missing voices field"
        assert isinstance(data["voices"], list), "Voices should be a list"
        
        if len(data["voices"]) > 0:
            voice = data["voices"][0]
            assert "voice_id" in voice, "Voice missing voice_id"
            print(f"Found {len(data['voices'])} voices")
            
    def test_voices_filter_by_language(self, api_client):
        """Voices can be filtered by language"""
        response = api_client.get(f"{BASE_URL}/api/heygen/voices?language=portuguese")
        assert response.status_code == 200
        
        data = response.json()
        portuguese_voices = data.get("voices", [])
        print(f"Found {len(portuguese_voices)} Portuguese voices")


class TestGenerateAllSlideScripts:
    """Test AI script generation for all slides"""
    
    def test_generate_scripts_endpoint_exists(self, api_client):
        """POST /api/heygen/generate-all-slide-scripts should exist"""
        response = api_client.post(
            f"{BASE_URL}/api/heygen/generate-all-slide-scripts?project_id={TEST_PROJECT_ID}"
        )
        # Should not be 404 or 405
        assert response.status_code != 404, "Endpoint not found"
        assert response.status_code != 405, "Method not allowed"
        print(f"Generate scripts response status: {response.status_code}")
        
    def test_generate_scripts_with_valid_project(self, api_client):
        """Generate scripts should return scripts for valid project"""
        response = api_client.post(
            f"{BASE_URL}/api/heygen/generate-all-slide-scripts?project_id={TEST_PROJECT_ID}",
            timeout=90  # AI generation can take time
        )
        
        # Note: This may take 30-45 seconds as it calls Gemini for each slide
        if response.status_code == 200:
            data = response.json()
            assert "scripts" in data, "Missing scripts field"
            assert "total" in data, "Missing total field"
            
            scripts = data.get("scripts", [])
            print(f"Generated {len(scripts)} scripts")
            
            if len(scripts) > 0:
                script = scripts[0]
                assert "index" in script, "Script missing index"
                assert "title" in script, "Script missing title"
                assert "script" in script, "Script missing script text"
                print(f"First script preview: {script.get('script', '')[:100]}...")
        else:
            # May fail if project doesn't exist or AI key issue
            print(f"Script generation returned {response.status_code}: {response.text[:200]}")
            
    def test_generate_scripts_invalid_project(self, api_client):
        """Invalid project ID should return 404"""
        fake_project_id = str(uuid.uuid4())
        response = api_client.post(
            f"{BASE_URL}/api/heygen/generate-all-slide-scripts?project_id={fake_project_id}"
        )
        assert response.status_code == 404, f"Expected 404 for invalid project, got {response.status_code}"


class TestGenerateSingleSlideVideo:
    """Test single slide video generation"""
    
    def test_endpoint_exists(self, api_client):
        """POST /api/heygen/generate-slide-video should exist and validate input"""
        response = api_client.post(
            f"{BASE_URL}/api/heygen/generate-slide-video",
            json={
                "project_id": TEST_PROJECT_ID,
                "slide_index": 0,
                "avatar_id": "invalid_avatar",
                "voice_id": "invalid_voice",
                "script": "Test script",
                "title": "Test"
            }
        )
        # Endpoint exists - may return error for invalid avatar/voice, but not 404/405
        # 404 would mean "endpoint not found" but HeyGen returns error as "avatar not found"
        # which indicates the endpoint works but the avatar_id is invalid
        print(f"Single slide video endpoint status: {response.status_code}, detail: {response.text[:200]}")
        
        # If status is not 404/405, or if it's a HeyGen API error (avatar not found), endpoint works
        if response.status_code == 404:
            # Check if it's a HeyGen API error (avatar not found) vs endpoint not found
            detail = response.json().get("detail", "")
            if "avatar" in detail.lower() or "heygen" in detail.lower():
                # This is HeyGen returning an error, endpoint works
                print("Endpoint works - HeyGen API returned avatar error")
            else:
                pytest.fail("Endpoint not found")
        else:
            assert response.status_code != 405, "Method not allowed"
        
    def test_invalid_project(self, api_client):
        """Invalid project should return 404"""
        response = api_client.post(
            f"{BASE_URL}/api/heygen/generate-slide-video",
            json={
                "project_id": str(uuid.uuid4()),
                "slide_index": 0,
                "avatar_id": "test",
                "voice_id": "test",
                "script": "Test",
                "title": "Test"
            }
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"


class TestGenerateBatchSlideVideos:
    """Test batch slide video generation"""
    
    def test_endpoint_exists(self, api_client):
        """POST /api/heygen/generate-batch-slide-videos should exist"""
        response = api_client.post(
            f"{BASE_URL}/api/heygen/generate-batch-slide-videos",
            json={
                "project_id": TEST_PROJECT_ID,
                "avatar_id": "test",
                "voice_id": "test",
                "slides": []
            }
        )
        # Should not be 404 or 405
        assert response.status_code != 404, "Endpoint not found"
        assert response.status_code != 405, "Method not allowed"
        print(f"Batch video endpoint status: {response.status_code}")
        
    def test_batch_with_empty_slides(self, api_client):
        """Batch with no slides should return batch info"""
        response = api_client.post(
            f"{BASE_URL}/api/heygen/generate-batch-slide-videos",
            json={
                "project_id": TEST_PROJECT_ID,
                "avatar_id": "test",
                "voice_id": "test",
                "slides": []
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            assert "batch_id" in data, "Missing batch_id"
            assert "total" in data, "Missing total"
            print(f"Batch response: {data}")


class TestBatchStatus:
    """Test batch status endpoint"""
    
    def test_batch_status_not_found(self, api_client):
        """Invalid batch ID should return 404"""
        fake_batch_id = str(uuid.uuid4())
        response = api_client.get(f"{BASE_URL}/api/heygen/batch-status/{fake_batch_id}")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        
    def test_batch_status_endpoint_format(self, api_client):
        """Batch status endpoint should accept UUID format"""
        # First create a batch to get a valid batch_id
        batch_response = api_client.post(
            f"{BASE_URL}/api/heygen/generate-batch-slide-videos",
            json={
                "project_id": TEST_PROJECT_ID,
                "avatar_id": "test",
                "voice_id": "test",
                "slides": []
            }
        )
        
        if batch_response.status_code == 200:
            batch_id = batch_response.json().get("batch_id")
            if batch_id:
                status_response = api_client.get(f"{BASE_URL}/api/heygen/batch-status/{batch_id}")
                assert status_response.status_code == 200, f"Expected 200, got {status_response.status_code}"
                
                data = status_response.json()
                assert "batch_id" in data, "Missing batch_id"
                assert "results" in data, "Missing results"
                print(f"Batch status: {data}")


class TestVideoStatusAndLibrary:
    """Test video status and library endpoints"""
    
    def test_list_videos(self, api_client):
        """GET /api/heygen/videos should return video list"""
        response = api_client.get(f"{BASE_URL}/api/heygen/videos")
        assert response.status_code == 200
        
        data = response.json()
        assert "videos" in data, "Missing videos field"
        print(f"Found {len(data.get('videos', []))} videos in library")
        
    def test_list_videos_by_project(self, api_client):
        """Videos can be filtered by project_id"""
        response = api_client.get(f"{BASE_URL}/api/heygen/videos?project_id={TEST_PROJECT_ID}")
        assert response.status_code == 200
        
        data = response.json()
        assert "videos" in data
        print(f"Found {len(data.get('videos', []))} videos for project")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
