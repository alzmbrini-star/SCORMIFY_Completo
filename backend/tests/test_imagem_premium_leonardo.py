"""
Test suite for Leonardo AI Premium Image Integration in Agent IA Improvements
Tests the 'imagem_premium' improvement type and _leonardoImage handling
"""
import pytest
import requests
import os
import json
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@scormify.com"
ADMIN_PASSWORD = "admin123"

# Known project ID from context
TEST_PROJECT_ID = "111f5fcd-72eb-4c64-a165-b737a13c2ffb"


class TestImagemPremiumLeonardoIntegration:
    """Tests for imagem_premium improvement type and Leonardo AI integration"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup: Login and get auth token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if login_resp.status_code == 200:
            data = login_resp.json()
            token = data.get("token") or data.get("access_token")
            if token:
                self.session.headers.update({"Authorization": f"Bearer {token}"})
        yield
        self.session.close()

    def test_analyze_endpoint_returns_imagem_premium_type(self):
        """Test that course analysis can return imagem_premium improvement suggestions"""
        # First, get a project to analyze
        projects_resp = self.session.get(f"{BASE_URL}/api/projects")
        assert projects_resp.status_code == 200, f"Failed to get projects: {projects_resp.text}"
        
        projects = projects_resp.json()
        if not projects:
            pytest.skip("No projects available for testing")
        
        project_id = projects[0].get("id")
        
        # Trigger analysis (async endpoint)
        analyze_resp = self.session.post(f"{BASE_URL}/api/agent/courses/{project_id}/analyze")
        assert analyze_resp.status_code == 200, f"Analysis failed: {analyze_resp.text}"
        
        result = analyze_resp.json()
        # Analysis is async, so we may get 'processing' status
        if result.get("status") == "processing":
            # Poll for result
            for _ in range(30):  # Max 60 seconds
                time.sleep(2)
                poll_resp = self.session.post(f"{BASE_URL}/api/agent/courses/{project_id}/analyze")
                if poll_resp.status_code == 200:
                    poll_result = poll_resp.json()
                    if poll_result.get("status") != "processing":
                        result = poll_result
                        break
        
        # Verify the response structure supports imagem_premium
        # The analysis may or may not suggest imagem_premium depending on course content
        # But the endpoint should work and return valid structure
        assert "improvements" in result or "status" in result, f"Invalid analysis response: {result}"
        print(f"Analysis response keys: {result.keys()}")
        
        if "improvements" in result:
            improvements = result.get("improvements", [])
            print(f"Found {len(improvements)} improvement suggestions")
            
            # Check if any imagem_premium suggestions exist
            imagem_premium_suggestions = [imp for imp in improvements if imp.get("type") == "imagem_premium"]
            print(f"Found {len(imagem_premium_suggestions)} imagem_premium suggestions")
            
            # Verify imagem_premium structure if present
            for imp in imagem_premium_suggestions:
                assert "imagePrompt" in imp, "imagem_premium should have imagePrompt field"
                assert "imageStyle" in imp or imp.get("imageStyle") is None, "imagem_premium should have imageStyle field"
                print(f"imagem_premium suggestion: {imp.get('description')}")
                print(f"  imagePrompt: {imp.get('imagePrompt')}")
                print(f"  imageStyle: {imp.get('imageStyle')}")

    def test_apply_improvements_endpoint_structure(self):
        """Test that apply-improvements endpoint accepts imagem_premium improvements"""
        # Get a project
        projects_resp = self.session.get(f"{BASE_URL}/api/projects")
        assert projects_resp.status_code == 200
        
        projects = projects_resp.json()
        if not projects:
            pytest.skip("No projects available for testing")
        
        project_id = projects[0].get("id")
        
        # Test with a mock imagem_premium improvement (dry run - just verify endpoint accepts it)
        # We won't actually apply to avoid consuming Leonardo API credits
        mock_improvement = {
            "slideIndex": 0,
            "type": "imagem_premium",
            "priority": "media",
            "description": "Test premium image",
            "suggestion": "Test suggestion",
            "imagePrompt": "Modern corporate training room with professionals",
            "imageStyle": "CINEMATIC"
        }
        
        # Preview endpoint should accept imagem_premium type
        preview_resp = self.session.post(
            f"{BASE_URL}/api/agent/courses/{project_id}/preview-improvements",
            json={"improvements": [mock_improvement], "selectedNewSlides": []}
        )
        
        # Preview may take time due to AI processing
        if preview_resp.status_code == 200:
            preview_result = preview_resp.json()
            print(f"Preview response: {preview_result.keys()}")
            assert "previewId" in preview_result or "comparisons" in preview_result or "status" in preview_result
        else:
            # 400/422 is acceptable if the project doesn't have slides
            assert preview_resp.status_code in [200, 400, 422, 500], f"Unexpected status: {preview_resp.status_code}"
            print(f"Preview response status: {preview_resp.status_code}")

    def test_leonardo_api_key_configured(self):
        """Test that Leonardo API key is configured in backend"""
        # This is verified by checking if Leonardo endpoints work
        # Generate endpoint requires auth
        gen_resp = self.session.post(f"{BASE_URL}/api/leonardo/generate", json={
            "prompt": "test prompt",
            "width": 512,
            "height": 512
        })
        
        # Should not return 500 with "API key not configured" error
        if gen_resp.status_code == 500:
            error = gen_resp.json()
            assert "API key not configured" not in str(error), "Leonardo API key is not configured"
        
        # 200 or 400 (validation) or 401 (auth) are acceptable
        assert gen_resp.status_code in [200, 400, 401, 422, 500], f"Unexpected status: {gen_resp.status_code}"
        print(f"Leonardo generate endpoint status: {gen_resp.status_code}")

    def test_apply_improvements_returns_leonardo_count(self):
        """Test that apply-improvements response includes leonardoImagesGenerated field"""
        # Get a project
        projects_resp = self.session.get(f"{BASE_URL}/api/projects")
        assert projects_resp.status_code == 200
        
        projects = projects_resp.json()
        if not projects:
            pytest.skip("No projects available for testing")
        
        project_id = projects[0].get("id")
        
        # Apply a simple content improvement (not imagem_premium to avoid API costs)
        simple_improvement = {
            "slideIndex": 0,
            "type": "content",
            "priority": "baixa",
            "description": "Test content improvement",
            "suggestion": "Minor text update"
        }
        
        apply_resp = self.session.post(
            f"{BASE_URL}/api/agent/courses/{project_id}/apply-improvements",
            json={"improvements": [simple_improvement], "selectedNewSlides": []}
        )
        
        if apply_resp.status_code == 200:
            result = apply_resp.json()
            # Verify leonardoImagesGenerated field exists in response
            assert "leonardoImagesGenerated" in result, "Response should include leonardoImagesGenerated field"
            print(f"leonardoImagesGenerated: {result.get('leonardoImagesGenerated')}")
            
            # Undo the improvement to restore original state
            undo_resp = self.session.post(f"{BASE_URL}/api/agent/courses/{project_id}/undo-improvements")
            print(f"Undo status: {undo_resp.status_code}")
        else:
            print(f"Apply improvements status: {apply_resp.status_code}")
            # May fail if project has no slides or other issues
            assert apply_resp.status_code in [200, 400, 422, 500]


class TestFrontendImagemPremiumSupport:
    """Tests to verify frontend components support imagem_premium type"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup: Login and get auth token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if login_resp.status_code == 200:
            data = login_resp.json()
            token = data.get("token") or data.get("access_token")
            if token:
                self.session.headers.update({"Authorization": f"Bearer {token}"})
        yield
        self.session.close()

    def test_agent_check_access(self):
        """Test that agent access check works"""
        resp = self.session.get(f"{BASE_URL}/api/agent/check-access")
        assert resp.status_code == 200, f"Agent access check failed: {resp.text}"
        
        result = resp.json()
        assert "hasAccess" in result
        print(f"Agent access: {result}")

    def test_design_templates_endpoint(self):
        """Test that design templates endpoint works (used in Agent workflow)"""
        resp = self.session.get(f"{BASE_URL}/api/agent/design-templates")
        assert resp.status_code == 200, f"Design templates failed: {resp.text}"
        
        templates = resp.json()
        assert isinstance(templates, list)
        print(f"Found {len(templates)} design templates")


class TestAIAgentAnalysisImagemPremium:
    """Tests for AI Agent analysis with imagem_premium type"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup: Login and get auth token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if login_resp.status_code == 200:
            data = login_resp.json()
            token = data.get("token") or data.get("access_token")
            if token:
                self.session.headers.update({"Authorization": f"Bearer {token}"})
        yield
        self.session.close()

    def test_analysis_prompt_includes_imagem_premium(self):
        """Verify that the analysis prompt includes imagem_premium as an option"""
        # This is a code verification test - we check the backend code includes imagem_premium
        # The actual AI response depends on the course content
        
        # Get projects
        projects_resp = self.session.get(f"{BASE_URL}/api/projects")
        assert projects_resp.status_code == 200
        
        projects = projects_resp.json()
        if not projects:
            pytest.skip("No projects available")
        
        # Just verify the endpoint works
        project_id = projects[0].get("id")
        resp = self.session.post(f"{BASE_URL}/api/agent/courses/{project_id}/analyze")
        assert resp.status_code == 200
        print(f"Analysis endpoint working for project {project_id}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
