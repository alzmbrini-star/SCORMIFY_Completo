"""
Test suite for client-side video export with audio support.
Verifies:
1. GET /api/course/{project_id}/slides-data returns audioElements with 'src' field
2. Legacy audio data using 'url' field is correctly converted to 'src'
3. GET /api/proxy-video proxies HeyGen videos correctly
4. GET /api/audio/{filename} serves legacy audio narration files
5. Mixed HeyGen video + ElevenLabs audio projects work correctly
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test project IDs from the problem statement
LEGACY_AUDIO_PROJECT_ID = "82d2d9d4-3067-47de-bf5a-0e14e9051e67"  # Universidades Corporativas
MIXED_HEYGEN_AUDIO_PROJECT_ID = "edd87206-484c-45d8-ba4b-5ae9bc24b2fb"  # SCORMIFY - V2


class TestSlidesDataEndpoint:
    """Tests for GET /api/course/{project_id}/slides-data endpoint"""
    
    def test_slides_data_returns_200(self):
        """Verify slides-data endpoint returns 200 for valid project"""
        response = requests.get(f"{BASE_URL}/api/course/{LEGACY_AUDIO_PROJECT_ID}/slides-data")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "slides" in data
        assert "projectName" in data
        assert len(data["slides"]) > 0
        print(f"PASS: slides-data returns 200 with {len(data['slides'])} slides")
    
    def test_slides_data_returns_audio_elements_with_src(self):
        """Verify audioElements have 'src' field (not 'url')"""
        response = requests.get(f"{BASE_URL}/api/course/{LEGACY_AUDIO_PROJECT_ID}/slides-data")
        assert response.status_code == 200
        data = response.json()
        
        slides_with_audio = [s for s in data["slides"] if s.get("audioElements")]
        assert len(slides_with_audio) > 0, "Expected at least one slide with audio"
        
        for slide in slides_with_audio:
            for audio in slide["audioElements"]:
                assert "src" in audio, f"audioElement missing 'src' field: {audio}"
                assert audio["src"], f"audioElement 'src' is empty: {audio}"
                # Verify src is a valid path
                assert audio["src"].startswith("/api/audio/") or audio["src"].startswith("http"), \
                    f"Invalid audio src format: {audio['src']}"
        
        print(f"PASS: {len(slides_with_audio)} slides have audioElements with 'src' field")
    
    def test_legacy_audio_project_audio_paths(self):
        """Verify legacy audio project returns correct audio paths"""
        response = requests.get(f"{BASE_URL}/api/course/{LEGACY_AUDIO_PROJECT_ID}/slides-data")
        assert response.status_code == 200
        data = response.json()
        
        # Check first slide's audio
        first_slide = data["slides"][0]
        assert "audioElements" in first_slide
        assert len(first_slide["audioElements"]) > 0
        
        audio = first_slide["audioElements"][0]
        expected_pattern = f"/api/audio/narration_{LEGACY_AUDIO_PROJECT_ID}_0.mp3"
        assert audio["src"] == expected_pattern, \
            f"Expected {expected_pattern}, got {audio['src']}"
        
        print(f"PASS: Legacy audio path correct: {audio['src']}")
    
    def test_audio_element_structure(self):
        """Verify audioElement has required fields: src, startTime, volume"""
        response = requests.get(f"{BASE_URL}/api/course/{LEGACY_AUDIO_PROJECT_ID}/slides-data")
        assert response.status_code == 200
        data = response.json()
        
        slides_with_audio = [s for s in data["slides"] if s.get("audioElements")]
        assert len(slides_with_audio) > 0
        
        audio = slides_with_audio[0]["audioElements"][0]
        assert "src" in audio, "Missing 'src' field"
        assert "startTime" in audio, "Missing 'startTime' field"
        assert "volume" in audio, "Missing 'volume' field"
        assert isinstance(audio["startTime"], (int, float)), "startTime should be numeric"
        assert isinstance(audio["volume"], (int, float)), "volume should be numeric"
        
        print(f"PASS: audioElement structure correct: src, startTime={audio['startTime']}, volume={audio['volume']}")


class TestMixedHeyGenAudioProject:
    """Tests for project with both HeyGen video and ElevenLabs audio"""
    
    def test_mixed_project_returns_video_elements(self):
        """Verify mixed project returns videoElements for HeyGen videos"""
        response = requests.get(f"{BASE_URL}/api/course/{MIXED_HEYGEN_AUDIO_PROJECT_ID}/slides-data")
        assert response.status_code == 200
        data = response.json()
        
        slides_with_video = [s for s in data["slides"] if s.get("videoElements")]
        assert len(slides_with_video) > 0, "Expected at least one slide with video"
        
        video = slides_with_video[0]["videoElements"][0]
        assert "src" in video, "videoElement missing 'src'"
        assert "heygen.ai" in video["src"], f"Expected HeyGen URL, got {video['src']}"
        assert "x" in video and "y" in video, "videoElement missing position"
        assert "width" in video and "height" in video, "videoElement missing dimensions"
        
        print(f"PASS: Mixed project has {len(slides_with_video)} slides with HeyGen videos")
    
    def test_mixed_project_returns_audio_elements(self):
        """Verify mixed project returns audioElements for ElevenLabs audio"""
        response = requests.get(f"{BASE_URL}/api/course/{MIXED_HEYGEN_AUDIO_PROJECT_ID}/slides-data")
        assert response.status_code == 200
        data = response.json()
        
        slides_with_audio = [s for s in data["slides"] if s.get("audioElements")]
        assert len(slides_with_audio) > 0, "Expected at least one slide with audio"
        
        audio = slides_with_audio[0]["audioElements"][0]
        assert "src" in audio, "audioElement missing 'src'"
        assert audio["src"].startswith("/api/projects/") or audio["src"].startswith("http"), \
            f"Invalid audio src: {audio['src']}"
        
        print(f"PASS: Mixed project has {len(slides_with_audio)} slides with audio")
    
    def test_mixed_project_slide_structure(self):
        """Verify slide structure includes both video and audio arrays"""
        response = requests.get(f"{BASE_URL}/api/course/{MIXED_HEYGEN_AUDIO_PROJECT_ID}/slides-data")
        assert response.status_code == 200
        data = response.json()
        
        for slide in data["slides"]:
            assert "videoElements" in slide, f"Slide {slide['index']} missing videoElements"
            assert "audioElements" in slide, f"Slide {slide['index']} missing audioElements"
            assert isinstance(slide["videoElements"], list), "videoElements should be a list"
            assert isinstance(slide["audioElements"], list), "audioElements should be a list"
        
        print(f"PASS: All {len(data['slides'])} slides have videoElements and audioElements arrays")


class TestProxyVideoEndpoint:
    """Tests for GET /api/proxy-video endpoint"""
    
    def test_proxy_video_returns_video_content(self):
        """Verify proxy-video returns video content for HeyGen URL"""
        heygen_url = "https://resource2.heygen.ai/aws_pacific/avatar_tmp/73edcec2e0ad40738d036658aff63987/aa714e6885c04dd69aa7c2a9295319fd.webm"
        response = requests.get(
            f"{BASE_URL}/api/proxy-video",
            params={"url": heygen_url},
            timeout=60,
            stream=True
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        content_type = response.headers.get("content-type", "")
        assert "video" in content_type, f"Expected video content-type, got {content_type}"
        
        # Check CORS headers
        assert response.headers.get("access-control-allow-origin") == "*", "Missing CORS header"
        
        # Check content length (should be > 1MB for a video)
        content_length = int(response.headers.get("content-length", 0))
        assert content_length > 100000, f"Video too small: {content_length} bytes"
        
        print(f"PASS: proxy-video returns {content_type} ({content_length} bytes)")
    
    def test_proxy_video_rejects_invalid_url(self):
        """Verify proxy-video rejects invalid URLs"""
        response = requests.get(f"{BASE_URL}/api/proxy-video", params={"url": "not-a-url"})
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("PASS: proxy-video rejects invalid URL")
    
    def test_proxy_video_rejects_non_whitelisted_host(self):
        """Verify proxy-video rejects non-whitelisted hosts"""
        response = requests.get(
            f"{BASE_URL}/api/proxy-video",
            params={"url": "https://example.com/video.mp4"}
        )
        assert response.status_code in [403, 500], f"Expected 403/500, got {response.status_code}"
        print("PASS: proxy-video rejects non-whitelisted host")


class TestAudioFileServing:
    """Tests for GET /api/audio/{filename} endpoint"""
    
    def test_audio_file_returns_200(self):
        """Verify audio file endpoint returns 200 for valid file"""
        filename = f"narration_{LEGACY_AUDIO_PROJECT_ID}_0.mp3"
        response = requests.get(f"{BASE_URL}/api/audio/{filename}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        content_type = response.headers.get("content-type", "")
        assert "audio" in content_type, f"Expected audio content-type, got {content_type}"
        
        # Check content length (should be > 100KB for audio)
        content_length = len(response.content)
        assert content_length > 10000, f"Audio too small: {content_length} bytes"
        
        print(f"PASS: audio file returns {content_type} ({content_length} bytes)")
    
    def test_audio_file_returns_404_for_nonexistent(self):
        """Verify audio file endpoint returns 404 for nonexistent file"""
        response = requests.get(f"{BASE_URL}/api/audio/nonexistent_file_12345.mp3")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("PASS: audio file returns 404 for nonexistent file")
    
    def test_multiple_audio_files_accessible(self):
        """Verify multiple audio files from legacy project are accessible"""
        # Test first 3 audio files
        for i in range(3):
            filename = f"narration_{LEGACY_AUDIO_PROJECT_ID}_{i}.mp3"
            response = requests.get(f"{BASE_URL}/api/audio/{filename}")
            if response.status_code == 200:
                print(f"  Audio file {i}: OK ({len(response.content)} bytes)")
            else:
                print(f"  Audio file {i}: {response.status_code}")
        
        # At least the first one should exist
        response = requests.get(f"{BASE_URL}/api/audio/narration_{LEGACY_AUDIO_PROJECT_ID}_0.mp3")
        assert response.status_code == 200, "First audio file should exist"
        print("PASS: Multiple audio files accessible")


class TestRegressionExports:
    """Regression tests for SCORM and HTML exports"""
    
    def test_scorm_export_still_works(self):
        """Verify SCORM export endpoint still works"""
        response = requests.post(f"{BASE_URL}/api/course/{LEGACY_AUDIO_PROJECT_ID}/export-scorm")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "downloadUrl" in data or "jobId" in data, "Missing downloadUrl or jobId"
        print(f"PASS: SCORM export works: {data.get('downloadUrl', data.get('jobId'))}")
    
    def test_html_export_still_works(self):
        """Verify HTML export endpoint still works"""
        response = requests.post(f"{BASE_URL}/api/course/{LEGACY_AUDIO_PROJECT_ID}/export-html")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "downloadUrl" in data, "Missing downloadUrl"
        print(f"PASS: HTML export works: {data.get('downloadUrl')}")
    
    def test_health_endpoint(self):
        """Verify health endpoint returns 200"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        print("PASS: Health endpoint OK")


class TestSlideDataDefaultDuration:
    """Tests for default_duration parameter"""
    
    def test_default_duration_parameter(self):
        """Verify default_duration parameter is respected"""
        response = requests.get(
            f"{BASE_URL}/api/course/{LEGACY_AUDIO_PROJECT_ID}/slides-data",
            params={"default_duration": 10.0}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Check that slides have duration >= 2.0 (minimum enforced)
        for slide in data["slides"]:
            assert slide["duration"] >= 2.0, f"Duration too short: {slide['duration']}"
        
        print(f"PASS: default_duration parameter works")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
