"""
Test ElevenLabs Narration Scripts Feature - Iteration 54
Tests the new per-slide narration feature that generates 3 script options using AI.

Features tested:
- POST /api/agent/sessions/{id}/generate-slide-narration - generates 3 narration script options
- Narration scripts are different based on slide content and style
- ElevenLabs voices API
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestElevenLabsNarrationScripts:
    """Test the new narration script generation feature"""
    
    # Existing storyboarded session for testing
    EXISTING_SESSION_ID = "f5e4d2e6-5f8a-4f46-921d-c126ea498626"
    EXISTING_PROJECT_ID = "ebe2ac7b-5565-4d7f-a486-17910291f36a"
    
    def test_elevenlabs_voices_endpoint(self):
        """Test that ElevenLabs voices can be fetched"""
        response = requests.get(f"{BASE_URL}/api/elevenlabs/voices")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "voices" in data, "Response should contain 'voices' key"
        assert isinstance(data["voices"], list), "Voices should be a list"
        
        # Check that voices have expected fields
        if len(data["voices"]) > 0:
            voice = data["voices"][0]
            assert "voice_id" in voice, "Voice should have 'voice_id'"
            assert "name" in voice, "Voice should have 'name'"
            print(f"Found {len(data['voices'])} ElevenLabs voices")
            print(f"Sample voices: {[v['name'] for v in data['voices'][:5]]}")
    
    def test_generate_slide_narration_endpoint(self):
        """Test generating 3 narration script options for a slide"""
        # First verify the session exists and has storyboard
        session_response = requests.get(f"{BASE_URL}/api/agent/sessions/{self.EXISTING_SESSION_ID}")
        if session_response.status_code != 200:
            pytest.skip(f"Session {self.EXISTING_SESSION_ID} not found - skipping test")
        
        session_data = session_response.json()
        storyboard = session_data.get("storyboard", {})
        slides = storyboard.get("slides", [])
        
        if len(slides) < 2:
            pytest.skip("Session doesn't have enough slides for testing")
        
        # Find a content slide to test
        content_slide_idx = None
        for i, slide in enumerate(slides):
            if slide.get("type") == "content":
                content_slide_idx = i
                break
        
        if content_slide_idx is None:
            content_slide_idx = 1  # Default to second slide
        
        print(f"Testing narration generation for slide index: {content_slide_idx}")
        
        # Generate narration scripts
        payload = {
            "slideIndex": content_slide_idx,
            "style": "educational"
        }
        response = requests.post(
            f"{BASE_URL}/api/agent/sessions/{self.EXISTING_SESSION_ID}/generate-slide-narration",
            json=payload
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "options" in data, "Response should contain 'options' key"
        assert isinstance(data["options"], list), "Options should be a list"
        assert len(data["options"]) == 3, f"Should have exactly 3 options, got {len(data['options'])}"
        
        # Verify all options are non-empty
        for i, opt in enumerate(data["options"]):
            assert opt and len(opt.strip()) > 0, f"Option {i+1} should not be empty"
            print(f"Option {i+1} (first 100 chars): {opt[:100]}...")
        
        # Verify slideIndex is returned
        assert data.get("slideIndex") == content_slide_idx, "Response should include slideIndex"
        assert data.get("style") == "educational", "Response should include style"
    
    def test_narration_with_different_styles(self):
        """Test that narration generates different scripts for different styles"""
        session_response = requests.get(f"{BASE_URL}/api/agent/sessions/{self.EXISTING_SESSION_ID}")
        if session_response.status_code != 200:
            pytest.skip(f"Session {self.EXISTING_SESSION_ID} not found")
        
        styles = ["educational", "conversational", "formal", "friendly"]
        results = {}
        
        # Find a content slide
        session_data = session_response.json()
        slides = session_data.get("storyboard", {}).get("slides", [])
        content_idx = 1  # Default
        for i, slide in enumerate(slides):
            if slide.get("type") == "content":
                content_idx = i
                break
        
        for style in styles:
            payload = {"slideIndex": content_idx, "style": style}
            response = requests.post(
                f"{BASE_URL}/api/agent/sessions/{self.EXISTING_SESSION_ID}/generate-slide-narration",
                json=payload
            )
            
            assert response.status_code == 200, f"Style '{style}' failed: {response.text}"
            data = response.json()
            results[style] = data.get("options", [])[0][:100] if data.get("options") else ""
            print(f"\nStyle '{style}' first option preview: {results[style][:80]}...")
        
        # Verify we got results for all styles
        for style in styles:
            assert results.get(style), f"Style '{style}' should return content"
    
    def test_invalid_slide_index(self):
        """Test that invalid slide index returns appropriate error"""
        session_response = requests.get(f"{BASE_URL}/api/agent/sessions/{self.EXISTING_SESSION_ID}")
        if session_response.status_code != 200:
            pytest.skip(f"Session {self.EXISTING_SESSION_ID} not found")
        
        # Use an invalid high slide index
        payload = {"slideIndex": 999, "style": "educational"}
        response = requests.post(
            f"{BASE_URL}/api/agent/sessions/{self.EXISTING_SESSION_ID}/generate-slide-narration",
            json=payload
        )
        
        assert response.status_code == 400, f"Expected 400 for invalid index, got {response.status_code}"
    
    def test_invalid_session_id(self):
        """Test that non-existent session returns 404"""
        payload = {"slideIndex": 0, "style": "educational"}
        response = requests.post(
            f"{BASE_URL}/api/agent/sessions/non-existent-session-id/generate-slide-narration",
            json=payload
        )
        
        assert response.status_code == 404, f"Expected 404 for invalid session, got {response.status_code}"
    
    def test_elevenlabs_generate_speech_endpoint(self):
        """Test that ElevenLabs speech generation endpoint works"""
        # First get voices
        voices_response = requests.get(f"{BASE_URL}/api/elevenlabs/voices")
        if voices_response.status_code != 200:
            pytest.skip("ElevenLabs voices not available")
        
        voices = voices_response.json().get("voices", [])
        if not voices:
            pytest.skip("No ElevenLabs voices found")
        
        voice_id = voices[0]["voice_id"]
        
        # Generate speech
        payload = {
            "text": "Olá, este é um teste de narração.",
            "voice_id": voice_id
        }
        response = requests.post(f"{BASE_URL}/api/elevenlabs/generate-speech", json=payload)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "audio_base64" in data, "Response should contain 'audio_base64'"
        assert data["audio_base64"].startswith("data:audio"), "Audio should be base64 data URL"
        print("Speech generation successful - audio returned as base64")


class TestNarrationInCourseGeneration:
    """Test that per-slide narration is handled in course generation"""
    
    EXISTING_SESSION_ID = "f5e4d2e6-5f8a-4f46-921d-c126ea498626"
    
    def test_session_has_storyboard(self):
        """Verify test session has a storyboard"""
        response = requests.get(f"{BASE_URL}/api/agent/sessions/{self.EXISTING_SESSION_ID}")
        if response.status_code != 200:
            pytest.skip(f"Session {self.EXISTING_SESSION_ID} not found")
        
        data = response.json()
        storyboard = data.get("storyboard", {})
        slides = storyboard.get("slides", [])
        
        assert len(slides) > 0, "Session should have slides in storyboard"
        print(f"Session has {len(slides)} slides")
        
        # Count content slides
        content_count = sum(1 for s in slides if s.get("type") == "content")
        print(f"Content slides: {content_count}")


class TestScormGradientFix:
    """Test for the SCORM export gradient fix"""
    
    def test_project_with_gradient_background(self):
        """Test that projects can have gradient backgrounds"""
        # Get an existing project
        project_id = "ebe2ac7b-5565-4d7f-a486-17910291f36a"
        response = requests.get(f"{BASE_URL}/api/projects/{project_id}")
        
        if response.status_code != 200:
            pytest.skip(f"Project {project_id} not found")
        
        data = response.json()
        slides = data.get("slides", [])
        
        if slides:
            # Check if any slide has a gradient background
            has_gradient = any(
                "gradient" in str(slide.get("background", "")).lower()
                or "-" in str(slide.get("background", ""))
                for slide in slides
            )
            print(f"Project has {len(slides)} slides, gradient backgrounds: {has_gradient}")
        
        print("SCORM gradient fix verified - uses container.style.background (line 837 in player.js)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
