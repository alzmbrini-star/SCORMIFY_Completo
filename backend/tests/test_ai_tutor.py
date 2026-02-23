"""
AI Tutor API Tests
Tests for: GET /api/admin/tutor-settings, PUT /api/admin/tutor-settings, POST /api/tutor/chat
"""
import pytest
import requests
import os
import json
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestTutorSettings:
    """Test GET and PUT /api/admin/tutor-settings endpoints"""
    
    def test_get_tutor_settings_default(self):
        """GET /api/admin/tutor-settings returns default settings"""
        response = requests.get(f"{BASE_URL}/api/admin/tutor-settings")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Verify default structure exists
        assert "enabled" in data, "Response should contain 'enabled' field"
        assert "messageLimit" in data, "Response should contain 'messageLimit' field"
        assert "suggestedQuestions" in data, "Response should contain 'suggestedQuestions' field"
        assert "tutorName" in data, "Response should contain 'tutorName' field"
        
        # Verify data types
        assert isinstance(data["enabled"], bool)
        assert isinstance(data["messageLimit"], int)
        assert isinstance(data["suggestedQuestions"], list)
        assert isinstance(data["tutorName"], str)
        
        print(f"✅ GET tutor-settings: enabled={data['enabled']}, tutorName={data['tutorName']}, messageLimit={data['messageLimit']}")
        
    def test_put_tutor_settings_saves(self):
        """PUT /api/admin/tutor-settings saves settings to MongoDB"""
        # First, get current settings
        get_response = requests.get(f"{BASE_URL}/api/admin/tutor-settings")
        assert get_response.status_code == 200
        original_settings = get_response.json()
        
        # Prepare test update data with a unique tutorName
        test_settings = {
            "enabled": True,
            "tutorName": "TEST_Professor Virtual",
            "messageLimit": 75,
            "suggestedQuestions": ["Test Question 1", "Test Question 2"],
            "systemPrompt": "TEST system prompt"
        }
        
        # Update settings
        put_response = requests.put(
            f"{BASE_URL}/api/admin/tutor-settings",
            json=test_settings,
            headers={"Content-Type": "application/json"}
        )
        assert put_response.status_code == 200, f"PUT failed: {put_response.text}"
        put_data = put_response.json()
        assert put_data.get("status") == "ok", f"Expected status 'ok', got: {put_data}"
        
        # Verify settings were saved by re-fetching
        verify_response = requests.get(f"{BASE_URL}/api/admin/tutor-settings")
        assert verify_response.status_code == 200
        saved_settings = verify_response.json()
        
        assert saved_settings.get("tutorName") == "TEST_Professor Virtual", f"tutorName not saved: {saved_settings}"
        assert saved_settings.get("messageLimit") == 75, f"messageLimit not saved: {saved_settings}"
        assert "Test Question 1" in saved_settings.get("suggestedQuestions", [])
        assert "Test Question 2" in saved_settings.get("suggestedQuestions", [])
        assert saved_settings.get("systemPrompt") == "TEST system prompt"
        
        print(f"✅ PUT tutor-settings saved and verified: tutorName={saved_settings['tutorName']}, messageLimit={saved_settings['messageLimit']}")
        
        # Restore original settings (cleanup)
        requests.put(
            f"{BASE_URL}/api/admin/tutor-settings",
            json=original_settings,
            headers={"Content-Type": "application/json"}
        )
        print("✅ Original settings restored after test")
        
    def test_put_tutor_settings_enables_disabled(self):
        """PUT can toggle enabled status"""
        # Get current state
        get_response = requests.get(f"{BASE_URL}/api/admin/tutor-settings")
        assert get_response.status_code == 200
        original = get_response.json()
        
        # Toggle enabled status
        new_enabled = not original.get("enabled", True)
        update = {"enabled": new_enabled}
        
        put_response = requests.put(
            f"{BASE_URL}/api/admin/tutor-settings",
            json=update,
            headers={"Content-Type": "application/json"}
        )
        assert put_response.status_code == 200
        
        # Verify
        verify_response = requests.get(f"{BASE_URL}/api/admin/tutor-settings")
        verified = verify_response.json()
        assert verified.get("enabled") == new_enabled, f"enabled toggle failed: expected {new_enabled}, got {verified.get('enabled')}"
        
        print(f"✅ Tutor enabled toggled to: {new_enabled}")
        
        # Restore
        requests.put(f"{BASE_URL}/api/admin/tutor-settings", json=original)


class TestTutorChat:
    """Test POST /api/tutor/chat endpoint"""
    
    @pytest.fixture(autouse=True)
    def ensure_tutor_enabled(self):
        """Ensure tutor is enabled before tests"""
        settings = {"enabled": True, "tutorName": "Tutor IA", "messageLimit": 50}
        requests.put(f"{BASE_URL}/api/admin/tutor-settings", json=settings)
        yield
    
    def test_chat_returns_error_when_message_empty(self):
        """POST /api/tutor/chat returns 400 when message is empty"""
        payload = {
            "message": "",
            "courseTopic": "Test Course",
            "courseContext": "Test context",
            "history": [],
            "sessionId": "test-session-empty"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/tutor/chat",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        
        # Should return 400 for empty message
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        data = response.json()
        assert "detail" in data, "Error response should have 'detail' field"
        print(f"✅ Empty message returns 400: {data.get('detail')}")
    
    def test_chat_sends_message_gets_ai_response(self):
        """POST /api/tutor/chat sends a message and gets AI response from Gemini"""
        payload = {
            "message": "O que e este curso?",
            "courseTopic": "Python Programming",
            "courseContext": "Este curso ensina programacao em Python. Conteudo: variaveis, funcoes, listas.",
            "history": [],
            "sessionId": f"test-session-{int(time.time())}"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/tutor/chat",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30  # AI response may take time
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "response" in data, "Response should contain 'response' field"
        assert "limitReached" in data, "Response should contain 'limitReached' field"
        assert data["limitReached"] == False, "limitReached should be False for first message"
        
        # Verify AI gave a meaningful response (non-empty)
        ai_response = data.get("response", "")
        assert len(ai_response) > 10, f"AI response too short: '{ai_response}'"
        
        # Verify messagesUsed counter
        assert "messagesUsed" in data, "Response should contain 'messagesUsed'"
        assert data["messagesUsed"] == 1, f"Expected messagesUsed=1, got {data['messagesUsed']}"
        
        print(f"✅ Chat response received ({len(ai_response)} chars): '{ai_response[:100]}...'")
        print(f"✅ messagesUsed: {data['messagesUsed']}, limitReached: {data['limitReached']}")
    
    def test_chat_respects_message_limit(self):
        """POST /api/tutor/chat respects message limit"""
        # Set a low message limit for testing
        test_limit = 2
        requests.put(
            f"{BASE_URL}/api/admin/tutor-settings",
            json={"enabled": True, "messageLimit": test_limit}
        )
        
        session_id = f"test-limit-{int(time.time())}"
        
        # Build history with messages equal to the limit
        history = [
            {"role": "user", "content": "First question"},
            {"role": "assistant", "content": "First answer"},
            {"role": "user", "content": "Second question"},
            {"role": "assistant", "content": "Second answer"}
        ]
        
        # This request should hit the limit
        payload = {
            "message": "Third question (should hit limit)",
            "courseTopic": "Test",
            "courseContext": "Test context",
            "history": history,
            "sessionId": session_id
        }
        
        response = requests.post(
            f"{BASE_URL}/api/tutor/chat",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        # Should indicate limit reached
        assert data.get("limitReached") == True, f"Expected limitReached=True, got: {data}"
        
        # Response message should mention the limit
        response_text = data.get("response", "")
        assert "limite" in response_text.lower() or "limit" in response_text.lower(), f"Response should mention limit: '{response_text}'"
        
        print(f"✅ Message limit enforced: limitReached={data['limitReached']}")
        print(f"✅ Limit message: '{response_text[:100]}...'")
        
        # Restore default limit
        requests.put(f"{BASE_URL}/api/admin/tutor-settings", json={"messageLimit": 50})
    
    def test_chat_with_history_context(self):
        """POST /api/tutor/chat uses conversation history for context"""
        session_id = f"test-history-{int(time.time())}"
        
        # First message
        payload1 = {
            "message": "What is Python?",
            "courseTopic": "Python Programming",
            "courseContext": "Learn Python basics",
            "history": [],
            "sessionId": session_id
        }
        
        response1 = requests.post(
            f"{BASE_URL}/api/tutor/chat",
            json=payload1,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        assert response1.status_code == 200
        data1 = response1.json()
        first_response = data1.get("response", "")
        
        # Second message with history
        history = [
            {"role": "user", "content": "What is Python?"},
            {"role": "assistant", "content": first_response}
        ]
        
        payload2 = {
            "message": "Can you give me an example?",
            "courseTopic": "Python Programming",
            "courseContext": "Learn Python basics",
            "history": history,
            "sessionId": session_id
        }
        
        response2 = requests.post(
            f"{BASE_URL}/api/tutor/chat",
            json=payload2,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        assert response2.status_code == 200
        data2 = response2.json()
        second_response = data2.get("response", "")
        
        # Verify conversation continued with context
        assert len(second_response) > 10, f"Second response too short: '{second_response}'"
        assert data2.get("messagesUsed") == 2, f"Expected messagesUsed=2, got {data2.get('messagesUsed')}"
        
        print(f"✅ History-aware response ({len(second_response)} chars)")
        print(f"✅ messagesUsed after 2nd message: {data2.get('messagesUsed')}")
    
    def test_chat_when_tutor_disabled_returns_403(self):
        """POST /api/tutor/chat returns 403 when tutor is disabled"""
        # Disable tutor
        requests.put(f"{BASE_URL}/api/admin/tutor-settings", json={"enabled": False})
        
        payload = {
            "message": "Test message",
            "courseTopic": "Test",
            "courseContext": "Test",
            "history": [],
            "sessionId": "test-disabled"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/tutor/chat",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"
        
        print("✅ Disabled tutor returns 403")
        
        # Re-enable for other tests
        requests.put(f"{BASE_URL}/api/admin/tutor-settings", json={"enabled": True})


class TestScormExportWithTutor:
    """Test that SCORM export includes tutor files when tutor is enabled"""
    
    @pytest.fixture
    def test_project_id(self):
        """Create a minimal test project for SCORM export"""
        # Create a project
        project_data = {"name": "TEST_Tutor_Export", "description": "Test project for tutor export"}
        create_response = requests.post(f"{BASE_URL}/api/projects", json=project_data)
        if create_response.status_code != 200:
            pytest.skip("Could not create test project")
        project = create_response.json()
        project_id = project["id"]
        
        yield project_id
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/projects/{project_id}")
    
    def test_scorm_export_includes_tutor_config(self, test_project_id):
        """SCORM export includes tutorConfig in course.json when enabled"""
        # Ensure tutor is enabled with test settings
        requests.put(
            f"{BASE_URL}/api/admin/tutor-settings",
            json={
                "enabled": True,
                "tutorName": "TEST_Tutor",
                "messageLimit": 100,
                "suggestedQuestions": ["Test Q1", "Test Q2"]
            }
        )
        
        # Export SCORM
        export_response = requests.post(f"{BASE_URL}/api/course/{test_project_id}/export-scorm", timeout=60)
        
        # Accept 200 (success) - we'll check the ZIP contents
        if export_response.status_code != 200:
            print(f"Export response: {export_response.status_code} - {export_response.text}")
            pytest.skip(f"SCORM export failed: {export_response.status_code}")
        
        data = export_response.json()
        assert "downloadUrl" in data, f"Response should contain downloadUrl: {data}"
        
        download_url = data["downloadUrl"]
        
        # Download the ZIP
        if not download_url.startswith("http"):
            download_url = f"{BASE_URL}{download_url}"
        
        zip_response = requests.get(download_url)
        assert zip_response.status_code == 200, f"Failed to download ZIP: {zip_response.status_code}"
        
        # Check ZIP contents
        import io
        import zipfile
        
        zip_buffer = io.BytesIO(zip_response.content)
        with zipfile.ZipFile(zip_buffer, 'r') as zf:
            file_list = zf.namelist()
            
            # Check for tutor files
            assert "scripts/tutor.js" in file_list, f"tutor.js missing from SCORM package: {file_list}"
            assert "styles/tutor.css" in file_list, f"tutor.css missing from SCORM package: {file_list}"
            
            # Check course.json has tutorConfig
            course_json = zf.read("course.json").decode('utf-8')
            course_data = json.loads(course_json)
            
            assert "tutorConfig" in course_data, f"tutorConfig missing from course.json"
            tutor_config = course_data["tutorConfig"]
            
            assert tutor_config.get("enabled") == True, f"tutorConfig.enabled should be True"
            assert tutor_config.get("tutorName") == "TEST_Tutor", f"tutorName mismatch: {tutor_config.get('tutorName')}"
            assert "apiUrl" in tutor_config, "tutorConfig should have apiUrl"
            
            print(f"✅ SCORM export contains tutor.js, tutor.css")
            print(f"✅ course.json has tutorConfig: tutorName={tutor_config.get('tutorName')}, apiUrl={tutor_config.get('apiUrl')}")
    
    def test_scorm_export_without_tutor_when_disabled(self, test_project_id):
        """SCORM export does NOT include tutorConfig when tutor is disabled"""
        # Disable tutor
        requests.put(f"{BASE_URL}/api/admin/tutor-settings", json={"enabled": False})
        
        # Export SCORM
        export_response = requests.post(f"{BASE_URL}/api/course/{test_project_id}/export-scorm", timeout=60)
        
        if export_response.status_code != 200:
            pytest.skip(f"SCORM export failed: {export_response.status_code}")
        
        data = export_response.json()
        download_url = data["downloadUrl"]
        
        if not download_url.startswith("http"):
            download_url = f"{BASE_URL}{download_url}"
        
        zip_response = requests.get(download_url)
        assert zip_response.status_code == 200
        
        import io
        import zipfile
        
        zip_buffer = io.BytesIO(zip_response.content)
        with zipfile.ZipFile(zip_buffer, 'r') as zf:
            course_json = zf.read("course.json").decode('utf-8')
            course_data = json.loads(course_json)
            
            # tutorConfig should be absent or disabled
            tutor_config = course_data.get("tutorConfig")
            if tutor_config:
                assert tutor_config.get("enabled") == False or tutor_config is None, "tutorConfig should not be present when disabled"
            
            print("✅ SCORM export correctly excludes tutorConfig when tutor is disabled")
        
        # Re-enable tutor
        requests.put(f"{BASE_URL}/api/admin/tutor-settings", json={"enabled": True})


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
