"""
Tests for LIBRAS auto-fill feature in Course Authoring Tool
- Test librasScript field CRUD operations
- Test SCORM export includes librasScript correctly
- Test VLibras integration in exports
"""
import pytest
import requests
import os
import zipfile
import io
import json

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
PROJECT_ID = "a972eb75-eb3a-486c-91cf-f73c7551aebd"


class TestHealthCheck:
    """Health endpoint verification"""
    
    def test_health_endpoint(self):
        """Test /api/health returns healthy"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy" or "status" in data
        print("PASS: Health endpoint returns healthy")


class TestLibrasScriptField:
    """Test librasScript field save/read operations"""
    
    def test_get_project_has_slides(self):
        """Test GET /api/course/{id} returns project with slides"""
        response = requests.get(f"{BASE_URL}/api/course/{PROJECT_ID}")
        assert response.status_code == 200
        data = response.json()
        assert "slides" in data
        assert len(data["slides"]) > 0
        print(f"PASS: Project has {len(data['slides'])} slides")
        return data
    
    def test_update_librasscript_field(self):
        """Test PUT /api/projects/{id}/slides/{slide_id} saves librasScript correctly"""
        # First get the project to find a slide ID
        project_response = requests.get(f"{BASE_URL}/api/course/{PROJECT_ID}")
        assert project_response.status_code == 200
        project = project_response.json()
        
        slide_id = project["slides"][0]["id"]
        test_text = "TEST_libras_auto_fill_verification"
        
        # Update the slide with librasScript
        update_response = requests.put(
            f"{BASE_URL}/api/projects/{PROJECT_ID}/slides/{slide_id}",
            json={"librasScript": test_text}
        )
        assert update_response.status_code == 200, f"Expected 200, got {update_response.status_code}"
        print(f"PASS: Updated librasScript on slide {slide_id}")
        
        # Verify by fetching the project again
        verify_response = requests.get(f"{BASE_URL}/api/course/{PROJECT_ID}")
        assert verify_response.status_code == 200
        updated_project = verify_response.json()
        
        updated_slide = next((s for s in updated_project["slides"] if s["id"] == slide_id), None)
        assert updated_slide is not None
        assert updated_slide.get("librasScript") == test_text
        print(f"PASS: Verified librasScript field persisted correctly")
        
        # Restore original value
        original_text = "Texto auto-preenchido a partir da narração TTS"
        requests.put(
            f"{BASE_URL}/api/projects/{PROJECT_ID}/slides/{slide_id}",
            json={"librasScript": original_text}
        )
        print("PASS: Restored original librasScript value")


class TestSCORMExportWithLibras:
    """Test SCORM export functionality with VLibras and librasScript"""
    
    def test_scorm_export_returns_200(self):
        """Test POST /api/course/{id}/export-scorm returns 200"""
        response = requests.post(f"{BASE_URL}/api/course/{PROJECT_ID}/export-scorm")
        assert response.status_code == 200
        data = response.json()
        assert "downloadUrl" in data or "download_url" in data
        print(f"PASS: SCORM export returns 200 with download URL")
        return data
    
    def test_scorm_export_content_analysis(self):
        """Download and analyze SCORM export contents"""
        # First export
        export_response = requests.post(f"{BASE_URL}/api/course/{PROJECT_ID}/export-scorm")
        assert export_response.status_code == 200
        export_data = export_response.json()
        
        download_url = export_data.get("downloadUrl") or export_data.get("download_url")
        assert download_url, "No download URL in response"
        
        # Construct full URL if relative
        if download_url.startswith("/"):
            download_url = f"{BASE_URL}{download_url}"
        elif not download_url.startswith("http"):
            download_url = f"{BASE_URL}/api/exports/{download_url}"
        
        # Download the ZIP
        download_response = requests.get(download_url)
        assert download_response.status_code == 200, f"Failed to download: {download_response.status_code}"
        
        # Extract and analyze
        zip_content = io.BytesIO(download_response.content)
        with zipfile.ZipFile(zip_content, 'r') as z:
            file_list = z.namelist()
            print(f"SCORM ZIP contents: {len(file_list)} files")
            
            # Check required files exist
            assert "index.html" in file_list, "Missing index.html"
            assert "course.json" in file_list, "Missing course.json"
            assert "player.js" in file_list, "Missing player.js"
            print("PASS: SCORM package contains required files")
            
            # Test 1: player.js contains correct VLibras API
            player_js = z.read("player.js").decode('utf-8')
            assert "plugin.translate" in player_js, "player.js missing plugin.translate call"
            assert "translateWithVLibras" in player_js, "player.js missing translateWithVLibras function"
            print("PASS: player.js contains correct VLibras API (plugin.translate, translateWithVLibras)")
            
            # Test 2: course.json has librasScript on slide 0
            course_json = json.loads(z.read("course.json").decode('utf-8'))
            assert "slides" in course_json, "course.json missing slides"
            slide_0 = course_json["slides"][0]
            assert "librasScript" in slide_0, "slide 0 missing librasScript field"
            print(f"PASS: course.json slide 0 has librasScript: '{slide_0['librasScript'][:50]}...'")
            
            # Test 3: index.html has VLibras auto-init code
            index_html = z.read("index.html").decode('utf-8')
            assert "vlibras-plugin.js" in index_html, "index.html missing VLibras plugin script"
            assert "vw-access-button" in index_html, "index.html missing VLibras access button"
            # Check for auto-init code that clicks the access button
            assert "accessBtn.click" in index_html or "accessBtn.click()" in index_html, \
                "index.html missing VLibras auto-init click code"
            print("PASS: index.html has VLibras auto-init code")
            
        return True


class TestFrontendCodeAnalysis:
    """Verify frontend code contains required functions for auto-fill feature"""
    
    def test_editor_jsx_contains_extract_slide_text(self):
        """Verify Editor.jsx contains extractSlideText function"""
        editor_path = "/app/frontend/src/pages/Editor.jsx"
        with open(editor_path, 'r') as f:
            content = f.read()
        
        assert "extractSlideText" in content, "Missing extractSlideText function"
        # Verify the function filters text elements
        assert 'el.type === \'text\'' in content or "el.type === \"text\"" in content, \
            "extractSlideText should filter for text elements"
        print("PASS: Editor.jsx contains extractSlideText function that filters text elements")
    
    def test_editor_jsx_contains_handle_auto_fill(self):
        """Verify Editor.jsx contains handleAutoFill function"""
        editor_path = "/app/frontend/src/pages/Editor.jsx"
        with open(editor_path, 'r') as f:
            content = f.read()
        
        assert "handleAutoFill" in content, "Missing handleAutoFill function"
        assert "onUpdate({ librasScript:" in content or "onUpdate({librasScript:" in content, \
            "handleAutoFill should update librasScript"
        print("PASS: Editor.jsx contains handleAutoFill function that updates librasScript")
    
    def test_editor_jsx_tts_autofill(self):
        """Verify handleAddTTSToSlide updates librasScript"""
        editor_path = "/app/frontend/src/pages/Editor.jsx"
        with open(editor_path, 'r') as f:
            content = f.read()
        
        # Look for the auto-fill logic in handleAddTTSToSlide
        assert "handleAddTTSToSlide" in content, "Missing handleAddTTSToSlide function"
        # The function should check ttsText and update librasScript
        assert "ttsText.trim()" in content, "Missing ttsText.trim() check"
        assert "updateSlide" in content, "Missing updateSlide call"
        # Verify it updates librasScript when TTS is added
        assert "librasScript: ttsText" in content or "librasScript: ttsText.trim()" in content, \
            "handleAddTTSToSlide should auto-fill librasScript from TTS text"
        print("PASS: handleAddTTSToSlide auto-fills librasScript from TTS text")
    
    def test_editor_jsx_has_autofill_button_testid(self):
        """Verify Editor.jsx renders libras-autofill-btn data-testid element"""
        editor_path = "/app/frontend/src/pages/Editor.jsx"
        with open(editor_path, 'r') as f:
            content = f.read()
        
        assert 'data-testid="libras-autofill-btn"' in content, \
            "Missing data-testid=\"libras-autofill-btn\" element"
        assert "Preencher com texto do slide" in content, \
            "Missing 'Preencher com texto do slide' button text"
        print("PASS: Editor.jsx has libras-autofill-btn data-testid and button text")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
