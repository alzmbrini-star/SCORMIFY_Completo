"""
Backend tests for Scormfy API after modularization refactoring.
Tests all route modules: auth, projects, course, questions, admin, agent, elevenlabs, vlibras.
"""
import pytest
import requests
import os

# Use production URL from environment
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    # Fallback for local testing
    BASE_URL = "https://ai-course-author.preview.emergentagent.com"

# Test credentials
ADMIN_EMAIL = "admin@scormify.com"
ADMIN_PASSWORD = "admin123"
TEST_PROJECT_ID = "c7de35a7-0f1a-4270-86d4-703151b377e5"


class TestHealthEndpoints:
    """Test health check endpoints - critical for deployment"""
    
    def test_root_health(self):
        """GET /health - root health check"""
        response = requests.get(f"{BASE_URL}/health")
        assert response.status_code == 200, f"Health check failed: {response.text}"
        data = response.json()
        assert data.get("status") == "healthy"
        print("✓ GET /health - healthy")
    
    def test_api_health(self):
        """GET /api/health - API health check"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200, f"API health failed: {response.text}"
        data = response.json()
        assert data.get("status") == "healthy"
        print("✓ GET /api/health - healthy")
    
    def test_api_root(self):
        """GET /api - API root"""
        response = requests.get(f"{BASE_URL}/api/")
        assert response.status_code == 200, f"API root failed: {response.text}"
        data = response.json()
        assert "message" in data or "Scormify" in str(data)
        print("✓ GET /api/ - accessible")


class TestAuthRoutes:
    """Test authentication routes (routes/auth.py)"""
    
    def test_login_success(self):
        """POST /api/auth/login - successful login with admin credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "token" in data, "Response missing token"
        assert "user" in data, "Response missing user"
        assert data["user"]["email"] == ADMIN_EMAIL
        assert data["user"]["role"] == "super_admin"
        print(f"✓ POST /api/auth/login - success, token: {data['token'][:20]}...")
        return data["token"]
    
    def test_login_invalid_credentials(self):
        """POST /api/auth/login - invalid credentials returns 401"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "wrong@email.com",
            "password": "wrongpassword"
        })
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ POST /api/auth/login - invalid credentials returns 401")
    
    def test_auth_me_with_token(self):
        """GET /api/auth/me - get current user with Bearer token"""
        # First login to get token
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        token = login_resp.json().get("token")
        
        # Use token to get current user
        response = requests.get(f"{BASE_URL}/api/auth/me", headers={
            "Authorization": f"Bearer {token}"
        })
        assert response.status_code == 200, f"Auth me failed: {response.text}"
        data = response.json()
        assert data.get("email") == ADMIN_EMAIL
        assert data.get("role") == "super_admin"
        print(f"✓ GET /api/auth/me - user: {data.get('name')} ({data.get('role')})")
    
    def test_auth_me_without_token(self):
        """GET /api/auth/me - returns 401 without token"""
        response = requests.get(f"{BASE_URL}/api/auth/me")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ GET /api/auth/me - returns 401 without token")


class TestProjectRoutes:
    """Test project CRUD routes (routes/projects.py)"""
    
    @pytest.fixture
    def auth_headers(self):
        """Get authentication headers"""
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        token = login_resp.json().get("token")
        return {"Authorization": f"Bearer {token}"}
    
    def test_list_projects(self):
        """GET /api/projects - list all projects"""
        response = requests.get(f"{BASE_URL}/api/projects")
        assert response.status_code == 200, f"List projects failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Expected list of projects"
        print(f"✓ GET /api/projects - found {len(data)} projects")
    
    def test_get_project_by_id(self):
        """GET /api/projects/{id} - get specific project"""
        response = requests.get(f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}")
        assert response.status_code == 200, f"Get project failed: {response.text}"
        data = response.json()
        assert data.get("id") == TEST_PROJECT_ID, "Project ID mismatch"
        assert "course" in data, "Project missing course data"
        assert "slides" in data.get("course", {}), "Course missing slides"
        print(f"✓ GET /api/projects/{TEST_PROJECT_ID[:8]}... - name: {data.get('name')}, slides: {len(data.get('course', {}).get('slides', []))}")
    
    def test_get_project_not_found(self):
        """GET /api/projects/{id} - non-existent project returns 404"""
        response = requests.get(f"{BASE_URL}/api/projects/non-existent-id-12345")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ GET /api/projects/non-existent - returns 404")


class TestCourseRoutes:
    """Test course data routes (routes/projects.py)"""
    
    def test_get_course_data(self):
        """GET /api/course/{id} - get course data for project"""
        response = requests.get(f"{BASE_URL}/api/course/{TEST_PROJECT_ID}")
        assert response.status_code == 200, f"Get course failed: {response.text}"
        data = response.json()
        assert "slides" in data, "Course missing slides"
        assert "metadata" in data, "Course missing metadata"
        print(f"✓ GET /api/course/{TEST_PROJECT_ID[:8]}... - slides: {len(data.get('slides', []))}")
    
    def test_get_course_not_found(self):
        """GET /api/course/{id} - non-existent course returns 404"""
        response = requests.get(f"{BASE_URL}/api/course/non-existent-project-id")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ GET /api/course/non-existent - returns 404")


class TestQuestionsRoutes:
    """Test quiz questions routes (routes/questions.py)"""
    
    def test_list_questions(self):
        """GET /api/questions - list all questions"""
        response = requests.get(f"{BASE_URL}/api/questions")
        assert response.status_code == 200, f"List questions failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Expected list of questions"
        print(f"✓ GET /api/questions - found {len(data)} questions")
    
    def test_list_questions_by_project(self):
        """GET /api/questions?project_id={id} - filter by project"""
        response = requests.get(f"{BASE_URL}/api/questions", params={"project_id": TEST_PROJECT_ID})
        assert response.status_code == 200, f"List questions failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Expected list of questions"
        print(f"✓ GET /api/questions?project_id={TEST_PROJECT_ID[:8]}... - found {len(data)} questions")


class TestAdminRoutes:
    """Test admin routes (routes/admin.py)"""
    
    @pytest.fixture
    def auth_headers(self):
        """Get authentication headers"""
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        token = login_resp.json().get("token")
        return {"Authorization": f"Bearer {token}"}
    
    def test_get_tutor_settings(self):
        """GET /api/admin/tutor-settings - get AI tutor settings"""
        response = requests.get(f"{BASE_URL}/api/admin/tutor-settings")
        assert response.status_code == 200, f"Get tutor settings failed: {response.text}"
        data = response.json()
        assert "enabled" in data or "key" in data, "Missing tutor settings"
        print(f"✓ GET /api/admin/tutor-settings - enabled: {data.get('enabled', 'N/A')}")
    
    def test_get_admin_reports(self, auth_headers):
        """GET /api/admin/reports - get admin reports (requires auth)"""
        response = requests.get(f"{BASE_URL}/api/admin/reports", headers=auth_headers)
        assert response.status_code == 200, f"Get admin reports failed: {response.text}"
        data = response.json()
        assert "reports" in data, "Missing reports data"
        assert "generatedAt" in data, "Missing generatedAt timestamp"
        print(f"✓ GET /api/admin/reports - found {len(data.get('reports', []))} company reports")
    
    def test_admin_reports_requires_auth(self):
        """GET /api/admin/reports - requires authentication"""
        response = requests.get(f"{BASE_URL}/api/admin/reports")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ GET /api/admin/reports - requires authentication (401)")


class TestAgentRoutes:
    """Test AI agent routes (routes/agent.py)"""
    
    @pytest.fixture
    def auth_headers(self):
        """Get authentication headers"""
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        token = login_resp.json().get("token")
        return {"Authorization": f"Bearer {token}"}
    
    def test_check_agent_access_with_token(self, auth_headers):
        """GET /api/agent/check-access - check access with token"""
        response = requests.get(f"{BASE_URL}/api/agent/check-access", headers=auth_headers)
        assert response.status_code == 200, f"Check access failed: {response.text}"
        data = response.json()
        assert "hasAccess" in data, "Missing hasAccess field"
        assert data.get("hasAccess") == True, "Super admin should have access"
        assert data.get("reason") == "super_admin", "Wrong reason for super admin"
        print(f"✓ GET /api/agent/check-access - hasAccess: {data.get('hasAccess')}, reason: {data.get('reason')}")
    
    def test_check_agent_access_without_token(self):
        """GET /api/agent/check-access - check access without token"""
        response = requests.get(f"{BASE_URL}/api/agent/check-access")
        assert response.status_code == 200, f"Check access failed: {response.text}"
        data = response.json()
        assert data.get("hasAccess") == False, "Unauthenticated should not have access"
        assert data.get("reason") == "not_authenticated", "Wrong reason for unauthenticated"
        print(f"✓ GET /api/agent/check-access (no token) - hasAccess: {data.get('hasAccess')}, reason: {data.get('reason')}")


class TestElevenLabsRoutes:
    """Test ElevenLabs TTS routes (routes/elevenlabs.py)"""
    
    def test_list_voices(self):
        """GET /api/elevenlabs/voices - list available voices"""
        response = requests.get(f"{BASE_URL}/api/elevenlabs/voices")
        # May return 400 if API key not configured, or 200 with voices
        if response.status_code == 200:
            data = response.json()
            assert "voices" in data, "Missing voices list"
            print(f"✓ GET /api/elevenlabs/voices - found {len(data.get('voices', []))} voices")
        elif response.status_code == 400:
            data = response.json()
            assert "not configured" in data.get("detail", "").lower() or "API key" in data.get("detail", "")
            print("✓ GET /api/elevenlabs/voices - returns 400 (API key not configured)")
        else:
            pytest.fail(f"Unexpected status {response.status_code}: {response.text}")


class TestVLibrasRoutes:
    """Test VLibras proxy routes (routes/vlibras.py)"""
    
    def test_vlibras_proxy_test_page(self):
        """GET /api/vlibras-proxy-test - VLibras proxy test page"""
        response = requests.get(f"{BASE_URL}/api/vlibras-proxy-test")
        assert response.status_code == 200, f"VLibras proxy test failed: {response.text}"
        assert "text/html" in response.headers.get("content-type", "").lower(), "Expected HTML response"
        assert "VLibras" in response.text or "vlibras" in response.text.lower(), "Missing VLibras content"
        print("✓ GET /api/vlibras-proxy-test - HTML page loaded")


class TestAssetServing:
    """Test asset serving routes (routes/projects.py)"""
    
    def test_serve_project_asset(self):
        """GET /api/projects/{project_id}/assets/{filename} - serve project asset"""
        # Use known asset from test project
        response = requests.get(f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/assets/ai_img_95827761f9.png")
        # May return 200 if asset exists, or 404 if not
        if response.status_code == 200:
            assert len(response.content) > 0, "Empty asset response"
            content_type = response.headers.get("content-type", "")
            assert "image" in content_type or "octet-stream" in content_type, f"Unexpected content type: {content_type}"
            print(f"✓ GET /api/projects/.../assets/ai_img_95827761f9.png - {len(response.content)} bytes")
        elif response.status_code == 404:
            print("✓ GET /api/projects/.../assets/... - returns 404 (asset not found)")
        else:
            pytest.fail(f"Unexpected status {response.status_code}: {response.text}")


class TestComprehensiveFlow:
    """Test complete authentication and data flow"""
    
    def test_full_auth_flow(self):
        """Test complete authentication flow: login -> get user -> access protected resource"""
        # Step 1: Login
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        token = login_resp.json().get("token")
        print(f"  Step 1: Login successful, token: {token[:20]}...")
        
        # Step 2: Get current user
        headers = {"Authorization": f"Bearer {token}"}
        me_resp = requests.get(f"{BASE_URL}/api/auth/me", headers=headers)
        assert me_resp.status_code == 200, f"Get me failed: {me_resp.text}"
        user = me_resp.json()
        assert user.get("role") == "super_admin"
        print(f"  Step 2: User verified - {user.get('name')} ({user.get('role')})")
        
        # Step 3: Access admin reports
        reports_resp = requests.get(f"{BASE_URL}/api/admin/reports", headers=headers)
        assert reports_resp.status_code == 200, f"Reports failed: {reports_resp.text}"
        reports = reports_resp.json()
        print(f"  Step 3: Admin reports accessed - {len(reports.get('reports', []))} companies")
        
        # Step 4: Check agent access
        agent_resp = requests.get(f"{BASE_URL}/api/agent/check-access", headers=headers)
        assert agent_resp.status_code == 200, f"Agent check failed: {agent_resp.text}"
        agent_data = agent_resp.json()
        assert agent_data.get("hasAccess") == True
        print(f"  Step 4: Agent access verified - hasAccess: {agent_data.get('hasAccess')}")
        
        print("✓ Full auth flow completed successfully")


# Run tests when executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
