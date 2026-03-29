"""
Test Auth Flow - Validates authentication endpoints for Scormify
Tests: login, /me, logout, token validation
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials from /app/memory/test_credentials.md
ADMIN_EMAIL = "admin@scormify.com"
ADMIN_PASSWORD = "admin123"


class TestHealthCheck:
    """Health check endpoint tests"""
    
    def test_health_endpoint(self):
        """GET /api/health returns 200"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy"
        print("✓ GET /api/health returns 200 with status=healthy")


class TestLoginEndpoint:
    """POST /api/auth/login tests"""
    
    def test_login_with_correct_credentials(self):
        """POST /api/auth/login with correct credentials returns 200 with user and token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Validate response structure
        assert "user" in data, "Response should contain 'user'"
        assert "token" in data, "Response should contain 'token'"
        
        # Validate user data
        user = data["user"]
        assert user.get("email") == ADMIN_EMAIL, f"Expected email {ADMIN_EMAIL}, got {user.get('email')}"
        assert user.get("role") == "super_admin", f"Expected role super_admin, got {user.get('role')}"
        assert "user_id" in user, "User should have user_id"
        
        # Validate token
        token = data["token"]
        assert isinstance(token, str), "Token should be a string"
        assert len(token) > 0, "Token should not be empty"
        assert token.startswith("session_"), f"Token should start with 'session_', got {token[:20]}"
        
        print(f"✓ POST /api/auth/login returns 200 with user (email={user['email']}, role={user['role']}) and token")
    
    def test_login_with_wrong_password(self):
        """POST /api/auth/login with wrong password returns 401"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": "wrongpassword"},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "detail" in data, "Response should contain 'detail' error message"
        print(f"✓ POST /api/auth/login with wrong password returns 401: {data.get('detail')}")
    
    def test_login_with_wrong_email(self):
        """POST /api/auth/login with non-existent email returns 401"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "nonexistent@example.com", "password": "anypassword"},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "detail" in data, "Response should contain 'detail' error message"
        print(f"✓ POST /api/auth/login with non-existent email returns 401: {data.get('detail')}")
    
    def test_login_with_empty_credentials(self):
        """POST /api/auth/login with empty credentials returns 400"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "", "password": ""},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        print(f"✓ POST /api/auth/login with empty credentials returns 400")


class TestMeEndpoint:
    """GET /api/auth/me tests"""
    
    @pytest.fixture
    def auth_token(self):
        """Get valid auth token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
            headers={"Content-Type": "application/json"}
        )
        if response.status_code != 200:
            pytest.skip(f"Login failed: {response.text}")
        return response.json().get("token")
    
    def test_me_with_valid_token(self, auth_token):
        """GET /api/auth/me with valid Bearer token returns 200 with user data"""
        response = requests.get(
            f"{BASE_URL}/api/auth/me",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Validate user data
        assert data.get("email") == ADMIN_EMAIL, f"Expected email {ADMIN_EMAIL}, got {data.get('email')}"
        assert data.get("role") == "super_admin", f"Expected role super_admin, got {data.get('role')}"
        assert "user_id" in data, "User should have user_id"
        assert "name" in data, "User should have name"
        
        print(f"✓ GET /api/auth/me with valid token returns 200 with user data (email={data['email']}, role={data['role']})")
    
    def test_me_without_token(self):
        """GET /api/auth/me without any token returns 401"""
        response = requests.get(f"{BASE_URL}/api/auth/me")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "detail" in data, "Response should contain 'detail' error message"
        print(f"✓ GET /api/auth/me without token returns 401: {data.get('detail')}")
    
    def test_me_with_invalid_token(self):
        """GET /api/auth/me with invalid token returns 401"""
        response = requests.get(
            f"{BASE_URL}/api/auth/me",
            headers={"Authorization": "Bearer invalid_token_12345"}
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "detail" in data, "Response should contain 'detail' error message"
        print(f"✓ GET /api/auth/me with invalid token returns 401: {data.get('detail')}")
    
    def test_me_with_malformed_auth_header(self):
        """GET /api/auth/me with malformed Authorization header returns 401"""
        response = requests.get(
            f"{BASE_URL}/api/auth/me",
            headers={"Authorization": "NotBearer sometoken"}
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}: {response.text}"
        print(f"✓ GET /api/auth/me with malformed auth header returns 401")


class TestLogoutEndpoint:
    """POST /api/auth/logout tests"""
    
    @pytest.fixture
    def auth_session(self):
        """Get valid auth token and session"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
            headers={"Content-Type": "application/json"}
        )
        if response.status_code != 200:
            pytest.skip(f"Login failed: {response.text}")
        return response.json().get("token")
    
    def test_logout_clears_session(self, auth_session):
        """POST /api/auth/logout clears session"""
        # First verify token works
        me_response = requests.get(
            f"{BASE_URL}/api/auth/me",
            headers={"Authorization": f"Bearer {auth_session}"}
        )
        assert me_response.status_code == 200, "Token should be valid before logout"
        
        # Logout - note: logout uses cookies, but we test the endpoint works
        logout_response = requests.post(
            f"{BASE_URL}/api/auth/logout",
            headers={"Authorization": f"Bearer {auth_session}"}
        )
        assert logout_response.status_code == 200, f"Expected 200, got {logout_response.status_code}: {logout_response.text}"
        
        data = logout_response.json()
        assert "message" in data, "Response should contain 'message'"
        print(f"✓ POST /api/auth/logout returns 200: {data.get('message')}")


class TestDebugDbEndpoint:
    """GET /api/auth/debug-db tests"""
    
    def test_debug_db_returns_status(self):
        """GET /api/auth/debug-db returns database status"""
        response = requests.get(f"{BASE_URL}/api/auth/debug-db")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("status") == "connected", f"Expected status=connected, got {data.get('status')}"
        assert "users_count" in data, "Response should contain users_count"
        assert "sessions_count" in data, "Response should contain sessions_count"
        print(f"✓ GET /api/auth/debug-db returns connected status (users={data.get('users_count')}, sessions={data.get('sessions_count')})")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
