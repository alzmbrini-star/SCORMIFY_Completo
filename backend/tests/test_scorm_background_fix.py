"""
Test SCORM/HTML Export Background Image Fix

Bug: When exporting to SCORM, the background image of slides is lost.
Root cause: '*{background:transparent!important}' CSS rule in player.js (line 1325) 
and html_exporter.py (line 2017) was overriding ALL inline CSS backgrounds.

Fix: Changed the wildcard rule to only target html,body for transparency.
The wildcard now only has 'box-sizing:border-box!important;max-width:100%!important;'
"""
import pytest
import requests
import os
import zipfile
import io
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@scormify.com"
ADMIN_PASSWORD = "admin123"

# Course ID with background images (from bug report)
TEST_COURSE_ID = "860e245f-0ad1-4909-a30e-b220a421b75d"


class TestSCORMBackgroundFix:
    """Tests for SCORM export background image fix"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session with authentication"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login to get auth token
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        
        if login_response.status_code == 200:
            data = login_response.json()
            token = data.get("token") or data.get("access_token")
            if token:
                self.session.headers.update({"Authorization": f"Bearer {token}"})
                print(f"✓ Logged in as {ADMIN_EMAIL}")
        else:
            print(f"⚠ Login failed: {login_response.status_code}")
    
    def test_player_js_no_wildcard_background_transparent(self):
        """Verify player.js does NOT contain '*{background:transparent!important}'"""
        player_js_path = "/app/backend/services/export_assets/player.js"
        
        with open(player_js_path, 'r') as f:
            content = f.read()
        
        # The bug was: '*{background:transparent!important}'
        # This should NOT be present anymore
        assert '*{background:transparent!important}' not in content, \
            "player.js still contains the problematic '*{background:transparent!important}' rule"
        
        # The fix should have: '*{box-sizing:border-box!important'
        assert '*{box-sizing:border-box!important' in content, \
            "player.js should have '*{box-sizing:border-box!important' instead"
        
        # body{...background:transparent!important} should still exist (for body only)
        assert 'body{' in content and 'background:transparent!important' in content, \
            "body element should still have background:transparent"
        
        print("✓ player.js CSS fix verified - no wildcard background:transparent")
    
    def test_html_exporter_no_wildcard_background_transparent(self):
        """Verify html_exporter.py does NOT contain '*{background:transparent!important}'"""
        html_exporter_path = "/app/backend/services/html_exporter.py"
        
        with open(html_exporter_path, 'r') as f:
            content = f.read()
        
        # The bug was: '*{background:transparent!important}'
        # This should NOT be present anymore (note: Python uses {{ for literal braces in f-strings)
        assert '*{{background:transparent!important}}' not in content, \
            "html_exporter.py still contains the problematic '*{background:transparent!important}' rule"
        
        # The fix should have: '*{{box-sizing:border-box!important'
        assert '*{{box-sizing:border-box!important' in content, \
            "html_exporter.py should have '*{box-sizing:border-box!important' instead"
        
        print("✓ html_exporter.py CSS fix verified - no wildcard background:transparent")
    
    def test_table_styles_still_work(self):
        """Verify table styles (th, td) are still present in player.js"""
        player_js_path = "/app/backend/services/export_assets/player.js"
        
        with open(player_js_path, 'r') as f:
            content = f.read()
        
        # Table styles should still be present
        assert 'th{' in content, "Table header (th) styles should be present"
        assert 'td{' in content, "Table cell (td) styles should be present"
        assert 'table{' in content, "Table styles should be present"
        
        print("✓ Table styles (th, td, table) are present in player.js")
    
    def test_scorm_export_endpoint_returns_zip(self):
        """Test SCORM export endpoint returns a valid ZIP file"""
        # First, get list of projects to find a valid project ID
        projects_response = self.session.get(f"{BASE_URL}/api/projects")
        
        if projects_response.status_code != 200:
            pytest.skip(f"Could not get projects list: {projects_response.status_code}")
        
        projects = projects_response.json()
        if not projects:
            pytest.skip("No projects available for testing")
        
        # Use first available project
        project_id = projects[0].get('id')
        print(f"Testing SCORM export with project: {project_id}")
        
        # Request SCORM export (POST endpoint, may take 10-30 seconds)
        export_response = self.session.post(
            f"{BASE_URL}/api/course/{project_id}/export-scorm",
            timeout=90
        )
        
        assert export_response.status_code == 200, \
            f"SCORM export failed with status {export_response.status_code}: {export_response.text[:200]}"
        
        # The endpoint returns JSON with jobId and downloadUrl
        export_data = export_response.json()
        download_url = export_data.get('downloadUrl')
        
        assert download_url, f"No downloadUrl in response: {export_data}"
        print(f"  Download URL: {download_url}")
        
        # Download the actual ZIP file
        if download_url.startswith('/'):
            download_url = f"{BASE_URL}{download_url}"
        
        zip_response = self.session.get(download_url, timeout=60)
        
        assert zip_response.status_code == 200, \
            f"ZIP download failed with status {zip_response.status_code}"
        
        # Verify it's a ZIP file
        content_type = zip_response.headers.get('content-type', '')
        assert 'zip' in content_type.lower() or 'octet-stream' in content_type.lower(), \
            f"Expected ZIP content type, got: {content_type}"
        
        # Verify ZIP is valid and contains expected files
        zip_buffer = io.BytesIO(zip_response.content)
        with zipfile.ZipFile(zip_buffer, 'r') as zf:
            file_list = zf.namelist()
            
            # Check for required SCORM files
            assert 'imsmanifest.xml' in file_list, "Missing imsmanifest.xml"
            assert 'index.html' in file_list, "Missing index.html"
            assert 'course.json' in file_list, "Missing course.json"
            
            # Check for player.js in scripts folder
            player_js_found = any('player.js' in f for f in file_list)
            assert player_js_found, "Missing scripts/player.js"
            
            print(f"✓ SCORM export successful - ZIP contains {len(file_list)} files")
            print(f"  Files: {', '.join(file_list[:10])}...")
    
    def test_scorm_export_player_js_content(self):
        """Test that the player.js in SCORM export has the CSS fix"""
        # Get list of projects
        projects_response = self.session.get(f"{BASE_URL}/api/projects")
        
        if projects_response.status_code != 200:
            pytest.skip(f"Could not get projects list: {projects_response.status_code}")
        
        projects = projects_response.json()
        if not projects:
            pytest.skip("No projects available for testing")
        
        project_id = projects[0].get('id')
        
        # Request SCORM export (POST endpoint)
        export_response = self.session.post(
            f"{BASE_URL}/api/course/{project_id}/export-scorm",
            timeout=90
        )
        
        if export_response.status_code != 200:
            pytest.skip(f"SCORM export failed: {export_response.status_code}")
        
        # Get download URL from response
        export_data = export_response.json()
        download_url = export_data.get('downloadUrl')
        
        if not download_url:
            pytest.skip("No downloadUrl in response")
        
        if download_url.startswith('/'):
            download_url = f"{BASE_URL}{download_url}"
        
        zip_response = self.session.get(download_url, timeout=60)
        
        if zip_response.status_code != 200:
            pytest.skip(f"ZIP download failed: {zip_response.status_code}")
        
        # Extract and check player.js content
        zip_buffer = io.BytesIO(zip_response.content)
        with zipfile.ZipFile(zip_buffer, 'r') as zf:
            # Find player.js
            player_js_path = None
            for f in zf.namelist():
                if 'player.js' in f:
                    player_js_path = f
                    break
            
            if not player_js_path:
                pytest.fail("player.js not found in SCORM package")
            
            player_js_content = zf.read(player_js_path).decode('utf-8')
            
            # Verify the fix is in place
            assert '*{background:transparent!important}' not in player_js_content, \
                "SCORM package player.js still has the problematic wildcard rule"
            
            assert '*{box-sizing:border-box!important' in player_js_content, \
                "SCORM package player.js should have the fixed wildcard rule"
            
            print("✓ SCORM package player.js has the CSS fix applied")
    
    def test_html_export_endpoint_works(self):
        """Test HTML export endpoint returns valid HTML"""
        # Get list of projects
        projects_response = self.session.get(f"{BASE_URL}/api/projects")
        
        if projects_response.status_code != 200:
            pytest.skip(f"Could not get projects list: {projects_response.status_code}")
        
        projects = projects_response.json()
        if not projects:
            pytest.skip("No projects available for testing")
        
        project_id = projects[0].get('id')
        print(f"Testing HTML export with project: {project_id}")
        
        # Request HTML export (POST endpoint)
        export_response = self.session.post(
            f"{BASE_URL}/api/course/{project_id}/export-html",
            timeout=90
        )
        
        assert export_response.status_code == 200, \
            f"HTML export failed with status {export_response.status_code}: {export_response.text[:200]}"
        
        # The endpoint returns JSON with downloadUrl
        export_data = export_response.json()
        download_url = export_data.get('downloadUrl')
        
        assert download_url, f"No downloadUrl in response: {export_data}"
        print(f"  Download URL: {download_url}")
        
        # Download the actual HTML file
        if download_url.startswith('/'):
            download_url = f"{BASE_URL}{download_url}"
        
        html_response = self.session.get(download_url, timeout=60)
        
        assert html_response.status_code == 200, \
            f"HTML download failed with status {html_response.status_code}"
        
        # Verify it's HTML
        content_type = html_response.headers.get('content-type', '')
        assert 'html' in content_type.lower() or 'text' in content_type.lower() or 'octet-stream' in content_type.lower(), \
            f"Expected HTML content type, got: {content_type}"
        
        html_content = html_response.text
        
        # Verify basic HTML structure
        assert '<!DOCTYPE html>' in html_content or '<html' in html_content, \
            "Response doesn't look like valid HTML"
        
        # Verify the CSS fix is in place (no wildcard background:transparent)
        assert '*{background:transparent!important}' not in html_content, \
            "HTML export still has the problematic wildcard rule"
        
        print("✓ HTML export successful and CSS fix verified")
    
    def test_specific_course_with_background_image(self):
        """Test the specific course mentioned in the bug report"""
        # Try to get the specific course
        course_response = self.session.get(f"{BASE_URL}/api/projects/{TEST_COURSE_ID}")
        
        if course_response.status_code == 404:
            pytest.skip(f"Test course {TEST_COURSE_ID} not found")
        
        if course_response.status_code != 200:
            pytest.skip(f"Could not get test course: {course_response.status_code}")
        
        course_data = course_response.json()
        course = course_data.get('course', {})
        slides = course.get('slides', [])
        
        # Check if any slide has background image
        has_background = False
        for slide in slides:
            bg = slide.get('background', '')
            bg_image = slide.get('backgroundImage', '')
            
            # Check for CSS url() in background property
            if 'url(' in str(bg) or bg_image:
                has_background = True
                print(f"  Found background in slide: {bg[:100] if bg else bg_image[:100]}...")
                break
            
            # Also check htmlContent for embedded backgrounds
            for element in slide.get('elements', []):
                html_content = element.get('htmlContent', '')
                if 'url(' in str(html_content) and 'background' in str(html_content).lower():
                    has_background = True
                    print(f"  Found background in htmlContent element")
                    break
        
        if has_background:
            print(f"✓ Course {TEST_COURSE_ID} has background images that should now export correctly")
        else:
            print(f"⚠ Course {TEST_COURSE_ID} doesn't have obvious background images")


class TestPreviewMode:
    """Tests for preview/visualize mode"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session with authentication"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        
        if login_response.status_code == 200:
            data = login_response.json()
            token = data.get("token") or data.get("access_token")
            if token:
                self.session.headers.update({"Authorization": f"Bearer {token}"})
    
    def test_preview_endpoint_exists(self):
        """Test that preview endpoint exists"""
        # Get a project first
        projects_response = self.session.get(f"{BASE_URL}/api/projects")
        
        if projects_response.status_code != 200:
            pytest.skip("Could not get projects list")
        
        projects = projects_response.json()
        if not projects:
            pytest.skip("No projects available")
        
        project_id = projects[0].get('id')
        
        # Try preview endpoint (may be /api/preview/{id} or similar)
        preview_response = self.session.get(f"{BASE_URL}/api/preview/{project_id}")
        
        # Accept 200 or 404 (endpoint may not exist)
        if preview_response.status_code == 200:
            print(f"✓ Preview endpoint works for project {project_id}")
        elif preview_response.status_code == 404:
            # Try alternative endpoint
            preview_response = self.session.get(f"{BASE_URL}/api/projects/{project_id}/preview")
            if preview_response.status_code == 200:
                print(f"✓ Alternative preview endpoint works")
            else:
                print(f"⚠ Preview endpoint not found (may be frontend-only)")
        else:
            print(f"⚠ Preview endpoint returned: {preview_response.status_code}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
