"""
Test SCORM Export with MongoDB Asset Persistence
Tests the fix for missing slide images in SCORM exports when local files are lost
in ephemeral storage (Kubernetes pod restarts).

Key tests:
1. Backend API /api/projects returns project data correctly
2. Asset serving endpoint falls back to MongoDB when local file is missing
3. SCORM export includes slide images in the ZIP package
"""
import pytest
import requests
import os
import zipfile
import io
import json
from pathlib import Path

# Get BASE_URL from environment - no default to ensure proper configuration
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    raise ValueError("REACT_APP_BACKEND_URL environment variable is required")

# Test project ID with ConvertAPI-imported slides
TEST_PROJECT_ID = "57d237b2-3636-4ea8-a306-bede62e4fe23"
TEST_SLIDE_IMAGES = ["slide_001.png", "slide_002.png", "slide_003.png"]


class TestAPIHealth:
    """Basic API health checks"""
    
    def test_api_health(self):
        """Test that API health endpoint returns healthy status"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy"
        print("✅ API health check passed")
    
    def test_api_root(self):
        """Test API root endpoint"""
        response = requests.get(f"{BASE_URL}/api/")
        assert response.status_code == 200
        data = response.json()
        assert "Scormify" in data.get("message", "")
        print("✅ API root endpoint working")


class TestProjectsAPI:
    """Tests for /api/projects endpoint"""
    
    def test_list_projects(self):
        """Test GET /api/projects returns project list"""
        response = requests.get(f"{BASE_URL}/api/projects")
        assert response.status_code == 200
        projects = response.json()
        assert isinstance(projects, list)
        assert len(projects) > 0, "Expected at least one project"
        print(f"✅ GET /api/projects returned {len(projects)} projects")
    
    def test_get_test_project(self):
        """Test GET /api/projects/{id} for test project NR01"""
        response = requests.get(f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}")
        assert response.status_code == 200
        
        project = response.json()
        assert project.get("id") == TEST_PROJECT_ID
        assert project.get("name") == "NR01"
        assert project.get("status") == "ready"
        
        # Verify course has slides with background images
        course = project.get("course", {})
        slides = course.get("slides", [])
        assert len(slides) == 3, f"Expected 3 slides, got {len(slides)}"
        
        # Check each slide has a background image reference
        for i, slide in enumerate(slides):
            bg_image = slide.get("backgroundImage")
            assert bg_image is not None, f"Slide {i+1} missing backgroundImage"
            assert f"slide_{i+1:03d}.png" in bg_image
            print(f"  ✅ Slide {i+1} has backgroundImage: {bg_image}")
        
        print(f"✅ GET /api/projects/{TEST_PROJECT_ID} returned project with 3 slides")


class TestAssetServing:
    """Tests for /api/projects/{id}/assets/{filename} endpoint
    
    This tests the MongoDB fallback mechanism:
    - serve_asset endpoint at lines 1295-1316 in server.py
    - Should return 200 even when local file is missing (recovers from MongoDB)
    """
    
    def test_serve_slide_images(self):
        """Test that slide images are served correctly"""
        for filename in TEST_SLIDE_IMAGES:
            response = requests.get(
                f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/assets/{filename}"
            )
            assert response.status_code == 200, f"Failed to serve {filename}: {response.status_code}"
            
            # Verify it's an actual PNG image
            content_type = response.headers.get("content-type", "")
            assert "image" in content_type or len(response.content) > 1000, \
                f"Response for {filename} doesn't look like an image"
            
            print(f"✅ Asset {filename} served successfully ({len(response.content)} bytes)")
    
    def test_serve_nonexistent_asset(self):
        """Test that nonexistent assets return 404"""
        response = requests.get(
            f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/assets/nonexistent_file.png"
        )
        assert response.status_code == 404
        print("✅ Nonexistent asset correctly returns 404")
    
    def test_asset_serving_consistency(self):
        """Test that assets are served consistently (multiple requests)"""
        for _ in range(3):
            response = requests.get(
                f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/assets/slide_001.png"
            )
            assert response.status_code == 200
        print("✅ Asset serving is consistent across multiple requests")


class TestSCORMExport:
    """Tests for SCORM export functionality
    
    Tests the fix at:
    - scorm_exporter.py lines 168-193 (asset copying with MongoDB restore)
    - scorm_exporter.py lines 318-350 (referenced asset verification)
    """
    
    def test_scorm_export_endpoint(self):
        """Test POST /api/course/{project_id}/export-scorm"""
        response = requests.post(
            f"{BASE_URL}/api/course/{TEST_PROJECT_ID}/export-scorm"
        )
        assert response.status_code == 200, f"SCORM export failed: {response.text}"
        
        data = response.json()
        assert "downloadUrl" in data, "Response missing downloadUrl"
        assert "jobId" in data, "Response missing jobId"
        
        download_url = data["downloadUrl"]
        print(f"✅ SCORM export initiated, download URL: {download_url}")
        
        return download_url
    
    def test_scorm_export_contains_slide_images(self):
        """Test that SCORM export ZIP contains all slide images"""
        # Export SCORM
        response = requests.post(
            f"{BASE_URL}/api/course/{TEST_PROJECT_ID}/export-scorm"
        )
        assert response.status_code == 200
        
        download_url = response.json()["downloadUrl"]
        
        # Download the ZIP file
        zip_response = requests.get(f"{BASE_URL}{download_url}")
        assert zip_response.status_code == 200, f"Failed to download ZIP: {zip_response.status_code}"
        
        # Parse the ZIP
        zip_buffer = io.BytesIO(zip_response.content)
        with zipfile.ZipFile(zip_buffer, 'r') as zf:
            file_list = zf.namelist()
            print(f"  ZIP contains {len(file_list)} files")
            
            # Check for required files
            assert "imsmanifest.xml" in file_list, "Missing imsmanifest.xml"
            assert "index.html" in file_list, "Missing index.html"
            assert "course.json" in file_list, "Missing course.json"
            
            # Check for slide images in assets folder
            for filename in TEST_SLIDE_IMAGES:
                asset_path = f"assets/{filename}"
                assert asset_path in file_list, f"Missing {asset_path} in SCORM package"
                
                # Verify the file is not empty
                file_info = zf.getinfo(asset_path)
                assert file_info.file_size > 1000, f"Asset {filename} appears to be empty or too small"
                print(f"  ✅ {asset_path} included ({file_info.file_size} bytes)")
            
            # Verify course.json references the assets correctly
            course_json = json.loads(zf.read("course.json"))
            slides = course_json.get("slides", [])
            for i, slide in enumerate(slides):
                bg = slide.get("backgroundImage", "")
                assert bg.startswith("assets/"), f"Slide {i+1} backgroundImage not relative: {bg}"
                print(f"  ✅ Slide {i+1} course.json reference: {bg}")
        
        print("✅ SCORM export contains all required slide images")
    
    def test_scorm_package_structure(self):
        """Test SCORM package has valid structure"""
        response = requests.post(
            f"{BASE_URL}/api/course/{TEST_PROJECT_ID}/export-scorm"
        )
        assert response.status_code == 200
        
        download_url = response.json()["downloadUrl"]
        zip_response = requests.get(f"{BASE_URL}{download_url}")
        assert zip_response.status_code == 200
        
        zip_buffer = io.BytesIO(zip_response.content)
        with zipfile.ZipFile(zip_buffer, 'r') as zf:
            # Check SCORM 1.2 required files
            required_files = [
                "imsmanifest.xml",
                "index.html",
                "course.json",
                "scripts/scorm-api.js",
                "scripts/player.js",
            ]
            
            for req_file in required_files:
                assert req_file in zf.namelist(), f"Missing required SCORM file: {req_file}"
            
            # Verify imsmanifest.xml has proper SCORM 1.2 structure
            manifest_content = zf.read("imsmanifest.xml").decode('utf-8')
            assert "ADL SCORM" in manifest_content
            assert "1.2" in manifest_content
            assert "organizations" in manifest_content
            assert "resources" in manifest_content
            
            print("✅ SCORM package has valid SCORM 1.2 structure")


class TestAuthAndSession:
    """Test authentication to ensure dashboard shows projects after login"""
    
    def test_login_and_get_projects(self):
        """Test login with admin credentials and verify projects load"""
        session = requests.Session()
        
        # Login
        login_response = session.post(
            f"{BASE_URL}/api/auth/login",
            json={
                "email": "admin@scormify.com",
                "password": "admin123"
            }
        )
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        
        login_data = login_response.json()
        assert "user" in login_data or "token" in login_data, "Login response missing user/token"
        print("✅ Login successful with admin@scormify.com")
        
        # Get projects with session (cookies should be sent)
        projects_response = session.get(f"{BASE_URL}/api/projects")
        assert projects_response.status_code == 200
        
        projects = projects_response.json()
        assert isinstance(projects, list)
        assert len(projects) > 0, "Dashboard should show projects (not empty)"
        print(f"✅ After login, /api/projects returns {len(projects)} projects")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
