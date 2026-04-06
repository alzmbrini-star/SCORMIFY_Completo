"""
Test Admin Panel CRUD Operations - Iteration 99
Tests: User CRUD (create, update with password/role change, hard delete), Company hard delete
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
SUPER_ADMIN_EMAIL = "admin@scormify.com"
SUPER_ADMIN_PASSWORD = "admin123"


class TestAdminPanelCRUD:
    """Test Admin Panel CRUD operations for users and companies"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session with auth"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        self.token = None
        self.test_user_id = None
        self.test_company_id = None
        
    def _login(self, email, password):
        """Helper to login and get token"""
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": email,
            "password": password
        })
        if response.status_code == 200:
            data = response.json()
            return data.get("token")
        return None
    
    def _auth_headers(self, token):
        """Get headers with auth token"""
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}"
        }
    
    # ==================== AUTH TESTS ====================
    
    def test_01_super_admin_login(self):
        """Test super admin can login"""
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": SUPER_ADMIN_EMAIL,
            "password": SUPER_ADMIN_PASSWORD
        })
        
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "token" in data, "No token in response"
        assert "user" in data, "No user in response"
        assert data["user"]["role"] == "super_admin", f"Expected super_admin role, got {data['user']['role']}"
        print(f"✓ Super admin login successful - user: {data['user']['email']}")
    
    # ==================== COMPANY TESTS ====================
    
    def test_02_get_companies(self):
        """Test getting list of companies"""
        token = self._login(SUPER_ADMIN_EMAIL, SUPER_ADMIN_PASSWORD)
        assert token, "Failed to get auth token"
        
        response = self.session.get(
            f"{BASE_URL}/api/companies",
            headers=self._auth_headers(token)
        )
        
        assert response.status_code == 200, f"Get companies failed: {response.text}"
        companies = response.json()
        assert isinstance(companies, list), "Expected list of companies"
        print(f"✓ Got {len(companies)} companies")
        
        # Store first company ID for user creation
        if companies:
            self.__class__.existing_company_id = companies[0]["id"]
            print(f"  Using company: {companies[0]['name']} ({companies[0]['id']})")
    
    def test_03_create_test_company(self):
        """Create a test company for deletion test"""
        token = self._login(SUPER_ADMIN_EMAIL, SUPER_ADMIN_PASSWORD)
        assert token, "Failed to get auth token"
        
        unique_slug = f"test-delete-{uuid.uuid4().hex[:8]}"
        response = self.session.post(
            f"{BASE_URL}/api/companies",
            headers=self._auth_headers(token),
            json={
                "name": f"TEST_DeleteCompany_{unique_slug}",
                "slug": unique_slug,
                "maxUsers": 5,
                "maxProjects": 10
            }
        )
        
        assert response.status_code == 200, f"Create company failed: {response.text}"
        company = response.json()
        assert "id" in company, "No id in created company"
        self.__class__.test_company_id = company["id"]
        print(f"✓ Created test company: {company['name']} ({company['id']})")
    
    def test_04_delete_company_hard_delete(self):
        """Test permanent deletion of company"""
        token = self._login(SUPER_ADMIN_EMAIL, SUPER_ADMIN_PASSWORD)
        assert token, "Failed to get auth token"
        
        company_id = getattr(self.__class__, 'test_company_id', None)
        assert company_id, "No test company ID - run test_03 first"
        
        response = self.session.delete(
            f"{BASE_URL}/api/companies/{company_id}",
            headers=self._auth_headers(token)
        )
        
        assert response.status_code == 200, f"Delete company failed: {response.text}"
        data = response.json()
        assert "message" in data, "No message in response"
        assert "deleted" in data["message"].lower(), f"Unexpected message: {data['message']}"
        print(f"✓ Company deleted permanently: {data['message']}")
        
        # Verify company no longer exists
        verify_response = self.session.get(
            f"{BASE_URL}/api/companies/{company_id}",
            headers=self._auth_headers(token)
        )
        assert verify_response.status_code == 404, f"Company should be deleted but got {verify_response.status_code}"
        print("✓ Verified company no longer exists (404)")
    
    # ==================== USER CRUD TESTS ====================
    
    def test_05_create_test_user(self):
        """Create a test user with editor role"""
        token = self._login(SUPER_ADMIN_EMAIL, SUPER_ADMIN_PASSWORD)
        assert token, "Failed to get auth token"
        
        # Get company ID
        company_id = getattr(self.__class__, 'existing_company_id', None)
        if not company_id:
            # Fetch companies
            comp_response = self.session.get(
                f"{BASE_URL}/api/companies",
                headers=self._auth_headers(token)
            )
            if comp_response.status_code == 200:
                companies = comp_response.json()
                if companies:
                    company_id = companies[0]["id"]
        
        assert company_id, "No company ID available for user creation"
        
        unique_email = f"test_user_{uuid.uuid4().hex[:8]}@test.com"
        self.__class__.test_user_email = unique_email
        self.__class__.test_user_password = "testpass123"
        
        response = self.session.post(
            f"{BASE_URL}/api/users",
            headers=self._auth_headers(token),
            json={
                "name": "TEST_User_For_Delete",
                "email": unique_email,
                "password": "testpass123",
                "role": "editor",
                "companyId": company_id
            }
        )
        
        assert response.status_code == 200, f"Create user failed: {response.text}"
        user = response.json()
        assert "user_id" in user, "No user_id in created user"
        assert user["email"] == unique_email, f"Email mismatch: {user['email']}"
        assert user["role"] == "editor", f"Role mismatch: {user['role']}"
        
        self.__class__.test_user_id = user["user_id"]
        print(f"✓ Created test user: {user['name']} ({user['email']}) - role: {user['role']}")
    
    def test_06_verify_new_user_can_login(self):
        """Verify the newly created user can login"""
        email = getattr(self.__class__, 'test_user_email', None)
        password = getattr(self.__class__, 'test_user_password', None)
        
        assert email and password, "No test user credentials - run test_05 first"
        
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": email,
            "password": password
        })
        
        assert response.status_code == 200, f"New user login failed: {response.text}"
        data = response.json()
        assert "token" in data, "No token in response"
        print(f"✓ New user can login successfully")
    
    def test_07_update_user_name_role_password(self):
        """Update user: change name, role to company_admin, and set new password"""
        token = self._login(SUPER_ADMIN_EMAIL, SUPER_ADMIN_PASSWORD)
        assert token, "Failed to get auth token"
        
        user_id = getattr(self.__class__, 'test_user_id', None)
        assert user_id, "No test user ID - run test_05 first"
        
        new_password = "newpassword456"
        self.__class__.test_user_new_password = new_password
        
        response = self.session.put(
            f"{BASE_URL}/api/users/{user_id}",
            headers=self._auth_headers(token),
            json={
                "name": "TEST_User_Updated_Name",
                "role": "company_admin",
                "password": new_password
            }
        )
        
        assert response.status_code == 200, f"Update user failed: {response.text}"
        user = response.json()
        assert user["name"] == "TEST_User_Updated_Name", f"Name not updated: {user['name']}"
        assert user["role"] == "company_admin", f"Role not updated: {user['role']}"
        print(f"✓ User updated: name={user['name']}, role={user['role']}, password changed")
    
    def test_08_verify_login_with_new_password(self):
        """Verify user can login with the new password"""
        email = getattr(self.__class__, 'test_user_email', None)
        new_password = getattr(self.__class__, 'test_user_new_password', None)
        old_password = getattr(self.__class__, 'test_user_password', None)
        
        assert email and new_password, "No test user credentials - run previous tests first"
        
        # Try login with NEW password - should succeed
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": email,
            "password": new_password
        })
        
        assert response.status_code == 200, f"Login with new password failed: {response.text}"
        print(f"✓ User can login with NEW password")
        
        # Try login with OLD password - should fail
        response_old = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": email,
            "password": old_password
        })
        
        assert response_old.status_code in [401, 400], f"Old password should fail but got {response_old.status_code}"
        print(f"✓ Old password correctly rejected (status: {response_old.status_code})")
    
    def test_09_delete_user_hard_delete(self):
        """Test permanent deletion of user"""
        token = self._login(SUPER_ADMIN_EMAIL, SUPER_ADMIN_PASSWORD)
        assert token, "Failed to get auth token"
        
        user_id = getattr(self.__class__, 'test_user_id', None)
        assert user_id, "No test user ID - run test_05 first"
        
        response = self.session.delete(
            f"{BASE_URL}/api/users/{user_id}",
            headers=self._auth_headers(token)
        )
        
        assert response.status_code == 200, f"Delete user failed: {response.text}"
        data = response.json()
        assert "message" in data, "No message in response"
        assert "deleted" in data["message"].lower(), f"Unexpected message: {data['message']}"
        print(f"✓ User deleted permanently: {data['message']}")
    
    def test_10_verify_deleted_user_cannot_login(self):
        """Verify deleted user can no longer login"""
        email = getattr(self.__class__, 'test_user_email', None)
        new_password = getattr(self.__class__, 'test_user_new_password', None)
        
        assert email and new_password, "No test user credentials - run previous tests first"
        
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": email,
            "password": new_password
        })
        
        # Should return 401 or 400 with "Invalid credentials" or similar
        assert response.status_code in [401, 400], f"Deleted user should not be able to login but got {response.status_code}"
        
        data = response.json()
        # Check for error message
        error_msg = data.get("detail", data.get("message", ""))
        print(f"✓ Deleted user correctly rejected: {error_msg} (status: {response.status_code})")
    
    def test_11_verify_deleted_user_not_in_list(self):
        """Verify deleted user no longer appears in user list"""
        token = self._login(SUPER_ADMIN_EMAIL, SUPER_ADMIN_PASSWORD)
        assert token, "Failed to get auth token"
        
        user_id = getattr(self.__class__, 'test_user_id', None)
        assert user_id, "No test user ID"
        
        response = self.session.get(
            f"{BASE_URL}/api/users",
            headers=self._auth_headers(token)
        )
        
        assert response.status_code == 200, f"Get users failed: {response.text}"
        users = response.json()
        
        # Check user is not in list
        user_ids = [u.get("user_id") for u in users]
        assert user_id not in user_ids, f"Deleted user {user_id} still in user list"
        print(f"✓ Deleted user not in user list (hard delete confirmed)")
    
    # ==================== ROLE CHANGE TESTS ====================
    
    def test_12_create_user_change_role_editor_to_company_admin(self):
        """Test creating user as editor and changing to company_admin"""
        token = self._login(SUPER_ADMIN_EMAIL, SUPER_ADMIN_PASSWORD)
        assert token, "Failed to get auth token"
        
        # Get company ID
        comp_response = self.session.get(
            f"{BASE_URL}/api/companies",
            headers=self._auth_headers(token)
        )
        companies = comp_response.json() if comp_response.status_code == 200 else []
        company_id = companies[0]["id"] if companies else None
        assert company_id, "No company available"
        
        unique_email = f"test_role_{uuid.uuid4().hex[:8]}@test.com"
        
        # Create as editor
        create_response = self.session.post(
            f"{BASE_URL}/api/users",
            headers=self._auth_headers(token),
            json={
                "name": "TEST_Role_Change_User",
                "email": unique_email,
                "password": "roletest123",
                "role": "editor",
                "companyId": company_id
            }
        )
        
        assert create_response.status_code == 200, f"Create user failed: {create_response.text}"
        user = create_response.json()
        user_id = user["user_id"]
        assert user["role"] == "editor", f"Initial role should be editor, got {user['role']}"
        print(f"✓ Created user as editor: {user['email']}")
        
        # Update to company_admin
        update_response = self.session.put(
            f"{BASE_URL}/api/users/{user_id}",
            headers=self._auth_headers(token),
            json={"role": "company_admin"}
        )
        
        assert update_response.status_code == 200, f"Update role failed: {update_response.text}"
        updated_user = update_response.json()
        assert updated_user["role"] == "company_admin", f"Role should be company_admin, got {updated_user['role']}"
        print(f"✓ Changed role to company_admin")
        
        # Cleanup - delete the test user
        delete_response = self.session.delete(
            f"{BASE_URL}/api/users/{user_id}",
            headers=self._auth_headers(token)
        )
        assert delete_response.status_code == 200, f"Cleanup delete failed: {delete_response.text}"
        print(f"✓ Cleanup: deleted test user")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
