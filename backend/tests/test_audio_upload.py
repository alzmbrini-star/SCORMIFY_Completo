"""
Test suite for Audio Upload functionality in Scormify
Tests:
- Slide audio upload (POST /api/projects/{project_id}/slides/{slide_id}/audio)
- Global audio upload (POST /api/projects/{project_id}/global-audio)
- Project listing (GET /api/projects)
- SCORM export (POST /api/course/{project_id}/export-scorm)
"""

import pytest
import requests
import os
import io
import wave
import struct

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
TEST_PROJECT_ID = "9e97f587-b940-4df0-bfeb-8414fffbc5c2"


def create_test_wav_file():
    """Create a simple WAV file in memory for testing"""
    # Create a simple WAV file
    sample_rate = 44100
    duration = 0.5  # 0.5 seconds
    frequency = 440  # Hz (A4 note)
    
    num_samples = int(sample_rate * duration)
    audio_data = []
    
    for i in range(num_samples):
        sample = int(32767 * 0.5 * (1 if (i * frequency / sample_rate) % 1 < 0.5 else -1))
        audio_data.append(struct.pack('<h', sample))
    
    wav_buffer = io.BytesIO()
    with wave.open(wav_buffer, 'wb') as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(b''.join(audio_data))
    
    wav_buffer.seek(0)
    return wav_buffer


def create_test_mp3_file():
    """Create a minimal MP3-like file for testing (just header bytes)"""
    # Minimal MP3 header for testing purposes
    mp3_buffer = io.BytesIO()
    # MP3 frame header (sync word + basic header)
    mp3_buffer.write(b'\xff\xfb\x90\x00' * 100)  # Simple MP3 frame pattern
    mp3_buffer.seek(0)
    return mp3_buffer


class TestHealthAndProjects:
    """Basic API health and project listing tests"""
    
    def test_api_health(self):
        """Test API health endpoint"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy"
        print("✅ API health check passed")
    
    def test_list_projects(self):
        """Test listing all projects"""
        response = requests.get(f"{BASE_URL}/api/projects")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✅ List projects passed - Found {len(data)} projects")
    
    def test_get_test_project(self):
        """Test getting the test project"""
        response = requests.get(f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}")
        assert response.status_code == 200
        data = response.json()
        assert data.get("id") == TEST_PROJECT_ID
        assert "course" in data
        assert "slides" in data.get("course", {})
        print(f"✅ Get test project passed - Project: {data.get('name')}")


class TestSlideAudioUpload:
    """Tests for slide-specific audio upload"""
    
    def test_upload_slide_audio_wav(self):
        """Test uploading WAV audio to a specific slide"""
        # Get project to find a slide ID
        response = requests.get(f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}")
        assert response.status_code == 200
        project = response.json()
        
        slides = project.get("course", {}).get("slides", [])
        assert len(slides) > 0, "Project must have at least one slide"
        
        # Use the second slide (index 1) to avoid conflicts with existing audio
        slide_id = slides[1]["id"] if len(slides) > 1 else slides[0]["id"]
        
        # Create test WAV file
        wav_file = create_test_wav_file()
        
        # Upload audio
        files = {"file": ("test_audio.wav", wav_file, "audio/wav")}
        data = {"audio_type": "narration"}
        
        response = requests.post(
            f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/slides/{slide_id}/audio",
            files=files,
            data=data
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        audio_data = response.json()
        
        # Verify response structure
        assert "id" in audio_data
        assert "src" in audio_data
        assert "filename" in audio_data
        assert audio_data.get("type") == "narration"
        
        print(f"✅ Slide audio upload (WAV) passed - Audio ID: {audio_data.get('id')}")
        return audio_data
    
    def test_upload_slide_audio_mp3(self):
        """Test uploading MP3 audio to a specific slide"""
        # Get project to find a slide ID
        response = requests.get(f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}")
        assert response.status_code == 200
        project = response.json()
        
        slides = project.get("course", {}).get("slides", [])
        assert len(slides) > 2, "Project must have at least 3 slides"
        
        slide_id = slides[2]["id"]
        
        # Create test MP3 file
        mp3_file = create_test_mp3_file()
        
        # Upload audio
        files = {"file": ("test_audio.mp3", mp3_file, "audio/mpeg")}
        data = {"audio_type": "background"}
        
        response = requests.post(
            f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/slides/{slide_id}/audio",
            files=files,
            data=data
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        audio_data = response.json()
        
        assert "id" in audio_data
        assert audio_data.get("type") == "background"
        
        print(f"✅ Slide audio upload (MP3) passed - Audio ID: {audio_data.get('id')}")
        return audio_data
    
    def test_upload_slide_audio_invalid_format(self):
        """Test uploading invalid audio format should fail"""
        response = requests.get(f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}")
        project = response.json()
        slide_id = project.get("course", {}).get("slides", [])[0]["id"]
        
        # Create a fake text file
        fake_file = io.BytesIO(b"This is not an audio file")
        
        files = {"file": ("test.txt", fake_file, "text/plain")}
        data = {"audio_type": "narration"}
        
        response = requests.post(
            f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/slides/{slide_id}/audio",
            files=files,
            data=data
        )
        
        assert response.status_code == 400, f"Expected 400 for invalid format, got {response.status_code}"
        print("✅ Invalid audio format rejection passed")
    
    def test_upload_slide_audio_nonexistent_slide(self):
        """Test uploading audio to non-existent slide should fail"""
        wav_file = create_test_wav_file()
        
        files = {"file": ("test_audio.wav", wav_file, "audio/wav")}
        data = {"audio_type": "narration"}
        
        response = requests.post(
            f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/slides/nonexistent-slide-id/audio",
            files=files,
            data=data
        )
        
        assert response.status_code == 404, f"Expected 404 for non-existent slide, got {response.status_code}"
        print("✅ Non-existent slide rejection passed")
    
    def test_upload_slide_audio_nonexistent_project(self):
        """Test uploading audio to non-existent project should fail"""
        wav_file = create_test_wav_file()
        
        files = {"file": ("test_audio.wav", wav_file, "audio/wav")}
        data = {"audio_type": "narration"}
        
        response = requests.post(
            f"{BASE_URL}/api/projects/nonexistent-project-id/slides/some-slide-id/audio",
            files=files,
            data=data
        )
        
        assert response.status_code == 404, f"Expected 404 for non-existent project, got {response.status_code}"
        print("✅ Non-existent project rejection passed")


class TestGlobalAudioUpload:
    """Tests for global audio/soundtrack upload"""
    
    def test_upload_global_audio_wav(self):
        """Test uploading global soundtrack (WAV)"""
        wav_file = create_test_wav_file()
        
        files = {"file": ("global_soundtrack.wav", wav_file, "audio/wav")}
        
        response = requests.post(
            f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/global-audio",
            files=files
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        audio_data = response.json()
        
        # Verify response structure
        assert "id" in audio_data
        assert "src" in audio_data
        assert "filename" in audio_data
        assert audio_data.get("loop") == True
        assert audio_data.get("volume") == 0.5
        
        print(f"✅ Global audio upload (WAV) passed - Audio ID: {audio_data.get('id')}")
        return audio_data
    
    def test_upload_global_audio_mp3(self):
        """Test uploading global soundtrack (MP3)"""
        mp3_file = create_test_mp3_file()
        
        files = {"file": ("global_soundtrack.mp3", mp3_file, "audio/mpeg")}
        
        response = requests.post(
            f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/global-audio",
            files=files
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        audio_data = response.json()
        
        assert "id" in audio_data
        assert "src" in audio_data
        
        print(f"✅ Global audio upload (MP3) passed - Audio ID: {audio_data.get('id')}")
        return audio_data
    
    def test_upload_global_audio_invalid_format(self):
        """Test uploading invalid format for global audio should fail"""
        fake_file = io.BytesIO(b"This is not an audio file")
        
        files = {"file": ("test.txt", fake_file, "text/plain")}
        
        response = requests.post(
            f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/global-audio",
            files=files
        )
        
        assert response.status_code == 400, f"Expected 400 for invalid format, got {response.status_code}"
        print("✅ Invalid global audio format rejection passed")
    
    def test_upload_global_audio_nonexistent_project(self):
        """Test uploading global audio to non-existent project should fail"""
        wav_file = create_test_wav_file()
        
        files = {"file": ("global_soundtrack.wav", wav_file, "audio/wav")}
        
        response = requests.post(
            f"{BASE_URL}/api/projects/nonexistent-project-id/global-audio",
            files=files
        )
        
        assert response.status_code == 404, f"Expected 404 for non-existent project, got {response.status_code}"
        print("✅ Non-existent project rejection for global audio passed")


class TestAudioPersistence:
    """Tests to verify audio data is persisted correctly"""
    
    def test_slide_audio_persisted(self):
        """Test that uploaded slide audio is persisted in project data"""
        # Get project
        response = requests.get(f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}")
        assert response.status_code == 200
        project = response.json()
        
        slides = project.get("course", {}).get("slides", [])
        
        # Check if any slide has audio
        slides_with_audio = [s for s in slides if s.get("audio") and len(s.get("audio", [])) > 0]
        
        assert len(slides_with_audio) > 0, "At least one slide should have audio after upload tests"
        
        # Verify audio structure
        for slide in slides_with_audio:
            for audio in slide.get("audio", []):
                assert "id" in audio
                assert "src" in audio
                assert "type" in audio
        
        print(f"✅ Slide audio persistence verified - {len(slides_with_audio)} slides have audio")
    
    def test_global_audio_persisted(self):
        """Test that uploaded global audio is persisted in project data"""
        response = requests.get(f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}")
        assert response.status_code == 200
        project = response.json()
        
        global_audio = project.get("course", {}).get("globalAudio")
        
        assert global_audio is not None, "Global audio should be set after upload tests"
        assert "id" in global_audio
        assert "src" in global_audio
        assert "filename" in global_audio
        
        print(f"✅ Global audio persistence verified - Filename: {global_audio.get('filename')}")


class TestSCORMExport:
    """Tests for SCORM export functionality"""
    
    def test_scorm_export(self):
        """Test SCORM package export"""
        response = requests.post(f"{BASE_URL}/api/course/{TEST_PROJECT_ID}/export-scorm")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "jobId" in data
        assert "downloadUrl" in data
        
        # Verify download URL is accessible
        download_url = f"{BASE_URL}{data['downloadUrl']}"
        download_response = requests.head(download_url)
        assert download_response.status_code == 200, f"Download URL not accessible: {download_url}"
        
        print(f"✅ SCORM export passed - Download URL: {data.get('downloadUrl')}")
    
    def test_scorm_export_nonexistent_project(self):
        """Test SCORM export for non-existent project should fail"""
        response = requests.post(f"{BASE_URL}/api/course/nonexistent-project-id/export-scorm")
        
        assert response.status_code == 404, f"Expected 404 for non-existent project, got {response.status_code}"
        print("✅ Non-existent project SCORM export rejection passed")


class TestAudioAssetServing:
    """Tests for serving audio assets"""
    
    def test_serve_audio_asset(self):
        """Test that audio assets can be served"""
        # Get project to find audio asset
        response = requests.get(f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}")
        assert response.status_code == 200
        project = response.json()
        
        global_audio = project.get("course", {}).get("globalAudio")
        
        if global_audio and global_audio.get("src"):
            asset_url = f"{BASE_URL}{global_audio['src']}"
            asset_response = requests.head(asset_url)
            assert asset_response.status_code == 200, f"Audio asset not accessible: {asset_url}"
            print(f"✅ Audio asset serving passed - URL: {global_audio['src']}")
        else:
            # Check slide audio
            slides = project.get("course", {}).get("slides", [])
            for slide in slides:
                for audio in slide.get("audio", []):
                    if audio.get("src"):
                        asset_url = f"{BASE_URL}{audio['src']}"
                        asset_response = requests.head(asset_url)
                        assert asset_response.status_code == 200, f"Audio asset not accessible: {asset_url}"
                        print(f"✅ Audio asset serving passed - URL: {audio['src']}")
                        return
            
            pytest.skip("No audio assets found to test")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
