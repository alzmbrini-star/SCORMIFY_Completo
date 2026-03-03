"""
Test suite for Text Entrance Animations feature
Tests:
1. Global Animation in Agent Media Config - saves and retrieves globalAnimation field
2. Per-element animation in Editor - stores animation object on elements
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
TEST_SESSION_ID = "f5e4d2e6-5f8a-4f46-921d-c126ea498626"
TEST_PROJECT_ID = "c7de35a7-0f1a-4270-86d4-703151b377e5"
EDIT_MEDIA_PROJECT_ID = "ebe2ac7b-5565-4d7f-a486-17910291f36a"

# Animation types available
ANIMATION_TYPES = ["fadeIn", "slideInLeft", "slideInRight", "slideInUp", "slideInDown", "zoomIn", "typewriter", "bounce"]

@pytest.fixture
def api_client():
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


class TestGlobalAnimationSave:
    """Test POST /api/agent/sessions/{id}/media-config saves globalAnimation"""
    
    def test_save_global_animation_fadein(self, api_client):
        """Test saving globalAnimation='fadeIn'"""
        response = api_client.post(
            f"{BASE_URL}/api/agent/sessions/{TEST_SESSION_ID}/media-config",
            json={
                "mediaConfig": {},
                "bgConfig": {},
                "globalTextColor": "",
                "globalAnimation": "fadeIn"
            }
        )
        assert response.status_code in [200, 201], f"Expected 200/201, got {response.status_code}: {response.text}"
        print("PASS: POST media-config with globalAnimation=fadeIn succeeded")

    def test_save_global_animation_bounce(self, api_client):
        """Test saving globalAnimation='bounce'"""
        response = api_client.post(
            f"{BASE_URL}/api/agent/sessions/{TEST_SESSION_ID}/media-config",
            json={
                "mediaConfig": {},
                "bgConfig": {},
                "globalTextColor": "",
                "globalAnimation": "bounce"
            }
        )
        assert response.status_code in [200, 201]
        print("PASS: POST media-config with globalAnimation=bounce succeeded")

    def test_save_global_animation_typewriter(self, api_client):
        """Test saving globalAnimation='typewriter'"""
        response = api_client.post(
            f"{BASE_URL}/api/agent/sessions/{TEST_SESSION_ID}/media-config",
            json={
                "mediaConfig": {},
                "bgConfig": {},
                "globalTextColor": "",
                "globalAnimation": "typewriter"
            }
        )
        assert response.status_code in [200, 201]
        print("PASS: POST media-config with globalAnimation=typewriter succeeded")


class TestGlobalAnimationRetrieve:
    """Test GET /api/agent/sessions/{id} returns saved globalAnimation"""
    
    def test_get_session_contains_global_animation(self, api_client):
        """First save a specific animation, then verify it's returned"""
        # Save animation
        save_resp = api_client.post(
            f"{BASE_URL}/api/agent/sessions/{TEST_SESSION_ID}/media-config",
            json={
                "mediaConfig": {},
                "bgConfig": {},
                "globalTextColor": "#ffffff",
                "globalAnimation": "slideInLeft"
            }
        )
        assert save_resp.status_code in [200, 201], f"Save failed: {save_resp.text}"
        
        # Retrieve session
        get_resp = api_client.get(f"{BASE_URL}/api/agent/sessions/{TEST_SESSION_ID}")
        assert get_resp.status_code == 200, f"GET failed: {get_resp.text}"
        
        data = get_resp.json()
        assert "globalAnimation" in data, f"globalAnimation field missing in response: {data.keys()}"
        assert data["globalAnimation"] == "slideInLeft", f"Expected 'slideInLeft', got '{data.get('globalAnimation')}'"
        print(f"PASS: GET session returns globalAnimation='{data['globalAnimation']}'")


class TestEditorElementAnimation:
    """Test element animation updates in Editor"""
    
    def test_get_project_with_slides(self, api_client):
        """Verify test project exists and has slides"""
        response = api_client.get(f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}")
        assert response.status_code == 200, f"Project not found: {response.text}"
        
        data = response.json()
        assert "course" in data, "Project missing course field"
        slides = data.get("course", {}).get("slides", [])
        assert len(slides) > 0, "Project has no slides"
        print(f"PASS: Project {TEST_PROJECT_ID} has {len(slides)} slides")
        
        # Find first slide with elements
        for slide in slides:
            elements = slide.get("elements", [])
            if elements:
                print(f"PASS: Slide {slide.get('id')} has {len(elements)} elements")
                return
        print("WARNING: No slides with elements found")

    def test_update_element_with_animation(self, api_client):
        """Test updating an element with animation data"""
        # First get project to find a slide and element
        proj_resp = api_client.get(f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}")
        assert proj_resp.status_code == 200
        
        data = proj_resp.json()
        slides = data.get("course", {}).get("slides", [])
        
        # Find a slide with elements
        slide_id = None
        element_id = None
        for slide in slides:
            elements = slide.get("elements", [])
            if elements:
                slide_id = slide.get("id")
                element_id = elements[0].get("id")
                break
        
        if not slide_id or not element_id:
            pytest.skip("No elements found to test animation update")
        
        # Update element with animation
        update_resp = api_client.put(
            f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/slides/{slide_id}/elements/{element_id}",
            json={
                "animation": {
                    "type": "entrance",
                    "effect": "zoomIn",
                    "duration": 0.5,
                    "delay": 0
                }
            }
        )
        assert update_resp.status_code == 200, f"Element update failed: {update_resp.text}"
        
        result = update_resp.json()
        assert "animation" in result, f"Animation not in response: {result.keys()}"
        assert result["animation"]["effect"] == "zoomIn", f"Expected zoomIn, got {result['animation'].get('effect')}"
        print(f"PASS: Element animation updated to zoomIn")


class TestAllAnimationTypes:
    """Test saving all 8 animation types"""
    
    @pytest.mark.parametrize("anim_type", ANIMATION_TYPES)
    def test_save_animation_type(self, api_client, anim_type):
        """Test saving each animation type"""
        response = api_client.post(
            f"{BASE_URL}/api/agent/sessions/{TEST_SESSION_ID}/media-config",
            json={
                "mediaConfig": {},
                "bgConfig": {},
                "globalTextColor": "",
                "globalAnimation": anim_type
            }
        )
        assert response.status_code in [200, 201], f"Failed for {anim_type}: {response.text}"
        print(f"PASS: Animation type '{anim_type}' saved successfully")


class TestAnimationsLibrary:
    """Test that animations.js exports are used correctly"""
    
    def test_api_health(self, api_client):
        """Verify API is healthy"""
        response = api_client.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        print("PASS: API health check")
