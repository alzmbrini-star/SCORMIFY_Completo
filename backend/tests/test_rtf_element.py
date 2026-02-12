"""
Test RTF/HTML Element CRUD Operations
Tests the critical bug fix for editing and saving RTF text elements
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "admin@scormify.com"
TEST_PASSWORD = "admin123"

# Known project/slide/element IDs from the test data
PROJECT_ID = "58753bb1-60a3-4190-8de3-ca51203e8f4d"
SLIDE_ID = "bb88db0a-07e1-4df7-b2a2-031aea0fa6b0"  # Slide index 2
ELEMENT_ID = "3b5164f0-d152-4def-8b05-79cd550e5737"  # HTML element on slide 2


@pytest.fixture(scope="module")
def api_session():
    """Create requests session and login"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    
    # Login
    login_response = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    })
    
    if login_response.status_code != 200:
        pytest.skip(f"Authentication failed: {login_response.status_code} - {login_response.text}")
    
    return session


class TestHealthAndAuth:
    """Basic health and auth tests"""
    
    def test_health_endpoint(self, api_session):
        """Test API is up"""
        response = api_session.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        print("✅ Health endpoint working")
    
    def test_auth_login(self):
        """Test login works"""
        session = requests.Session()
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        assert "id" in data or "user" in data or "email" in data
        print(f"✅ Login successful: {data.get('email', data.get('id', 'OK'))}")


class TestProjectAccess:
    """Test project access"""
    
    def test_get_project(self, api_session):
        """Test getting the demo project"""
        response = api_session.get(f"{BASE_URL}/api/projects/{PROJECT_ID}")
        assert response.status_code == 200
        data = response.json()
        assert "course" in data
        assert "slides" in data["course"]
        print(f"✅ Project '{data.get('name', 'N/A')}' loaded with {len(data['course']['slides'])} slides")
    
    def test_get_slide_with_html_element(self, api_session):
        """Test getting the slide with HTML element"""
        response = api_session.get(f"{BASE_URL}/api/projects/{PROJECT_ID}")
        assert response.status_code == 200
        data = response.json()
        
        slides = data["course"]["slides"]
        slide = next((s for s in slides if s.get("id") == SLIDE_ID), None)
        assert slide is not None, f"Slide {SLIDE_ID} not found"
        
        elements = slide.get("elements", [])
        html_element = next((e for e in elements if e.get("id") == ELEMENT_ID), None)
        assert html_element is not None, f"Element {ELEMENT_ID} not found"
        assert html_element.get("type") == "html", f"Element type is {html_element.get('type')}, expected 'html'"
        print(f"✅ Found HTML element with id {ELEMENT_ID}")
        print(f"   Content preview: {str(html_element.get('htmlContent', ''))[:100]}...")


class TestElementUpdate:
    """Critical tests for the RTF element update bug fix"""
    
    def test_update_element_with_html_content(self, api_session):
        """
        CRITICAL TEST: Update element with htmlContent field
        This tests the fix for the bug where editing RTF elements failed
        """
        unique_marker = str(uuid.uuid4())[:8]
        new_html_content = f"<p>Test update content - marker: {unique_marker}</p>"
        
        response = api_session.put(
            f"{BASE_URL}/api/projects/{PROJECT_ID}/slides/{SLIDE_ID}/elements/{ELEMENT_ID}",
            json={"htmlContent": new_html_content}
        )
        
        assert response.status_code == 200, f"Update failed: {response.status_code} - {response.text}"
        data = response.json()
        assert data.get("htmlContent") == new_html_content, "htmlContent not updated"
        print(f"✅ Element updated successfully with htmlContent")
        
        # Verify persistence by fetching project again
        get_response = api_session.get(f"{BASE_URL}/api/projects/{PROJECT_ID}")
        assert get_response.status_code == 200
        
        project_data = get_response.json()
        slides = project_data["course"]["slides"]
        slide = next((s for s in slides if s.get("id") == SLIDE_ID), None)
        element = next((e for e in slide.get("elements", []) if e.get("id") == ELEMENT_ID), None)
        
        assert element is not None, "Element not found after update"
        assert element.get("htmlContent") == new_html_content, "htmlContent did not persist"
        print(f"✅ htmlContent persisted correctly in database")
    
    def test_update_element_preserves_other_fields(self, api_session):
        """Test that updating htmlContent preserves other element fields"""
        # First, get current element state
        get_response = api_session.get(f"{BASE_URL}/api/projects/{PROJECT_ID}")
        assert get_response.status_code == 200
        project_data = get_response.json()
        
        slides = project_data["course"]["slides"]
        slide = next((s for s in slides if s.get("id") == SLIDE_ID), None)
        element_before = next((e for e in slide.get("elements", []) if e.get("id") == ELEMENT_ID), None)
        
        original_x = element_before.get("x")
        original_y = element_before.get("y")
        original_width = element_before.get("width")
        original_height = element_before.get("height")
        
        # Update only htmlContent
        new_content = "<p>Preserving other fields test</p>"
        response = api_session.put(
            f"{BASE_URL}/api/projects/{PROJECT_ID}/slides/{SLIDE_ID}/elements/{ELEMENT_ID}",
            json={"htmlContent": new_content}
        )
        assert response.status_code == 200
        
        # Verify other fields preserved
        updated_element = response.json()
        assert updated_element.get("x") == original_x, "x coordinate changed"
        assert updated_element.get("y") == original_y, "y coordinate changed"
        assert updated_element.get("width") == original_width, "width changed"
        assert updated_element.get("height") == original_height, "height changed"
        print(f"✅ Other element fields preserved after htmlContent update")
    
    def test_update_element_invalid_project(self, api_session):
        """Test error handling for invalid project ID"""
        response = api_session.put(
            f"{BASE_URL}/api/projects/invalid-project-id/slides/{SLIDE_ID}/elements/{ELEMENT_ID}",
            json={"htmlContent": "<p>Test</p>"}
        )
        assert response.status_code == 404
        print(f"✅ Returns 404 for invalid project ID")
    
    def test_update_element_invalid_slide(self, api_session):
        """Test error handling for invalid slide ID"""
        response = api_session.put(
            f"{BASE_URL}/api/projects/{PROJECT_ID}/slides/invalid-slide-id/elements/{ELEMENT_ID}",
            json={"htmlContent": "<p>Test</p>"}
        )
        assert response.status_code == 404
        print(f"✅ Returns 404 for invalid slide ID")
    
    def test_update_element_invalid_element(self, api_session):
        """Test error handling for invalid element ID"""
        response = api_session.put(
            f"{BASE_URL}/api/projects/{PROJECT_ID}/slides/{SLIDE_ID}/elements/invalid-element-id",
            json={"htmlContent": "<p>Test</p>"}
        )
        assert response.status_code == 404
        print(f"✅ Returns 404 for invalid element ID")


class TestAddNewElement:
    """Test adding new HTML elements"""
    
    def test_add_new_html_element(self, api_session):
        """Test creating a new HTML element on a slide"""
        unique_marker = str(uuid.uuid4())[:8]
        new_element = {
            "type": "html",
            "x": 100,
            "y": 100,
            "width": 400,
            "height": 200,
            "htmlContent": f"<p>New element - marker: {unique_marker}</p>"
        }
        
        response = api_session.post(
            f"{BASE_URL}/api/projects/{PROJECT_ID}/slides/{SLIDE_ID}/elements",
            json=new_element
        )
        
        assert response.status_code == 200, f"Create failed: {response.status_code} - {response.text}"
        data = response.json()
        assert "id" in data, "New element should have an ID"
        assert data.get("type") == "html", "Element type should be 'html'"
        assert unique_marker in data.get("htmlContent", ""), "htmlContent not saved correctly"
        
        new_element_id = data["id"]
        print(f"✅ Created new HTML element with ID: {new_element_id}")
        
        # Clean up - delete the test element
        delete_response = api_session.delete(
            f"{BASE_URL}/api/projects/{PROJECT_ID}/slides/{SLIDE_ID}/elements/{new_element_id}"
        )
        assert delete_response.status_code in [200, 204], f"Delete failed: {delete_response.status_code}"
        print(f"✅ Cleaned up test element")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
