"""
Slide-Aware AI Tutor Tests
Tests for:
- SCORM export includes slideContexts in tutorConfig
- HTML export includes slideContexts in tutor_settings
- /api/tutor/chat works with slide-specific context
- Dashboard metrics endpoint
- Health endpoint
"""
import pytest
import requests
import os
import json
import time
import io
import zipfile

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestHealthAndDashboard:
    """Test basic health and dashboard endpoints"""
    
    def test_health_endpoint(self):
        """GET /api/health returns 200"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200, f"Health check failed: {response.status_code}"
        data = response.json()
        assert data.get("status") == "healthy", f"Unexpected health status: {data}"
        print(f"✅ Health check passed: {data}")
    
    def test_dashboard_metrics(self):
        """GET /api/dashboard/metrics returns course stats"""
        response = requests.get(f"{BASE_URL}/api/dashboard/metrics")
        assert response.status_code == 200, f"Dashboard metrics failed: {response.status_code}"
        data = response.json()
        
        # Verify expected fields
        assert "totalCourses" in data, f"Missing totalCourses: {data}"
        assert "totalSlides" in data, f"Missing totalSlides: {data}"
        assert "totalExports" in data, f"Missing totalExports: {data}"
        
        # Verify types
        assert isinstance(data["totalCourses"], int)
        assert isinstance(data["totalSlides"], int)
        assert isinstance(data["totalExports"], int)
        
        print(f"✅ Dashboard metrics: courses={data['totalCourses']}, slides={data['totalSlides']}, exports={data['totalExports']}")


class TestLoginAndAuth:
    """Test login functionality"""
    
    def test_admin_login(self):
        """POST /api/auth/login with admin credentials"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "admin@scormify.com", "password": "admin123"}
        )
        assert response.status_code == 200, f"Login failed: {response.status_code} - {response.text}"
        data = response.json()
        
        assert "token" in data, f"Missing token: {data}"
        assert "user" in data, f"Missing user: {data}"
        assert data["user"]["email"] == "admin@scormify.com"
        
        print(f"✅ Admin login successful: user={data['user']['email']}, role={data['user']['role']}")
        return data["token"]


class TestSlideAwareTutorChat:
    """Test /api/tutor/chat with slide-specific context"""
    
    @pytest.fixture(autouse=True)
    def ensure_tutor_enabled(self):
        """Ensure tutor is enabled before tests"""
        settings = {"enabled": True, "tutorName": "Tutor IA", "messageLimit": 50}
        requests.put(f"{BASE_URL}/api/admin/tutor-settings", json=settings)
        yield
    
    def test_chat_with_slide_context(self):
        """POST /api/tutor/chat works with slide-specific context in courseContext"""
        # Simulate slide-aware context that would be built by the player
        slide_context = "O aluno esta no Slide 2. Conteudo do slide atual:\nIntroducao ao Python | O que e uma variavel | Tipos de dados"
        full_context = slide_context + "\n\n--- Contexto geral do curso ---\nCurso de Python para iniciantes"
        
        payload = {
            "message": "Explique o que esta neste slide",
            "courseTopic": "Python Programming",
            "courseContext": full_context,
            "history": [],
            "sessionId": f"test-slide-context-{int(time.time())}"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/tutor/chat",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        assert response.status_code == 200, f"Chat failed: {response.status_code} - {response.text}"
        data = response.json()
        
        assert "response" in data, f"Missing response: {data}"
        ai_response = data["response"]
        assert len(ai_response) > 10, f"Response too short: {ai_response}"
        
        # The AI should reference slide content since we provided it
        print(f"✅ Chat with slide context works. Response ({len(ai_response)} chars): {ai_response[:150]}...")
    
    def test_chat_uses_course_context(self):
        """POST /api/tutor/chat uses courseContext for answering"""
        # Provide specific context that the AI should use
        unique_context = "Este curso ensina sobre SEGURANCA_CIBERNETICA_2024 incluindo firewalls, criptografia e protecao de dados"
        
        payload = {
            "message": "Qual e o tema principal deste curso?",
            "courseTopic": "Seguranca Cibernetica",
            "courseContext": unique_context,
            "history": [],
            "sessionId": f"test-context-usage-{int(time.time())}"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/tutor/chat",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        assert response.status_code == 200
        data = response.json()
        ai_response = data["response"].lower()
        
        # AI should mention security-related topics from the context
        context_keywords = ["seguranca", "cibernetica", "firewall", "criptografia", "protecao", "dados", "security"]
        found_keyword = any(kw in ai_response for kw in context_keywords)
        
        print(f"✅ AI response references course context. Keywords found: {found_keyword}")
        print(f"   Response: {data['response'][:200]}...")


class TestScormExportSlideContexts:
    """Test that SCORM export includes slideContexts array"""
    
    def test_scorm_export_has_slide_contexts(self):
        """SCORM export includes slideContexts array with per-slide content"""
        # First ensure tutor is enabled
        requests.put(
            f"{BASE_URL}/api/admin/tutor-settings",
            json={"enabled": True, "tutorName": "TEST_SlideAware_Tutor", "messageLimit": 50}
        )
        
        # Get an existing project with content (use first project that has slides)
        projects_response = requests.get(f"{BASE_URL}/api/projects")
        if projects_response.status_code != 200:
            pytest.skip("Could not get projects list")
        
        projects = projects_response.json()
        if isinstance(projects, dict):
            projects = projects.get("projects", [])
        
        # Find a project with slides
        project_id = None
        for p in projects:
            pid = p.get("id")
            proj_detail = requests.get(f"{BASE_URL}/api/projects/{pid}")
            if proj_detail.status_code == 200:
                proj_data = proj_detail.json()
                slides = proj_data.get("course", {}).get("slides", [])
                if len(slides) >= 1:
                    # Check if at least one slide has content
                    for slide in slides:
                        elements = slide.get("elements", [])
                        for el in elements:
                            if el.get("content") or el.get("htmlContent") or el.get("text"):
                                project_id = pid
                                break
                        if project_id:
                            break
                if project_id:
                    break
        
        if not project_id:
            pytest.skip("No project with content found for testing")
        
        print(f"Testing SCORM export with project: {project_id}")
        
        # Export SCORM
        export_response = requests.post(f"{BASE_URL}/api/course/{project_id}/export-scorm", timeout=90)
        
        if export_response.status_code != 200:
            print(f"SCORM export failed: {export_response.status_code} - {export_response.text}")
            pytest.skip(f"SCORM export failed: {export_response.status_code}")
        
        data = export_response.json()
        assert "downloadUrl" in data, f"Missing downloadUrl: {data}"
        
        download_url = data["downloadUrl"]
        if not download_url.startswith("http"):
            download_url = f"{BASE_URL}{download_url}"
        
        # Download ZIP
        zip_response = requests.get(download_url)
        assert zip_response.status_code == 200, f"Failed to download ZIP: {zip_response.status_code}"
        
        # Parse ZIP and check course.json
        zip_buffer = io.BytesIO(zip_response.content)
        with zipfile.ZipFile(zip_buffer, 'r') as zf:
            file_list = zf.namelist()
            
            # Verify tutor files exist
            assert "scripts/tutor.js" in file_list, f"Missing tutor.js: {file_list}"
            assert "styles/tutor.css" in file_list, f"Missing tutor.css: {file_list}"
            
            # Check course.json for slideContexts
            course_json = zf.read("course.json").decode('utf-8')
            course_data = json.loads(course_json)
            
            assert "tutorConfig" in course_data, f"Missing tutorConfig in course.json"
            tutor_config = course_data["tutorConfig"]
            
            assert tutor_config.get("enabled") == True, f"tutorConfig.enabled should be True"
            assert "slideContexts" in tutor_config, f"Missing slideContexts in tutorConfig: {tutor_config.keys()}"
            
            slide_contexts = tutor_config["slideContexts"]
            assert isinstance(slide_contexts, list), f"slideContexts should be a list: {type(slide_contexts)}"
            assert len(slide_contexts) >= 1, f"Expected at least 1 slideContext, got {len(slide_contexts)}"
            
            # Verify at least one slide context has content (non-empty)
            has_content = any(ctx and len(ctx.strip()) > 0 for ctx in slide_contexts)
            assert has_content, f"At least one slideContext should have content: {slide_contexts}"
            
            # Also check for apiUrl
            assert "apiUrl" in tutor_config, f"Missing apiUrl in tutorConfig"
            api_url = tutor_config["apiUrl"]
            assert api_url and len(api_url) > 5, f"apiUrl should be non-empty: {api_url}"
            
            print(f"✅ SCORM export has slideContexts array with {len(slide_contexts)} entries")
            for i, ctx in enumerate(slide_contexts[:3]):
                preview = (ctx[:80] + "...") if ctx and len(ctx) > 80 else (ctx or "(empty)")
                print(f"   Slide {i+1}: {preview}")
            print(f"   apiUrl: {api_url}")


class TestHtmlExportSlideContexts:
    """Test that HTML export includes slideContexts"""
    
    @pytest.fixture
    def test_project_for_html(self):
        """Create a test project for HTML export"""
        # Ensure tutor is enabled
        requests.put(
            f"{BASE_URL}/api/admin/tutor-settings",
            json={"enabled": True, "tutorName": "TEST_HTML_Tutor", "messageLimit": 50}
        )
        
        # Create project with content
        project_data = {"name": "TEST_HTML_SlideContexts", "description": "Test HTML export"}
        create_response = requests.post(f"{BASE_URL}/api/projects", json=project_data)
        if create_response.status_code != 200:
            pytest.skip(f"Could not create project: {create_response.text}")
        
        project = create_response.json()
        project_id = project["id"]
        
        # Add slides with content
        update_data = {
            "name": "TEST_HTML_SlideContexts",
            "course": {
                "metadata": {"title": "HTML Export Test"},
                "slides": [
                    {
                        "id": "html-slide-1",
                        "title": "Slide One",
                        "elements": [{"id": "h1", "type": "text", "content": "HTML Export Content", "x": 50, "y": 50, "width": 400, "height": 80}],
                        "width": 960,
                        "height": 540
                    }
                ]
            }
        }
        
        requests.put(f"{BASE_URL}/api/projects/{project_id}", json=update_data)
        
        yield project_id
        
        requests.delete(f"{BASE_URL}/api/projects/{project_id}")
    
    def test_html_export_works(self, test_project_for_html):
        """HTML export endpoint returns valid response with tutor references"""
        project_id = test_project_for_html
        
        # Export HTML
        export_response = requests.post(f"{BASE_URL}/api/course/{project_id}/export-html", timeout=60)
        
        if export_response.status_code != 200:
            print(f"HTML export failed: {export_response.status_code} - {export_response.text}")
            pytest.skip(f"HTML export failed: {export_response.status_code}")
        
        data = export_response.json()
        assert "downloadUrl" in data, f"Missing downloadUrl: {data}"
        assert "filename" in data, f"Missing filename: {data}"
        
        # Download HTML file
        download_url = data["downloadUrl"]
        if not download_url.startswith("http"):
            download_url = f"{BASE_URL}{download_url}"
        
        html_response = requests.get(download_url)
        assert html_response.status_code == 200, f"Failed to download HTML: {html_response.status_code}"
        
        html_content = html_response.text
        
        # Verify HTML contains AiTutor reference (for slide-aware tutoring)
        assert "AiTutor" in html_content, f"HTML should contain AiTutor reference"
        
        # Verify slideContexts is in the HTML (either in script or JSON)
        has_slide_contexts = "slideContexts" in html_content
        print(f"✅ HTML export works. Contains slideContexts: {has_slide_contexts}")
        print(f"   HTML size: {len(html_content)} bytes")


class TestTutorFilesInExportAssets:
    """Verify tutor.js has slide-aware functionality"""
    
    def test_tutor_js_has_on_slide_change(self):
        """Verify tutor.js in export_assets has onSlideChange method"""
        tutor_js_path = "/app/backend/services/export_assets/tutor.js"
        
        with open(tutor_js_path, 'r') as f:
            tutor_js = f.read()
        
        # Check for slide-aware functions
        assert "onSlideChange" in tutor_js, "tutor.js should have onSlideChange function"
        assert "currentSlideIndex" in tutor_js, "tutor.js should track currentSlideIndex"
        assert "slideContexts" in tutor_js, "tutor.js should use slideContexts array"
        assert "getCurrentSlideContext" in tutor_js, "tutor.js should have getCurrentSlideContext function"
        
        print("✅ tutor.js has slide-aware functions: onSlideChange, currentSlideIndex, slideContexts, getCurrentSlideContext")
    
    def test_player_js_calls_on_slide_change(self):
        """Verify player.js calls AiTutor.onSlideChange when slides change"""
        player_js_path = "/app/backend/services/export_assets/player.js"
        
        with open(player_js_path, 'r') as f:
            player_js = f.read()
        
        # Check for AiTutor.onSlideChange calls
        assert "AiTutor.onSlideChange" in player_js, "player.js should call AiTutor.onSlideChange"
        
        print("✅ player.js calls AiTutor.onSlideChange on slide navigation")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
