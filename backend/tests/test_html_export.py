"""
Test HTML Export Functionality
Tests the HTML export endpoint and verifies the exported HTML renders correctly
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestHTMLExport:
    """Test cases for HTML export functionality"""
    
    def test_api_health(self):
        """Test API health check"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        print("✅ API health check passed")
    
    def test_get_projects_list(self):
        """Get list of projects"""
        response = requests.get(f"{BASE_URL}/api/projects")
        assert response.status_code == 200
        projects = response.json()
        assert isinstance(projects, list)
        print(f"✅ Found {len(projects)} projects")
        return projects
    
    def test_serve_html_export(self):
        """Test serving an existing HTML export file"""
        # Test with the known export file
        filename = "SCORMIFY_20260204_202429.html"
        response = requests.get(f"{BASE_URL}/api/exports/{filename}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        # Check content type is HTML
        content_type = response.headers.get('content-type', '')
        assert 'text/html' in content_type, f"Expected text/html, got {content_type}"
        
        # Check content has expected HTML elements
        content = response.text
        assert '<!DOCTYPE html>' in content
        assert '<title>' in content
        assert '#player-container' in content
        assert '#header' in content
        assert '#controls' in content
        
        print(f"✅ HTML export served correctly ({len(content)} bytes)")
        print(f"   Content-Type: {content_type}")
    
    def test_html_export_has_desktop_css_fix(self):
        """Verify the CSS media query fix for desktop is in place"""
        filename = "SCORMIFY_20260204_202429.html"
        response = requests.get(f"{BASE_URL}/api/exports/{filename}")
        
        assert response.status_code == 200
        content = response.text
        
        # Check that the new restrictive media query is present
        # The fix adds max-height: 450px to target only mobile devices
        assert 'max-height: 450px' in content or 'max-height:450px' in content, \
            "CSS fix for mobile landscape detection not found (max-height: 450px)"
        
        # Check that pointer: coarse media query is present for touch detection
        assert 'pointer: coarse' in content or 'pointer:coarse' in content, \
            "CSS fix for touch device detection not found (pointer: coarse)"
        
        print("✅ CSS media query fix verified - desktop won't be affected by mobile landscape styles")
    
    def test_html_export_has_required_elements(self):
        """Verify HTML export has all required player elements"""
        filename = "SCORMIFY_20260204_202429.html"
        response = requests.get(f"{BASE_URL}/api/exports/{filename}")
        
        assert response.status_code == 200
        content = response.text
        
        # Required elements for the player
        required_elements = [
            'id="player-container"',
            'id="header"',
            'id="controls"',
            'id="slide-container"',
            'id="slide-wrapper"',
            'id="progress-dots"',
            'id="prev-btn"',
            'id="next-btn"',
            'id="progress-info"',
            'id="mobile-float-controls"',
        ]
        
        for element in required_elements:
            assert element in content, f"Missing required element: {element}"
        
        print("✅ All required HTML elements present")
    
    def test_html_export_has_navigation_labels(self):
        """Verify navigation buttons have correct Portuguese labels"""
        filename = "SCORMIFY_20260204_202429.html"
        response = requests.get(f"{BASE_URL}/api/exports/{filename}")
        
        assert response.status_code == 200
        content = response.text
        
        # Navigation labels
        assert 'Anterior' in content, "Missing 'Anterior' (Previous) button label"
        assert 'Próximo' in content or 'Proximo' in content, "Missing 'Próximo' (Next) button label"
        
        print("✅ Navigation labels in Portuguese verified")
    
    def test_html_export_has_audio_overlay(self):
        """Verify audio overlay functionality exists"""
        filename = "SCORMIFY_20260204_202429.html"
        response = requests.get(f"{BASE_URL}/api/exports/{filename}")
        
        assert response.status_code == 200
        content = response.text
        
        # Audio overlay elements
        assert 'showStartOverlay' in content or 'start-overlay' in content, \
            "Missing audio start overlay functionality"
        assert 'startCourse' in content or 'hideStartOverlay' in content, \
            "Missing start course function"
        
        print("✅ Audio overlay functionality present")
    
    def test_html_export_not_found(self):
        """Test 404 response for non-existent export file"""
        response = requests.get(f"{BASE_URL}/api/exports/nonexistent_file.html")
        assert response.status_code == 404
        print("✅ 404 returned for non-existent file")
    
    def test_export_zip_file_content_type(self):
        """Test that ZIP exports return correct content type"""
        # List files in exports
        # First get a known ZIP file
        response = requests.get(f"{BASE_URL}/api/projects")
        assert response.status_code == 200
        projects = response.json()
        
        if projects:
            # Try to export SCORM for the first project
            project_id = projects[0].get('id')
            if project_id:
                export_response = requests.post(f"{BASE_URL}/api/course/{project_id}/export-scorm")
                
                if export_response.status_code == 200:
                    data = export_response.json()
                    download_url = data.get('downloadUrl')
                    if download_url:
                        # Verify the ZIP file
                        zip_response = requests.get(f"{BASE_URL}{download_url}")
                        content_type = zip_response.headers.get('content-type', '')
                        assert 'application/zip' in content_type or 'application/octet-stream' in content_type
                        print(f"✅ SCORM ZIP export content type: {content_type}")


class TestHTMLExportGeneration:
    """Test HTML export generation for projects"""
    
    def test_export_html_for_project(self):
        """Test generating HTML export for a project"""
        # Get projects
        response = requests.get(f"{BASE_URL}/api/projects")
        assert response.status_code == 200
        projects = response.json()
        
        if not projects:
            pytest.skip("No projects available for testing")
        
        # Use first project
        project_id = projects[0].get('id')
        
        # Generate HTML export
        export_response = requests.post(f"{BASE_URL}/api/course/{project_id}/export-html")
        assert export_response.status_code == 200
        
        data = export_response.json()
        assert 'downloadUrl' in data
        assert 'filename' in data
        assert data['filename'].endswith('.html')
        
        print(f"✅ HTML export generated: {data['filename']}")
        
        # Verify the generated file is accessible
        download_url = data['downloadUrl']
        file_response = requests.get(f"{BASE_URL}{download_url}")
        assert file_response.status_code == 200
        
        content_type = file_response.headers.get('content-type', '')
        assert 'text/html' in content_type
        
        print(f"✅ Generated HTML export accessible at {download_url}")
    
    def test_export_html_nonexistent_project(self):
        """Test HTML export for non-existent project returns 404"""
        response = requests.post(f"{BASE_URL}/api/course/nonexistent-id/export-html")
        assert response.status_code == 404
        print("✅ 404 returned for non-existent project")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
