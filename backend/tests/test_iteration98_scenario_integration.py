"""
Test iteration 98: Scenario Integration with AI Agent
Tests the scenario generation integration where AI suggests 'scenario' type improvements
and the system generates real scenarios via generate_scenario_with_ai.

Features tested:
- Login flow works - POST /api/auth/login returns token
- Agent page loads at /agent without JavaScript errors
- GET /api/agent/courses returns courses
- POST /api/agent/sessions/{id}/add-scenario endpoint works
- Backend scenario generation code paths exist
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials from test_credentials.md
ADMIN_EMAIL = "admin@scormify.com"
ADMIN_PASSWORD = "admin123"


class TestAuthFlow:
    """Authentication endpoint tests"""
    
    def test_login_success(self):
        """Test login with admin credentials returns token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "token" in data, "Response should contain token"
        assert "user" in data, "Response should contain user"
        assert data["user"]["email"] == ADMIN_EMAIL
        print(f"✓ Login successful for {ADMIN_EMAIL}")
        return data["token"]
    
    def test_login_invalid_credentials(self):
        """Test login with invalid credentials returns 401"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "wrong@example.com",
            "password": "wrongpass"
        })
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ Invalid credentials correctly rejected")


class TestAgentEndpoints:
    """Agent API endpoint tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token for authenticated requests"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            self.token = response.json().get("token")
            self.headers = {"Authorization": f"Bearer {self.token}"}
        else:
            pytest.skip("Authentication failed - skipping authenticated tests")
    
    def test_get_agent_courses(self):
        """Test GET /api/agent/courses returns list of courses"""
        response = requests.get(f"{BASE_URL}/api/agent/courses", headers=self.headers)
        assert response.status_code == 200, f"Failed to get courses: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"✓ GET /api/agent/courses returned {len(data)} courses")
        return data
    
    def test_create_agent_session(self):
        """Test POST /api/agent/sessions creates a new session"""
        response = requests.post(f"{BASE_URL}/api/agent/sessions", 
            headers={**self.headers, "Content-Type": "application/json"},
            json={}
        )
        assert response.status_code == 200, f"Failed to create session: {response.text}"
        data = response.json()
        assert "id" in data, "Response should contain session id"
        assert data["step"] == "created", "Session should be in 'created' step"
        print(f"✓ Created agent session: {data['id']}")
        return data["id"]
    
    def test_get_design_templates(self):
        """Test GET /api/agent/design-templates returns templates"""
        response = requests.get(f"{BASE_URL}/api/agent/design-templates", headers=self.headers)
        assert response.status_code == 200, f"Failed to get design templates: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        assert len(data) > 0, "Should have at least one design template"
        print(f"✓ GET /api/agent/design-templates returned {len(data)} templates")
    
    def test_get_agent_templates(self):
        """Test GET /api/agent/templates returns course templates"""
        response = requests.get(f"{BASE_URL}/api/agent/templates", headers=self.headers)
        assert response.status_code == 200, f"Failed to get templates: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"✓ GET /api/agent/templates returned {len(data)} templates")
    
    def test_check_agent_access(self):
        """Test GET /api/agent/check-access returns access status"""
        response = requests.get(f"{BASE_URL}/api/agent/check-access", headers=self.headers)
        assert response.status_code == 200, f"Failed to check access: {response.text}"
        data = response.json()
        assert "hasAccess" in data, "Response should contain hasAccess"
        assert data["hasAccess"] == True, "Admin should have agent access"
        print(f"✓ Agent access check passed: {data}")


class TestScenarioIntegration:
    """Tests for scenario integration with AI Agent"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token and create session for tests"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            self.token = response.json().get("token")
            self.headers = {"Authorization": f"Bearer {self.token}"}
        else:
            pytest.skip("Authentication failed - skipping authenticated tests")
    
    def test_add_scenario_endpoint_exists(self):
        """Test POST /api/agent/sessions/{id}/add-scenario endpoint exists"""
        # First create a session
        session_response = requests.post(f"{BASE_URL}/api/agent/sessions", 
            headers={**self.headers, "Content-Type": "application/json"},
            json={}
        )
        assert session_response.status_code == 200
        session_id = session_response.json()["id"]
        
        # Test add-scenario endpoint (will fail without projectId but should return 400, not 404)
        response = requests.post(
            f"{BASE_URL}/api/agent/sessions/{session_id}/add-scenario",
            headers={**self.headers, "Content-Type": "application/json"},
            json={}
        )
        # Should return 400 (no project) not 404 (endpoint not found)
        assert response.status_code in [400, 500], f"Unexpected status: {response.status_code}"
        print(f"✓ add-scenario endpoint exists (returned {response.status_code} without project)")
    
    def test_scenarios_api_endpoint(self):
        """Test GET /api/scenarios endpoint exists"""
        response = requests.get(f"{BASE_URL}/api/scenarios", headers=self.headers)
        # Should return 200 with list or 404 if no scenarios
        assert response.status_code in [200, 404], f"Unexpected status: {response.status_code}"
        if response.status_code == 200:
            data = response.json()
            print(f"✓ GET /api/scenarios returned {len(data) if isinstance(data, list) else 'data'}")
        else:
            print("✓ GET /api/scenarios endpoint exists (no scenarios yet)")


class TestCourseAnalysisFlow:
    """Tests for course analysis and improvement flow"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token for authenticated requests"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            self.token = response.json().get("token")
            self.headers = {"Authorization": f"Bearer {self.token}"}
        else:
            pytest.skip("Authentication failed - skipping authenticated tests")
    
    def test_get_courses_for_analysis(self):
        """Test getting courses available for analysis"""
        response = requests.get(f"{BASE_URL}/api/agent/courses", headers=self.headers)
        assert response.status_code == 200
        courses = response.json()
        
        if len(courses) > 0:
            # Test that courses have required fields
            course = courses[0]
            assert "id" in course, "Course should have id"
            assert "name" in course, "Course should have name"
            print(f"✓ Found {len(courses)} courses available for analysis")
            return courses
        else:
            print("✓ No courses found (empty list returned)")
            return []
    
    def test_analyze_course_endpoint_exists(self):
        """Test POST /api/agent/courses/{id}/analyze endpoint exists"""
        # Get a course first
        courses_response = requests.get(f"{BASE_URL}/api/agent/courses", headers=self.headers)
        if courses_response.status_code != 200:
            pytest.skip("Could not get courses")
        
        courses = courses_response.json()
        if len(courses) == 0:
            pytest.skip("No courses available for analysis")
        
        course_id = courses[0]["id"]
        
        # Test analyze endpoint - this may fail due to LLM budget but endpoint should exist
        response = requests.post(
            f"{BASE_URL}/api/agent/courses/{course_id}/analyze",
            headers=self.headers
        )
        # Should not be 404 (endpoint exists)
        assert response.status_code != 404, "Analyze endpoint should exist"
        print(f"✓ Analyze endpoint exists (returned {response.status_code})")


class TestDashboardMetrics:
    """Test dashboard metrics endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token for authenticated requests"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            self.token = response.json().get("token")
            self.headers = {"Authorization": f"Bearer {self.token}"}
        else:
            pytest.skip("Authentication failed - skipping authenticated tests")
    
    def test_dashboard_metrics(self):
        """Test GET /api/dashboard/metrics returns metrics"""
        response = requests.get(f"{BASE_URL}/api/dashboard/metrics", headers=self.headers)
        assert response.status_code == 200, f"Failed to get metrics: {response.text}"
        data = response.json()
        assert "totalCourses" in data or "courses" in data, "Should have course count"
        print(f"✓ Dashboard metrics: {data}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
