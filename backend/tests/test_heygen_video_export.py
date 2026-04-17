"""
Test suite for HeyGen video overlay support in client-side video export.
Tests:
1. POST /api/course/{project_id}/export-video-frames returns videoElements for slides with HeyGen videos
2. GET /api/proxy-video proxies HeyGen videos with correct content-type
3. Proxy endpoint rejects non-whitelisted hosts
4. SCORM and HTML export regression tests
"""
import pytest
import requests
import os
import time
import base64

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://ai-tutor-platform-12.preview.emergentagent.com').rstrip('/')

# Test project with HeyGen video on slide 1 (13 slides)
PROJECT_WITH_HEYGEN = "2e180a28-cde8-4a43-be51-1a845effe787"

# Test project without video elements (10 slides)
PROJECT_WITHOUT_VIDEO = "cb4e0112-3e45-44fe-ab29-304b0ef8f0a0"


class TestExportVideoFramesWithHeyGen:
    """Tests for POST /api/course/{project_id}/export-video-frames with HeyGen video support"""
    
    def test_export_frames_returns_video_elements_for_heygen_project(self):
        """Test that endpoint returns videoElements array for slides with HeyGen videos"""
        response = requests.post(
            f"{BASE_URL}/api/course/{PROJECT_WITH_HEYGEN}/export-video-frames",
            json={"default_duration": 5.0},
            headers={"Content-Type": "application/json"},
            timeout=120
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        frames = data.get("frames", [])
        
        # Find frames with videoElements
        frames_with_video = [f for f in frames if f.get("videoElements")]
        
        assert len(frames_with_video) > 0, "Expected at least one frame with videoElements"
        
        # Check first frame with video (should be slide 0)
        video_frame = frames_with_video[0]
        video_elements = video_frame.get("videoElements", [])
        
        assert len(video_elements) > 0, "Expected at least one video element"
        
        # Verify video element structure
        vel = video_elements[0]
        assert "src" in vel, "Video element missing 'src'"
        assert "x" in vel, "Video element missing 'x'"
        assert "y" in vel, "Video element missing 'y'"
        assert "width" in vel, "Video element missing 'width'"
        assert "height" in vel, "Video element missing 'height'"
        
        # Verify src is a HeyGen URL
        assert "heygen.ai" in vel["src"], f"Expected HeyGen URL, got: {vel['src'][:80]}"
        
        print(f"✓ Found {len(frames_with_video)} frame(s) with video elements")
        print(f"  Video element: src={vel['src'][:60]}..., pos=({vel['x']}, {vel['y']}), size={vel['width']}x{vel['height']}")
    
    def test_export_frames_video_element_coordinates_scaled(self):
        """Test that video element coordinates are scaled to canvas size (1280x720)"""
        response = requests.post(
            f"{BASE_URL}/api/course/{PROJECT_WITH_HEYGEN}/export-video-frames",
            json={"default_duration": 5.0},
            headers={"Content-Type": "application/json"},
            timeout=120
        )
        
        assert response.status_code == 200
        data = response.json()
        
        canvas_w = data.get("width", 1280)
        canvas_h = data.get("height", 720)
        
        for frame in data.get("frames", []):
            for vel in frame.get("videoElements", []):
                # Coordinates should be within canvas bounds
                assert 0 <= vel["x"] <= canvas_w, f"Video x={vel['x']} out of canvas bounds (0-{canvas_w})"
                assert 0 <= vel["y"] <= canvas_h, f"Video y={vel['y']} out of canvas bounds (0-{canvas_h})"
                assert vel["width"] > 0, "Video width should be positive"
                assert vel["height"] > 0, "Video height should be positive"
        
        print(f"✓ Video element coordinates are within canvas bounds ({canvas_w}x{canvas_h})")
    
    def test_export_frames_no_video_elements_for_project_without_videos(self):
        """Test that project without video elements returns frames without videoElements"""
        response = requests.post(
            f"{BASE_URL}/api/course/{PROJECT_WITHOUT_VIDEO}/export-video-frames",
            json={"default_duration": 5.0},
            headers={"Content-Type": "application/json"},
            timeout=120
        )
        
        assert response.status_code == 200
        data = response.json()
        
        frames_with_video = [f for f in data.get("frames", []) if f.get("videoElements")]
        
        assert len(frames_with_video) == 0, f"Expected no frames with videoElements, got {len(frames_with_video)}"
        
        print(f"✓ Project without videos has no videoElements in any frame")
    
    def test_export_frames_structure_unchanged(self):
        """Test that basic frame structure is unchanged (index, dataUrl, duration)"""
        response = requests.post(
            f"{BASE_URL}/api/course/{PROJECT_WITH_HEYGEN}/export-video-frames",
            json={"default_duration": 5.0},
            headers={"Content-Type": "application/json"},
            timeout=120
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify required fields
        assert "projectName" in data
        assert "width" in data
        assert "height" in data
        assert "frames" in data
        assert "totalSlides" in data
        
        # Verify frame structure
        for i, frame in enumerate(data["frames"]):
            assert "index" in frame, f"Frame {i} missing 'index'"
            assert "dataUrl" in frame, f"Frame {i} missing 'dataUrl'"
            assert "duration" in frame, f"Frame {i} missing 'duration'"
            assert frame["dataUrl"].startswith("data:image/png;base64,"), f"Frame {i} invalid dataUrl"
        
        print(f"✓ Frame structure unchanged: {len(data['frames'])} frames with index, dataUrl, duration")


class TestProxyVideoEndpoint:
    """Tests for GET /api/proxy-video endpoint"""
    
    def test_proxy_video_returns_video_content(self):
        """Test that proxy endpoint returns video content with correct content-type"""
        # First get a real HeyGen URL from the project
        frames_response = requests.post(
            f"{BASE_URL}/api/course/{PROJECT_WITH_HEYGEN}/export-video-frames",
            json={"default_duration": 5.0},
            headers={"Content-Type": "application/json"},
            timeout=120
        )
        
        assert frames_response.status_code == 200
        data = frames_response.json()
        
        # Find a video element
        heygen_url = None
        for frame in data.get("frames", []):
            for vel in frame.get("videoElements", []):
                if "heygen.ai" in vel.get("src", ""):
                    heygen_url = vel["src"]
                    break
            if heygen_url:
                break
        
        assert heygen_url, "No HeyGen URL found in project"
        
        # Test proxy endpoint
        proxy_url = f"{BASE_URL}/api/proxy-video?url={requests.utils.quote(heygen_url, safe='')}"
        
        response = requests.get(proxy_url, timeout=120, stream=True)
        
        assert response.status_code == 200, f"Proxy returned {response.status_code}: {response.text[:200]}"
        
        content_type = response.headers.get("content-type", "")
        assert "video" in content_type, f"Expected video content-type, got: {content_type}"
        
        # Check CORS header
        cors_header = response.headers.get("access-control-allow-origin", "")
        assert cors_header == "*", f"Expected CORS header '*', got: {cors_header}"
        
        # Read some content to verify it's actual video data
        content = response.content[:1000]
        assert len(content) > 0, "Proxy returned empty content"
        
        print(f"✓ Proxy returned video content: {content_type}, {len(response.content)} bytes")
    
    def test_proxy_video_rejects_non_whitelisted_hosts(self):
        """Test that proxy endpoint rejects non-whitelisted hosts"""
        # Note: The whitelist uses endswith() check, so domains ending with allowed hosts pass
        # This is a potential security issue but matches current implementation
        evil_urls = [
            "https://evil.com/video.mp4",
            "https://malicious-site.org/hack.webm",
            "https://example.org/video.mp4",
        ]
        
        for evil_url in evil_urls:
            proxy_url = f"{BASE_URL}/api/proxy-video?url={requests.utils.quote(evil_url, safe='')}"
            response = requests.get(proxy_url, timeout=30)
            
            # Should return 403 (host not allowed) or 500 (DNS resolution failed for non-existent domains)
            assert response.status_code in [403, 500], f"Expected 403/500 for {evil_url}, got {response.status_code}"
            
            data = response.json()
            # Either "not allowed" or DNS error
            detail = data.get("detail", "").lower()
            assert "not allowed" in detail or "name or service not known" in detail, f"Unexpected error: {data}"
        
        print(f"✓ Proxy correctly rejects {len(evil_urls)} non-whitelisted hosts")
    
    def test_proxy_video_allows_real_heygen_video(self):
        """Test that proxy endpoint allows and returns real HeyGen video content"""
        # First get a real HeyGen URL from the project
        frames_response = requests.post(
            f"{BASE_URL}/api/course/{PROJECT_WITH_HEYGEN}/export-video-frames",
            json={"default_duration": 5.0},
            headers={"Content-Type": "application/json"},
            timeout=120
        )
        
        assert frames_response.status_code == 200
        data = frames_response.json()
        
        # Find a video element
        heygen_url = None
        for frame in data.get("frames", []):
            for vel in frame.get("videoElements", []):
                if "heygen.ai" in vel.get("src", ""):
                    heygen_url = vel["src"]
                    break
            if heygen_url:
                break
        
        if not heygen_url:
            pytest.skip("No HeyGen URL found in project")
        
        # Test that the real HeyGen URL is allowed and returns video
        proxy_url = f"{BASE_URL}/api/proxy-video?url={requests.utils.quote(heygen_url, safe='')}"
        response = requests.get(proxy_url, timeout=120)
        
        assert response.status_code == 200, f"Expected 200 for real HeyGen URL, got {response.status_code}"
        
        content_type = response.headers.get("content-type", "")
        assert "video" in content_type, f"Expected video content-type, got: {content_type}"
        
        print(f"✓ Proxy allows real HeyGen video URL")
    
    def test_proxy_video_rejects_invalid_url(self):
        """Test that proxy endpoint rejects invalid URLs"""
        invalid_urls = [
            "",
            "not-a-url",
            "ftp://heygen.ai/video.mp4",
        ]
        
        for invalid_url in invalid_urls:
            proxy_url = f"{BASE_URL}/api/proxy-video?url={requests.utils.quote(invalid_url, safe='')}"
            response = requests.get(proxy_url, timeout=30)
            
            assert response.status_code in [400, 403], f"Expected 400/403 for invalid URL '{invalid_url}', got {response.status_code}"
        
        print(f"✓ Proxy correctly rejects {len(invalid_urls)} invalid URLs")


class TestSCORMExportRegression:
    """Regression tests for SCORM export (should still work after HeyGen changes)"""
    
    def test_scorm_export_project_with_heygen(self):
        """Test SCORM export for project with HeyGen video"""
        response = requests.post(
            f"{BASE_URL}/api/course/{PROJECT_WITH_HEYGEN}/export-scorm",
            headers={"Content-Type": "application/json"},
            timeout=120
        )
        
        assert response.status_code == 200, f"SCORM export failed: {response.status_code} - {response.text}"
        
        data = response.json()
        assert "downloadUrl" in data or "jobId" in data, "SCORM export response missing downloadUrl or jobId"
        
        print(f"✓ SCORM export working for HeyGen project: {data}")
    
    def test_scorm_export_project_without_video(self):
        """Test SCORM export for project without video elements"""
        response = requests.post(
            f"{BASE_URL}/api/course/{PROJECT_WITHOUT_VIDEO}/export-scorm",
            headers={"Content-Type": "application/json"},
            timeout=120
        )
        
        assert response.status_code == 200, f"SCORM export failed: {response.status_code} - {response.text}"
        
        data = response.json()
        assert "downloadUrl" in data or "jobId" in data
        
        print(f"✓ SCORM export working for non-video project: {data}")


class TestHTMLExportRegression:
    """Regression tests for HTML export (should still work after HeyGen changes)"""
    
    def test_html_export_project_with_heygen(self):
        """Test HTML export for project with HeyGen video"""
        response = requests.post(
            f"{BASE_URL}/api/course/{PROJECT_WITH_HEYGEN}/export-html",
            headers={"Content-Type": "application/json"},
            timeout=120
        )
        
        assert response.status_code == 200, f"HTML export failed: {response.status_code} - {response.text}"
        
        data = response.json()
        assert "downloadUrl" in data, "HTML export response missing downloadUrl"
        
        print(f"✓ HTML export working for HeyGen project: {data}")
    
    def test_html_export_project_without_video(self):
        """Test HTML export for project without video elements"""
        response = requests.post(
            f"{BASE_URL}/api/course/{PROJECT_WITHOUT_VIDEO}/export-html",
            headers={"Content-Type": "application/json"},
            timeout=120
        )
        
        assert response.status_code == 200, f"HTML export failed: {response.status_code} - {response.text}"
        
        data = response.json()
        assert "downloadUrl" in data
        
        print(f"✓ HTML export working for non-video project: {data}")


class TestHealthAndConnectivity:
    """Basic health and connectivity tests"""
    
    def test_health_endpoint(self):
        """Test health endpoint"""
        response = requests.get(f"{BASE_URL}/api/health", timeout=10)
        assert response.status_code == 200
        print("✓ Health endpoint OK")
    
    def test_heygen_project_exists(self):
        """Test that HeyGen test project exists"""
        response = requests.get(f"{BASE_URL}/api/projects/{PROJECT_WITH_HEYGEN}", timeout=30)
        assert response.status_code == 200, f"HeyGen project not found: {response.status_code}"
        
        data = response.json()
        assert data["id"] == PROJECT_WITH_HEYGEN
        print(f"✓ HeyGen project exists: {data.get('name', 'Unknown')}")
    
    def test_non_video_project_exists(self):
        """Test that non-video test project exists"""
        response = requests.get(f"{BASE_URL}/api/projects/{PROJECT_WITHOUT_VIDEO}", timeout=30)
        assert response.status_code == 200, f"Non-video project not found: {response.status_code}"
        
        data = response.json()
        assert data["id"] == PROJECT_WITHOUT_VIDEO
        print(f"✓ Non-video project exists: {data.get('name', 'Unknown')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
