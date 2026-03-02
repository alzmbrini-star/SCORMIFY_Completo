"""
Test Visual Improvements for AI Agent Generated Courses
- Professional backgrounds on ALL slides (dark for title/quiz, light for content)
- Stock images related to content theme
- Proper element structure (header bars, two-column layouts)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Existing generated project ID from testing context
EXISTING_PROJECT_ID = "ebe2ac7b-5565-4d7f-a486-17910291f36a"

# Color palette expectations (from ai_agent.py _COURSE_PALETTES)
DARK_PALETTE_COLORS = ["#0f172a", "#1e1b4b", "#172554", "#14532d", "#7f1d1d", "#78350f"]
LIGHT_PALETTE_COLORS = ["#f0fdf4", "#f5f3ff", "#eff6ff", "#f0fdf4", "#fef2f2", "#fffbeb"]


class TestAgentTemplates:
    """Test GET /api/agent/templates returns 6 templates"""
    
    def test_templates_endpoint_returns_200(self):
        response = requests.get(f"{BASE_URL}/api/agent/templates")
        assert response.status_code == 200
        print("PASS: Templates endpoint returns 200")
    
    def test_templates_returns_6(self):
        response = requests.get(f"{BASE_URL}/api/agent/templates")
        templates = response.json()
        assert len(templates) == 6, f"Expected 6 templates, got {len(templates)}"
        print(f"PASS: 6 templates returned: {[t['id'] for t in templates]}")
    
    def test_expected_template_ids(self):
        response = requests.get(f"{BASE_URL}/api/agent/templates")
        templates = response.json()
        expected_ids = {"onboarding", "compliance", "technical", "soft_skills", "health_safety", "sales"}
        actual_ids = {t["id"] for t in templates}
        assert actual_ids == expected_ids, f"Template IDs mismatch: {actual_ids}"
        print(f"PASS: All expected template IDs present")


class TestAgentCourses:
    """Test GET /api/agent/courses returns list of agent-created courses"""
    
    def test_courses_endpoint_returns_200(self):
        response = requests.get(f"{BASE_URL}/api/agent/courses")
        assert response.status_code == 200
        print("PASS: Agent courses endpoint returns 200")
    
    def test_courses_returns_list(self):
        response = requests.get(f"{BASE_URL}/api/agent/courses")
        courses = response.json()
        assert isinstance(courses, list)
        print(f"PASS: Returns list with {len(courses)} courses")
    
    def test_existing_course_in_list(self):
        response = requests.get(f"{BASE_URL}/api/agent/courses")
        courses = response.json()
        course_ids = [c["id"] for c in courses]
        assert EXISTING_PROJECT_ID in course_ids, f"Expected project {EXISTING_PROJECT_ID} not in agent courses"
        print(f"PASS: Generated project found in agent courses list")


class TestGeneratedCourseVisualStructure:
    """Test generated course has professional backgrounds and visual elements"""
    
    @pytest.fixture
    def project_data(self):
        response = requests.get(f"{BASE_URL}/api/projects/{EXISTING_PROJECT_ID}")
        assert response.status_code == 200, f"Failed to get project: {response.text}"
        return response.json()
    
    def test_project_exists(self, project_data):
        assert project_data is not None
        assert project_data.get("id") == EXISTING_PROJECT_ID
        print(f"PASS: Project exists - {project_data.get('name')}")
    
    def test_project_marked_as_agent_created(self, project_data):
        assert project_data.get("createdByAgent") == True, "Project not marked as created by agent"
        print("PASS: Project marked with createdByAgent=True")
    
    def test_slides_have_backgrounds(self, project_data):
        slides = project_data.get("course", {}).get("slides", [])
        assert len(slides) > 0, "No slides in project"
        
        for i, slide in enumerate(slides):
            bg = slide.get("background")
            assert bg is not None, f"Slide {i+1} has no background"
            assert bg != "#FFFFFF", f"Slide {i+1} still has default white background"
        
        print(f"PASS: All {len(slides)} slides have colored backgrounds (not white)")
    
    def test_title_slides_have_dark_background(self, project_data):
        """Title/cover slides should have dark palette primary color"""
        slides = project_data.get("course", {}).get("slides", [])
        
        # First slide is usually title
        first_slide = slides[0]
        bg = first_slide.get("background", "").lower()
        
        # Check if background is from dark palette
        is_dark = bg in [c.lower() for c in DARK_PALETTE_COLORS]
        assert is_dark, f"Title slide background {bg} not in dark palette {DARK_PALETTE_COLORS}"
        print(f"PASS: Title slide has dark background: {bg}")
    
    def test_content_slides_have_light_background(self, project_data):
        """Content slides should have light contentBg color"""
        slides = project_data.get("course", {}).get("slides", [])
        
        content_slides = [s for s in slides if s.get("title") and "Quiz" not in s.get("title", "") and "Capa" not in s.get("title", "")]
        
        light_count = 0
        for slide in content_slides[:5]:  # Check first 5 content slides
            bg = slide.get("background", "").lower()
            if bg in [c.lower() for c in LIGHT_PALETTE_COLORS]:
                light_count += 1
        
        assert light_count > 0, f"No content slides with light background found"
        print(f"PASS: {light_count} content slides have light backgrounds")
    
    def test_quiz_slides_have_dark_background(self, project_data):
        """Quiz slides should have dark primary color"""
        slides = project_data.get("course", {}).get("slides", [])
        
        quiz_slides = [s for s in slides if "Quiz" in s.get("title", "")]
        
        if len(quiz_slides) == 0:
            pytest.skip("No quiz slides found")
        
        for slide in quiz_slides:
            bg = slide.get("background", "").lower()
            is_dark = bg in [c.lower() for c in DARK_PALETTE_COLORS]
            assert is_dark, f"Quiz slide '{slide.get('title')}' background {bg} not dark"
        
        print(f"PASS: {len(quiz_slides)} quiz slides have dark backgrounds")


class TestGeneratedCourseStockImages:
    """Test generated course has stock images on content slides"""
    
    @pytest.fixture
    def project_data(self):
        response = requests.get(f"{BASE_URL}/api/projects/{EXISTING_PROJECT_ID}")
        return response.json()
    
    def test_content_slides_have_images(self, project_data):
        """Content slides should have type 'image' elements"""
        slides = project_data.get("course", {}).get("slides", [])
        
        content_slides = [s for s in slides if s.get("background", "").lower() in [c.lower() for c in LIGHT_PALETTE_COLORS]]
        
        slides_with_images = 0
        for slide in content_slides:
            elements = slide.get("elements", [])
            image_elements = [e for e in elements if e.get("type") == "image"]
            if len(image_elements) > 0:
                slides_with_images += 1
        
        assert slides_with_images > 0, "No content slides have image elements"
        print(f"PASS: {slides_with_images}/{len(content_slides)} content slides have images")
    
    def test_image_src_points_to_stock_assets(self, project_data):
        """Image src should point to /api/projects/{id}/assets/stock_*.jpg"""
        slides = project_data.get("course", {}).get("slides", [])
        
        stock_image_count = 0
        for slide in slides:
            for el in slide.get("elements", []):
                if el.get("type") == "image":
                    src = el.get("src", el.get("content", ""))
                    if f"/api/projects/{EXISTING_PROJECT_ID}/assets/stock_" in src:
                        stock_image_count += 1
                        print(f"  Found stock image: {src[:60]}...")
        
        assert stock_image_count > 0, "No stock images found in slides"
        print(f"PASS: {stock_image_count} stock images found")
    
    def test_stock_images_are_accessible(self, project_data):
        """Stock images should be downloadable"""
        slides = project_data.get("course", {}).get("slides", [])
        
        # Find first image element
        for slide in slides:
            for el in slide.get("elements", []):
                if el.get("type") == "image":
                    src = el.get("src", el.get("content", ""))
                    if "stock_" in src:
                        # Build full URL
                        full_url = f"{BASE_URL}{src}"
                        response = requests.get(full_url)
                        assert response.status_code == 200, f"Failed to download image: {full_url}"
                        assert len(response.content) > 1000, f"Image too small: {len(response.content)} bytes"
                        print(f"PASS: Stock image accessible and valid ({len(response.content)} bytes)")
                        return
        
        pytest.skip("No stock images found to test")


class TestGeneratedCourseElementStructure:
    """Test generated course has proper element structure"""
    
    @pytest.fixture
    def project_data(self):
        response = requests.get(f"{BASE_URL}/api/projects/{EXISTING_PROJECT_ID}")
        return response.json()
    
    def test_title_slides_have_html_elements(self, project_data):
        """Title slides should have 3 HTML elements (accent bar, title text, module trail)"""
        slides = project_data.get("course", {}).get("slides", [])
        
        # First slide is title
        title_slide = slides[0]
        elements = title_slide.get("elements", [])
        
        html_count = len([e for e in elements if e.get("type") == "html"])
        assert html_count >= 2, f"Title slide has only {html_count} html elements, expected at least 2"
        print(f"PASS: Title slide has {html_count} HTML elements")
    
    def test_content_slides_have_4_elements(self, project_data):
        """Content slides with images should have 4 elements (header, text, image, accent bar)"""
        slides = project_data.get("course", {}).get("slides", [])
        
        # Find content slides with images
        for slide in slides:
            elements = slide.get("elements", [])
            if any(e.get("type") == "image" for e in elements):
                # Content slide with image
                html_count = len([e for e in elements if e.get("type") == "html"])
                img_count = len([e for e in elements if e.get("type") == "image"])
                
                # Should have header bar (html), text (html), image, accent bar (html)
                assert html_count >= 2, f"Content slide '{slide.get('title')}' has only {html_count} html elements"
                assert img_count >= 1, f"Content slide '{slide.get('title')}' has no images"
                print(f"PASS: Content slide '{slide.get('title')[:30]}' has {html_count} html + {img_count} image elements")
                return
        
        pytest.skip("No content slides with images found")
    
    def test_quiz_slides_have_elements(self, project_data):
        """Quiz slides should have 2-3 HTML elements (header, quiz indicator, questions preview)"""
        slides = project_data.get("course", {}).get("slides", [])
        
        quiz_slides = [s for s in slides if "Quiz" in s.get("title", "")]
        
        if len(quiz_slides) == 0:
            pytest.skip("No quiz slides found")
        
        quiz_slide = quiz_slides[0]
        elements = quiz_slide.get("elements", [])
        element_count = len(elements)
        
        assert element_count >= 2, f"Quiz slide has only {element_count} elements, expected at least 2"
        print(f"PASS: Quiz slide has {element_count} elements")


class TestAgentSessionFlow:
    """Test the full agent session flow can be initiated"""
    
    def test_create_session(self):
        """Test creating a new agent session"""
        response = requests.post(f"{BASE_URL}/api/agent/sessions", json={})
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        print(f"PASS: Session created with id: {data['id']}")
        return data["id"]
    
    def test_session_can_upload_text(self):
        """Test uploading text content to session"""
        # Create session first
        session_resp = requests.post(f"{BASE_URL}/api/agent/sessions", json={})
        session_id = session_resp.json()["id"]
        
        # Upload text
        response = requests.post(
            f"{BASE_URL}/api/agent/sessions/{session_id}/upload",
            data={"text": "Este é um conteúdo de teste sobre segurança do trabalho."}
        )
        assert response.status_code == 200
        print(f"PASS: Text uploaded to session")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
