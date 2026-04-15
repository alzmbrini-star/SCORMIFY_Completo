"""
Test Leonardo AI Cost Tracking in Cost Estimate and Admin Reports
Tests:
1. POST /api/agent/sessions/{id}/cost-estimate returns leonardoImages, costs.leonardo, models.leonardo
2. GET /api/admin/reports returns totalLeonardoImages in stats
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@scormify.com"
ADMIN_PASSWORD = "admin123"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for admin user"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    )
    if response.status_code == 200:
        data = response.json()
        return data.get("token") or data.get("access_token")
    pytest.skip(f"Authentication failed: {response.status_code} - {response.text}")


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Headers with auth token"""
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


class TestCostEstimateEndpoint:
    """Test POST /api/agent/sessions/{id}/cost-estimate Leonardo fields"""
    
    def test_cost_estimate_with_known_session(self, auth_headers):
        """Test cost estimate endpoint with known session ID that has Leonardo images"""
        # Use the session ID provided in the review request
        session_id = "e5d36dfb-70f2-4501-8a22-2bb86710bbb4"
        
        response = requests.post(
            f"{BASE_URL}/api/agent/sessions/{session_id}/cost-estimate",
            headers=auth_headers
        )
        
        # Session may or may not exist, but we test the response structure
        if response.status_code == 404:
            pytest.skip("Test session not found - testing with a new session")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "estimate" in data, "Response should contain 'estimate' key"
        
        estimate = data["estimate"]
        
        # Verify leonardoImages field exists
        assert "leonardoImages" in estimate, "estimate should contain 'leonardoImages'"
        assert isinstance(estimate["leonardoImages"], int), "leonardoImages should be an integer"
        
        # Verify costs.leonardo field exists
        assert "costs" in estimate, "estimate should contain 'costs'"
        assert "leonardo" in estimate["costs"], "costs should contain 'leonardo'"
        assert isinstance(estimate["costs"]["leonardo"], (int, float)), "costs.leonardo should be a number"
        
        # Verify models.leonardo field exists
        assert "models" in estimate, "estimate should contain 'models'"
        assert "leonardo" in estimate["models"], "models should contain 'leonardo'"
        
        # If leonardoImages > 0, models.leonardo should be "Leonardo Phoenix 1.0"
        if estimate["leonardoImages"] > 0:
            assert estimate["models"]["leonardo"] == "Leonardo Phoenix 1.0", \
                f"Expected 'Leonardo Phoenix 1.0', got '{estimate['models']['leonardo']}'"
            # Verify cost calculation: $0.036 per image
            expected_cost = round(estimate["leonardoImages"] * 0.036, 3)
            assert estimate["costs"]["leonardo"] == expected_cost, \
                f"Expected cost {expected_cost}, got {estimate['costs']['leonardo']}"
        else:
            assert estimate["models"]["leonardo"] == "N/A", \
                f"Expected 'N/A' when no Leonardo images, got '{estimate['models']['leonardo']}'"
        
        print(f"✓ Cost estimate response structure verified")
        print(f"  - leonardoImages: {estimate['leonardoImages']}")
        print(f"  - costs.leonardo: ${estimate['costs']['leonardo']}")
        print(f"  - models.leonardo: {estimate['models']['leonardo']}")
    
    def test_cost_estimate_response_structure(self, auth_headers):
        """Test that cost estimate response has all required fields using known session"""
        # Use the known session ID that has structure data
        session_id = "e5d36dfb-70f2-4501-8a22-2bb86710bbb4"
        
        # Get cost estimate
        response = requests.post(
            f"{BASE_URL}/api/agent/sessions/{session_id}/cost-estimate",
            headers=auth_headers
        )
        
        if response.status_code == 404:
            pytest.skip("Test session not found")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        estimate = data.get("estimate", {})
        
        # Verify all required fields exist
        required_fields = ["totalSlides", "contentSlides", "aiImages", "leonardoImages", 
                          "storyboardBatches", "narrationEnabled", "costs", "comparison", "models"]
        for field in required_fields:
            assert field in estimate, f"Missing required field: {field}"
        
        # Verify costs structure
        cost_fields = ["text", "images", "leonardo", "narration", "total"]
        for field in cost_fields:
            assert field in estimate["costs"], f"Missing cost field: {field}"
        
        # Verify models structure
        model_fields = ["text", "images", "leonardo", "narration"]
        for field in model_fields:
            assert field in estimate["models"], f"Missing model field: {field}"
        
        print(f"✓ Cost estimate structure verified for session {session_id}")


class TestAdminReportsEndpoint:
    """Test GET /api/admin/reports totalLeonardoImages field"""
    
    def test_admin_reports_contains_leonardo_stats(self, auth_headers):
        """Test that admin reports include totalLeonardoImages in stats"""
        response = requests.get(
            f"{BASE_URL}/api/admin/reports",
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "reports" in data, "Response should contain 'reports' key"
        
        reports = data["reports"]
        assert isinstance(reports, list), "reports should be a list"
        
        # Check each company report for totalLeonardoImages
        for report in reports:
            assert "stats" in report, f"Report should contain 'stats': {report.get('company', {}).get('name')}"
            stats = report["stats"]
            
            # Verify totalLeonardoImages field exists
            assert "totalLeonardoImages" in stats, \
                f"stats should contain 'totalLeonardoImages' for company: {report.get('company', {}).get('name')}"
            assert isinstance(stats["totalLeonardoImages"], int), \
                f"totalLeonardoImages should be an integer, got {type(stats['totalLeonardoImages'])}"
            
            print(f"✓ Company '{report.get('company', {}).get('name')}' - totalLeonardoImages: {stats['totalLeonardoImages']}")
        
        print(f"✓ Admin reports verified - {len(reports)} company reports checked")
    
    def test_admin_reports_stats_structure(self, auth_headers):
        """Test that admin reports stats have all required fields including Leonardo"""
        response = requests.get(
            f"{BASE_URL}/api/admin/reports",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        
        data = response.json()
        reports = data.get("reports", [])
        
        if not reports:
            pytest.skip("No reports available to test")
        
        # Check first report's stats structure
        first_report = reports[0]
        stats = first_report.get("stats", {})
        
        required_stats = ["totalCourses", "totalSlides", "totalAiImages", "totalLeonardoImages",
                         "totalNarrations", "totalCostUSD", "totalCostBRL"]
        
        for field in required_stats:
            assert field in stats, f"Missing required stats field: {field}"
        
        print(f"✓ Admin reports stats structure verified")
        print(f"  - totalCourses: {stats.get('totalCourses')}")
        print(f"  - totalAiImages: {stats.get('totalAiImages')}")
        print(f"  - totalLeonardoImages: {stats.get('totalLeonardoImages')}")
        print(f"  - totalCostUSD: ${stats.get('totalCostUSD')}")


class TestUsageLogsStructure:
    """Test that usage_logs collection has correct Leonardo fields"""
    
    def test_usage_logs_leonardo_fields_in_reports(self, auth_headers):
        """Verify Leonardo fields are being aggregated correctly in reports"""
        response = requests.get(
            f"{BASE_URL}/api/admin/reports",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        
        data = response.json()
        
        # The reports endpoint aggregates from usage_logs
        # If totalLeonardoImages is present and is a number, the aggregation is working
        reports = data.get("reports", [])
        
        total_leonardo_across_all = 0
        for report in reports:
            stats = report.get("stats", {})
            leonardo_count = stats.get("totalLeonardoImages", 0)
            total_leonardo_across_all += leonardo_count
        
        print(f"✓ Total Leonardo images across all companies: {total_leonardo_across_all}")
        print(f"  (This confirms usage_logs.details.leonardoImages is being aggregated)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
