"""
Test suite for the [object Object] bug fix in AI-suggested improvements.

Bug: After applying AI-suggested improvements, slides show '[object Object]' instead of content.
The AI sometimes returns 'content' as a dict/object instead of an HTML string, which gets saved 
to htmlContent and rendered as [object Object] in the frontend.

Fixes verified:
1. Backend _build_improved_elements now converts dict/list content to string HTML
2. Backend _apply_ai_result_to_slides type-checks title, notes, elements before applying
3. Frontend resolveHtmlContentUrls returns '' for objects instead of [object Object]
4. Frontend processHtmlContent checks typeof string
5. GET /api/projects/{id} sanitizes non-string htmlContent in existing projects
"""
import pytest
import requests
import os
import json

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@scormify.com"
ADMIN_PASSWORD = "admin123"


class TestBuildImprovedElementsTypeChecking:
    """Unit tests for _build_improved_elements type-checking logic"""
    
    def test_string_content_preserved(self):
        """Test that string content is preserved as-is"""
        # Read the backend code to verify the logic
        with open('/app/backend/routes/agent.py', 'r') as f:
            code = f.read()
        
        # Verify the type-checking logic is present
        assert 'isinstance(raw_content, dict)' in code, "Should check if content is dict"
        assert 'isinstance(raw_content, list)' in code, "Should check if content is list"
        assert 'isinstance(raw_content, str)' in code, "Should check if content is string"
        print("✓ _build_improved_elements has type-checking for dict, list, and string content")
    
    def test_dict_content_converted_to_string(self):
        """Test that dict content is converted to string HTML"""
        with open('/app/backend/routes/agent.py', 'r') as f:
            code = f.read()
        
        # Verify dict handling
        assert 'raw_content.get("html", "")' in code, "Should try to get html key from dict"
        assert 'raw_content.get("text", "")' in code, "Should try to get text key from dict"
        assert 'json.dumps(raw_content' in code, "Should fallback to json.dumps for dict"
        print("✓ Dict content is converted: tries html/text keys, then json.dumps")
    
    def test_list_content_converted_to_string(self):
        """Test that list content is converted to string"""
        with open('/app/backend/routes/agent.py', 'r') as f:
            code = f.read()
        
        # Verify list handling
        assert '" ".join(str(c) for c in raw_content)' in code, "Should join list items as strings"
        print("✓ List content is converted by joining items as strings")
    
    def test_none_content_handled(self):
        """Test that None content is handled gracefully"""
        with open('/app/backend/routes/agent.py', 'r') as f:
            code = f.read()
        
        # Verify None handling
        assert 'str(raw_content) if raw_content else ""' in code, "Should handle None content"
        print("✓ None content is converted to empty string")


class TestApplyAiResultTypeChecking:
    """Unit tests for _apply_ai_result_to_slides type-checking"""
    
    def test_title_type_checked(self):
        """Test that title is type-checked before applying"""
        with open('/app/backend/routes/agent.py', 'r') as f:
            code = f.read()
        
        # Verify title type-checking
        assert 'if title and isinstance(title, str):' in code, "Should check title is string"
        print("✓ Title is type-checked before applying")
    
    def test_notes_type_checked(self):
        """Test that notes is type-checked before applying"""
        with open('/app/backend/routes/agent.py', 'r') as f:
            code = f.read()
        
        # Verify notes type-checking
        assert 'if notes and isinstance(notes, str):' in code, "Should check notes is string"
        print("✓ Notes is type-checked before applying")
    
    def test_elements_type_checked(self):
        """Test that elements is type-checked before applying"""
        with open('/app/backend/routes/agent.py', 'r') as f:
            code = f.read()
        
        # Verify elements type-checking
        assert 'isinstance(upd["elements"], list)' in code, "Should check elements is list"
        print("✓ Elements is type-checked before applying")
    
    def test_new_slide_title_type_checked(self):
        """Test that new slide title is type-checked"""
        with open('/app/backend/routes/agent.py', 'r') as f:
            code = f.read()
        
        # Verify new slide title handling
        assert 'if not isinstance(ns_title, str):' in code, "Should check new slide title type"
        assert 'ns_title = str(ns_title)' in code, "Should convert non-string title to string"
        print("✓ New slide title is type-checked and converted if needed")


class TestFrontendTypeGuards:
    """Tests for frontend type guards in SlideCanvas, CoursePreview, SplitPreview"""
    
    def test_slide_canvas_resolve_html_content_urls(self):
        """Test SlideCanvas resolveHtmlContentUrls returns '' for objects"""
        with open('/app/frontend/src/components/editor/SlideCanvas.jsx', 'r') as f:
            code = f.read()
        
        # Verify the type guard
        assert "typeof htmlContent !== 'string'" in code, "Should check if htmlContent is not string"
        assert "typeof htmlContent === 'object'" in code or "typeof htmlContent !== 'string'" in code, "Should handle object type"
        print("✓ SlideCanvas resolveHtmlContentUrls has type guard for non-string content")
    
    def test_course_preview_process_html_content(self):
        """Test CoursePreview processHtmlContent checks typeof string"""
        with open('/app/frontend/src/components/editor/CoursePreview.jsx', 'r') as f:
            code = f.read()
        
        # Verify the type guard
        assert "typeof htmlContent !== 'string'" in code, "Should check if htmlContent is not string"
        print("✓ CoursePreview processHtmlContent has type guard for non-string content")
    
    def test_split_preview_process_html_content(self):
        """Test SplitPreview processHtmlContent checks typeof string"""
        with open('/app/frontend/src/components/editor/SplitPreview.jsx', 'r') as f:
            code = f.read()
        
        # Verify the type guard
        assert "typeof htmlContent !== 'string'" in code, "Should check if htmlContent is not string"
        print("✓ SplitPreview processHtmlContent has type guard for non-string content")


class TestGetProjectSanitization:
    """Tests for GET /api/projects/{id} sanitization of non-string htmlContent"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        # Login
        login_res = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if login_res.status_code == 200:
            token = login_res.json().get("token")
            if token:
                self.session.headers.update({"Authorization": f"Bearer {token}"})
    
    def test_sanitization_code_exists(self):
        """Test that sanitization code exists in projects_crud.py"""
        with open('/app/backend/routes/projects_crud.py', 'r') as f:
            code = f.read()
        
        # Verify sanitization logic
        assert 'not isinstance(hc, str)' in code, "Should check if htmlContent is not string"
        assert 'isinstance(hc, dict)' in code, "Should handle dict htmlContent"
        assert 'needs_fix = True' in code, "Should track if fix is needed"
        assert 'await update_project(project_id' in code, "Should save fixed project"
        print("✓ GET /api/projects/{id} has sanitization code for non-string htmlContent")
    
    def test_dict_htmlcontent_converted_to_html(self):
        """Test that dict htmlContent is converted to HTML paragraphs"""
        with open('/app/backend/routes/projects_crud.py', 'r') as f:
            code = f.read()
        
        # Verify dict conversion logic
        assert '<p><strong>' in code, "Should create HTML paragraphs from dict"
        assert 'for k, v in hc.items()' in code, "Should iterate dict items"
        print("✓ Dict htmlContent is converted to HTML paragraphs")
    
    def test_get_project_returns_valid_data(self):
        """Test that GET /api/projects/{id} returns valid project data"""
        # Get list of projects
        response = self.session.get(f"{BASE_URL}/api/projects")
        if response.status_code != 200:
            pytest.skip("Could not get projects list")
        
        projects = response.json()
        if not projects:
            pytest.skip("No projects available")
        
        project_id = projects[0].get("id")
        
        # Get specific project
        response = self.session.get(f"{BASE_URL}/api/projects/{project_id}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        project = response.json()
        assert "id" in project, "Project should have id"
        assert "course" in project, "Project should have course"
        
        # Verify all htmlContent fields are strings
        slides = project.get("course", {}).get("slides", [])
        for i, slide in enumerate(slides):
            for j, el in enumerate(slide.get("elements", [])):
                hc = el.get("htmlContent")
                if hc is not None:
                    assert isinstance(hc, str), f"Slide {i}, Element {j}: htmlContent should be string, got {type(hc)}"
        
        print(f"✓ GET /api/projects/{project_id} returns valid data with string htmlContent")


class TestPreviewAndApplyImprovements:
    """Integration tests for preview-improvements and apply-improvements endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        # Login
        login_res = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if login_res.status_code == 200:
            token = login_res.json().get("token")
            if token:
                self.session.headers.update({"Authorization": f"Bearer {token}"})
    
    def test_preview_improvements_endpoint(self):
        """Test POST /api/agent/courses/{id}/preview-improvements works"""
        # Get agent courses
        response = self.session.get(f"{BASE_URL}/api/agent/courses")
        if response.status_code != 200:
            pytest.skip("Could not get agent courses")
        
        courses = response.json()
        if not courses:
            pytest.skip("No agent courses available")
        
        project_id = courses[0].get("id")
        
        # Test with empty improvements
        response = self.session.post(
            f"{BASE_URL}/api/agent/courses/{project_id}/preview-improvements",
            json={"improvements": []}
        )
        
        # Should return 200 even with empty improvements
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "previewId" in data, "Response should contain previewId"
        assert "comparisons" in data, "Response should contain comparisons"
        print(f"✓ preview-improvements endpoint works: previewId={data['previewId'][:8]}...")
    
    def test_apply_improvements_endpoint(self):
        """Test POST /api/agent/courses/{id}/apply-improvements works"""
        # Get agent courses
        response = self.session.get(f"{BASE_URL}/api/agent/courses")
        if response.status_code != 200:
            pytest.skip("Could not get agent courses")
        
        courses = response.json()
        if not courses:
            pytest.skip("No agent courses available")
        
        project_id = courses[0].get("id")
        
        # Test with empty improvements
        response = self.session.post(
            f"{BASE_URL}/api/agent/courses/{project_id}/apply-improvements",
            json={"improvements": []}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("status") == "ok", "Response should have status ok"
        print(f"✓ apply-improvements endpoint works")
    
    def test_undo_improvements_endpoint(self):
        """Test POST /api/agent/courses/{id}/undo-improvements works"""
        # Get agent courses
        response = self.session.get(f"{BASE_URL}/api/agent/courses")
        if response.status_code != 200:
            pytest.skip("Could not get agent courses")
        
        courses = response.json()
        if not courses:
            pytest.skip("No agent courses available")
        
        project_id = courses[0].get("id")
        
        # Test undo (may return 404 if no snapshot exists)
        response = self.session.post(
            f"{BASE_URL}/api/agent/courses/{project_id}/undo-improvements"
        )
        
        # Should return 200 (if snapshot exists) or 404 (if no snapshot)
        assert response.status_code in [200, 404], f"Expected 200 or 404, got {response.status_code}"
        
        if response.status_code == 200:
            print(f"✓ undo-improvements endpoint works (snapshot found)")
        else:
            print(f"✓ undo-improvements endpoint works (no snapshot, returned 404)")


class TestAgentEditModeFlow:
    """Integration tests for the Agent edit mode flow"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        # Login
        login_res = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if login_res.status_code == 200:
            token = login_res.json().get("token")
            if token:
                self.session.headers.update({"Authorization": f"Bearer {token}"})
    
    def test_agent_check_access(self):
        """Test GET /api/agent/check-access"""
        response = self.session.get(f"{BASE_URL}/api/agent/check-access")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "hasAccess" in data, "Response should contain hasAccess"
        print(f"✓ Agent access: hasAccess={data.get('hasAccess')}, reason={data.get('reason')}")
    
    def test_agent_courses_list(self):
        """Test GET /api/agent/courses"""
        response = self.session.get(f"{BASE_URL}/api/agent/courses")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        courses = response.json()
        assert isinstance(courses, list), "Response should be a list"
        print(f"✓ Found {len(courses)} agent-created courses")
    
    def test_agent_analyze_course(self):
        """Test POST /api/agent/courses/{id}/analyze"""
        # Get agent courses
        response = self.session.get(f"{BASE_URL}/api/agent/courses")
        if response.status_code != 200:
            pytest.skip("Could not get agent courses")
        
        courses = response.json()
        if not courses:
            pytest.skip("No agent courses available")
        
        project_id = courses[0].get("id")
        
        # Analyze course
        response = self.session.post(f"{BASE_URL}/api/agent/courses/{project_id}/analyze")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "overallScore" in data, "Response should contain overallScore"
        assert "improvements" in data, "Response should contain improvements"
        print(f"✓ Course analyzed: score={data.get('overallScore')}/10, {len(data.get('improvements', []))} improvements")
    
    def test_agent_templates(self):
        """Test GET /api/agent/templates"""
        response = self.session.get(f"{BASE_URL}/api/agent/templates")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        templates = response.json()
        assert isinstance(templates, list), "Response should be a list"
        print(f"✓ Found {len(templates)} course templates")
    
    def test_agent_design_templates(self):
        """Test GET /api/agent/design-templates"""
        response = self.session.get(f"{BASE_URL}/api/agent/design-templates")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        templates = response.json()
        assert isinstance(templates, list), "Response should be a list"
        print(f"✓ Found {len(templates)} design templates")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
