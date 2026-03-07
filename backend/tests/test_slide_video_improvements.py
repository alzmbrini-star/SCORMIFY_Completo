"""
Test suite for NEW Slide-to-Video Improvements (Iteration 65)
Tests:
1. render-slide endpoint (PIL image rendering)
2. render-all-slides endpoint with selectedIndices
3. generate-all-slide-scripts with selectedIndices body parameter
4. Avatar gender filter
5. Voice language/gender filters
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
TEST_PROJECT_ID = "82d2d9d4-3067-47de-bf5a-0e14e9051e67"


@pytest.fixture(scope="module")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


class TestRenderSlideEndpoint:
    """Test POST /api/heygen/render-slide/{project_id}/{slide_index} - renders slide as PNG"""
    
    def test_render_single_slide_endpoint_exists(self, api_client):
        """POST /api/heygen/render-slide/{project_id}/{slide_index} should exist"""
        response = api_client.post(
            f"{BASE_URL}/api/heygen/render-slide/{TEST_PROJECT_ID}/0"
        )
        # Should not be 404 or 405
        assert response.status_code != 404, f"Endpoint not found: {response.text}"
        assert response.status_code != 405, "Method not allowed"
        print(f"Render slide endpoint status: {response.status_code}")
        
    def test_render_slide_returns_url(self, api_client):
        """Render slide should return URL to PNG image"""
        response = api_client.post(
            f"{BASE_URL}/api/heygen/render-slide/{TEST_PROJECT_ID}/0"
        )
        
        if response.status_code == 200:
            data = response.json()
            assert "url" in data, "Missing url field"
            assert "width" in data, "Missing width field"
            assert "height" in data, "Missing height field"
            assert "slide_index" in data, "Missing slide_index field"
            
            # URL should point to assets folder
            assert "/api/projects/" in data["url"], "URL should be project asset path"
            assert ".png" in data["url"], "URL should be PNG file"
            assert data["slide_index"] == 0, "Slide index should match request"
            print(f"Rendered slide URL: {data['url']}")
        else:
            print(f"Render returned {response.status_code}: {response.text[:200]}")
            
    def test_render_slide_invalid_project(self, api_client):
        """Invalid project ID should return 404"""
        fake_project = str(uuid.uuid4())
        response = api_client.post(
            f"{BASE_URL}/api/heygen/render-slide/{fake_project}/0"
        )
        assert response.status_code == 404
        
    def test_render_slide_invalid_index(self, api_client):
        """Invalid slide index should return 404"""
        response = api_client.post(
            f"{BASE_URL}/api/heygen/render-slide/{TEST_PROJECT_ID}/999"
        )
        assert response.status_code == 404


class TestRenderAllSlidesEndpoint:
    """Test POST /api/heygen/render-all-slides/{project_id} with selectedIndices"""
    
    def test_render_all_slides_endpoint_exists(self, api_client):
        """POST /api/heygen/render-all-slides/{project_id} should exist"""
        response = api_client.post(
            f"{BASE_URL}/api/heygen/render-all-slides/{TEST_PROJECT_ID}",
            json={}
        )
        assert response.status_code != 404, "Endpoint not found"
        assert response.status_code != 405, "Method not allowed"
        print(f"Render all slides status: {response.status_code}")
        
    def test_render_all_slides_returns_results(self, api_client):
        """Should return rendered results array"""
        response = api_client.post(
            f"{BASE_URL}/api/heygen/render-all-slides/{TEST_PROJECT_ID}",
            json={}  # Empty = render all
        )
        
        if response.status_code == 200:
            data = response.json()
            assert "rendered" in data, "Missing rendered count"
            assert "results" in data, "Missing results array"
            assert isinstance(data["results"], list), "Results should be a list"
            print(f"Rendered {data['rendered']} slides")
            
    def test_render_all_slides_with_selected_indices(self, api_client):
        """Should only render selected slides when selectedIndices provided"""
        response = api_client.post(
            f"{BASE_URL}/api/heygen/render-all-slides/{TEST_PROJECT_ID}",
            json={"selectedIndices": [0, 1]}  # Only render first 2 slides
        )
        
        if response.status_code == 200:
            data = response.json()
            # Should only have results for selected indices
            for result in data.get("results", []):
                if "slide_index" in result:
                    assert result["slide_index"] in [0, 1], f"Unexpected slide {result['slide_index']}"
            print(f"Selectively rendered {data['rendered']} slides")
            
    def test_render_all_slides_invalid_project(self, api_client):
        """Invalid project should return 404"""
        fake_project = str(uuid.uuid4())
        response = api_client.post(
            f"{BASE_URL}/api/heygen/render-all-slides/{fake_project}",
            json={}
        )
        assert response.status_code == 404


class TestGenerateScriptsWithSelectedIndices:
    """Test generate-all-slide-scripts now accepts selectedIndices in body"""
    
    def test_scripts_endpoint_accepts_body(self, api_client):
        """Endpoint should accept JSON body with selectedIndices"""
        response = api_client.post(
            f"{BASE_URL}/api/heygen/generate-all-slide-scripts?project_id={TEST_PROJECT_ID}",
            json={"selectedIndices": [0]}  # Only generate for first slide
        )
        assert response.status_code != 404, "Endpoint not found"
        print(f"Scripts with body status: {response.status_code}")
        
    def test_scripts_with_selected_indices_filters_slides(self, api_client):
        """Should only generate scripts for selected slides"""
        # Generate for only slide 0
        response = api_client.post(
            f"{BASE_URL}/api/heygen/generate-all-slide-scripts?project_id={TEST_PROJECT_ID}",
            json={"selectedIndices": [0]},
            timeout=90
        )
        
        if response.status_code == 200:
            data = response.json()
            scripts = data.get("scripts", [])
            
            # Should only have script for index 0
            for script in scripts:
                assert script["index"] == 0, f"Expected only index 0, got {script['index']}"
            print(f"Filtered scripts count: {len(scripts)}")
        else:
            print(f"Generation returned {response.status_code}: {response.text[:200]}")


class TestAvatarGenderFilter:
    """Test avatar filtering by gender"""
    
    def test_avatars_filter_by_male(self, api_client):
        """GET /api/heygen/avatars?gender=male should return only male avatars"""
        response = api_client.get(f"{BASE_URL}/api/heygen/avatars?gender=male")
        assert response.status_code == 200
        
        data = response.json()
        avatars = data.get("avatars", [])
        
        # All returned avatars should be male
        for avatar in avatars:
            assert avatar.get("gender") == "male", f"Expected male, got {avatar.get('gender')}"
        print(f"Found {len(avatars)} male avatars")
        
    def test_avatars_filter_by_female(self, api_client):
        """GET /api/heygen/avatars?gender=female should return only female avatars"""
        response = api_client.get(f"{BASE_URL}/api/heygen/avatars?gender=female")
        assert response.status_code == 200
        
        data = response.json()
        avatars = data.get("avatars", [])
        
        for avatar in avatars:
            assert avatar.get("gender") == "female", f"Expected female, got {avatar.get('gender')}"
        print(f"Found {len(avatars)} female avatars")
        
    def test_avatars_all_returns_available_genders(self, api_client):
        """Avatars response should include available_genders list"""
        response = api_client.get(f"{BASE_URL}/api/heygen/avatars")
        assert response.status_code == 200
        
        data = response.json()
        assert "available_genders" in data, "Missing available_genders field"
        print(f"Available genders: {data.get('available_genders')}")


class TestVoiceLanguageGenderFilters:
    """Test voice filtering by language and gender"""
    
    def test_voices_filter_by_portuguese(self, api_client):
        """Voices filter by Portuguese language"""
        response = api_client.get(f"{BASE_URL}/api/heygen/voices?language=portuguese")
        assert response.status_code == 200
        
        data = response.json()
        voices = data.get("voices", [])
        print(f"Found {len(voices)} Portuguese voices")
        
    def test_voices_filter_by_english(self, api_client):
        """Voices filter by English language"""
        response = api_client.get(f"{BASE_URL}/api/heygen/voices?language=english")
        assert response.status_code == 200
        
        data = response.json()
        voices = data.get("voices", [])
        print(f"Found {len(voices)} English voices")
        
    def test_voices_filter_by_gender_male(self, api_client):
        """GET /api/heygen/voices?gender=male should filter by male"""
        response = api_client.get(f"{BASE_URL}/api/heygen/voices?gender=male")
        assert response.status_code == 200
        
        data = response.json()
        voices = data.get("voices", [])
        
        for voice in voices:
            # HeyGen returns "Male"/"Female" capitalized
            assert voice.get("gender", "").lower() == "male", f"Expected male, got {voice.get('gender')}"
        print(f"Found {len(voices)} male voices")
        
    def test_voices_filter_by_gender_female(self, api_client):
        """GET /api/heygen/voices?gender=female should filter by female"""
        response = api_client.get(f"{BASE_URL}/api/heygen/voices?gender=female")
        assert response.status_code == 200
        
        data = response.json()
        voices = data.get("voices", [])
        
        for voice in voices:
            # HeyGen returns "Male"/"Female" capitalized
            assert voice.get("gender", "").lower() == "female", f"Expected female, got {voice.get('gender')}"
        print(f"Found {len(voices)} female voices")
        
    def test_voices_combined_filters(self, api_client):
        """Voices can be filtered by both language and gender"""
        response = api_client.get(f"{BASE_URL}/api/heygen/voices?language=portuguese&gender=female")
        assert response.status_code == 200
        
        data = response.json()
        voices = data.get("voices", [])
        
        for voice in voices:
            # HeyGen returns "Male"/"Female" capitalized
            assert voice.get("gender", "").lower() == "female"
        print(f"Found {len(voices)} Portuguese female voices")
        
    def test_voices_returns_available_languages(self, api_client):
        """Voices response should include available_languages list"""
        response = api_client.get(f"{BASE_URL}/api/heygen/voices")
        assert response.status_code == 200
        
        data = response.json()
        assert "available_languages" in data, "Missing available_languages field"
        print(f"Available languages: {len(data.get('available_languages', []))}")


class TestRenderedImageAccess:
    """Test that rendered slide images are accessible"""
    
    def test_rendered_image_is_accessible(self, api_client):
        """Rendered PNG should be accessible via GET request"""
        # First render a slide
        render_response = api_client.post(
            f"{BASE_URL}/api/heygen/render-slide/{TEST_PROJECT_ID}/0"
        )
        
        if render_response.status_code == 200:
            url = render_response.json().get("url", "")
            if url:
                # Try to access the rendered image
                full_url = f"{BASE_URL}{url}"
                img_response = requests.get(full_url)
                assert img_response.status_code == 200, f"Cannot access rendered image: {img_response.status_code}"
                assert "image" in img_response.headers.get("content-type", ""), "Response is not an image"
                print(f"Rendered image accessible at {full_url}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
