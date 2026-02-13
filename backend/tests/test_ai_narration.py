"""
Test suite for AI-powered narration text generation feature
POST /api/projects/{project_id}/slides/{slide_id}/generate-narration

Tests:
- Endpoint returns 3 narration options
- Each option is a non-empty string
- Style parameter is respected
- Works with different styles (educational, conversational, formal, friendly)
- Handles missing project/slide with 404
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials from review request
TEST_PROJECT_ID = "58753bb1-60a3-4190-8de3-ca51203e8f4d"
TEST_SLIDE_ID = "a15ba602-9030-46c5-996c-0fdcd64fa366"


class TestAINarrationGeneration:
    """Tests for AI Narration Generation endpoint"""

    def test_health_check(self):
        """Verify backend is healthy before running tests"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        print("✅ Backend health check passed")

    def test_generate_narration_returns_3_options(self):
        """Test that endpoint returns exactly 3 narration options"""
        response = requests.post(
            f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/slides/{TEST_SLIDE_ID}/generate-narration",
            json={
                "slide_content": "Test slide content",
                "style": "educational",
                "language": "português brasileiro"
            },
            timeout=60  # AI calls can take time
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "options" in data, "Response should contain 'options' field"
        assert len(data["options"]) == 3, f"Expected 3 options, got {len(data['options'])}"
        print("✅ Endpoint returns exactly 3 options")

    def test_narration_options_are_non_empty_strings(self):
        """Test that each narration option is a non-empty string"""
        response = requests.post(
            f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/slides/{TEST_SLIDE_ID}/generate-narration",
            json={
                "slide_content": "Introduction slide for course",
                "style": "educational",
                "language": "português brasileiro"
            },
            timeout=60
        )
        
        assert response.status_code == 200
        data = response.json()
        
        for i, option in enumerate(data["options"]):
            assert isinstance(option, str), f"Option {i} should be a string"
            assert len(option.strip()) > 10, f"Option {i} should have meaningful content"
        print("✅ All 3 options are non-empty strings with meaningful content")

    def test_style_parameter_educational(self):
        """Test educational style narration generation"""
        response = requests.post(
            f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/slides/{TEST_SLIDE_ID}/generate-narration",
            json={
                "slide_content": "Mathematics fundamentals",
                "style": "educational",
                "language": "português brasileiro"
            },
            timeout=60
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["style"] == "educational"
        assert len(data["options"]) == 3
        print("✅ Educational style works correctly")

    def test_style_parameter_conversational(self):
        """Test conversational style narration generation"""
        response = requests.post(
            f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/slides/{TEST_SLIDE_ID}/generate-narration",
            json={
                "slide_content": "About our company",
                "style": "conversational",
                "language": "português brasileiro"
            },
            timeout=60
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["style"] == "conversational"
        assert len(data["options"]) == 3
        print("✅ Conversational style works correctly")

    def test_style_parameter_formal(self):
        """Test formal style narration generation"""
        response = requests.post(
            f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/slides/{TEST_SLIDE_ID}/generate-narration",
            json={
                "slide_content": "Corporate policies and procedures",
                "style": "formal",
                "language": "português brasileiro"
            },
            timeout=60
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["style"] == "formal"
        assert len(data["options"]) == 3
        print("✅ Formal style works correctly")

    def test_style_parameter_friendly(self):
        """Test friendly style narration generation"""
        response = requests.post(
            f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/slides/{TEST_SLIDE_ID}/generate-narration",
            json={
                "slide_content": "Welcome to the team!",
                "style": "friendly",
                "language": "português brasileiro"
            },
            timeout=60
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["style"] == "friendly"
        assert len(data["options"]) == 3
        print("✅ Friendly style works correctly")

    def test_response_includes_slide_id(self):
        """Test that response includes the slide_id"""
        response = requests.post(
            f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/slides/{TEST_SLIDE_ID}/generate-narration",
            json={
                "slide_content": "Test content",
                "style": "educational",
                "language": "português brasileiro"
            },
            timeout=60
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "slide_id" in data
        assert data["slide_id"] == TEST_SLIDE_ID
        print("✅ Response includes correct slide_id")

    def test_nonexistent_project_returns_404(self):
        """Test that non-existent project returns 404"""
        fake_project_id = "00000000-0000-0000-0000-000000000000"
        response = requests.post(
            f"{BASE_URL}/api/projects/{fake_project_id}/slides/{TEST_SLIDE_ID}/generate-narration",
            json={
                "slide_content": "Test",
                "style": "educational",
                "language": "português brasileiro"
            },
            timeout=30
        )
        
        assert response.status_code == 404
        print("✅ Non-existent project returns 404")

    def test_nonexistent_slide_returns_404(self):
        """Test that non-existent slide returns 404"""
        fake_slide_id = "00000000-0000-0000-0000-000000000000"
        response = requests.post(
            f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/slides/{fake_slide_id}/generate-narration",
            json={
                "slide_content": "Test",
                "style": "educational",
                "language": "português brasileiro"
            },
            timeout=30
        )
        
        assert response.status_code == 404
        print("✅ Non-existent slide returns 404")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
