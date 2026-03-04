"""
Tests for AI Agent RBAC (Role-Based Access Control) feature.
Tests that:
1. Super Admins always have access to AI Agent
2. Company users need 'agentAccess' permission in company.permissions
3. API endpoints return 403 for users without permission
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
SUPER_ADMIN_EMAIL = "admin@scormify.com"
SUPER_ADMIN_PASSWORD = "admin123"
TEST_USER_EMAIL = "usuario@teste.com"
TEST_USER_PASSWORD = "teste123"
TEST_COMPANY_ID = "company_d9dec773d063"


class TestAgentRBAC:
    """Test AI Agent RBAC access control"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
    
    def login(self, email, password):
        """Helper to login and return token"""
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": email,
            "password": password
        })
        if response.status_code == 200:
            data = response.json()
            token = data.get("token")
            if token:
                self.session.headers.update({"Authorization": f"Bearer {token}"})
            return data
        return None
    
    def logout(self):
        """Helper to logout"""
        self.session.post(f"{BASE_URL}/api/auth/logout")
        self.session.headers.pop("Authorization", None)
    
    # ==========================================
    # Test 1: Super Admin always has access
    # ==========================================
    def test_super_admin_check_access_returns_true(self):
        """Verify that Super Admin always has access to AI Agent (check-access returns hasAccess: true)"""
        login_data = self.login(SUPER_ADMIN_EMAIL, SUPER_ADMIN_PASSWORD)
        assert login_data is not None, "Super Admin login failed"
        assert login_data.get("user", {}).get("role") == "super_admin", "User is not super_admin"
        
        # Check access endpoint
        response = self.session.get(f"{BASE_URL}/api/agent/check-access")
        assert response.status_code == 200, f"Check access failed: {response.text}"
        
        data = response.json()
        assert data.get("hasAccess") == True, f"Super Admin should have access: {data}"
        assert data.get("reason") == "super_admin", f"Reason should be 'super_admin': {data}"
        
        print(f"✓ Super Admin has access: {data}")
        self.logout()
    
    def test_super_admin_can_access_agent_sessions(self):
        """Verify Super Admin can create and access agent sessions"""
        self.login(SUPER_ADMIN_EMAIL, SUPER_ADMIN_PASSWORD)
        
        # Create session
        response = self.session.post(f"{BASE_URL}/api/agent/sessions", json={})
        assert response.status_code == 200, f"Session creation failed: {response.text}"
        
        session_data = response.json()
        assert "id" in session_data, "Session ID not returned"
        session_id = session_data["id"]
        
        # Get session
        response = self.session.get(f"{BASE_URL}/api/agent/sessions/{session_id}")
        assert response.status_code == 200, f"Get session failed: {response.text}"
        
        print(f"✓ Super Admin can create and access sessions: {session_id}")
        self.logout()
    
    # ==========================================
    # Test 2: User without permission denied
    # ==========================================
    def test_user_without_permission_check_access_returns_false(self):
        """Verify that company user without agentAccess permission cannot access AI Agent"""
        # First, ensure the company has agentAccess: false
        admin_data = self.login(SUPER_ADMIN_EMAIL, SUPER_ADMIN_PASSWORD)
        assert admin_data is not None, "Super Admin login failed"
        
        # Update company to remove agentAccess permission
        response = self.session.put(f"{BASE_URL}/api/companies/{TEST_COMPANY_ID}", json={
            "permissions": {
                "agentAccess": False,
                "heygen": False,
                "elevenlabs": False
            }
        })
        print(f"Updating company permissions (remove agentAccess): {response.status_code}")
        self.logout()
        
        # Login as test user
        login_data = self.login(TEST_USER_EMAIL, TEST_USER_PASSWORD)
        if login_data is None:
            pytest.skip("Test user login failed - user may not exist")
        
        user = login_data.get("user", {})
        print(f"Test user: {user.get('email')}, role: {user.get('role')}, companyId: {user.get('companyId')}")
        
        # Check access
        response = self.session.get(f"{BASE_URL}/api/agent/check-access")
        assert response.status_code == 200, f"Check access request failed: {response.text}"
        
        data = response.json()
        assert data.get("hasAccess") == False, f"User without permission should NOT have access: {data}"
        assert data.get("reason") == "not_authorized", f"Reason should be 'not_authorized': {data}"
        
        print(f"✓ User without permission denied access: {data}")
        self.logout()
    
    def test_user_without_permission_sessions_returns_403(self):
        """Verify that /api/agent/sessions returns 403 for user without permission"""
        # Ensure company has no agentAccess
        self.login(SUPER_ADMIN_EMAIL, SUPER_ADMIN_PASSWORD)
        self.session.put(f"{BASE_URL}/api/companies/{TEST_COMPANY_ID}", json={
            "permissions": {"agentAccess": False, "heygen": False, "elevenlabs": False}
        })
        self.logout()
        
        # Login as test user
        login_data = self.login(TEST_USER_EMAIL, TEST_USER_PASSWORD)
        if login_data is None:
            pytest.skip("Test user login failed - user may not exist")
        
        # Try to create session - should return 403
        response = self.session.post(f"{BASE_URL}/api/agent/sessions", json={})
        assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"
        
        print(f"✓ User without permission gets 403 on sessions: {response.status_code}")
        self.logout()
    
    # ==========================================
    # Test 3: User with permission has access
    # ==========================================
    def test_user_with_permission_check_access_returns_true(self):
        """Verify that company user WITH agentAccess permission can access AI Agent"""
        # First, grant agentAccess permission to company
        self.login(SUPER_ADMIN_EMAIL, SUPER_ADMIN_PASSWORD)
        
        response = self.session.put(f"{BASE_URL}/api/companies/{TEST_COMPANY_ID}", json={
            "permissions": {
                "agentAccess": True,
                "heygen": False,
                "elevenlabs": False
            }
        })
        print(f"Updating company permissions (grant agentAccess): {response.status_code}")
        self.logout()
        
        # Login as test user
        login_data = self.login(TEST_USER_EMAIL, TEST_USER_PASSWORD)
        if login_data is None:
            pytest.skip("Test user login failed - user may not exist")
        
        # Check access
        response = self.session.get(f"{BASE_URL}/api/agent/check-access")
        assert response.status_code == 200, f"Check access request failed: {response.text}"
        
        data = response.json()
        assert data.get("hasAccess") == True, f"User with permission should have access: {data}"
        assert data.get("reason") == "company_permission", f"Reason should be 'company_permission': {data}"
        
        print(f"✓ User with permission has access: {data}")
        self.logout()
    
    def test_user_with_permission_can_create_session(self):
        """Verify that user with agentAccess permission can create agent sessions"""
        # Grant permission
        self.login(SUPER_ADMIN_EMAIL, SUPER_ADMIN_PASSWORD)
        self.session.put(f"{BASE_URL}/api/companies/{TEST_COMPANY_ID}", json={
            "permissions": {"agentAccess": True, "heygen": False, "elevenlabs": False}
        })
        self.logout()
        
        # Login as test user
        login_data = self.login(TEST_USER_EMAIL, TEST_USER_PASSWORD)
        if login_data is None:
            pytest.skip("Test user login failed - user may not exist")
        
        # Create session
        response = self.session.post(f"{BASE_URL}/api/agent/sessions", json={})
        assert response.status_code == 200, f"Session creation failed: {response.status_code} {response.text}"
        
        session_data = response.json()
        assert "id" in session_data, "Session ID not returned"
        
        print(f"✓ User with permission can create session: {session_data['id']}")
        self.logout()
    
    # ==========================================
    # Test 4: Unauthenticated user denied
    # ==========================================
    def test_unauthenticated_check_access_returns_false(self):
        """Verify unauthenticated request to check-access returns hasAccess: false"""
        # Don't login - make unauthenticated request
        response = requests.get(f"{BASE_URL}/api/agent/check-access")
        assert response.status_code == 200, f"Check access failed: {response.text}"
        
        data = response.json()
        assert data.get("hasAccess") == False, f"Unauthenticated user should NOT have access: {data}"
        assert data.get("reason") == "not_authenticated", f"Reason should be 'not_authenticated': {data}"
        
        print(f"✓ Unauthenticated user denied: {data}")
    
    def test_unauthenticated_sessions_returns_401(self):
        """Verify unauthenticated request to agent/sessions returns 401"""
        response = requests.post(f"{BASE_URL}/api/agent/sessions", json={})
        assert response.status_code == 401, f"Expected 401, got {response.status_code}: {response.text}"
        
        print(f"✓ Unauthenticated user gets 401 on sessions: {response.status_code}")
    
    # ==========================================
    # Test 5: Admin panel shows agent checkbox
    # ==========================================
    def test_company_has_permissions_field(self):
        """Verify company has permissions field including agentAccess"""
        self.login(SUPER_ADMIN_EMAIL, SUPER_ADMIN_PASSWORD)
        
        # Get company
        response = self.session.get(f"{BASE_URL}/api/companies/{TEST_COMPANY_ID}")
        assert response.status_code == 200, f"Get company failed: {response.text}"
        
        company = response.json()
        assert "permissions" in company, f"Company should have permissions field: {company}"
        assert "agentAccess" in company.get("permissions", {}), f"Permissions should include agentAccess: {company}"
        
        print(f"✓ Company has permissions.agentAccess field: {company.get('permissions')}")
        self.logout()
    
    def test_update_company_permissions(self):
        """Verify Super Admin can update company permissions including agentAccess"""
        self.login(SUPER_ADMIN_EMAIL, SUPER_ADMIN_PASSWORD)
        
        # Update to true
        response = self.session.put(f"{BASE_URL}/api/companies/{TEST_COMPANY_ID}", json={
            "permissions": {"agentAccess": True, "heygen": True, "elevenlabs": True}
        })
        assert response.status_code == 200, f"Update company failed: {response.text}"
        
        updated = response.json()
        assert updated.get("permissions", {}).get("agentAccess") == True, f"agentAccess should be True: {updated}"
        
        # Update to false
        response = self.session.put(f"{BASE_URL}/api/companies/{TEST_COMPANY_ID}", json={
            "permissions": {"agentAccess": False, "heygen": False, "elevenlabs": False}
        })
        assert response.status_code == 200, f"Update company failed: {response.text}"
        
        updated = response.json()
        assert updated.get("permissions", {}).get("agentAccess") == False, f"agentAccess should be False: {updated}"
        
        print(f"✓ Super Admin can toggle agentAccess permission")
        self.logout()


class TestAgentRBACCleanup:
    """Cleanup after tests - restore original state"""
    
    def test_cleanup_restore_permission(self):
        """Restore test company permission to True for future tests"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        
        # Login as admin
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": SUPER_ADMIN_EMAIL,
            "password": SUPER_ADMIN_PASSWORD
        })
        if response.status_code == 200:
            token = response.json().get("token")
            session.headers.update({"Authorization": f"Bearer {token}"})
            
            # Restore permission to true
            session.put(f"{BASE_URL}/api/companies/{TEST_COMPANY_ID}", json={
                "permissions": {"agentAccess": True, "heygen": False, "elevenlabs": False}
            })
            print("✓ Cleanup: Restored agentAccess to True")
