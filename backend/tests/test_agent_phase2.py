"""
Tests for AI Agent Phase 2 features:
- GET /api/agent/templates - Course templates endpoint
- GET /api/agent/courses - List agent-created courses
- POST /api/agent/courses/{id}/analyze - Analyze existing course
- POST /api/agent/courses/{id}/apply-improvements - Apply improvements
- POST /api/agent/sessions/{id}/generate-structure - Optional templateId support
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestAgentTemplates:
    """Test GET /api/agent/templates endpoint"""

    def test_templates_endpoint_returns_200(self):
        """Templates endpoint should return 200 OK"""
        response = requests.get(f"{BASE_URL}/api/agent/templates")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("PASS: GET /api/agent/templates returns 200")

    def test_templates_returns_6_templates(self):
        """Should return exactly 6 templates"""
        response = requests.get(f"{BASE_URL}/api/agent/templates")
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        assert len(data) == 6, f"Expected 6 templates, got {len(data)}"
        print(f"PASS: Received {len(data)} templates")

    def test_templates_have_required_fields(self):
        """Each template should have id, name, description, icon, color, defaultConfig"""
        response = requests.get(f"{BASE_URL}/api/agent/templates")
        templates = response.json()
        required_fields = ["id", "name", "description", "icon", "color", "defaultConfig"]
        
        for template in templates:
            for field in required_fields:
                assert field in template, f"Template missing required field: {field}"
            print(f"PASS: Template '{template['id']}' has all required fields")

    def test_templates_expected_types(self):
        """Verify expected template types exist"""
        response = requests.get(f"{BASE_URL}/api/agent/templates")
        templates = response.json()
        template_ids = [t["id"] for t in templates]
        
        expected_ids = ["onboarding", "compliance", "technical", "soft_skills", "health_safety", "sales"]
        for expected_id in expected_ids:
            assert expected_id in template_ids, f"Missing expected template: {expected_id}"
        print(f"PASS: All 6 expected template types found: {expected_ids}")

    def test_template_default_config_has_expected_keys(self):
        """defaultConfig should have depth, duration, modules, interactivity, format"""
        response = requests.get(f"{BASE_URL}/api/agent/templates")
        templates = response.json()
        config_keys = ["depth", "duration", "modules", "interactivity", "format"]
        
        for template in templates:
            default_config = template.get("defaultConfig", {})
            for key in config_keys:
                assert key in default_config, f"Template {template['id']} missing config key: {key}"
        print("PASS: All templates have complete defaultConfig")


class TestAgentCoursesList:
    """Test GET /api/agent/courses endpoint"""

    def test_courses_endpoint_returns_200(self):
        """Courses endpoint should return 200 OK"""
        response = requests.get(f"{BASE_URL}/api/agent/courses")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("PASS: GET /api/agent/courses returns 200")

    def test_courses_returns_list(self):
        """Should return a list (potentially empty if no agent courses exist)"""
        response = requests.get(f"{BASE_URL}/api/agent/courses")
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"PASS: Received list with {len(data)} agent-created courses")

    def test_courses_response_format(self):
        """If courses exist, they should have expected fields"""
        response = requests.get(f"{BASE_URL}/api/agent/courses")
        courses = response.json()
        
        if len(courses) > 0:
            expected_fields = ["id", "name", "slidesCount"]
            for course in courses:
                for field in expected_fields:
                    assert field in course, f"Course missing field: {field}"
            print(f"PASS: {len(courses)} courses have expected fields")
        else:
            print("PASS: No agent courses yet (expected for fresh db)")


class TestAgentCourseAnalyze:
    """Test POST /api/agent/courses/{id}/analyze endpoint"""

    def test_analyze_nonexistent_course_returns_404(self):
        """Analyzing non-existing project should return 404"""
        fake_id = "nonexistent-project-id-12345"
        response = requests.post(f"{BASE_URL}/api/agent/courses/{fake_id}/analyze")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("PASS: POST /api/agent/courses/{fake_id}/analyze returns 404 for non-existent project")


class TestAgentCourseApplyImprovements:
    """Test POST /api/agent/courses/{id}/apply-improvements endpoint"""

    def test_apply_improvements_nonexistent_course_returns_404(self):
        """Applying improvements to non-existing project should return 404"""
        fake_id = "nonexistent-project-id-67890"
        response = requests.post(
            f"{BASE_URL}/api/agent/courses/{fake_id}/apply-improvements",
            json={"improvements": []}
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("PASS: POST /api/agent/courses/{fake_id}/apply-improvements returns 404")


class TestAgentGenerateStructureWithTemplate:
    """Test POST /api/agent/sessions/{id}/generate-structure with optional templateId"""

    def test_generate_structure_endpoint_exists(self):
        """Verify generate-structure endpoint exists (even if session doesn't)"""
        fake_session = "fake-session-id-test"
        response = requests.post(
            f"{BASE_URL}/api/agent/sessions/{fake_session}/generate-structure",
            json={"templateId": "onboarding"}
        )
        # Should return 404 (session not found), not 405 (method not allowed)
        assert response.status_code in [404, 500], f"Unexpected status: {response.status_code}"
        print("PASS: generate-structure endpoint accepts POST with templateId in body")

    def test_generate_structure_accepts_empty_body(self):
        """Endpoint should accept empty body (no templateId)"""
        fake_session = "fake-session-id-no-template"
        response = requests.post(
            f"{BASE_URL}/api/agent/sessions/{fake_session}/generate-structure",
            json={}
        )
        assert response.status_code in [404, 500], f"Unexpected status: {response.status_code}"
        print("PASS: generate-structure endpoint accepts empty body")


class TestHealthCheck:
    """Basic health check"""

    def test_api_health(self):
        """API should be healthy"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        print("PASS: API health check OK")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
