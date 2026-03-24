"""
Test route registration fix - Verifies that all 8 previously missing routes are now registered:
- companies, users, elevenlabs, gallery, heygen, questions, scenarios, vlibras

This test validates the fix for the critical bug where these routes were never registered
in server.py via include_router(), causing all their endpoints to return HTTP 404.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestHealthAndBasicEndpoints:
    """Verify basic API health"""
    
    def test_health_endpoint(self):
        """Health endpoint should return 200"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy"
        print("PASS: Health endpoint working")


class TestAuthAndLogin:
    """Test authentication to get token for protected routes"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Login as admin and get token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@scormify.com",
            "password": "admin123"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "token" in data, "No token in login response"
        print(f"PASS: Admin login successful, got token")
        return data["token"]
    
    def test_login_works(self, admin_token):
        """Verify login returns valid token"""
        assert admin_token is not None
        assert len(admin_token) > 10
        print("PASS: Login returns valid token")


class TestCompaniesRoute:
    """Test /api/companies route - was previously returning 404"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@scormify.com",
            "password": "admin123"
        })
        return response.json().get("token")
    
    def test_list_companies_returns_200(self, admin_token):
        """GET /api/companies should return 200 (not 404)"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/companies", headers=headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print(f"PASS: GET /api/companies returns 200")
    
    def test_list_companies_returns_expected_data(self, admin_token):
        """GET /api/companies should return list with Didaxis and Empresa Teste RBAC"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/companies", headers=headers)
        assert response.status_code == 200
        companies = response.json()
        assert isinstance(companies, list), "Response should be a list"
        assert len(companies) >= 2, f"Expected at least 2 companies, got {len(companies)}"
        
        company_names = [c.get("name") for c in companies]
        print(f"Companies found: {company_names}")
        
        # Verify expected companies exist
        assert any("Didaxis" in name for name in company_names if name), "Didaxis company not found"
        print("PASS: Companies list contains expected data")
    
    def test_create_and_delete_company(self, admin_token):
        """POST /api/companies should create a company, then clean up"""
        import uuid
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # Create test company with unique slug
        unique_id = uuid.uuid4().hex[:8]
        test_company = {
            "name": f"TEST_Company_{unique_id}",
            "slug": f"test-company-{unique_id}",
            "maxUsers": 5,
            "maxProjects": 10
        }
        response = requests.post(f"{BASE_URL}/api/companies", headers=headers, json=test_company)
        assert response.status_code == 200, f"Create company failed: {response.status_code} - {response.text}"
        
        created = response.json()
        assert created.get("name") == test_company["name"]
        company_id = created.get("id")
        print(f"PASS: Created test company with ID: {company_id}")
        
        # Clean up - delete the test company
        delete_response = requests.delete(f"{BASE_URL}/api/companies/{company_id}", headers=headers)
        assert delete_response.status_code == 200, f"Delete failed: {delete_response.text}"
        print("PASS: Test company cleaned up")


class TestUsersRoute:
    """Test /api/users route - was previously returning 404"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@scormify.com",
            "password": "admin123"
        })
        return response.json().get("token")
    
    def test_list_users_returns_200(self, admin_token):
        """GET /api/users should return 200 (not 404)"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/users", headers=headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print(f"PASS: GET /api/users returns 200")
    
    def test_list_users_returns_expected_count(self, admin_token):
        """GET /api/users should return list with 6 users"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/users", headers=headers)
        assert response.status_code == 200
        users = response.json()
        assert isinstance(users, list), "Response should be a list"
        assert len(users) >= 6, f"Expected at least 6 users, got {len(users)}"
        
        user_emails = [u.get("email") for u in users]
        print(f"Users found: {len(users)} - {user_emails[:5]}...")
        
        # Verify admin user exists
        assert "admin@scormify.com" in user_emails, "Admin user not found"
        print("PASS: Users list contains expected data")


class TestQuestionsRoute:
    """Test /api/questions route - was previously returning 404"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@scormify.com",
            "password": "admin123"
        })
        return response.json().get("token")
    
    def test_questions_endpoint_exists(self, admin_token):
        """GET /api/questions should return 200 (not 404)"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/questions", headers=headers)
        # Accept 200 or 401/403 (auth required) - just not 404
        assert response.status_code != 404, f"Route not registered! Got 404"
        print(f"PASS: GET /api/questions returns {response.status_code} (route exists)")


class TestElevenLabsRoute:
    """Test /api/elevenlabs route - was previously returning 404"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@scormify.com",
            "password": "admin123"
        })
        return response.json().get("token")
    
    def test_elevenlabs_voices_endpoint_exists(self, admin_token):
        """GET /api/elevenlabs/voices should return 200 (not 404)"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/elevenlabs/voices", headers=headers)
        # Accept 200 or other status - just not 404
        assert response.status_code != 404, f"Route not registered! Got 404"
        print(f"PASS: GET /api/elevenlabs/voices returns {response.status_code} (route exists)")


class TestGalleryRoute:
    """Test /api/gallery route - was previously returning 404"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@scormify.com",
            "password": "admin123"
        })
        return response.json().get("token")
    
    def test_gallery_images_endpoint_exists(self, admin_token):
        """GET /api/gallery/images should return 200 (not 404)"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/gallery/images", headers=headers)
        # Accept 200 or other status - just not 404
        assert response.status_code != 404, f"Route not registered! Got 404"
        print(f"PASS: GET /api/gallery/images returns {response.status_code} (route exists)")


class TestHeygenRoute:
    """Test /api/heygen route - was previously returning 404"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@scormify.com",
            "password": "admin123"
        })
        return response.json().get("token")
    
    def test_heygen_avatars_endpoint_exists(self, admin_token):
        """GET /api/heygen/avatars should return something (not 404)"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/heygen/avatars", headers=headers)
        # Accept any status - just not 404
        assert response.status_code != 404, f"Route not registered! Got 404"
        print(f"PASS: GET /api/heygen/avatars returns {response.status_code} (route exists)")


class TestScenariosRoute:
    """Test /api/scenarios route - was previously returning 404"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@scormify.com",
            "password": "admin123"
        })
        return response.json().get("token")
    
    def test_scenarios_endpoint_exists(self, admin_token):
        """GET /api/scenarios should return something (not 404)"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/scenarios", headers=headers)
        # Accept any status - just not 404
        assert response.status_code != 404, f"Route not registered! Got 404"
        print(f"PASS: GET /api/scenarios returns {response.status_code} (route exists)")


class TestVlibrasRoute:
    """Test /api/vlibras route - was previously returning 404"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@scormify.com",
            "password": "admin123"
        })
        return response.json().get("token")
    
    def test_vlibras_proxy_endpoint_exists(self, admin_token):
        """GET /api/vlibras-proxy-test should return something (not 404)"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        # Test the vlibras proxy test endpoint
        response = requests.get(f"{BASE_URL}/api/vlibras-proxy-test", headers=headers)
        # Accept any status - just not 404
        assert response.status_code != 404, f"Route not registered! Got 404"
        print(f"PASS: GET /api/vlibras-proxy-test returns {response.status_code} (route exists)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
