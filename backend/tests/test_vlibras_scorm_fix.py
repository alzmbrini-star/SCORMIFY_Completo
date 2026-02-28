"""
Test VLibras SCORM Export Bug Fix
================================
Tests the VLibras API fix (window.plugin.translate instead of sendMessage)
and SCORM export functionality with VLibras accessibility features.
"""

import pytest
import requests
import os
import zipfile
import io
import json
import tempfile

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Project ID provided for testing
PROJECT_ID = "a972eb75-eb3a-486c-91cf-f73c7551aebd"


class TestHealthCheck:
    """Basic health check tests"""
    
    def test_health_endpoint(self):
        """GET /api/health returns healthy"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200, f"Health check failed: {response.status_code}"
        data = response.json()
        assert data.get("status") == "healthy", f"Health status: {data}"
        print(f"[PASS] Health check: {data}")


class TestSCORMExport:
    """Test SCORM export functionality"""
    
    def test_scorm_export_returns_200(self):
        """POST /api/course/{project_id}/export-scorm returns 200 with downloadUrl"""
        response = requests.post(f"{BASE_URL}/api/course/{PROJECT_ID}/export-scorm")
        assert response.status_code == 200, f"SCORM export failed: {response.status_code}, {response.text}"
        data = response.json()
        assert "downloadUrl" in data, f"No downloadUrl in response: {data}"
        print(f"[PASS] SCORM export returned 200 with downloadUrl: {data['downloadUrl']}")
        return data["downloadUrl"]
    
    def test_scorm_export_download(self):
        """Download and verify SCORM package can be opened as ZIP"""
        # First export
        response = requests.post(f"{BASE_URL}/api/course/{PROJECT_ID}/export-scorm")
        assert response.status_code == 200, f"SCORM export failed: {response.status_code}"
        data = response.json()
        download_url = data["downloadUrl"]
        
        # Download the ZIP
        if download_url.startswith('/'):
            download_url = f"{BASE_URL}{download_url}"
        
        download_response = requests.get(download_url)
        assert download_response.status_code == 200, f"Download failed: {download_response.status_code}"
        
        # Verify it's a valid ZIP
        zip_buffer = io.BytesIO(download_response.content)
        with zipfile.ZipFile(zip_buffer, 'r') as zf:
            file_list = zf.namelist()
            assert "index.html" in file_list, f"index.html not found in SCORM package"
            assert "course.json" in file_list, f"course.json not found in SCORM package"
            assert any("player.js" in f for f in file_list), f"player.js not found in SCORM package"
            print(f"[PASS] SCORM ZIP is valid with files: {file_list[:5]}...")
        return zip_buffer
    
    def test_scorm_index_html_contains_vlibras_autoinit(self):
        """Exported SCORM index.html contains VLibras auto-init code"""
        # Export SCORM
        response = requests.post(f"{BASE_URL}/api/course/{PROJECT_ID}/export-scorm")
        assert response.status_code == 200
        download_url = response.json()["downloadUrl"]
        
        # Download
        if download_url.startswith('/'):
            download_url = f"{BASE_URL}{download_url}"
        download_response = requests.get(download_url)
        assert download_response.status_code == 200
        
        # Check index.html content
        zip_buffer = io.BytesIO(download_response.content)
        with zipfile.ZipFile(zip_buffer, 'r') as zf:
            index_html = zf.read("index.html").decode('utf-8')
            
            # Check for VLibras auto-init code
            assert "vlibras-plugin.js" in index_html, "vlibras-plugin.js script not found in index.html"
            assert "Auto-initialize" in index_html or "accessBtn.click()" in index_html, \
                "Auto-init code not found in index.html"
            print("[PASS] index.html contains VLibras auto-init code")
    
    def test_scorm_player_js_uses_correct_api(self):
        """Exported SCORM player.js contains correct API (plugin.translate) and NOT sendMessage"""
        # Export SCORM
        response = requests.post(f"{BASE_URL}/api/course/{PROJECT_ID}/export-scorm")
        assert response.status_code == 200
        download_url = response.json()["downloadUrl"]
        
        # Download
        if download_url.startswith('/'):
            download_url = f"{BASE_URL}{download_url}"
        download_response = requests.get(download_url)
        assert download_response.status_code == 200
        
        # Check player.js content
        zip_buffer = io.BytesIO(download_response.content)
        with zipfile.ZipFile(zip_buffer, 'r') as zf:
            # Find player.js (might be in scripts/ folder)
            player_js_path = None
            for name in zf.namelist():
                if name.endswith("player.js"):
                    player_js_path = name
                    break
            
            assert player_js_path is not None, "player.js not found in SCORM package"
            player_js = zf.read(player_js_path).decode('utf-8')
            
            # Verify correct API is used
            assert "plugin.translate" in player_js, "plugin.translate not found in player.js"
            assert "translateWithVLibras" in player_js, "translateWithVLibras function not found in player.js"
            
            # Verify broken API is NOT used
            assert "sendMessage" not in player_js, "BROKEN API 'sendMessage' still present in player.js!"
            
            print("[PASS] player.js uses correct VLibras API (plugin.translate)")
    
    def test_scorm_course_json_contains_librasscript(self):
        """Exported SCORM course.json contains librasScript data on slide 0"""
        # Export SCORM
        response = requests.post(f"{BASE_URL}/api/course/{PROJECT_ID}/export-scorm")
        assert response.status_code == 200
        download_url = response.json()["downloadUrl"]
        
        # Download
        if download_url.startswith('/'):
            download_url = f"{BASE_URL}{download_url}"
        download_response = requests.get(download_url)
        assert download_response.status_code == 200
        
        # Check course.json content
        zip_buffer = io.BytesIO(download_response.content)
        with zipfile.ZipFile(zip_buffer, 'r') as zf:
            course_json_data = zf.read("course.json").decode('utf-8')
            course_data = json.loads(course_json_data)
            
            # Check that slides exist
            assert "slides" in course_data, "No slides in course.json"
            assert len(course_data["slides"]) > 0, "No slides found"
            
            # Check first slide has librasScript
            first_slide = course_data["slides"][0]
            libras_script = first_slide.get("librasScript", "")
            assert libras_script, f"librasScript is empty or missing on slide 0: {first_slide.keys()}"
            
            print(f"[PASS] course.json slide 0 has librasScript: {libras_script[:50]}...")


class TestLibrasScriptField:
    """Test librasScript field save/load functionality"""
    
    def test_get_project_slides(self):
        """GET /api/course/{project_id} returns slides with librasScript"""
        response = requests.get(f"{BASE_URL}/api/course/{PROJECT_ID}")
        assert response.status_code == 200, f"Failed to get course: {response.status_code}"
        data = response.json()
        
        assert "slides" in data, "No slides in response"
        assert len(data["slides"]) > 0, "No slides found"
        
        # Get first slide ID for next test
        first_slide = data["slides"][0]
        slide_id = first_slide.get("id")
        libras_script = first_slide.get("librasScript", "")
        
        print(f"[PASS] Got {len(data['slides'])} slides. First slide ID: {slide_id}")
        print(f"  librasScript on slide 0: {libras_script[:50] if libras_script else '(empty)'}...")
        return slide_id
    
    def test_update_librasscript_field(self):
        """PUT /api/projects/{project_id}/slides/{slide_id} with librasScript saves correctly"""
        # First get the slide ID
        response = requests.get(f"{BASE_URL}/api/course/{PROJECT_ID}")
        assert response.status_code == 200
        first_slide_id = response.json()["slides"][0]["id"]
        
        # Update with a test librasScript value
        test_script = "Teste de script LIBRAS - Olá mundo!"
        update_response = requests.put(
            f"{BASE_URL}/api/projects/{PROJECT_ID}/slides/{first_slide_id}",
            json={"librasScript": test_script}
        )
        assert update_response.status_code == 200, f"Update failed: {update_response.status_code}, {update_response.text}"
        
        updated_data = update_response.json()
        assert updated_data.get("librasScript") == test_script, \
            f"librasScript mismatch. Got: {updated_data.get('librasScript')}"
        
        # Verify persistence by re-fetching
        verify_response = requests.get(f"{BASE_URL}/api/course/{PROJECT_ID}")
        assert verify_response.status_code == 200
        verify_slide = verify_response.json()["slides"][0]
        assert verify_slide.get("librasScript") == test_script, \
            f"librasScript not persisted. Got: {verify_slide.get('librasScript')}"
        
        print(f"[PASS] librasScript field saved and persisted: {test_script}")


class TestEnableVlibrasToggle:
    """Test enableVlibras project setting"""
    
    def test_disable_vlibras_removes_from_export(self):
        """PUT /api/projects/{project_id} with enableVlibras=false removes VLibras from export"""
        # First disable VLibras
        update_response = requests.put(
            f"{BASE_URL}/api/projects/{PROJECT_ID}",
            json={"enableVlibras": False}
        )
        assert update_response.status_code == 200, f"Update failed: {update_response.status_code}"
        
        # Export SCORM
        export_response = requests.post(f"{BASE_URL}/api/course/{PROJECT_ID}/export-scorm")
        assert export_response.status_code == 200
        download_url = export_response.json()["downloadUrl"]
        
        # Download
        if download_url.startswith('/'):
            download_url = f"{BASE_URL}{download_url}"
        download_response = requests.get(download_url)
        assert download_response.status_code == 200
        
        # Check index.html does NOT contain vlibras-plugin.js
        zip_buffer = io.BytesIO(download_response.content)
        with zipfile.ZipFile(zip_buffer, 'r') as zf:
            index_html = zf.read("index.html").decode('utf-8')
            
            # Should NOT contain VLibras when disabled
            assert "vlibras-plugin.js" not in index_html, \
                "vlibras-plugin.js SHOULD NOT be in index.html when enableVlibras=false"
            print("[PASS] VLibras correctly excluded from export when enableVlibras=false")
    
    def test_reenable_vlibras(self):
        """PUT /api/projects/{project_id} with enableVlibras=true re-enables VLibras"""
        # Re-enable VLibras
        update_response = requests.put(
            f"{BASE_URL}/api/projects/{PROJECT_ID}",
            json={"enableVlibras": True}
        )
        assert update_response.status_code == 200, f"Update failed: {update_response.status_code}"
        
        # Export SCORM
        export_response = requests.post(f"{BASE_URL}/api/course/{PROJECT_ID}/export-scorm")
        assert export_response.status_code == 200
        download_url = export_response.json()["downloadUrl"]
        
        # Download
        if download_url.startswith('/'):
            download_url = f"{BASE_URL}{download_url}"
        download_response = requests.get(download_url)
        assert download_response.status_code == 200
        
        # Check index.html DOES contain vlibras-plugin.js
        zip_buffer = io.BytesIO(download_response.content)
        with zipfile.ZipFile(zip_buffer, 'r') as zf:
            index_html = zf.read("index.html").decode('utf-8')
            
            # Should contain VLibras when enabled
            assert "vlibras-plugin.js" in index_html, \
                "vlibras-plugin.js SHOULD be in index.html when enableVlibras=true"
            print("[PASS] VLibras correctly included in export when enableVlibras=true")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
