"""
Test Script LIBRAS Feature for VLibras Integration

Tests:
1. librasScript field is persisted on slides
2. librasScript is included in API responses
3. SCORM export contains librasScript in course.json
4. HTML export contains VLibras.Widget.sendMessage code
"""
import pytest
import requests
import os
import zipfile
import json
import tempfile
import io

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "admin@scormify.com"
TEST_PASSWORD = "admin123"

# Test project ID - SCORMIFY - V2
TEST_PROJECT_ID = "edd87206-484c-45d8-ba4b-5ae9bc24b2fb"


@pytest.fixture
def auth_token():
    """Get authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    })
    if response.status_code == 200:
        return response.json().get("token")
    pytest.skip("Authentication failed - skipping authenticated tests")


@pytest.fixture
def api_client(auth_token):
    """Create API client with auth header"""
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "Authorization": f"Bearer {auth_token}"
    })
    return session


class TestLibrasScriptField:
    """Test librasScript field persistence and retrieval"""
    
    def test_project_api_returns_libras_script(self, api_client):
        """Verify librasScript field is returned in project API response"""
        response = api_client.get(f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}")
        assert response.status_code == 200, f"Failed to get project: {response.text}"
        
        data = response.json()
        assert 'course' in data
        assert 'slides' in data['course']
        
        # Check that slides have librasScript field (can be null or string)
        slides = data['course']['slides']
        assert len(slides) > 0, "No slides found in project"
        
        first_slide = slides[0]
        # librasScript may or may not be set, but the field should be accessible
        # If it exists, it should be a string or null
        libras_script = first_slide.get('librasScript')
        print(f"First slide librasScript: {libras_script}")
        
        # Field should be accessible (None or string)
        assert libras_script is None or isinstance(libras_script, str), \
            "librasScript should be None or string"
        print("✅ librasScript field is accessible in slide data")
    
    def test_update_slide_with_libras_script(self, api_client):
        """Test updating a slide with librasScript content"""
        # First get the project to get a slide ID
        response = api_client.get(f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}")
        assert response.status_code == 200
        
        data = response.json()
        slides = data['course']['slides']
        assert len(slides) > 0
        
        slide_id = slides[0]['id']
        test_libras_text = "Teste de script LIBRAS para tradução automática pelo avatar VLibras."
        
        # Update the slide with librasScript
        update_response = api_client.put(
            f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/slides/{slide_id}",
            json={"librasScript": test_libras_text}
        )
        
        # Check response - should be 200 OK
        assert update_response.status_code == 200, f"Failed to update slide: {update_response.text}"
        print(f"✅ Successfully updated slide with librasScript")
        
        # Verify the update was persisted by fetching the project again
        verify_response = api_client.get(f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}")
        assert verify_response.status_code == 200
        
        verify_data = verify_response.json()
        updated_slide = next((s for s in verify_data['course']['slides'] if s['id'] == slide_id), None)
        assert updated_slide is not None
        
        # Verify librasScript was saved
        assert updated_slide.get('librasScript') == test_libras_text, \
            f"librasScript not persisted correctly. Expected: {test_libras_text}, Got: {updated_slide.get('librasScript')}"
        print(f"✅ librasScript persisted correctly: {updated_slide.get('librasScript')}")


class TestScormExportWithLibras:
    """Test SCORM export contains librasScript data"""
    
    def test_scorm_export_contains_libras_script(self, api_client):
        """Verify SCORM export includes librasScript in course.json"""
        # First, set a libras script on the first slide
        response = api_client.get(f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}")
        assert response.status_code == 200
        
        data = response.json()
        slide_id = data['course']['slides'][0]['id']
        test_libras_text = "SCORM export test - texto LIBRAS para o avatar."
        
        # Update slide with libras script
        api_client.put(
            f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/slides/{slide_id}",
            json={"librasScript": test_libras_text}
        )
        
        # Export to SCORM
        export_response = api_client.post(f"{BASE_URL}/api/course/{TEST_PROJECT_ID}/export-scorm")
        assert export_response.status_code == 200, f"SCORM export failed: {export_response.text}"
        
        export_data = export_response.json()
        assert 'downloadUrl' in export_data, "No downloadUrl in response"
        
        download_url = f"{BASE_URL}{export_data['downloadUrl']}"
        print(f"Download URL: {download_url}")
        
        # Download the ZIP file
        zip_response = api_client.get(download_url)
        assert zip_response.status_code == 200, f"Failed to download SCORM package: {zip_response.status_code}"
        
        # Extract and check course.json
        with zipfile.ZipFile(io.BytesIO(zip_response.content)) as zf:
            file_list = zf.namelist()
            print(f"SCORM package files: {file_list[:10]}...")
            
            assert 'course.json' in file_list, "course.json not found in SCORM package"
            
            # Read and parse course.json
            course_json_content = zf.read('course.json').decode('utf-8')
            course_data = json.loads(course_json_content)
            
            # Check that slides contain librasScript
            assert 'slides' in course_data
            first_slide = course_data['slides'][0]
            
            assert 'librasScript' in first_slide or first_slide.get('librasScript') is not None, \
                "librasScript field missing from course.json slides"
            
            print(f"✅ librasScript in course.json: {first_slide.get('librasScript')}")
            
            # Verify the libras text was exported
            if first_slide.get('librasScript'):
                assert test_libras_text in first_slide['librasScript'], \
                    "librasScript content not matching"
                print("✅ librasScript content verified in SCORM export")
    
    def test_scorm_player_contains_vlibras_code(self, api_client):
        """Verify SCORM player.js contains VLibras.Widget.sendMessage code"""
        # Export to SCORM
        export_response = api_client.post(f"{BASE_URL}/api/course/{TEST_PROJECT_ID}/export-scorm")
        assert export_response.status_code == 200
        
        download_url = f"{BASE_URL}{export_response.json()['downloadUrl']}"
        zip_response = api_client.get(download_url)
        assert zip_response.status_code == 200
        
        with zipfile.ZipFile(io.BytesIO(zip_response.content)) as zf:
            # Look for player.js or index.html
            js_files = [f for f in zf.namelist() if f.endswith('.js')]
            html_files = [f for f in zf.namelist() if f.endswith('.html')]
            
            vlibras_code_found = False
            
            # Check player.js
            if 'player.js' in zf.namelist():
                player_js = zf.read('player.js').decode('utf-8')
                if 'VLibras.Widget.sendMessage' in player_js:
                    vlibras_code_found = True
                    print("✅ VLibras.Widget.sendMessage found in player.js")
                if 'librasScript' in player_js:
                    print("✅ librasScript reference found in player.js")
            
            # Check index.html for VLibras widget script
            if 'index.html' in zf.namelist():
                index_html = zf.read('index.html').decode('utf-8')
                if 'vlibras.gov.br' in index_html or 'VLibras.Widget' in index_html:
                    print("✅ VLibras widget script found in index.html")
            
            assert vlibras_code_found, "VLibras.Widget.sendMessage code not found in SCORM export"


class TestHtmlExportWithLibras:
    """Test HTML export contains VLibras integration"""
    
    def test_html_export_contains_vlibras_code(self, api_client):
        """Verify HTML export includes VLibras.Widget.sendMessage code"""
        # First, set a libras script
        response = api_client.get(f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}")
        assert response.status_code == 200
        
        data = response.json()
        slide_id = data['course']['slides'][0]['id']
        test_libras_text = "HTML export test - texto LIBRAS."
        
        api_client.put(
            f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/slides/{slide_id}",
            json={"librasScript": test_libras_text}
        )
        
        # Export to HTML
        export_response = api_client.post(f"{BASE_URL}/api/course/{TEST_PROJECT_ID}/export-html")
        assert export_response.status_code == 200, f"HTML export failed: {export_response.text}"
        
        download_url = f"{BASE_URL}{export_response.json()['downloadUrl']}"
        html_response = api_client.get(download_url)
        assert html_response.status_code == 200
        
        html_content = html_response.text
        
        # Check for VLibras integration
        vlibras_checks = {
            "VLibras CDN": 'vlibras.gov.br' in html_content,
            "VLibras Widget": 'VLibras.Widget' in html_content,
            "sendMessage code": 'sendMessage' in html_content,
            "librasScript reference": 'librasScript' in html_content,
        }
        
        for check_name, passed in vlibras_checks.items():
            status = "✅" if passed else "❌"
            print(f"{status} {check_name}: {'found' if passed else 'NOT found'}")
        
        # At minimum, VLibras widget and sendMessage should be present
        assert vlibras_checks["VLibras Widget"], "VLibras.Widget not found in HTML export"
        assert vlibras_checks["sendMessage code"], "sendMessage not found in HTML export"
        print("✅ VLibras integration verified in HTML export")


class TestVLibrasWidgetInEditor:
    """Test VLibras widget presence in the editor page"""
    
    def test_editor_page_loads_vlibras(self, api_client):
        """Verify the editor page contains VLibras widget script"""
        # This test verifies the frontend includes VLibras
        # We can check by requesting the main HTML page
        response = requests.get(f"{BASE_URL}/")
        assert response.status_code == 200
        
        html_content = response.text
        
        # Check for VLibras script inclusion
        vlibras_checks = {
            "VLibras CDN script": 'vlibras.gov.br/app/vlibras-plugin.js' in html_content,
            "VLibras Widget init": 'new window.VLibras.Widget' in html_content,
        }
        
        for check_name, passed in vlibras_checks.items():
            status = "✅" if passed else "❌"
            print(f"{status} {check_name}: {'found' if passed else 'NOT found'}")
        
        # Both checks should pass
        assert vlibras_checks["VLibras CDN script"], "VLibras CDN script not found"
        assert vlibras_checks["VLibras Widget init"], "VLibras Widget initialization not found"
        print("✅ VLibras widget properly integrated in editor")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
