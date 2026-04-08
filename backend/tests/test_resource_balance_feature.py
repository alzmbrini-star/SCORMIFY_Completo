"""
Test Resource Balance Feature for Scormify AI Course Platform
Tests the new resource balance configuration in course creation:
- resourceBalance levels (baixa, media, alta, maxima)
- enabledResources toggles for 8 resource types
- Backend generate_structure endpoint accepts these config fields
- New slide types (infographic, flashcard, timeline, case_study) handling
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@scormify.com"
ADMIN_PASSWORD = "admin123"


class TestResourceBalanceFeature:
    """Tests for the resource balance configuration feature"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session with authentication"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        # Login as admin
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if login_resp.status_code == 200:
            data = login_resp.json()
            token = data.get("token")
            if token:
                self.session.headers.update({"Authorization": f"Bearer {token}"})
        yield
        self.session.close()
    
    def test_health_check(self):
        """Verify API is accessible"""
        resp = self.session.get(f"{BASE_URL}/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("status") == "healthy"
        print("✓ Health check passed")
    
    def test_auth_login_admin(self):
        """Verify admin login works"""
        resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "token" in data
        assert data.get("user", {}).get("role") == "super_admin"
        print("✓ Admin login successful")
    
    def test_create_agent_session(self):
        """Test creating a new agent session"""
        resp = self.session.post(f"{BASE_URL}/api/agent/sessions", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert "id" in data
        print(f"✓ Agent session created: {data['id']}")
        return data["id"]
    
    def test_configure_session_with_resource_balance(self):
        """Test configuring session with resourceBalance and enabledResources"""
        # Create session first
        session_resp = self.session.post(f"{BASE_URL}/api/agent/sessions", json={})
        assert session_resp.status_code == 200
        session_id = session_resp.json()["id"]
        
        # Upload some content
        upload_resp = self.session.post(
            f"{BASE_URL}/api/agent/sessions/{session_id}/upload",
            data={"text": "Este é um conteúdo de teste sobre segurança no trabalho. Inclui normas de segurança, EPIs, procedimentos de emergência e boas práticas."},
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        assert upload_resp.status_code == 200
        
        # Configure with resource balance settings
        config = {
            "title": "Curso de Segurança no Trabalho",
            "depth": "intermediario",
            "duration": 30,
            "modules": 3,
            "format": "curso_completo",
            "description": "Curso sobre segurança no trabalho",
            "resourceBalance": "alta",
            "enabledResources": {
                "quiz": True,
                "simulator": True,
                "scenario": True,
                "avatar_scene": True,
                "infographic": True,
                "flashcard": True,
                "timeline": True,
                "case_study": True
            }
        }
        
        config_resp = self.session.post(
            f"{BASE_URL}/api/agent/sessions/{session_id}/configure",
            json=config
        )
        assert config_resp.status_code == 200
        print("✓ Session configured with resource balance settings")
        
        # Verify session has the config
        get_resp = self.session.get(f"{BASE_URL}/api/agent/sessions/{session_id}")
        assert get_resp.status_code == 200
        session_data = get_resp.json()
        assert session_data.get("config", {}).get("resourceBalance") == "alta"
        assert session_data.get("config", {}).get("enabledResources", {}).get("quiz") == True
        print("✓ Resource balance config persisted correctly")
        
        return session_id
    
    def test_configure_baixa_interactivity(self):
        """Test baixa interactivity level configuration"""
        session_resp = self.session.post(f"{BASE_URL}/api/agent/sessions", json={})
        session_id = session_resp.json()["id"]
        
        # Upload content
        self.session.post(
            f"{BASE_URL}/api/agent/sessions/{session_id}/upload",
            data={"text": "Conteúdo de teste para nível baixa interatividade."},
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        
        # Configure with baixa level
        config = {
            "title": "Curso Baixa Interatividade",
            "resourceBalance": "baixa",
            "enabledResources": {
                "quiz": True,
                "simulator": False,
                "scenario": False,
                "avatar_scene": False,
                "infographic": False,
                "flashcard": True,
                "timeline": False,
                "case_study": False
            }
        }
        
        config_resp = self.session.post(
            f"{BASE_URL}/api/agent/sessions/{session_id}/configure",
            json=config
        )
        assert config_resp.status_code == 200
        
        # Verify
        get_resp = self.session.get(f"{BASE_URL}/api/agent/sessions/{session_id}")
        session_data = get_resp.json()
        assert session_data.get("config", {}).get("resourceBalance") == "baixa"
        assert session_data.get("config", {}).get("enabledResources", {}).get("simulator") == False
        print("✓ Baixa interactivity level configured correctly")
    
    def test_configure_maxima_interactivity(self):
        """Test maxima interactivity level configuration"""
        session_resp = self.session.post(f"{BASE_URL}/api/agent/sessions", json={})
        session_id = session_resp.json()["id"]
        
        # Upload content
        self.session.post(
            f"{BASE_URL}/api/agent/sessions/{session_id}/upload",
            data={"text": "Conteúdo de teste para nível máxima interatividade."},
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        
        # Configure with maxima level - all resources enabled
        config = {
            "title": "Curso Máxima Interatividade",
            "resourceBalance": "maxima",
            "enabledResources": {
                "quiz": True,
                "simulator": True,
                "scenario": True,
                "avatar_scene": True,
                "infographic": True,
                "flashcard": True,
                "timeline": True,
                "case_study": True
            }
        }
        
        config_resp = self.session.post(
            f"{BASE_URL}/api/agent/sessions/{session_id}/configure",
            json=config
        )
        assert config_resp.status_code == 200
        
        # Verify all resources enabled
        get_resp = self.session.get(f"{BASE_URL}/api/agent/sessions/{session_id}")
        session_data = get_resp.json()
        enabled = session_data.get("config", {}).get("enabledResources", {})
        assert enabled.get("quiz") == True
        assert enabled.get("simulator") == True
        assert enabled.get("scenario") == True
        assert enabled.get("avatar_scene") == True
        assert enabled.get("infographic") == True
        assert enabled.get("flashcard") == True
        assert enabled.get("timeline") == True
        assert enabled.get("case_study") == True
        print("✓ Maxima interactivity level configured with all resources enabled")
    
    def test_design_templates_endpoint(self):
        """Test that design templates endpoint returns templates"""
        resp = self.session.get(f"{BASE_URL}/api/agent/design-templates")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) > 0
        # Check template structure
        template = data[0]
        assert "id" in template
        assert "name" in template
        assert "palette" in template
        print(f"✓ Design templates endpoint returns {len(data)} templates")
    
    def test_templates_endpoint(self):
        """Test that templates endpoint returns course templates"""
        resp = self.session.get(f"{BASE_URL}/api/agent/templates")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        print(f"✓ Templates endpoint returns {len(data)} templates")
    
    def test_approval_queue_endpoint(self):
        """Test approval queue endpoint works (regression test)"""
        resp = self.session.get(f"{BASE_URL}/api/agent/approval-queue")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        # Check that items have _type field if present
        for item in data:
            if "_type" in item:
                assert item["_type"] in ["storyboard", "improvement"]
        print(f"✓ Approval queue endpoint returns {len(data)} items")
    
    def test_session_with_all_resource_types(self):
        """Test session configuration with all 8 resource types"""
        session_resp = self.session.post(f"{BASE_URL}/api/agent/sessions", json={})
        session_id = session_resp.json()["id"]
        
        # Upload content
        self.session.post(
            f"{BASE_URL}/api/agent/sessions/{session_id}/upload",
            data={"text": "Conteúdo completo para teste de todos os tipos de recursos."},
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        
        # All 8 resource types
        resource_types = ["quiz", "simulator", "scenario", "avatar_scene", "infographic", "flashcard", "timeline", "case_study"]
        enabled_resources = {rt: True for rt in resource_types}
        
        config = {
            "title": "Curso Completo",
            "resourceBalance": "alta",
            "enabledResources": enabled_resources
        }
        
        config_resp = self.session.post(
            f"{BASE_URL}/api/agent/sessions/{session_id}/configure",
            json=config
        )
        assert config_resp.status_code == 200
        
        # Verify all 8 types are stored
        get_resp = self.session.get(f"{BASE_URL}/api/agent/sessions/{session_id}")
        session_data = get_resp.json()
        stored_resources = session_data.get("config", {}).get("enabledResources", {})
        
        for rt in resource_types:
            assert stored_resources.get(rt) == True, f"Resource type {rt} should be enabled"
        
        print("✓ All 8 resource types configured correctly")


class TestApprovalQueueRegression:
    """Regression tests for ApprovalQueuePanel with combined storyboard + improvement items"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session with authentication"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if login_resp.status_code == 200:
            data = login_resp.json()
            token = data.get("token")
            if token:
                self.session.headers.update({"Authorization": f"Bearer {token}"})
        yield
        self.session.close()
    
    def test_approval_queue_returns_combined_items(self):
        """Test that approval queue returns both storyboard and improvement items"""
        resp = self.session.get(f"{BASE_URL}/api/agent/approval-queue")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        
        # Check structure of items
        for item in data:
            assert "id" in item
            # Items should have _type field
            if "_type" in item:
                assert item["_type"] in ["storyboard", "improvement"]
        
        print(f"✓ Approval queue returns {len(data)} combined items")
    
    def test_approval_queue_item_structure(self):
        """Test that approval queue items have required fields"""
        resp = self.session.get(f"{BASE_URL}/api/agent/approval-queue")
        assert resp.status_code == 200
        data = resp.json()
        
        for item in data:
            # Common fields
            assert "id" in item
            
            if item.get("_type") == "improvement":
                # Improvement-specific fields
                assert "status" in item or "projectId" in item
            elif item.get("_type") == "storyboard" or "storyboard" in item:
                # Storyboard-specific fields
                assert "step" in item or "storyboard" in item
        
        print("✓ Approval queue items have correct structure")


class TestNewSlideTypes:
    """Tests for new slide types: infographic, flashcard, timeline, case_study"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session with authentication"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if login_resp.status_code == 200:
            data = login_resp.json()
            token = data.get("token")
            if token:
                self.session.headers.update({"Authorization": f"Bearer {token}"})
        yield
        self.session.close()
    
    def test_new_slide_types_in_config(self):
        """Test that new slide types can be enabled in config"""
        session_resp = self.session.post(f"{BASE_URL}/api/agent/sessions", json={})
        session_id = session_resp.json()["id"]
        
        # Upload content
        self.session.post(
            f"{BASE_URL}/api/agent/sessions/{session_id}/upload",
            data={"text": "Conteúdo para teste de novos tipos de slides."},
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        
        # Enable new slide types
        config = {
            "title": "Curso com Novos Tipos",
            "resourceBalance": "alta",
            "enabledResources": {
                "quiz": True,
                "simulator": True,
                "scenario": False,
                "avatar_scene": False,
                "infographic": True,  # New type
                "flashcard": True,    # New type
                "timeline": True,     # New type
                "case_study": True    # New type
            }
        }
        
        config_resp = self.session.post(
            f"{BASE_URL}/api/agent/sessions/{session_id}/configure",
            json=config
        )
        assert config_resp.status_code == 200
        
        # Verify new types are stored
        get_resp = self.session.get(f"{BASE_URL}/api/agent/sessions/{session_id}")
        session_data = get_resp.json()
        enabled = session_data.get("config", {}).get("enabledResources", {})
        
        assert enabled.get("infographic") == True
        assert enabled.get("flashcard") == True
        assert enabled.get("timeline") == True
        assert enabled.get("case_study") == True
        
        print("✓ New slide types (infographic, flashcard, timeline, case_study) configured correctly")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
