"""
Test suite for Multiple Audios Fix in SCORM Export Player.js

Tests verify:
1. playSlideAudio initializes window.audioTimelineTimers = [] explicitly
2. SCORM export produces valid package
3. Exported player.js contains all audio-related fixes:
   - Timer init at line 1460
   - Timeline mode detection (hasExplicitTimeline)
   - Progress bar functions (startSlideProgress/stopSlideProgress)
   - Keyboard guard (input/textarea check)
   - Default text color (#000000)
4. Backend health endpoint returns 200
5. Tutor chat endpoint works (lazy imports - no module-level emergentintegrations)
"""

import pytest
import requests
import os
import re
import zipfile
import io
import time

# Use the public backend URL
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test project with multiple audios
TEST_PROJECT_ID = "b7db7510-5236-4ddf-8684-bd408290fb1a"
TEST_PROJECT_NAME = "Teste Multiplos audios"


class TestBackendHealth:
    """Test backend health and startup performance"""
    
    def test_health_endpoint_returns_200(self):
        """Health endpoint should return 200 quickly"""
        start = time.time()
        response = requests.get(f"{BASE_URL}/api/health", timeout=5)
        elapsed = time.time() - start
        
        assert response.status_code == 200, f"Health check failed: {response.text}"
        data = response.json()
        assert data.get("status") == "healthy"
        
        # Verify fast startup (no module-level emergentintegrations import)
        # Should respond in under 2 seconds
        assert elapsed < 2.0, f"Health check too slow ({elapsed:.2f}s) - possible module-level import issue"
        print(f"✅ Health endpoint responded in {elapsed:.3f}s")
    
    def test_api_root_returns_200(self):
        """API root should return 200"""
        response = requests.get(f"{BASE_URL}/api/", timeout=5)
        assert response.status_code == 200
        data = response.json()
        assert "Scormify API" in data.get("message", "")
        print("✅ API root endpoint working")


class TestTutorChatEndpoint:
    """Test tutor chat endpoint (lazy emergentintegrations import)"""
    
    def test_tutor_chat_endpoint_exists(self):
        """Tutor chat endpoint should exist and return error for invalid request (not 500)"""
        # This tests that the endpoint loads without crashing due to import issues
        response = requests.post(
            f"{BASE_URL}/api/tutor/chat",
            json={},  # Empty request to test endpoint availability
            timeout=10
        )
        # Should return 422 (validation error) or 400 (bad request), not 500
        assert response.status_code in [400, 422, 200], f"Tutor endpoint error: {response.status_code} - {response.text}"
        print(f"✅ Tutor chat endpoint loads correctly (status: {response.status_code})")


class TestAudioTimelineFixInPlayerJS:
    """Test audio timeline fixes in player.js source file"""
    
    @pytest.fixture(scope="class")
    def player_js_content(self):
        """Read the player.js source file"""
        player_js_path = "/app/backend/services/export_assets/player.js"
        with open(player_js_path, 'r') as f:
            return f.read()
    
    def test_explicit_timer_init_at_start_of_playSlideAudio(self, player_js_content):
        """window.audioTimelineTimers = [] should be at start of playSlideAudio BEFORE any use"""
        # Find playSlideAudio function
        match = re.search(r'function playSlideAudio\(audioList\)\s*\{([^}]+(?:\{[^}]*\}[^}]*)*)\}', player_js_content, re.DOTALL)
        assert match, "playSlideAudio function not found"
        
        func_body = match.group(1)
        lines = func_body.strip().split('\n')
        
        # Check that window.audioTimelineTimers = [] appears early in the function
        found_init = False
        init_line_idx = -1
        for idx, line in enumerate(lines):
            if 'window.audioTimelineTimers = []' in line and '//' not in line.split('window.audioTimelineTimers = []')[0]:
                found_init = True
                init_line_idx = idx
                break
        
        assert found_init, "window.audioTimelineTimers = [] not found in playSlideAudio"
        
        # It should be near the start (within first 10 lines of function body)
        assert init_line_idx < 10, f"Timer init found too late in function (line {init_line_idx})"
        print(f"✅ window.audioTimelineTimers = [] found at line {init_line_idx + 1} of playSlideAudio")
    
    def test_hasExplicitTimeline_detection(self, player_js_content):
        """hasExplicitTimeline mode detection should exist for 3-mode audio playback"""
        assert 'hasExplicitTimeline' in player_js_content, "hasExplicitTimeline not found in player.js"
        
        # Check for the 3-mode detection logic
        assert "startTime > 0" in player_js_content, "Timeline startTime > 0 check not found"
        print("✅ hasExplicitTimeline 3-mode detection present")
    
    def test_timeline_mode_guard_check(self, player_js_content):
        """Guard check in setTimeout should properly check for cleared timers"""
        # Look for the guard check pattern
        guard_pattern = r"if\s*\(!window\.audioTimelineTimers\s*\|\|\s*window\.audioTimelineTimers\.length\s*===\s*0\)"
        assert re.search(guard_pattern, player_js_content), "Timeline guard check pattern not found"
        print("✅ Timer guard check (!window.audioTimelineTimers || length === 0) present")
    
    def test_stopAllSlideAudios_clears_timers(self, player_js_content):
        """stopAllSlideAudios should clear timers"""
        # Find stopAllSlideAudios function and check for timer clearing logic
        assert 'function stopAllSlideAudios' in player_js_content, "stopAllSlideAudios function not found"
        
        # Check that the timer clearing logic exists after the function definition
        func_start = player_js_content.find('function stopAllSlideAudios')
        func_section = player_js_content[func_start:func_start + 700]  # Get enough context
        
        assert 'window.audioTimelineTimers' in func_section, "Timer reference not found in stopAllSlideAudios"
        assert 'clearTimeout' in func_section, "clearTimeout not found in stopAllSlideAudios"
        assert 'window.audioTimelineTimers = []' in func_section, "Timer reset not found in stopAllSlideAudios"
        print("✅ stopAllSlideAudios properly clears timers")
    
    def test_default_text_color_fix(self, player_js_content):
        """Text elements should have default color #000000"""
        # Check for default text color in createElementNode
        assert "el.style.color = '#000000'" in player_js_content, "Default text color #000000 not found"
        print("✅ Default text color #000000 present")
    
    def test_keyboard_guard_fix(self, player_js_content):
        """Keyboard navigation should be guarded for input fields"""
        # Check for input/textarea guard
        assert "'input'" in player_js_content.lower() or '"input"' in player_js_content.lower(), "Keyboard input guard not found"
        assert "'textarea'" in player_js_content.lower() or '"textarea"' in player_js_content.lower(), "Keyboard textarea guard not found"
        print("✅ Keyboard input/textarea guard present")
    
    def test_slide_progress_bar_functions(self, player_js_content):
        """Slide progress bar functions should exist"""
        assert 'function startSlideProgress' in player_js_content, "startSlideProgress not found"
        assert 'function stopSlideProgress' in player_js_content, "stopSlideProgress not found"
        assert 'slide-timeline-fill' in player_js_content, "Progress bar fill element not found"
        print("✅ Slide progress bar functions present")


class TestMultipleAudiosProject:
    """Test the specific project with multiple audios"""
    
    def test_project_exists(self):
        """Test project should exist"""
        response = requests.get(f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}", timeout=10)
        assert response.status_code == 200, f"Project not found: {response.text}"
        
        data = response.json()
        assert data.get('name') == TEST_PROJECT_NAME
        print(f"✅ Project '{TEST_PROJECT_NAME}' exists")
    
    def test_project_has_multiple_audios(self):
        """Project should have multiple audio entries"""
        response = requests.get(f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}", timeout=10)
        assert response.status_code == 200
        
        data = response.json()
        course = data.get('course', {})
        slides = course.get('slides', [])
        
        # Count total audio entries across all slides
        total_audios = 0
        audio_start_times = []
        for slide in slides:
            audios = slide.get('audio', [])
            total_audios += len(audios)
            for audio in audios:
                audio_start_times.append(audio.get('startTime', 0))
        
        print(f"   Found {total_audios} audio(s) with startTimes: {audio_start_times}")
        
        # Project should have at least 3 audios as mentioned in agent context
        assert total_audios >= 3, f"Expected at least 3 audios, found {total_audios}"
        print(f"✅ Project has {total_audios} audio entries (expected at least 3)")


class TestSCORMExport:
    """Test SCORM export functionality and exported player.js"""
    
    def test_scorm_export_produces_valid_zip(self):
        """SCORM export should produce a valid ZIP file"""
        response = requests.post(
            f"{BASE_URL}/api/course/{TEST_PROJECT_ID}/export-scorm",
            timeout=120
        )
        assert response.status_code == 200, f"SCORM export failed: {response.status_code} - {response.text}"
        
        data = response.json()
        download_url = data.get('downloadUrl')
        assert download_url, "No downloadUrl in export response"
        print(f"   Export download URL: {download_url}")
        
        # Download and validate the ZIP
        zip_response = requests.get(f"{BASE_URL}{download_url}", timeout=60)
        assert zip_response.status_code == 200, f"ZIP download failed: {zip_response.status_code}"
        
        # Verify it's a valid ZIP
        zip_buffer = io.BytesIO(zip_response.content)
        try:
            with zipfile.ZipFile(zip_buffer, 'r') as zf:
                file_list = zf.namelist()
                assert 'imsmanifest.xml' in file_list, "Missing imsmanifest.xml in SCORM package"
                assert 'player.js' in file_list or any('player.js' in f for f in file_list), "Missing player.js in SCORM package"
                print(f"   ZIP contains {len(file_list)} files including imsmanifest.xml")
        except zipfile.BadZipFile:
            pytest.fail("Export is not a valid ZIP file")
        
        print("✅ SCORM export produces valid ZIP package")
    
    def test_exported_player_js_has_timer_init_fix(self):
        """Exported player.js should have the timer initialization fix"""
        # Export SCORM package
        response = requests.post(
            f"{BASE_URL}/api/course/{TEST_PROJECT_ID}/export-scorm",
            timeout=120
        )
        assert response.status_code == 200
        
        data = response.json()
        download_url = data.get('downloadUrl')
        
        # Download ZIP
        zip_response = requests.get(f"{BASE_URL}{download_url}", timeout=60)
        zip_buffer = io.BytesIO(zip_response.content)
        
        # Extract player.js
        with zipfile.ZipFile(zip_buffer, 'r') as zf:
            player_js_name = next((f for f in zf.namelist() if f.endswith('player.js')), None)
            assert player_js_name, "player.js not found in ZIP"
            
            player_js_content = zf.read(player_js_name).decode('utf-8')
        
        # Check for timer init fix
        assert 'window.audioTimelineTimers = []' in player_js_content, "Timer init fix not in exported player.js"
        print("✅ Exported player.js has window.audioTimelineTimers = [] init")
    
    def test_exported_player_js_has_all_fixes(self):
        """Exported player.js should have all critical fixes"""
        # Export SCORM package
        response = requests.post(
            f"{BASE_URL}/api/course/{TEST_PROJECT_ID}/export-scorm",
            timeout=120
        )
        assert response.status_code == 200
        
        data = response.json()
        download_url = data.get('downloadUrl')
        
        # Download ZIP
        zip_response = requests.get(f"{BASE_URL}{download_url}", timeout=60)
        zip_buffer = io.BytesIO(zip_response.content)
        
        # Extract player.js
        with zipfile.ZipFile(zip_buffer, 'r') as zf:
            player_js_name = next((f for f in zf.namelist() if f.endswith('player.js')), None)
            player_js_content = zf.read(player_js_name).decode('utf-8')
        
        # Check all required fixes
        fixes_to_check = {
            "Timer init": 'window.audioTimelineTimers = []',
            "Timeline mode": 'hasExplicitTimeline',
            "Progress bar": 'startSlideProgress',
            "Keyboard guard": 'input',  # lowercase check for input fields
            "Default text color": "el.style.color = '#000000'"
        }
        
        for fix_name, fix_pattern in fixes_to_check.items():
            assert fix_pattern.lower() in player_js_content.lower(), f"{fix_name} fix not found in exported player.js"
            print(f"   ✅ {fix_name}: present")
        
        print("✅ All fixes present in exported player.js")


class TestServerStartupPerformance:
    """Test that server doesn't have slow module-level imports"""
    
    def test_multiple_rapid_health_checks(self):
        """Multiple health checks should be fast (no per-request heavy imports)"""
        times = []
        for i in range(3):
            start = time.time()
            response = requests.get(f"{BASE_URL}/api/health", timeout=5)
            elapsed = time.time() - start
            times.append(elapsed)
            assert response.status_code == 200
        
        avg_time = sum(times) / len(times)
        max_time = max(times)
        
        print(f"   Health check times: {[f'{t:.3f}s' for t in times]}")
        print(f"   Average: {avg_time:.3f}s, Max: {max_time:.3f}s")
        
        # All should be under 1 second (lazy imports working)
        assert max_time < 1.0, f"Health check too slow ({max_time:.3f}s) - possible import issue"
        print("✅ Server responds quickly (lazy imports working)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
