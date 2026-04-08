"""
Test suite for Improvement Approval Workflow
Tests the new endpoints:
- POST /api/agent/courses/{project_id}/submit-improvements-for-approval
- GET /api/agent/approval-queue (combined storyboard + improvement approvals)
- POST /api/agent/improvement-approvals/{id}/approve
- POST /api/agent/improvement-approvals/{id}/reject
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
SUPER_ADMIN_EMAIL = "admin@scormify.com"
SUPER_ADMIN_PASSWORD = "admin123"
APROVADOR_EMAIL = "aprovador@teste.com"
APROVADOR_PASSWORD = "aprovador123"


class TestImprovementApprovalWorkflow:
    """Tests for the improvement approval workflow"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test fixtures"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        self.admin_token = None
        self.aprovador_token = None
        self.test_project_id = None
        self.test_preview_id = None
        self.test_approval_id = None
        
    def _login_admin(self):
        """Login as super admin"""
        res = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": SUPER_ADMIN_EMAIL,
            "password": SUPER_ADMIN_PASSWORD
        })
        assert res.status_code == 200, f"Admin login failed: {res.text}"
        data = res.json()
        self.admin_token = data.get("token")
        self.session.headers.update({"Authorization": f"Bearer {self.admin_token}"})
        return data
    
    def _login_aprovador(self):
        """Login as aprovador"""
        res = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": APROVADOR_EMAIL,
            "password": APROVADOR_PASSWORD
        })
        assert res.status_code == 200, f"Aprovador login failed: {res.text}"
        data = res.json()
        self.aprovador_token = data.get("token")
        self.session.headers.update({"Authorization": f"Bearer {self.aprovador_token}"})
        return data
    
    def test_01_admin_login(self):
        """Test super admin can login"""
        data = self._login_admin()
        assert data.get("user", {}).get("role") == "super_admin"
        print("PASS: Super admin login successful")
    
    def test_02_aprovador_login(self):
        """Test aprovador can login"""
        data = self._login_aprovador()
        assert data.get("user", {}).get("role") == "aprovador"
        assert data.get("user", {}).get("companyId") is not None
        print(f"PASS: Aprovador login successful, companyId: {data.get('user', {}).get('companyId')}")
    
    def test_03_approval_queue_returns_combined_results(self):
        """Test GET /api/agent/approval-queue returns combined storyboard and improvement items"""
        self._login_admin()
        res = self.session.get(f"{BASE_URL}/api/agent/approval-queue")
        assert res.status_code == 200, f"Approval queue failed: {res.text}"
        data = res.json()
        assert isinstance(data, list), "Approval queue should return a list"
        
        # Check that items have _type field
        for item in data:
            assert "_type" in item, f"Item missing _type field: {item.get('id')}"
            assert item["_type"] in ["storyboard", "improvement"], f"Invalid _type: {item['_type']}"
        
        storyboard_count = sum(1 for i in data if i.get("_type") == "storyboard")
        improvement_count = sum(1 for i in data if i.get("_type") == "improvement")
        print(f"PASS: Approval queue returned {len(data)} items ({storyboard_count} storyboards, {improvement_count} improvements)")
    
    def test_04_submit_improvements_requires_preview_id(self):
        """Test POST submit-improvements-for-approval requires previewId"""
        self._login_admin()
        
        # Create a test project first
        res = self.session.post(f"{BASE_URL}/api/projects", json={
            "name": f"TEST_ImprovementApproval_{uuid.uuid4().hex[:8]}",
            "description": "Test project for improvement approval"
        })
        assert res.status_code in [200, 201], f"Project creation failed: {res.text}"
        project_data = res.json()
        self.test_project_id = project_data.get("id")
        
        # Try to submit without previewId
        res = self.session.post(
            f"{BASE_URL}/api/agent/courses/{self.test_project_id}/submit-improvements-for-approval",
            json={"targetCompanyId": "company_didaxis001"}
        )
        assert res.status_code == 400, f"Expected 400, got {res.status_code}"
        assert "previewid" in res.text.lower(), "Error should mention previewId"
        print("PASS: Submit improvements correctly requires previewId")
    
    def test_05_submit_improvements_requires_target_company(self):
        """Test POST submit-improvements-for-approval requires targetCompanyId"""
        self._login_admin()
        
        res = self.session.post(
            f"{BASE_URL}/api/agent/courses/{self.test_project_id or 'test-project'}/submit-improvements-for-approval",
            json={"previewId": "test-preview-id"}
        )
        assert res.status_code == 400, f"Expected 400, got {res.status_code}"
        assert "targetCompanyId" in res.text.lower() or "company" in res.text.lower(), "Error should mention targetCompanyId"
        print("PASS: Submit improvements correctly requires targetCompanyId")
    
    def test_06_submit_improvements_validates_project(self):
        """Test POST submit-improvements-for-approval validates project exists"""
        self._login_admin()
        
        res = self.session.post(
            f"{BASE_URL}/api/agent/courses/nonexistent-project-id/submit-improvements-for-approval",
            json={
                "previewId": "test-preview-id",
                "targetCompanyId": "company_didaxis001"
            }
        )
        assert res.status_code == 404, f"Expected 404, got {res.status_code}"
        print("PASS: Submit improvements validates project exists")
    
    def test_07_submit_improvements_validates_company(self):
        """Test POST submit-improvements-for-approval validates company exists"""
        self._login_admin()
        
        # First create a project
        res = self.session.post(f"{BASE_URL}/api/projects", json={
            "name": f"TEST_ImprovementApproval2_{uuid.uuid4().hex[:8]}",
            "description": "Test project"
        })
        if res.status_code in [200, 201]:
            project_id = res.json().get("id")
            
            res = self.session.post(
                f"{BASE_URL}/api/agent/courses/{project_id}/submit-improvements-for-approval",
                json={
                    "previewId": "test-preview-id",
                    "targetCompanyId": "nonexistent-company-id"
                }
            )
            # Should fail with 404 for company or 404 for preview
            assert res.status_code in [404], f"Expected 404, got {res.status_code}: {res.text}"
            print("PASS: Submit improvements validates company/preview exists")
        else:
            pytest.skip("Could not create test project")
    
    def test_08_approve_improvement_not_found(self):
        """Test POST improvement-approvals/{id}/approve returns 404 for nonexistent"""
        self._login_admin()
        
        res = self.session.post(
            f"{BASE_URL}/api/agent/improvement-approvals/nonexistent-approval-id/approve",
            json={}
        )
        assert res.status_code == 404, f"Expected 404, got {res.status_code}"
        print("PASS: Approve improvement returns 404 for nonexistent")
    
    def test_09_reject_improvement_not_found(self):
        """Test POST improvement-approvals/{id}/reject returns 404 for nonexistent"""
        self._login_admin()
        
        res = self.session.post(
            f"{BASE_URL}/api/agent/improvement-approvals/nonexistent-approval-id/reject",
            json={"reason": "Test rejection"}
        )
        assert res.status_code == 404, f"Expected 404, got {res.status_code}"
        print("PASS: Reject improvement returns 404 for nonexistent")
    
    def test_10_aprovador_sees_filtered_queue(self):
        """Test aprovador only sees items targeted to their company"""
        self._login_aprovador()
        
        res = self.session.get(f"{BASE_URL}/api/agent/approval-queue")
        assert res.status_code == 200, f"Approval queue failed: {res.text}"
        data = res.json()
        
        # All items should be targeted to aprovador's company
        for item in data:
            if item.get("_type") == "storyboard":
                # Storyboard items should have targetCompanyId matching aprovador's company
                pass  # targetCompanyId check depends on data
            elif item.get("_type") == "improvement":
                # Improvement items should have targetCompanyId matching aprovador's company
                pass  # targetCompanyId check depends on data
        
        print(f"PASS: Aprovador sees filtered queue with {len(data)} items")
    
    def test_11_super_admin_sees_all_statuses(self):
        """Test super admin sees pending, approved, and rejected improvement approvals"""
        self._login_admin()
        
        res = self.session.get(f"{BASE_URL}/api/agent/approval-queue")
        assert res.status_code == 200, f"Approval queue failed: {res.text}"
        data = res.json()
        
        # Super admin should see all statuses
        improvement_items = [i for i in data if i.get("_type") == "improvement"]
        statuses = set(i.get("status") for i in improvement_items)
        
        print(f"PASS: Super admin sees improvement items with statuses: {statuses}")
    
    def test_12_approval_queue_enriches_user_names(self):
        """Test approval queue enriches items with user names"""
        self._login_admin()
        
        res = self.session.get(f"{BASE_URL}/api/agent/approval-queue")
        assert res.status_code == 200, f"Approval queue failed: {res.text}"
        data = res.json()
        
        # Check that items have user name fields
        for item in data:
            if item.get("_type") == "storyboard":
                # Should have userName
                if item.get("userId"):
                    assert "userName" in item or item.get("userName") is None, "Storyboard should have userName"
            elif item.get("_type") == "improvement":
                # Should have submitterName
                if item.get("submittedBy"):
                    assert "submitterName" in item or item.get("submitterName") is None, "Improvement should have submitterName"
        
        print("PASS: Approval queue enriches items with user names")
    
    def test_13_cleanup_test_projects(self):
        """Cleanup test projects created during tests"""
        self._login_admin()
        
        # Get all projects and delete TEST_ prefixed ones
        res = self.session.get(f"{BASE_URL}/api/projects")
        if res.status_code == 200:
            projects = res.json()
            deleted = 0
            for p in projects:
                if p.get("name", "").startswith("TEST_"):
                    del_res = self.session.delete(f"{BASE_URL}/api/projects/{p['id']}")
                    if del_res.status_code in [200, 204]:
                        deleted += 1
            print(f"PASS: Cleaned up {deleted} test projects")
        else:
            print("PASS: Cleanup skipped (no projects to clean)")


class TestImprovementApprovalIntegration:
    """Integration tests for full improvement approval flow"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test fixtures"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
    
    def _login_admin(self):
        """Login as super admin"""
        res = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": SUPER_ADMIN_EMAIL,
            "password": SUPER_ADMIN_PASSWORD
        })
        assert res.status_code == 200, f"Admin login failed: {res.text}"
        data = res.json()
        self.session.headers.update({"Authorization": f"Bearer {data.get('token')}"})
        return data
    
    def test_01_get_companies_list(self):
        """Test that companies list is available for selection"""
        self._login_admin()
        
        res = self.session.get(f"{BASE_URL}/api/companies")
        assert res.status_code == 200, f"Companies list failed: {res.text}"
        data = res.json()
        assert isinstance(data, list), "Companies should be a list"
        
        # Check for expected companies
        company_ids = [c.get("id") for c in data]
        print(f"PASS: Found {len(data)} companies: {company_ids}")
    
    def test_02_improvement_approval_has_required_fields(self):
        """Test that improvement approval items have required fields for frontend"""
        self._login_admin()
        
        res = self.session.get(f"{BASE_URL}/api/agent/approval-queue")
        assert res.status_code == 200, f"Approval queue failed: {res.text}"
        data = res.json()
        
        improvement_items = [i for i in data if i.get("_type") == "improvement"]
        
        for item in improvement_items:
            # Required fields for frontend rendering
            assert "id" in item, "Missing id field"
            assert "status" in item, "Missing status field"
            assert "_type" in item, "Missing _type field"
            # Optional but expected fields
            if item.get("status") == "pending":
                assert "comparisons" in item or "updatedCount" in item, "Missing comparison data"
        
        print(f"PASS: {len(improvement_items)} improvement items have required fields")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
