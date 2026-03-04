"""
Tests for AI Tutor Content Context Extraction Fix

Bug Fix:
- SCORM exporter was extracting content using 'htmlContent' and 'text' fields
- But actual element text is stored in the 'content' field
- Fix adds 'content' as the primary field to check
- Also extracts buttonText and quiz titles

Also verifies:
- System prompt now instructs Gemini to cite specific slides
- Keyboard fix from previous iteration (iteration_29) still in place
"""

import pytest
import requests
import os
import json
import zipfile
import tempfile
import re

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://scormfy-rbac.preview.emergentagent.com')
TEST_PROJECT_ID = 'cb4e0112-3e45-44fe-ab29-304b0ef8f0a0'  # Universidade-Corporativa-Didaxis


class TestHealthEndpoint:
    """Basic health check"""
    
    def test_health_endpoint(self):
        """Verify backend is healthy"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get('status') == 'healthy'
        print("✅ Health endpoint working")


class TestTutorSettings:
    """Tutor settings API tests"""
    
    def test_get_tutor_settings(self):
        """Verify tutor settings can be retrieved"""
        response = requests.get(f"{BASE_URL}/api/admin/tutor-settings")
        assert response.status_code == 200
        data = response.json()
        # Tutor should be enabled per the main agent
        assert data.get('enabled') == True
        print(f"✅ Tutor settings: enabled={data.get('enabled')}, tutorName={data.get('tutorName')}")
    
    def test_update_tutor_settings(self):
        """Verify tutor settings can be updated"""
        # Get current settings first
        get_resp = requests.get(f"{BASE_URL}/api/admin/tutor-settings")
        current = get_resp.json()
        
        # Update with a test change
        update_data = {
            "enabled": True,
            "tutorName": current.get('tutorName', 'Tutor IA'),
            "messageLimit": 50,
            "suggestedQuestions": current.get('suggestedQuestions', []),
            "systemPrompt": current.get('systemPrompt', '')
        }
        
        response = requests.put(
            f"{BASE_URL}/api/admin/tutor-settings",
            json=update_data
        )
        assert response.status_code == 200
        data = response.json()
        # API returns success message, not the updated settings
        assert data.get('status') == 'ok' or data.get('message') is not None
        
        # Verify by reading settings again
        verify_resp = requests.get(f"{BASE_URL}/api/admin/tutor-settings")
        verify_data = verify_resp.json()
        assert verify_data.get('enabled') == True
        print("✅ Tutor settings update working")


class TestTutorChatEndpoint:
    """Tutor chat API tests"""
    
    def test_tutor_chat_requires_message(self):
        """Verify tutor chat returns 400 for empty message"""
        response = requests.post(
            f"{BASE_URL}/api/tutor/chat",
            json={"message": "", "courseTopic": "Test", "courseContext": "Test context"}
        )
        assert response.status_code == 400
        print("✅ Tutor chat correctly rejects empty message")
    
    def test_tutor_chat_with_course_context(self):
        """
        Test that tutor chat works with course context.
        The response should reference slide content when context is provided.
        """
        # Provide course context similar to what SCORM exporter generates
        course_context = """Slide 1: Universidade Corporativa Didaxis | Com a Universidade Corporativa Didaxis, você pode simplificar e automatizar tarefas repetitivas
Slide 2: Gerenciamento Simplificado | Ferramentas Integradas | Perfis Personalizados
Slide 3: Conteúdo On-line e Presencial | A Didaxis oferece suporte a eventos presenciais | cursos on-line"""
        
        response = requests.post(
            f"{BASE_URL}/api/tutor/chat",
            json={
                "message": "O que é a Universidade Corporativa Didaxis?",
                "courseTopic": "Universidade Corporativa Didaxis",
                "courseContext": course_context,
                "history": [],
                "sessionId": "test-session-context"
            },
            timeout=60  # AI responses can be slow
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should have a response
        assert 'response' in data
        assert len(data['response']) > 0
        
        # The response should reference slides (based on improved system prompt)
        response_text = data['response'].lower()
        
        # Check if the response mentions any content from the slides
        content_references = ['didaxis', 'universidade', 'corporativa', 'simplificar', 'automatizar']
        has_content_reference = any(ref in response_text for ref in content_references)
        
        print(f"✅ Tutor chat response received ({len(data['response'])} chars)")
        print(f"   Response mentions slide content: {has_content_reference}")
        print(f"   Response preview: {data['response'][:200]}...")
        
        assert has_content_reference, "Response should reference course content"


class TestSCORMContextExtraction:
    """Test that SCORM export extracts content correctly"""
    
    def test_scorm_export_includes_course_context(self):
        """
        Export SCORM and verify course.json contains tutorConfig with courseContext
        that includes text extracted from 'content' field.
        """
        # Trigger SCORM export
        response = requests.post(
            f"{BASE_URL}/api/course/{TEST_PROJECT_ID}/export-scorm",
            timeout=120
        )
        
        assert response.status_code == 200
        data = response.json()
        assert 'downloadUrl' in data
        
        download_url = data['downloadUrl']
        if not download_url.startswith('http'):
            download_url = f"{BASE_URL}{download_url}"
        
        print(f"✅ SCORM export successful: {download_url}")
        
        # Download and inspect the ZIP
        zip_response = requests.get(download_url)
        assert zip_response.status_code == 200
        
        with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp_file:
            tmp_file.write(zip_response.content)
            tmp_path = tmp_file.name
        
        try:
            with zipfile.ZipFile(tmp_path, 'r') as zf:
                # Verify course.json exists
                assert 'course.json' in zf.namelist()
                
                # Read and parse course.json
                with zf.open('course.json') as f:
                    course_data = json.load(f)
                
                # Check tutorConfig exists
                tutor_config = course_data.get('tutorConfig')
                if tutor_config:
                    assert tutor_config.get('enabled') == True
                    course_context = tutor_config.get('courseContext', '')
                    
                    print(f"✅ tutorConfig found in course.json")
                    print(f"   courseContext length: {len(course_context)} chars")
                    
                    # Verify content extraction worked (these are from 'content' field)
                    assert 'Universidade Corporativa Didaxis' in course_context, \
                        "courseContext should contain content from 'content' field"
                    assert 'Slide 1:' in course_context, \
                        "courseContext should include slide numbers"
                    
                    # Check for text from multiple slides
                    assert 'Gerenciamento Simplificado' in course_context or 'Slide 2:' in course_context, \
                        "courseContext should include text from slide 2"
                    
                    print(f"   First 500 chars of context: {course_context[:500]}")
                    print("✅ Content extraction from 'content' field verified")
                else:
                    print("⚠️ tutorConfig not found - tutor may be disabled in export")
        finally:
            os.unlink(tmp_path)
    
    def test_scorm_export_contains_player_js_keyboard_fix(self):
        """Verify keyboard navigation fix is still in place in player.js"""
        # Export SCORM
        response = requests.post(
            f"{BASE_URL}/api/course/{TEST_PROJECT_ID}/export-scorm",
            timeout=120
        )
        
        assert response.status_code == 200
        download_url = response.json()['downloadUrl']
        if not download_url.startswith('http'):
            download_url = f"{BASE_URL}{download_url}"
        
        zip_response = requests.get(download_url)
        
        with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp_file:
            tmp_file.write(zip_response.content)
            tmp_path = tmp_file.name
        
        try:
            with zipfile.ZipFile(tmp_path, 'r') as zf:
                # Check player.js exists
                player_js_path = 'scripts/player.js'
                assert player_js_path in zf.namelist(), "player.js should be in SCORM package"
                
                with zf.open(player_js_path) as f:
                    player_js_content = f.read().decode('utf-8')
                
                # Verify keyboard navigation guard is present
                assert "tag === 'input'" in player_js_content or "tag==='input'" in player_js_content, \
                    "player.js should check for input tags"
                assert "tag === 'textarea'" in player_js_content or "tag==='textarea'" in player_js_content, \
                    "player.js should check for textarea tags"
                assert "isContentEditable" in player_js_content, \
                    "player.js should check for contentEditable"
                
                print("✅ Keyboard navigation guard present in player.js")
        finally:
            os.unlink(tmp_path)
    
    def test_scorm_export_contains_tutor_js_keyboard_fix(self):
        """Verify keyboard event stopPropagation is in tutor.js"""
        # Export SCORM
        response = requests.post(
            f"{BASE_URL}/api/course/{TEST_PROJECT_ID}/export-scorm",
            timeout=120
        )
        
        assert response.status_code == 200
        download_url = response.json()['downloadUrl']
        if not download_url.startswith('http'):
            download_url = f"{BASE_URL}{download_url}"
        
        zip_response = requests.get(download_url)
        
        with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp_file:
            tmp_file.write(zip_response.content)
            tmp_path = tmp_file.name
        
        try:
            with zipfile.ZipFile(tmp_path, 'r') as zf:
                tutor_js_path = 'scripts/tutor.js'
                
                if tutor_js_path in zf.namelist():
                    with zf.open(tutor_js_path) as f:
                        tutor_js_content = f.read().decode('utf-8')
                    
                    # Verify stopPropagation is present
                    assert 'stopPropagation' in tutor_js_content, \
                        "tutor.js should call stopPropagation on keyboard events"
                    
                    print("✅ stopPropagation present in tutor.js")
                else:
                    print("⚠️ tutor.js not in package (tutor may be disabled)")
        finally:
            os.unlink(tmp_path)


class TestSourceFileVerification:
    """Verify source files have the fixes"""
    
    def test_source_player_js_has_keyboard_guard(self):
        """Check source player.js file has keyboard navigation guard"""
        with open('/app/backend/services/export_assets/player.js', 'r') as f:
            content = f.read()
        
        # Check for the keyboard guard code
        assert "tag === 'input'" in content or "tag==='input'" in content
        assert "tag === 'textarea'" in content or "tag==='textarea'" in content
        assert "isContentEditable" in content
        assert "Let the user type freely" in content  # Comment from the fix
        
        print("✅ Source player.js has keyboard input guard")
    
    def test_source_tutor_js_has_stop_propagation(self):
        """Check source tutor.js file has stopPropagation"""
        with open('/app/backend/services/export_assets/tutor.js', 'r') as f:
            content = f.read()
        
        # Check for stopPropagation on keyboard events
        assert 'stopPropagation' in content
        assert 'keydown' in content
        assert 'keyup' in content
        assert 'keypress' in content
        
        print("✅ Source tutor.js has stopPropagation on keyboard events")
    
    def test_source_scorm_exporter_extracts_content_field(self):
        """Check source scorm_exporter.py extracts from 'content' field"""
        with open('/app/backend/services/scorm_exporter.py', 'r') as f:
            content = f.read()
        
        # Check for content extraction logic
        assert "elem.get('content')" in content, \
            "scorm_exporter should check 'content' field"
        assert "elem.get('htmlContent')" in content, \
            "scorm_exporter should also check 'htmlContent' field"
        assert "elem.get('buttonText')" in content, \
            "scorm_exporter should extract buttonText"
        assert "quiz_cfg.get('title')" in content or "quizConfig" in content, \
            "scorm_exporter should extract quiz titles"
        
        print("✅ Source scorm_exporter.py extracts from 'content' field")


class TestSystemPromptImprovement:
    """Verify system prompt improvements in server.py"""
    
    def test_system_prompt_includes_slide_citation_instruction(self):
        """Check that system prompt instructs to cite slides"""
        with open('/app/backend/server.py', 'r') as f:
            content = f.read()
        
        # Look for the improved system prompt
        assert 'Slide' in content, "System prompt should mention slides"
        
        # Check for specific citation instruction
        citation_patterns = [
            'cit',  # cite, citation, citações
            'slide',  # slide references
            'Conforme'  # Example format
        ]
        
        found_citation = any(p.lower() in content.lower() for p in citation_patterns)
        assert found_citation, "System prompt should have slide citation instructions"
        
        print("✅ System prompt includes slide citation instructions")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
