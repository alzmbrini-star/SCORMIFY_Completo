"""
Test suite for client-side video export feature.
Tests the POST /api/course/{project_id}/export-video-frames endpoint
which returns base64 frames for browser-based video generation.
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://agent-authfix.preview.emergentagent.com').rstrip('/')

# Test project ID with 10 slides
TEST_PROJECT_ID = "cb4e0112-3e45-44fe-ab29-304b0ef8f0a0"


class TestExportVideoFramesEndpoint:
    """Tests for POST /api/course/{project_id}/export-video-frames"""
    
    def test_export_video_frames_returns_valid_structure(self):
        """Test that endpoint returns correct JSON structure with frames array"""
        response = requests.post(
            f"{BASE_URL}/api/course/{TEST_PROJECT_ID}/export-video-frames",
            json={"default_duration": 5.0},
            headers={"Content-Type": "application/json"},
            timeout=120
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Verify required fields exist
        assert "projectName" in data, "Response missing 'projectName'"
        assert "width" in data, "Response missing 'width'"
        assert "height" in data, "Response missing 'height'"
        assert "frames" in data, "Response missing 'frames'"
        assert "totalSlides" in data, "Response missing 'totalSlides'"
        
        print(f"✓ Response structure valid: projectName={data['projectName']}, width={data['width']}, height={data['height']}")
    
    def test_export_video_frames_returns_correct_dimensions(self):
        """Test that frames have correct canvas dimensions (1280x720)"""
        response = requests.post(
            f"{BASE_URL}/api/course/{TEST_PROJECT_ID}/export-video-frames",
            json={"default_duration": 5.0},
            headers={"Content-Type": "application/json"},
            timeout=120
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["width"] == 1280, f"Expected width 1280, got {data['width']}"
        assert data["height"] == 720, f"Expected height 720, got {data['height']}"
        
        print(f"✓ Canvas dimensions correct: {data['width']}x{data['height']}")
    
    def test_export_video_frames_returns_all_slides(self):
        """Test that endpoint returns frames for all slides"""
        response = requests.post(
            f"{BASE_URL}/api/course/{TEST_PROJECT_ID}/export-video-frames",
            json={"default_duration": 5.0},
            headers={"Content-Type": "application/json"},
            timeout=120
        )
        
        assert response.status_code == 200
        data = response.json()
        
        frames = data["frames"]
        total_slides = data["totalSlides"]
        
        assert len(frames) == total_slides, f"Expected {total_slides} frames, got {len(frames)}"
        assert len(frames) == 10, f"Expected 10 frames for test project, got {len(frames)}"
        
        print(f"✓ All {len(frames)} slides returned as frames")
    
    def test_export_video_frames_frame_structure(self):
        """Test that each frame has correct structure (index, dataUrl, duration)"""
        response = requests.post(
            f"{BASE_URL}/api/course/{TEST_PROJECT_ID}/export-video-frames",
            json={"default_duration": 5.0},
            headers={"Content-Type": "application/json"},
            timeout=120
        )
        
        assert response.status_code == 200
        data = response.json()
        
        for i, frame in enumerate(data["frames"]):
            assert "index" in frame, f"Frame {i} missing 'index'"
            assert "dataUrl" in frame, f"Frame {i} missing 'dataUrl'"
            assert "duration" in frame, f"Frame {i} missing 'duration'"
            
            assert frame["index"] == i, f"Frame index mismatch: expected {i}, got {frame['index']}"
            assert frame["dataUrl"].startswith("data:image/png;base64,"), f"Frame {i} dataUrl not valid base64 PNG"
            assert frame["duration"] >= 2.0, f"Frame {i} duration too short: {frame['duration']}"
        
        print(f"✓ All {len(data['frames'])} frames have valid structure")
    
    def test_export_video_frames_base64_images_valid(self):
        """Test that base64 images can be decoded"""
        import base64
        
        response = requests.post(
            f"{BASE_URL}/api/course/{TEST_PROJECT_ID}/export-video-frames",
            json={"default_duration": 5.0},
            headers={"Content-Type": "application/json"},
            timeout=120
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Test first frame's base64 is valid
        first_frame = data["frames"][0]
        base64_data = first_frame["dataUrl"].replace("data:image/png;base64,", "")
        
        try:
            decoded = base64.b64decode(base64_data)
            # PNG magic bytes
            assert decoded[:8] == b'\x89PNG\r\n\x1a\n', "Decoded data is not valid PNG"
            print(f"✓ Base64 image decodes to valid PNG ({len(decoded)} bytes)")
        except Exception as e:
            pytest.fail(f"Failed to decode base64 image: {e}")
    
    def test_export_video_frames_custom_duration(self):
        """Test that custom default_duration is respected"""
        response = requests.post(
            f"{BASE_URL}/api/course/{TEST_PROJECT_ID}/export-video-frames",
            json={"default_duration": 8.0},
            headers={"Content-Type": "application/json"},
            timeout=120
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Check that duration is at least 2.0 (minimum enforced by backend)
        for frame in data["frames"]:
            assert frame["duration"] >= 2.0, f"Duration below minimum: {frame['duration']}"
        
        print(f"✓ Custom duration parameter accepted")
    
    def test_export_video_frames_nonexistent_project(self):
        """Test that nonexistent project returns 404"""
        response = requests.post(
            f"{BASE_URL}/api/course/nonexistent-project-id/export-video-frames",
            json={"default_duration": 5.0},
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ Nonexistent project returns 404")
    
    def test_export_video_frames_response_time(self):
        """Test that endpoint responds within reasonable time (< 60s for 10 slides)"""
        start_time = time.time()
        
        response = requests.post(
            f"{BASE_URL}/api/course/{TEST_PROJECT_ID}/export-video-frames",
            json={"default_duration": 5.0},
            headers={"Content-Type": "application/json"},
            timeout=120
        )
        
        elapsed = time.time() - start_time
        
        assert response.status_code == 200
        assert elapsed < 60, f"Response took too long: {elapsed:.2f}s (expected < 60s)"
        
        print(f"✓ Response time: {elapsed:.2f}s for 10 slides")


class TestSCORMExportRegression:
    """Regression tests for SCORM export (should still work)"""
    
    def test_scorm_export_endpoint_exists(self):
        """Test that SCORM export endpoint still works"""
        response = requests.post(
            f"{BASE_URL}/api/course/{TEST_PROJECT_ID}/export-scorm",
            headers={"Content-Type": "application/json"},
            timeout=120
        )
        
        # Should return 200 with jobId and downloadUrl
        assert response.status_code == 200, f"SCORM export failed: {response.status_code} - {response.text}"
        
        data = response.json()
        assert "downloadUrl" in data or "jobId" in data, "SCORM export response missing downloadUrl or jobId"
        
        print(f"✓ SCORM export working: {data}")


class TestHTMLExportRegression:
    """Regression tests for HTML export (should still work)"""
    
    def test_html_export_endpoint_exists(self):
        """Test that HTML export endpoint still works"""
        response = requests.post(
            f"{BASE_URL}/api/course/{TEST_PROJECT_ID}/export-html",
            headers={"Content-Type": "application/json"},
            timeout=120
        )
        
        # Should return 200 with downloadUrl
        assert response.status_code == 200, f"HTML export failed: {response.status_code} - {response.text}"
        
        data = response.json()
        assert "downloadUrl" in data, "HTML export response missing downloadUrl"
        
        print(f"✓ HTML export working: {data}")


class TestHealthAndBasicEndpoints:
    """Basic health and connectivity tests"""
    
    def test_health_endpoint(self):
        """Test health endpoint"""
        response = requests.get(f"{BASE_URL}/api/health", timeout=10)
        assert response.status_code == 200
        print("✓ Health endpoint OK")
    
    def test_project_exists(self):
        """Test that test project exists"""
        response = requests.get(f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}", timeout=30)
        assert response.status_code == 200, f"Test project not found: {response.status_code}"
        
        data = response.json()
        assert "id" in data
        assert data["id"] == TEST_PROJECT_ID
        
        print(f"✓ Test project exists: {data.get('name', 'Unknown')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
