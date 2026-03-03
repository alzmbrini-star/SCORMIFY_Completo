"""
Test Suite for Gemini Model Switch and Cost Estimation Feature
Tests: cost-estimate endpoint, model configurations, generate-bg-image, media-config
Session: 3c7aba89-3c78-47af-992a-8f350ef194fd (existing generated course)
"""
import pytest
import requests
import os

# Use production URL from environment
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestHealthAndBase:
    """Basic health check tests"""
    
    def test_api_health(self):
        """Test API is healthy"""
        response = requests.get(f"{BASE_URL}/api/health", timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy"
        print("PASS: API health check")


class TestCostEstimateEndpoint:
    """Tests for POST /api/agent/sessions/{session_id}/cost-estimate"""
    
    SESSION_ID = "3c7aba89-3c78-47af-992a-8f350ef194fd"
    
    def test_cost_estimate_returns_200(self):
        """Test cost-estimate endpoint returns 200 for valid session"""
        response = requests.post(f"{BASE_URL}/api/agent/sessions/{self.SESSION_ID}/cost-estimate", timeout=10)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print(f"PASS: cost-estimate returns 200 for session {self.SESSION_ID}")
        
    def test_cost_estimate_structure(self):
        """Test cost-estimate response has correct structure"""
        response = requests.post(f"{BASE_URL}/api/agent/sessions/{self.SESSION_ID}/cost-estimate", timeout=10)
        data = response.json()
        
        assert "estimate" in data, "Response should contain 'estimate' key"
        estimate = data["estimate"]
        
        # Check required fields
        assert "totalSlides" in estimate, "estimate should have totalSlides"
        assert "costs" in estimate, "estimate should have costs"
        assert "comparison" in estimate, "estimate should have comparison"
        assert "models" in estimate, "estimate should have models"
        
        print(f"PASS: cost-estimate has correct structure")
        
    def test_cost_estimate_costs_breakdown(self):
        """Test costs breakdown includes text, images, narration, total"""
        response = requests.post(f"{BASE_URL}/api/agent/sessions/{self.SESSION_ID}/cost-estimate", timeout=10)
        data = response.json()
        
        costs = data["estimate"]["costs"]
        assert "text" in costs, "costs should have 'text'"
        assert "images" in costs, "costs should have 'images'"
        assert "narration" in costs, "costs should have 'narration'"
        assert "total" in costs, "costs should have 'total'"
        
        # Verify types are numeric
        assert isinstance(costs["text"], (int, float))
        assert isinstance(costs["images"], (int, float))
        assert isinstance(costs["total"], (int, float))
        
        print(f"PASS: costs breakdown correct - text: ${costs['text']}, images: ${costs['images']}, total: ${costs['total']}")
        
    def test_cost_estimate_comparison_with_old_gpt(self):
        """Test comparison shows old GPT pricing and savings"""
        response = requests.post(f"{BASE_URL}/api/agent/sessions/{self.SESSION_ID}/cost-estimate", timeout=10)
        data = response.json()
        
        comparison = data["estimate"]["comparison"]
        assert "oldTotal" in comparison, "comparison should have oldTotal"
        assert "newTotal" in comparison, "comparison should have newTotal"
        assert "savingsPercent" in comparison, "comparison should have savingsPercent"
        
        # Verify old is higher than new (cost savings)
        assert comparison["oldTotal"] >= comparison["newTotal"], "Old GPT total should be >= new Gemini total"
        
        print(f"PASS: comparison shows savings - old: ${comparison['oldTotal']}, new: ${comparison['newTotal']}, savings: {comparison['savingsPercent']}%")
        
    def test_cost_estimate_shows_gemini_models(self):
        """Test models shows Gemini 3 Flash for text and Gemini Nano Banana for images"""
        response = requests.post(f"{BASE_URL}/api/agent/sessions/{self.SESSION_ID}/cost-estimate", timeout=10)
        data = response.json()
        
        models = data["estimate"]["models"]
        assert "text" in models, "models should have 'text'"
        assert "images" in models, "models should have 'images'"
        
        # Check model names
        assert "Gemini 3 Flash" in models["text"], f"Text model should be Gemini 3 Flash, got: {models['text']}"
        assert "Gemini Nano Banana" in models["images"] or "gemini" in models["images"].lower(), f"Image model should be Gemini Nano Banana, got: {models['images']}"
        
        print(f"PASS: models are correct - text: {models['text']}, images: {models['images']}")
        
    def test_cost_estimate_invalid_session(self):
        """Test cost-estimate returns 404 for invalid session"""
        response = requests.post(f"{BASE_URL}/api/agent/sessions/invalid-session-id/cost-estimate", timeout=10)
        assert response.status_code == 404
        print("PASS: cost-estimate returns 404 for invalid session")
        
    def test_cost_estimate_savings_percentage_reasonable(self):
        """Test that savings percentage is reasonable (between 50-90%)"""
        response = requests.post(f"{BASE_URL}/api/agent/sessions/{self.SESSION_ID}/cost-estimate", timeout=10)
        data = response.json()
        
        savings = data["estimate"]["comparison"]["savingsPercent"]
        # Gemini should be ~75-80% cheaper than GPT-5.2 + GPT Image
        assert 50 <= savings <= 95, f"Savings should be between 50-95%, got {savings}%"
        
        print(f"PASS: savings percentage is reasonable at {savings}%")


class TestMediaConfigEndpoint:
    """Tests for POST /api/agent/sessions/{session_id}/media-config"""
    
    SESSION_ID = "3c7aba89-3c78-47af-992a-8f350ef194fd"
    
    def test_media_config_with_both_configs(self):
        """Test media-config accepts both mediaConfig and bgConfig"""
        payload = {
            "mediaConfig": {
                "0": {"type": "ai_image"},
                "1": {"type": "youtube", "url": "https://youtube.com/watch?v=test"}
            },
            "bgConfig": {
                "0": {"type": "solid", "color": "#1e293b"},
                "1": {"type": "gradient", "color1": "#1e293b", "color2": "#10b981", "direction": "to right"}
            }
        }
        response = requests.post(
            f"{BASE_URL}/api/agent/sessions/{self.SESSION_ID}/media-config",
            json=payload,
            timeout=10
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert data.get("status") == "ok"
        assert data.get("configured") == 2  # 2 media configs
        assert data.get("backgrounds") == 2  # 2 background configs
        
        print(f"PASS: media-config accepts both mediaConfig and bgConfig")
        
    def test_media_config_invalid_session(self):
        """Test media-config returns 404 for invalid session"""
        response = requests.post(
            f"{BASE_URL}/api/agent/sessions/invalid-session-id/media-config",
            json={"mediaConfig": {}, "bgConfig": {}},
            timeout=10
        )
        assert response.status_code == 404
        print("PASS: media-config returns 404 for invalid session")


class TestAgentSessionEndpoint:
    """Tests for GET /api/agent/sessions/{session_id}"""
    
    SESSION_ID = "3c7aba89-3c78-47af-992a-8f350ef194fd"
    
    def test_session_exists_and_has_content(self):
        """Test session exists and has required data"""
        response = requests.get(f"{BASE_URL}/api/agent/sessions/{self.SESSION_ID}", timeout=10)
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("id") == self.SESSION_ID
        assert data.get("step") in ["generated", "storyboarded", "structured"], f"Session step is: {data.get('step')}"
        
        print(f"PASS: session exists with step '{data.get('step')}'")


class TestSuggestionsEndpoint:
    """Tests for GET /api/agent/sessions/{session_id}/suggestions"""
    
    SESSION_ID = "3c7aba89-3c78-47af-992a-8f350ef194fd"
    
    def test_suggestions_endpoint_works(self):
        """Test suggestions endpoint returns data"""
        response = requests.get(f"{BASE_URL}/api/agent/sessions/{self.SESSION_ID}/suggestions", timeout=10)
        assert response.status_code == 200
        data = response.json()
        
        assert "status" in data
        print(f"PASS: suggestions endpoint works, status: {data.get('status')}")


class TestGenerateBgImageEndpoint:
    """Tests for POST /api/agent/generate-bg-image (structure test only - no actual generation)"""
    
    def test_generate_bg_image_requires_prompt(self):
        """Test generate-bg-image requires prompt field"""
        response = requests.post(
            f"{BASE_URL}/api/agent/generate-bg-image",
            json={},
            timeout=10
        )
        assert response.status_code == 400, f"Expected 400 for missing prompt, got {response.status_code}"
        print("PASS: generate-bg-image requires prompt field")
        
    def test_generate_bg_image_endpoint_exists(self):
        """Test generate-bg-image endpoint exists (structure test)"""
        # Send with prompt but don't wait for full generation
        response = requests.post(
            f"{BASE_URL}/api/agent/generate-bg-image",
            json={"prompt": "test"},
            timeout=30  # Longer timeout for actual generation attempt
        )
        # Either 200 (success) or 500 (budget/timeout) - but NOT 404 (not found)
        assert response.status_code != 404, "Endpoint should exist"
        print(f"PASS: generate-bg-image endpoint exists, returned {response.status_code}")


class TestAIAgentModels:
    """Tests for AI agent model configuration in ai_agent.py"""
    
    def test_primary_model_config_in_code(self):
        """Verify PRIMARY_MODEL and FALLBACK_MODEL are configured correctly"""
        import sys
        sys.path.insert(0, '/app/backend')
        
        from services.ai_agent import PRIMARY_MODEL, FALLBACK_MODEL, IMAGE_MODEL
        
        # Check PRIMARY_MODEL is Gemini
        assert PRIMARY_MODEL[0] == "gemini", f"PRIMARY_MODEL provider should be 'gemini', got {PRIMARY_MODEL[0]}"
        assert "gemini-3-flash" in PRIMARY_MODEL[1], f"PRIMARY_MODEL should be gemini-3-flash, got {PRIMARY_MODEL[1]}"
        
        # Check FALLBACK_MODEL is OpenAI
        assert FALLBACK_MODEL[0] == "openai", f"FALLBACK_MODEL provider should be 'openai', got {FALLBACK_MODEL[0]}"
        assert "gpt-4o" in FALLBACK_MODEL[1], f"FALLBACK_MODEL should be gpt-4o, got {FALLBACK_MODEL[1]}"
        
        # Check IMAGE_MODEL is Gemini
        assert IMAGE_MODEL[0] == "gemini", f"IMAGE_MODEL provider should be 'gemini', got {IMAGE_MODEL[0]}"
        
        print(f"PASS: Model configs correct - PRIMARY: {PRIMARY_MODEL}, FALLBACK: {FALLBACK_MODEL}, IMAGE: {IMAGE_MODEL}")


class TestAllAgentEndpoints:
    """Verify all agent endpoints are functional"""
    
    SESSION_ID = "3c7aba89-3c78-47af-992a-8f350ef194fd"
    
    def test_templates_endpoint(self):
        """Test templates endpoint works"""
        response = requests.get(f"{BASE_URL}/api/agent/templates", timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"PASS: templates endpoint returns {len(data)} templates")
        
    def test_create_session_endpoint(self):
        """Test session creation endpoint"""
        response = requests.post(f"{BASE_URL}/api/agent/sessions", json={}, timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        print(f"PASS: session creation works, created session {data['id'][:8]}...")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
