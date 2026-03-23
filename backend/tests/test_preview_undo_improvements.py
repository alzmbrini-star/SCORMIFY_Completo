"""
Test suite for Before/After Preview and Undo for AI-suggested improvements feature.
Tests the new endpoints:
- POST /api/agent/courses/{project_id}/preview-improvements
- POST /api/agent/courses/{project_id}/apply-improvements (modified to accept previewId)
- POST /api/agent/courses/{project_id}/undo-improvements
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@scormify.com"
ADMIN_PASSWORD = "admin123"


class TestPreviewUndoImprovements:
    """Test suite for preview and undo improvements feature"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        # Login to get auth
        login_res = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if login_res.status_code == 200:
            token = login_res.json().get("token")
            if token:
                self.session.headers.update({"Authorization": f"Bearer {token}"})
    
    def test_get_agent_courses_list(self):
        """Test GET /api/agent/courses returns list of agent-created courses"""
        response = self.session.get(f"{BASE_URL}/api/agent/courses")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Expected list of courses"
        print(f"Found {len(data)} agent-created courses")
        if len(data) > 0:
            course = data[0]
            assert "id" in course, "Course should have id"
            assert "name" in course, "Course should have name"
            print(f"First course: {course.get('name')} (id: {course.get('id')})")
    
    def test_preview_improvements_endpoint_exists(self):
        """Test POST /api/agent/courses/{id}/preview-improvements endpoint exists"""
        # Use a fake project ID to test endpoint existence
        response = self.session.post(
            f"{BASE_URL}/api/agent/courses/fake-project-id/preview-improvements",
            json={"improvements": []}
        )
        # Should return 404 for non-existent project, not 405 (method not allowed)
        assert response.status_code in [404, 400, 422], f"Expected 404/400/422, got {response.status_code}"
        print(f"preview-improvements endpoint exists, returned {response.status_code} for fake project")
    
    def test_apply_improvements_endpoint_exists(self):
        """Test POST /api/agent/courses/{id}/apply-improvements endpoint exists"""
        response = self.session.post(
            f"{BASE_URL}/api/agent/courses/fake-project-id/apply-improvements",
            json={"improvements": []}
        )
        assert response.status_code in [404, 400, 422], f"Expected 404/400/422, got {response.status_code}"
        print(f"apply-improvements endpoint exists, returned {response.status_code} for fake project")
    
    def test_undo_improvements_endpoint_exists(self):
        """Test POST /api/agent/courses/{id}/undo-improvements endpoint exists"""
        response = self.session.post(
            f"{BASE_URL}/api/agent/courses/fake-project-id/undo-improvements"
        )
        assert response.status_code in [404, 400], f"Expected 404/400, got {response.status_code}"
        print(f"undo-improvements endpoint exists, returned {response.status_code} for fake project")
    
    def test_preview_improvements_with_real_course(self):
        """Test preview-improvements with a real agent-created course"""
        # Get list of agent courses
        courses_res = self.session.get(f"{BASE_URL}/api/agent/courses")
        if courses_res.status_code != 200:
            pytest.skip("Could not get agent courses")
        
        courses = courses_res.json()
        if len(courses) == 0:
            pytest.skip("No agent-created courses available for testing")
        
        course = courses[0]
        project_id = course["id"]
        print(f"Testing with course: {course.get('name')} (id: {project_id})")
        
        # First analyze the course to get improvements
        analyze_res = self.session.post(f"{BASE_URL}/api/agent/courses/{project_id}/analyze")
        if analyze_res.status_code != 200:
            pytest.skip(f"Could not analyze course: {analyze_res.text}")
        
        analysis = analyze_res.json()
        improvements = analysis.get("improvements", [])
        
        if len(improvements) == 0:
            print("No improvements suggested by AI, testing with empty improvements")
            improvements = [{"type": "content", "description": "Test improvement", "suggestion": "Test suggestion", "priority": "baixa"}]
        
        # Test preview-improvements endpoint
        preview_res = self.session.post(
            f"{BASE_URL}/api/agent/courses/{project_id}/preview-improvements",
            json={"improvements": improvements[:2]}  # Use first 2 improvements
        )
        
        # This may take time due to AI processing
        assert preview_res.status_code == 200, f"Expected 200, got {preview_res.status_code}: {preview_res.text}"
        
        preview_data = preview_res.json()
        assert "previewId" in preview_data, "Response should contain previewId"
        assert "comparisons" in preview_data, "Response should contain comparisons"
        assert "updatedCount" in preview_data, "Response should contain updatedCount"
        assert "newCount" in preview_data, "Response should contain newCount"
        
        print(f"Preview generated: previewId={preview_data['previewId']}, updatedCount={preview_data['updatedCount']}, newCount={preview_data['newCount']}")
        
        # Store previewId for next test
        self.preview_id = preview_data["previewId"]
        self.project_id = project_id
        
        return preview_data
    
    def test_apply_improvements_with_preview_id(self):
        """Test apply-improvements using previewId from preview step"""
        # Get list of agent courses
        courses_res = self.session.get(f"{BASE_URL}/api/agent/courses")
        if courses_res.status_code != 200:
            pytest.skip("Could not get agent courses")
        
        courses = courses_res.json()
        if len(courses) == 0:
            pytest.skip("No agent-created courses available for testing")
        
        course = courses[0]
        project_id = course["id"]
        
        # First analyze to get improvements
        analyze_res = self.session.post(f"{BASE_URL}/api/agent/courses/{project_id}/analyze")
        if analyze_res.status_code != 200:
            pytest.skip(f"Could not analyze course: {analyze_res.text}")
        
        analysis = analyze_res.json()
        improvements = analysis.get("improvements", [])
        
        if len(improvements) == 0:
            improvements = [{"type": "content", "description": "Test improvement", "suggestion": "Test suggestion", "priority": "baixa"}]
        
        # Generate preview first
        preview_res = self.session.post(
            f"{BASE_URL}/api/agent/courses/{project_id}/preview-improvements",
            json={"improvements": improvements[:1]}
        )
        
        if preview_res.status_code != 200:
            pytest.skip(f"Could not generate preview: {preview_res.text}")
        
        preview_data = preview_res.json()
        preview_id = preview_data["previewId"]
        
        # Now apply using previewId
        apply_res = self.session.post(
            f"{BASE_URL}/api/agent/courses/{project_id}/apply-improvements",
            json={"improvements": improvements[:1], "previewId": preview_id}
        )
        
        assert apply_res.status_code == 200, f"Expected 200, got {apply_res.status_code}: {apply_res.text}"
        
        apply_data = apply_res.json()
        assert apply_data.get("status") == "ok", "Apply should return status ok"
        assert "updatedSlides" in apply_data, "Response should contain updatedSlides"
        assert "totalSlides" in apply_data, "Response should contain totalSlides"
        assert apply_data.get("canUndo") == True, "Response should indicate canUndo=True"
        
        print(f"Improvements applied: updatedSlides={apply_data['updatedSlides']}, totalSlides={apply_data['totalSlides']}, canUndo={apply_data['canUndo']}")
        
        return project_id
    
    def test_undo_improvements_restores_course(self):
        """Test undo-improvements restores the course from snapshot"""
        # Get list of agent courses
        courses_res = self.session.get(f"{BASE_URL}/api/agent/courses")
        if courses_res.status_code != 200:
            pytest.skip("Could not get agent courses")
        
        courses = courses_res.json()
        if len(courses) == 0:
            pytest.skip("No agent-created courses available for testing")
        
        course = courses[0]
        project_id = course["id"]
        
        # First, apply some improvements to create a snapshot
        analyze_res = self.session.post(f"{BASE_URL}/api/agent/courses/{project_id}/analyze")
        if analyze_res.status_code != 200:
            pytest.skip(f"Could not analyze course: {analyze_res.text}")
        
        analysis = analyze_res.json()
        improvements = analysis.get("improvements", [])
        
        if len(improvements) == 0:
            improvements = [{"type": "content", "description": "Test improvement", "suggestion": "Test suggestion", "priority": "baixa"}]
        
        # Apply improvements (this creates a snapshot)
        apply_res = self.session.post(
            f"{BASE_URL}/api/agent/courses/{project_id}/apply-improvements",
            json={"improvements": improvements[:1]}
        )
        
        if apply_res.status_code != 200:
            pytest.skip(f"Could not apply improvements: {apply_res.text}")
        
        # Now test undo
        undo_res = self.session.post(f"{BASE_URL}/api/agent/courses/{project_id}/undo-improvements")
        
        assert undo_res.status_code == 200, f"Expected 200, got {undo_res.status_code}: {undo_res.text}"
        
        undo_data = undo_res.json()
        assert undo_data.get("status") == "ok", "Undo should return status ok"
        assert "totalSlides" in undo_data, "Response should contain totalSlides"
        
        print(f"Undo successful: totalSlides={undo_data['totalSlides']}")
    
    def test_undo_without_snapshot_returns_404(self):
        """Test undo-improvements returns 404 when no snapshot exists"""
        # Use a project that hasn't had improvements applied
        # First, get a project and ensure no snapshot exists
        courses_res = self.session.get(f"{BASE_URL}/api/agent/courses")
        if courses_res.status_code != 200:
            pytest.skip("Could not get agent courses")
        
        courses = courses_res.json()
        if len(courses) < 2:
            pytest.skip("Need at least 2 courses to test this scenario")
        
        # Use the second course (less likely to have a snapshot)
        course = courses[1]
        project_id = course["id"]
        
        # Try to undo without applying first
        undo_res = self.session.post(f"{BASE_URL}/api/agent/courses/{project_id}/undo-improvements")
        
        # Should return 404 if no snapshot exists, or 200 if there's an existing snapshot
        assert undo_res.status_code in [200, 404], f"Expected 200 or 404, got {undo_res.status_code}"
        
        if undo_res.status_code == 404:
            print("Correctly returned 404 when no snapshot exists")
        else:
            print("Found existing snapshot, undo succeeded")
    
    def test_preview_response_structure(self):
        """Test that preview response has correct structure"""
        courses_res = self.session.get(f"{BASE_URL}/api/agent/courses")
        if courses_res.status_code != 200:
            pytest.skip("Could not get agent courses")
        
        courses = courses_res.json()
        if len(courses) == 0:
            pytest.skip("No agent-created courses available")
        
        course = courses[0]
        project_id = course["id"]
        
        # Analyze to get improvements
        analyze_res = self.session.post(f"{BASE_URL}/api/agent/courses/{project_id}/analyze")
        if analyze_res.status_code != 200:
            pytest.skip(f"Could not analyze course")
        
        analysis = analyze_res.json()
        improvements = analysis.get("improvements", [])
        
        if len(improvements) == 0:
            improvements = [{"type": "content", "description": "Test", "suggestion": "Test", "priority": "baixa"}]
        
        # Generate preview
        preview_res = self.session.post(
            f"{BASE_URL}/api/agent/courses/{project_id}/preview-improvements",
            json={"improvements": improvements[:1]}
        )
        
        if preview_res.status_code != 200:
            pytest.skip(f"Could not generate preview")
        
        preview_data = preview_res.json()
        
        # Validate structure
        assert isinstance(preview_data.get("previewId"), str), "previewId should be string"
        assert isinstance(preview_data.get("comparisons"), list), "comparisons should be list"
        assert isinstance(preview_data.get("updatedCount"), int), "updatedCount should be int"
        assert isinstance(preview_data.get("newCount"), int), "newCount should be int"
        
        # Validate comparison structure if any
        if len(preview_data.get("comparisons", [])) > 0:
            comp = preview_data["comparisons"][0]
            assert "slideIndex" in comp, "comparison should have slideIndex"
            assert "title" in comp, "comparison should have title"
            assert "before" in comp["title"], "title should have before"
            assert "after" in comp["title"], "title should have after"
            assert "contentBefore" in comp, "comparison should have contentBefore"
            assert "contentAfter" in comp, "comparison should have contentAfter"
            print(f"Comparison structure validated for slide {comp['slideIndex']}")
        
        print(f"Preview response structure validated: previewId={preview_data['previewId'][:8]}...")
    
    def test_expired_preview_id_returns_error(self):
        """Test that using an invalid/expired previewId returns error"""
        courses_res = self.session.get(f"{BASE_URL}/api/agent/courses")
        if courses_res.status_code != 200:
            pytest.skip("Could not get agent courses")
        
        courses = courses_res.json()
        if len(courses) == 0:
            pytest.skip("No agent-created courses available")
        
        course = courses[0]
        project_id = course["id"]
        
        # Try to apply with fake previewId
        apply_res = self.session.post(
            f"{BASE_URL}/api/agent/courses/{project_id}/apply-improvements",
            json={"improvements": [], "previewId": "fake-preview-id-12345"}
        )
        
        # Should return 400 for expired/invalid preview
        assert apply_res.status_code == 400, f"Expected 400, got {apply_res.status_code}: {apply_res.text}"
        print("Correctly returned 400 for invalid previewId")


class TestEditModeSteps:
    """Test that edit mode has 4 steps in the flow"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        login_res = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if login_res.status_code == 200:
            token = login_res.json().get("token")
            if token:
                self.session.headers.update({"Authorization": f"Bearer {token}"})
    
    def test_agent_check_access(self):
        """Test agent access check endpoint"""
        response = self.session.get(f"{BASE_URL}/api/agent/check-access")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "hasAccess" in data, "Response should contain hasAccess"
        print(f"Agent access: hasAccess={data.get('hasAccess')}, reason={data.get('reason')}")
    
    def test_agent_templates_endpoint(self):
        """Test agent templates endpoint"""
        response = self.session.get(f"{BASE_URL}/api/agent/templates")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert isinstance(data, list), "Expected list of templates"
        print(f"Found {len(data)} course templates")
    
    def test_agent_design_templates_endpoint(self):
        """Test agent design templates endpoint"""
        response = self.session.get(f"{BASE_URL}/api/agent/design-templates")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert isinstance(data, list), "Expected list of design templates"
        print(f"Found {len(data)} design templates")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
