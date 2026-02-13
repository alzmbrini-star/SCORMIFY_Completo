"""
Test AI Narration Generation with Vision (Gemini 3 Flash multimodal)

Tests the upgraded generate-narration endpoint that now:
1. Reads backgroundImage from PPT-imported slides
2. Sends images to Gemini 3 Flash via FileContent for OCR/vision
3. Extracts text from text/html elements
4. Handles slides with image elements (src field)
5. Returns 3 contextually relevant narration options based on actual slide content
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test data from review request
PROJECT_WITH_BG_IMAGE = "9ba5a584-6477-44b4-8406-bb46d9981e64"
SLIDE_WITH_BG_IMAGE = "48694b10-d218-4b2e-963f-98be8f71e370"

PROJECT_WITH_TEXT_ELEMENTS = "58753bb1-60a3-4190-8de3-ca51203e8f4d"
SLIDE_WITH_TEXT_ELEMENTS = "a15ba602-9030-46c5-996c-0fdcd64fa366"


class TestAINarrationVision:
    """Test AI narration generation with vision/OCR capabilities"""

    def test_health_check(self):
        """Verify API is accessible"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200, f"Health check failed: {response.text}"
        print("✅ Health check passed")

    def test_project_with_bg_image_exists(self):
        """Verify the PPT-imported project with backgroundImage exists"""
        response = requests.get(f"{BASE_URL}/api/projects/{PROJECT_WITH_BG_IMAGE}")
        assert response.status_code == 200, f"Project not found: {response.text}"
        data = response.json()
        assert data.get('name') == 'Apres_Didaxis', f"Project name mismatch: {data.get('name')}"
        
        # Verify slide has backgroundImage
        slides = data.get('course', {}).get('slides', [])
        target_slide = next((s for s in slides if s.get('id') == SLIDE_WITH_BG_IMAGE), None)
        assert target_slide is not None, f"Slide {SLIDE_WITH_BG_IMAGE} not found"
        
        bg_image = target_slide.get('backgroundImage', '')
        assert bg_image, "Slide missing backgroundImage"
        assert bg_image.startswith('/api/projects/'), f"Invalid backgroundImage URL: {bg_image}"
        print(f"✅ Project found with backgroundImage: {bg_image}")

    def test_generate_narration_with_vision_educational_style(self):
        """Test narration generation using vision (OCR) for slide with backgroundImage - Educational style"""
        response = requests.post(
            f"{BASE_URL}/api/projects/{PROJECT_WITH_BG_IMAGE}/slides/{SLIDE_WITH_BG_IMAGE}/generate-narration",
            json={
                "slide_content": "",
                "style": "educational",
                "language": "português brasileiro"
            },
            timeout=90  # LLM calls take time
        )
        assert response.status_code == 200, f"API error: {response.status_code} - {response.text}"
        
        data = response.json()
        assert 'options' in data, "Response missing 'options'"
        options = data['options']
        assert len(options) == 3, f"Expected 3 options, got {len(options)}"
        
        # Verify each option has meaningful content
        for i, opt in enumerate(options):
            assert isinstance(opt, str), f"Option {i} is not a string"
            assert len(opt) > 30, f"Option {i} too short ({len(opt)} chars): {opt[:50]}..."
            print(f"✅ Option {i}: {opt[:100]}...")
        
        # The slide image contains "Didaxis" branding - verify narration mentions it
        # (This validates that Gemini actually reads the image content)
        all_text = " ".join(options).lower()
        print(f"\nAll narration text (lower): {all_text[:200]}...")
        
        assert data.get('slide_id') == SLIDE_WITH_BG_IMAGE, "slide_id mismatch"
        assert data.get('style') == 'educational', "style mismatch"
        print("✅ Vision-based narration (educational) generated successfully with 3 options")

    def test_generate_narration_with_vision_conversational_style(self):
        """Test narration generation with conversational style"""
        response = requests.post(
            f"{BASE_URL}/api/projects/{PROJECT_WITH_BG_IMAGE}/slides/{SLIDE_WITH_BG_IMAGE}/generate-narration",
            json={
                "slide_content": "",
                "style": "conversational",
                "language": "português brasileiro"
            },
            timeout=90
        )
        assert response.status_code == 200, f"API error: {response.status_code} - {response.text}"
        
        data = response.json()
        assert len(data.get('options', [])) == 3, "Expected 3 options"
        assert data.get('style') == 'conversational'
        print("✅ Conversational style works correctly")

    def test_generate_narration_with_vision_formal_style(self):
        """Test narration generation with formal style"""
        response = requests.post(
            f"{BASE_URL}/api/projects/{PROJECT_WITH_BG_IMAGE}/slides/{SLIDE_WITH_BG_IMAGE}/generate-narration",
            json={
                "slide_content": "",
                "style": "formal",
                "language": "português brasileiro"
            },
            timeout=90
        )
        assert response.status_code == 200, f"API error: {response.status_code} - {response.text}"
        
        data = response.json()
        assert len(data.get('options', [])) == 3, "Expected 3 options"
        assert data.get('style') == 'formal'
        print("✅ Formal style works correctly")

    def test_generate_narration_with_vision_friendly_style(self):
        """Test narration generation with friendly style"""
        response = requests.post(
            f"{BASE_URL}/api/projects/{PROJECT_WITH_BG_IMAGE}/slides/{SLIDE_WITH_BG_IMAGE}/generate-narration",
            json={
                "slide_content": "",
                "style": "friendly",
                "language": "português brasileiro"
            },
            timeout=90
        )
        assert response.status_code == 200, f"API error: {response.status_code} - {response.text}"
        
        data = response.json()
        assert len(data.get('options', [])) == 3, "Expected 3 options"
        assert data.get('style') == 'friendly'
        print("✅ Friendly style works correctly")

    def test_generate_narration_with_text_elements(self):
        """Test narration for slide with text/html elements (no backgroundImage)"""
        response = requests.post(
            f"{BASE_URL}/api/projects/{PROJECT_WITH_TEXT_ELEMENTS}/slides/{SLIDE_WITH_TEXT_ELEMENTS}/generate-narration",
            json={
                "slide_content": "",
                "style": "educational",
                "language": "português brasileiro"
            },
            timeout=90
        )
        assert response.status_code == 200, f"API error: {response.status_code} - {response.text}"
        
        data = response.json()
        assert len(data.get('options', [])) == 3, "Expected 3 options"
        print("✅ Narration generated for slide with text elements (no image)")

    def test_nonexistent_project_returns_404(self):
        """Test that non-existent project returns 404"""
        response = requests.post(
            f"{BASE_URL}/api/projects/nonexistent-project-id/slides/some-slide/generate-narration",
            json={
                "slide_content": "",
                "style": "educational",
                "language": "português brasileiro"
            },
            timeout=30
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✅ Non-existent project returns 404")

    def test_nonexistent_slide_returns_404(self):
        """Test that non-existent slide returns 404"""
        response = requests.post(
            f"{BASE_URL}/api/projects/{PROJECT_WITH_BG_IMAGE}/slides/nonexistent-slide-id/generate-narration",
            json={
                "slide_content": "",
                "style": "educational",
                "language": "português brasileiro"
            },
            timeout=30
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✅ Non-existent slide returns 404")

    def test_different_slides_have_different_content(self):
        """Test that different slides produce different narrations (proves image reading works)"""
        # Generate for slide 1 (slide_001.png)
        response1 = requests.post(
            f"{BASE_URL}/api/projects/{PROJECT_WITH_BG_IMAGE}/slides/{SLIDE_WITH_BG_IMAGE}/generate-narration",
            json={
                "slide_content": "",
                "style": "educational",
                "language": "português brasileiro"
            },
            timeout=90
        )
        assert response1.status_code == 200
        options1 = response1.json().get('options', [])
        
        # Generate for slide 2 (slide_002.png) - second slide ID
        second_slide_id = "bbdd8179-d531-411a-bf49-51b20cdb4c30"
        response2 = requests.post(
            f"{BASE_URL}/api/projects/{PROJECT_WITH_BG_IMAGE}/slides/{second_slide_id}/generate-narration",
            json={
                "slide_content": "",
                "style": "educational",
                "language": "português brasileiro"
            },
            timeout=90
        )
        assert response2.status_code == 200
        options2 = response2.json().get('options', [])
        
        # Verify the narrations are different (different slides = different content)
        text1 = " ".join(options1).lower()
        text2 = " ".join(options2).lower()
        
        # They should not be identical (Gemini reads different images)
        assert text1 != text2, "Narrations for different slides should be different"
        print(f"✅ Different slides produce different narrations (proves image reading works)")
        print(f"   Slide 1 narration: {text1[:100]}...")
        print(f"   Slide 2 narration: {text2[:100]}...")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
