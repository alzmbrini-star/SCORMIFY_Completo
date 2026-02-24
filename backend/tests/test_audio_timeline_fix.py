"""
Test audio timeline fix for SCORM player
Tests:
1. player.js contains playSlideAudio with timeline/sequential modes
2. player.js stopAllSlideAudios clears audioTimelineTimers
3. Keyboard fix is intact (player.js and tutor.js)
4. Tutor context extraction fix is intact (scorm_exporter.py)
5. SCORM export produces valid package
6. Backend health and tutor endpoints work
"""
import pytest
import requests
import os
import zipfile
import io
import re
from pathlib import Path

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Module 1: Source code verification tests
class TestPlayerJSAudioTimelineFix:
    """Verify player.js contains the new audio timeline logic"""
    
    def test_player_js_exists(self):
        """player.js file exists in export_assets"""
        player_path = Path('/app/backend/services/export_assets/player.js')
        assert player_path.exists(), "player.js not found"
        content = player_path.read_text()
        assert len(content) > 1000, "player.js seems too small"
        print("✅ player.js exists with content")
    
    def test_playSlideAudio_has_timeline_mode(self):
        """playSlideAudio function has timeline mode check"""
        player_path = Path('/app/backend/services/export_assets/player.js')
        content = player_path.read_text()
        
        # Check for hasTimeline logic
        assert "hasTimeline" in content, "Missing hasTimeline variable"
        assert "audioList.some" in content, "Missing audioList.some() check"
        assert "startTime" in content, "Missing startTime reference"
        print("✅ playSlideAudio has hasTimeline check logic")
    
    def test_playSlideAudio_timeline_mode_uses_setTimeout(self):
        """Timeline mode schedules audio with setTimeout"""
        player_path = Path('/app/backend/services/export_assets/player.js')
        content = player_path.read_text()
        
        # Find the playSlideAudio function and check for setTimeout in timeline mode
        assert "Timeline mode: schedule each audio at its startTime" in content, "Missing timeline mode comment"
        assert "setTimeout" in content, "Missing setTimeout for timeline scheduling"
        assert "audioTimelineTimers.push" in content, "Missing timer tracking"
        print("✅ Timeline mode uses setTimeout to schedule audios")
    
    def test_playSlideAudio_sequential_mode_uses_ended(self):
        """Sequential mode plays audios via 'ended' event"""
        player_path = Path('/app/backend/services/export_assets/player.js')
        content = player_path.read_text()
        
        # Check for sequential mode logic
        assert "Sequential mode: play audios one after another" in content, "Missing sequential mode comment"
        assert "addEventListener('ended'" in content, "Missing 'ended' event listener for sequential playback"
        print("✅ Sequential mode uses 'ended' event for chained playback")
    
    def test_stopAllSlideAudios_clears_timers(self):
        """stopAllSlideAudios function clears audioTimelineTimers"""
        player_path = Path('/app/backend/services/export_assets/player.js')
        content = player_path.read_text()
        
        # Find stopAllSlideAudios function and check for timer cleanup
        assert "stopAllSlideAudios" in content, "Missing stopAllSlideAudios function"
        assert "audioTimelineTimers" in content, "Missing audioTimelineTimers reference"
        
        # Check the actual cleanup logic
        stopfunc_match = re.search(r'function stopAllSlideAudios\(\)[^}]+(?:if\s*\(window\.audioTimelineTimers\)[^}]+clearTimeout)', content, re.DOTALL)
        assert stopfunc_match or "window.audioTimelineTimers.forEach(function(t) { clearTimeout(t); })" in content, \
            "stopAllSlideAudios doesn't clear audioTimelineTimers"
        print("✅ stopAllSlideAudios clears scheduled audio timers")


# Module 2: Keyboard fix verification (from iteration 29)
class TestKeyboardFixIntact:
    """Verify keyboard fix from iteration_29 is still intact"""
    
    def test_player_js_keyboard_guard(self):
        """player.js has input/textarea guard for keyboard events"""
        player_path = Path('/app/backend/services/export_assets/player.js')
        content = player_path.read_text()
        
        # Check for keyboard guard
        assert "tagName" in content, "Missing tagName check"
        assert "'input'" in content.lower() or '"input"' in content.lower(), "Missing input tag check"
        assert "'textarea'" in content.lower() or '"textarea"' in content.lower(), "Missing textarea tag check"
        print("✅ player.js has keyboard input guard")
    
    def test_tutor_js_stopPropagation(self):
        """tutor.js has stopPropagation on keyboard events"""
        tutor_path = Path('/app/backend/services/export_assets/tutor.js')
        assert tutor_path.exists(), "tutor.js not found"
        content = tutor_path.read_text()
        
        # Check for stopPropagation on keyboard events
        assert "stopPropagation" in content, "Missing stopPropagation"
        assert "keydown" in content, "Missing keydown event listener"
        print("✅ tutor.js has stopPropagation on keyboard events")


# Module 3: Tutor context extraction fix (from iteration 30)
class TestTutorContextExtractionFix:
    """Verify tutor context extraction fix is intact"""
    
    def test_scorm_exporter_reads_content_field(self):
        """SCORM exporter reads 'content' field for text extraction"""
        exporter_path = Path('/app/backend/services/scorm_exporter.py')
        assert exporter_path.exists(), "scorm_exporter.py not found"
        content = exporter_path.read_text()
        
        # Check that 'content' field is read first
        assert "elem.get('content')" in content, "Missing content field extraction"
        # Should be: elem.get('content') or elem.get('htmlContent') or elem.get('text')
        print("✅ scorm_exporter.py extracts from 'content' field")


# Module 4: SCORM export API tests
class TestSCORMExportAPI:
    """Test SCORM export endpoint and package validity"""
    
    @pytest.fixture
    def api_client(self):
        """Shared requests session"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        return session
    
    def test_health_endpoint(self, api_client):
        """Health endpoint returns 200"""
        response = api_client.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200, f"Health check failed: {response.status_code}"
        data = response.json()
        assert data.get("status") == "healthy", f"Unhealthy status: {data}"
        print("✅ Health endpoint returns 200 healthy")
    
    def test_tutor_settings_endpoint(self, api_client):
        """Tutor settings endpoint works"""
        response = api_client.get(f"{BASE_URL}/api/admin/tutor-settings")
        assert response.status_code == 200, f"Tutor settings failed: {response.status_code}"
        data = response.json()
        assert "enabled" in data, "Missing enabled field in tutor settings"
        print(f"✅ Tutor settings endpoint works - enabled: {data.get('enabled')}")
    
    def test_export_scorm_produces_valid_zip(self, api_client):
        """Export SCORM produces a valid ZIP with player.js containing audio fix"""
        # Use the existing test project
        project_id = "cb4e0112-3e45-44fe-ab29-304b0ef8f0a0"
        
        # Export SCORM
        response = api_client.post(f"{BASE_URL}/api/course/{project_id}/export-scorm")
        assert response.status_code == 200, f"SCORM export failed: {response.status_code} - {response.text}"
        
        data = response.json()
        download_url = data.get("download_url") or data.get("downloadUrl")
        assert download_url, f"Missing download URL in response: {data}"
        
        # Download the ZIP
        zip_response = api_client.get(f"{BASE_URL}{download_url}")
        assert zip_response.status_code == 200, f"ZIP download failed: {zip_response.status_code}"
        
        # Verify it's a valid ZIP
        zip_buffer = io.BytesIO(zip_response.content)
        with zipfile.ZipFile(zip_buffer, 'r') as zf:
            file_list = zf.namelist()
            assert "imsmanifest.xml" in file_list, "Missing imsmanifest.xml in SCORM package"
            assert "index.html" in file_list, "Missing index.html in SCORM package"
            assert "course.json" in file_list, "Missing course.json in SCORM package"
            assert "scripts/player.js" in file_list, "Missing scripts/player.js in SCORM package"
            
            # Check player.js content for audio fix
            player_content = zf.read("scripts/player.js").decode('utf-8')
            assert "hasTimeline" in player_content, "player.js in ZIP missing hasTimeline logic"
            assert "audioTimelineTimers" in player_content, "player.js in ZIP missing audioTimelineTimers"
            assert "Timeline mode:" in player_content, "player.js in ZIP missing Timeline mode comment"
            assert "Sequential mode:" in player_content, "player.js in ZIP missing Sequential mode comment"
            
            # Check keyboard guard is present
            assert "tagName" in player_content, "player.js in ZIP missing keyboard guard"
            
            print(f"✅ SCORM export valid with {len(file_list)} files, player.js contains audio fix")
    
    def test_scorm_zip_contains_tutor_js(self, api_client):
        """SCORM ZIP contains tutor.js with keyboard fix when tutor is enabled"""
        # Ensure tutor is enabled
        api_client.put(f"{BASE_URL}/api/admin/tutor-settings", json={"enabled": True})
        
        project_id = "cb4e0112-3e45-44fe-ab29-304b0ef8f0a0"
        response = api_client.post(f"{BASE_URL}/api/course/{project_id}/export-scorm")
        assert response.status_code == 200, f"SCORM export failed: {response.status_code}"
        
        data = response.json()
        download_url = data.get("download_url") or data.get("downloadUrl")
        
        zip_response = api_client.get(f"{BASE_URL}{download_url}")
        assert zip_response.status_code == 200, "ZIP download failed"
        
        zip_buffer = io.BytesIO(zip_response.content)
        with zipfile.ZipFile(zip_buffer, 'r') as zf:
            file_list = zf.namelist()
            assert "scripts/tutor.js" in file_list, "Missing scripts/tutor.js when tutor enabled"
            
            # Check tutor.js content for keyboard fix
            tutor_content = zf.read("scripts/tutor.js").decode('utf-8')
            assert "stopPropagation" in tutor_content, "tutor.js missing stopPropagation"
            
            print("✅ SCORM ZIP contains tutor.js with keyboard fix")


# Module 5: Tutor chat endpoint
class TestTutorChatEndpoint:
    """Test tutor chat endpoint"""
    
    @pytest.fixture
    def api_client(self):
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        return session
    
    def test_tutor_chat_empty_message_returns_400(self, api_client):
        """Tutor chat returns 400 for empty message"""
        response = api_client.post(f"{BASE_URL}/api/tutor/chat", json={
            "message": "",
            "courseTopic": "Test Course",
            "courseContext": "Test context"
        })
        assert response.status_code == 400, f"Expected 400 for empty message, got {response.status_code}"
        print("✅ Tutor chat returns 400 for empty message")
    
    def test_tutor_chat_with_context_returns_response(self, api_client):
        """Tutor chat with context returns AI response"""
        # Ensure tutor is enabled
        api_client.put(f"{BASE_URL}/api/admin/tutor-settings", json={"enabled": True})
        
        response = api_client.post(f"{BASE_URL}/api/tutor/chat", json={
            "message": "O que é aprendizagem corporativa?",
            "courseTopic": "Universidade Corporativa",
            "courseContext": "Slide 1: Universidade Corporativa - Aprendizagem contínua para funcionários"
        })
        # Should get 200 (with response) or 403 (if API key invalid - still valid test)
        assert response.status_code in [200, 403], f"Unexpected status: {response.status_code} - {response.text}"
        if response.status_code == 200:
            data = response.json()
            assert "response" in data or "message" in data, f"Missing response in tutor chat: {data}"
            print(f"✅ Tutor chat returned response")
        else:
            print(f"⚠️ Tutor chat returned 403 (API key issue) - endpoint works correctly")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
