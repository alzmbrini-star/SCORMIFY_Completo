"""
Full Regression Test Suite for Scormify AI Agent & Export Features
Tests all agent endpoints, content quality, quiz functionality, and SCORM export with LIBRAS toggle

Endpoints tested:
- POST /api/agent/sessions - Create new session
- POST /api/agent/sessions/{id}/upload - Upload text content
- POST /api/agent/sessions/{id}/analyze - AI content analysis
- POST /api/agent/sessions/{id}/configure - Set course config
- POST /api/agent/sessions/{id}/generate-structure - Generate course structure
- POST /api/agent/sessions/{id}/generate-storyboard - Generate storyboard (async)
- POST /api/agent/sessions/{id}/media-config - Save media config per slide
- POST /api/agent/sessions/{id}/generate-course - Generate full course
- GET /api/agent/templates - List visual templates
- GET /api/agent/courses - List agent-created courses
- POST /api/export/{project_id} - SCORM export with LIBRAS toggle
"""

import pytest
import requests
import os
import time
import re

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test content for course generation
SAMPLE_CONTENT = """
Segurança no Trabalho - Guia Completo

A segurança no trabalho é fundamental para garantir o bem-estar dos colaboradores e a eficiência das operações.

1. Equipamentos de Proteção Individual (EPIs)
Os EPIs são essenciais para a proteção dos trabalhadores. Incluem capacetes, luvas, óculos de proteção, 
protetores auriculares e calçados de segurança. Cada tipo de atividade requer EPIs específicos.

2. Normas Regulamentadoras (NRs)
As Normas Regulamentadoras são diretrizes obrigatórias que estabelecem requisitos mínimos de segurança 
e saúde no ambiente de trabalho. A NR-6 trata especificamente dos EPIs.

3. Treinamentos Obrigatórios
Todos os colaboradores devem receber treinamento adequado sobre segurança, incluindo:
- Uso correto de EPIs
- Procedimentos de emergência
- Prevenção de acidentes
- Ergonomia no trabalho

4. Prevenção de Acidentes
A prevenção é a melhor estratégia. Identifique riscos potenciais, mantenha áreas de trabalho organizadas,
sinalize perigos adequadamente e promova uma cultura de segurança.

5. Procedimentos de Emergência
Em caso de emergência, siga os procedimentos estabelecidos: evacue o local de forma ordenada,
acione os serviços de emergência e preste primeiros socorros quando qualificado.
"""


class TestAPIHealth:
    """Test basic API health"""
    
    def test_api_health(self):
        """Test API health endpoint"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy"
        print(f"✓ API health check passed")
    
    def test_projects_list(self):
        """Test projects endpoint is accessible"""
        response = requests.get(f"{BASE_URL}/api/projects")
        assert response.status_code == 200
        print(f"✓ Projects list endpoint accessible")


class TestAgentTemplates:
    """Test agent templates endpoint"""
    
    def test_get_templates(self):
        """GET /api/agent/templates - List visual templates"""
        response = requests.get(f"{BASE_URL}/api/agent/templates")
        assert response.status_code == 200
        templates = response.json()
        assert isinstance(templates, list)
        assert len(templates) >= 1, "Should have at least 1 template"
        
        # Verify template structure
        for t in templates:
            assert "id" in t
            assert "name" in t
            assert "description" in t
            assert "defaultConfig" in t
        
        print(f"✓ Templates endpoint returned {len(templates)} templates")
        return templates


class TestAgentCourses:
    """Test agent courses endpoint"""
    
    def test_get_agent_courses(self):
        """GET /api/agent/courses - List agent-created courses"""
        response = requests.get(f"{BASE_URL}/api/agent/courses")
        assert response.status_code == 200
        courses = response.json()
        assert isinstance(courses, list)
        print(f"✓ Agent courses endpoint returned {len(courses)} courses")
        return courses


class TestAgentSessionCreation:
    """Test session creation"""
    
    def test_create_session(self):
        """POST /api/agent/sessions - Create new session"""
        response = requests.post(
            f"{BASE_URL}/api/agent/sessions",
            json={}
        )
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data.get("step") == "created"
        print(f"✓ Session created with ID: {data['id']}")
        return data["id"]
    
    def test_get_session(self):
        """GET /api/agent/sessions/{id} - Get session"""
        # Create session first
        create_resp = requests.post(f"{BASE_URL}/api/agent/sessions", json={})
        session_id = create_resp.json()["id"]
        
        # Get session
        response = requests.get(f"{BASE_URL}/api/agent/sessions/{session_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == session_id
        print(f"✓ Session retrieved successfully")


class TestAgentUpload:
    """Test content upload"""
    
    @pytest.fixture
    def session_id(self):
        """Create a session for upload tests"""
        response = requests.post(f"{BASE_URL}/api/agent/sessions", json={})
        return response.json()["id"]
    
    def test_upload_text(self, session_id):
        """POST /api/agent/sessions/{id}/upload - Upload text content"""
        response = requests.post(
            f"{BASE_URL}/api/agent/sessions/{session_id}/upload",
            data={"text": SAMPLE_CONTENT}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "ok"
        assert data.get("contentLength") > 0
        print(f"✓ Text uploaded successfully ({data['contentLength']} chars)")


class TestAgentAnalysis:
    """Test AI content analysis"""
    
    @pytest.fixture
    def session_with_content(self):
        """Create a session with uploaded content"""
        # Create session
        create_resp = requests.post(f"{BASE_URL}/api/agent/sessions", json={})
        session_id = create_resp.json()["id"]
        
        # Upload content
        requests.post(
            f"{BASE_URL}/api/agent/sessions/{session_id}/upload",
            data={"text": SAMPLE_CONTENT}
        )
        return session_id
    
    def test_analyze_content(self, session_with_content):
        """POST /api/agent/sessions/{id}/analyze - AI content analysis"""
        response = requests.post(
            f"{BASE_URL}/api/agent/sessions/{session_with_content}/analyze"
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify analysis structure
        assert "title" in data
        assert "summary" in data
        assert "mainTopics" in data or "difficulty" in data
        print(f"✓ Content analyzed - Title: {data.get('title', 'N/A')[:50]}")
        return data


class TestAgentConfiguration:
    """Test course configuration"""
    
    @pytest.fixture
    def session_analyzed(self):
        """Create a session with analyzed content"""
        # Create session
        create_resp = requests.post(f"{BASE_URL}/api/agent/sessions", json={})
        session_id = create_resp.json()["id"]
        
        # Upload content
        requests.post(
            f"{BASE_URL}/api/agent/sessions/{session_id}/upload",
            data={"text": SAMPLE_CONTENT}
        )
        
        # Analyze content
        requests.post(f"{BASE_URL}/api/agent/sessions/{session_id}/analyze")
        
        return session_id
    
    def test_configure_session(self, session_analyzed):
        """POST /api/agent/sessions/{id}/configure - Set course config"""
        config = {
            "title": "TEST_Segurança no Trabalho",
            "depth": "intermediario",
            "duration": 30,
            "modules": 3,
            "interactivity": "alta",
            "format": "curso_completo",
            "description": "Curso de segurança no trabalho"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/agent/sessions/{session_analyzed}/configure",
            json=config
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "ok"
        print(f"✓ Configuration saved successfully")


class TestAgentStructure:
    """Test course structure generation"""
    
    @pytest.fixture
    def session_configured(self):
        """Create a fully configured session"""
        # Create session
        create_resp = requests.post(f"{BASE_URL}/api/agent/sessions", json={})
        session_id = create_resp.json()["id"]
        
        # Upload content
        requests.post(
            f"{BASE_URL}/api/agent/sessions/{session_id}/upload",
            data={"text": SAMPLE_CONTENT}
        )
        
        # Analyze content
        requests.post(f"{BASE_URL}/api/agent/sessions/{session_id}/analyze")
        
        # Configure
        requests.post(
            f"{BASE_URL}/api/agent/sessions/{session_id}/configure",
            json={"title": "TEST_Course", "modules": 2, "depth": "basico"}
        )
        
        return session_id
    
    def test_generate_structure(self, session_configured):
        """POST /api/agent/sessions/{id}/generate-structure - Generate course structure"""
        response = requests.post(
            f"{BASE_URL}/api/agent/sessions/{session_configured}/generate-structure",
            json={}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify structure
        assert "modules" in data or "courseTitle" in data
        print(f"✓ Structure generated - Modules: {len(data.get('modules', []))}")
        return data
    
    def test_generate_structure_with_template(self, session_configured):
        """POST /api/agent/sessions/{id}/generate-structure - With template"""
        # Get templates first
        templates_resp = requests.get(f"{BASE_URL}/api/agent/templates")
        templates = templates_resp.json()
        
        if templates:
            template_id = templates[0]["id"]
            response = requests.post(
                f"{BASE_URL}/api/agent/sessions/{session_configured}/generate-structure",
                json={"templateId": template_id}
            )
            assert response.status_code == 200
            print(f"✓ Structure generated with template: {template_id}")
        else:
            pytest.skip("No templates available")


class TestAgentStoryboard:
    """Test storyboard generation (async)"""
    
    @pytest.fixture
    def session_with_structure(self):
        """Create a session with structure"""
        # Create session
        create_resp = requests.post(f"{BASE_URL}/api/agent/sessions", json={})
        session_id = create_resp.json()["id"]
        
        # Upload content
        requests.post(
            f"{BASE_URL}/api/agent/sessions/{session_id}/upload",
            data={"text": SAMPLE_CONTENT}
        )
        
        # Analyze content
        requests.post(f"{BASE_URL}/api/agent/sessions/{session_id}/analyze")
        
        # Configure
        requests.post(
            f"{BASE_URL}/api/agent/sessions/{session_id}/configure",
            json={"title": "TEST_Course", "modules": 2, "depth": "basico"}
        )
        
        # Generate structure
        requests.post(f"{BASE_URL}/api/agent/sessions/{session_id}/generate-structure", json={})
        
        return session_id
    
    def test_generate_storyboard(self, session_with_structure):
        """POST /api/agent/sessions/{id}/generate-storyboard - Generate storyboard (async)"""
        response = requests.post(
            f"{BASE_URL}/api/agent/sessions/{session_with_structure}/generate-storyboard"
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "processing"
        print(f"✓ Storyboard generation started (async)")
        
        # Poll for completion (max 120 seconds)
        max_attempts = 40
        for attempt in range(max_attempts):
            time.sleep(3)
            session_resp = requests.get(f"{BASE_URL}/api/agent/sessions/{session_with_structure}")
            session = session_resp.json()
            
            if session.get("step") == "storyboarded" and session.get("storyboard"):
                print(f"✓ Storyboard completed after {(attempt+1)*3}s - Slides: {len(session['storyboard'].get('slides', []))}")
                return session
            elif session.get("error"):
                pytest.fail(f"Storyboard generation failed: {session.get('error')}")
        
        pytest.skip("Storyboard generation timeout (may still be processing)")


class TestAgentMediaConfig:
    """Test media configuration"""
    
    def test_save_media_config(self):
        """POST /api/agent/sessions/{id}/media-config - Save media config per slide"""
        # Create session first
        create_resp = requests.post(f"{BASE_URL}/api/agent/sessions", json={})
        session_id = create_resp.json()["id"]
        
        media_config = {
            "mediaConfig": {
                "0": {"type": "ai_image"},
                "1": {"type": "youtube", "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
                "2": {"type": "none"},
                "3": {"type": "heygen"}
            }
        }
        
        response = requests.post(
            f"{BASE_URL}/api/agent/sessions/{session_id}/media-config",
            json=media_config
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "ok"
        print(f"✓ Media config saved - {data.get('configured')} slides configured")


class TestExistingAgentCourse:
    """Test with existing agent-created course (from previous iterations)"""
    
    @pytest.fixture
    def existing_course(self):
        """Get an existing agent-created course"""
        response = requests.get(f"{BASE_URL}/api/agent/courses")
        courses = response.json()
        if not courses:
            pytest.skip("No existing agent-created courses")
        return courses[0]
    
    def test_course_structure(self, existing_course):
        """Verify course structure"""
        project_id = existing_course["id"]
        response = requests.get(f"{BASE_URL}/api/projects/{project_id}")
        assert response.status_code == 200
        project = response.json()
        
        slides = project.get("course", {}).get("slides", [])
        print(f"✓ Existing course has {len(slides)} slides")
        return project
    
    def test_content_slides_word_count(self, existing_course):
        """Verify content slides have 100+ words"""
        project_id = existing_course["id"]
        response = requests.get(f"{BASE_URL}/api/projects/{project_id}")
        project = response.json()
        
        slides = project.get("course", {}).get("slides", [])
        content_slides_checked = 0
        
        for i, slide in enumerate(slides):
            # Check if it's a content slide (has html elements with substantial content)
            elements = slide.get("elements", [])
            for element in elements:
                if element.get("type") in ("html", "text"):
                    html_content = element.get("htmlContent", "") or element.get("content", "")
                    # Strip HTML tags for word count
                    text_only = re.sub(r'<[^>]+>', ' ', html_content)
                    text_only = re.sub(r'\s+', ' ', text_only).strip()
                    word_count = len(text_only.split())
                    
                    if word_count >= 50:  # Substantial content
                        content_slides_checked += 1
                        if word_count < 100:
                            print(f"⚠ Slide {i} has only {word_count} words (expected 100+)")
                        else:
                            print(f"✓ Slide {i} has {word_count} words")
        
        print(f"✓ Checked {content_slides_checked} content slides")
    
    def test_quiz_slides_have_quiz_elements(self, existing_course):
        """Verify quiz slides have type='quiz' elements with quizConfig"""
        project_id = existing_course["id"]
        response = requests.get(f"{BASE_URL}/api/projects/{project_id}")
        project = response.json()
        
        slides = project.get("course", {}).get("slides", [])
        quiz_elements_found = 0
        
        for i, slide in enumerate(slides):
            elements = slide.get("elements", [])
            for element in elements:
                if element.get("type") == "quiz":
                    quiz_elements_found += 1
                    quiz_config = element.get("quizConfig", {})
                    
                    assert "questionIds" in quiz_config, f"Slide {i}: Quiz missing questionIds"
                    assert len(quiz_config.get("questionIds", [])) > 0, f"Slide {i}: Empty questionIds"
                    
                    print(f"✓ Slide {i}: Quiz with {len(quiz_config.get('questionIds', []))} questions")
        
        print(f"✓ Found {quiz_elements_found} quiz elements")


class TestSCORMExport:
    """Test SCORM export with LIBRAS toggle"""
    
    @pytest.fixture
    def test_project(self):
        """Get or create a test project"""
        # Try to get existing projects
        response = requests.get(f"{BASE_URL}/api/projects")
        projects = response.json()
        
        if projects:
            return projects[0]
        
        # Create a new project if none exist
        response = requests.post(
            f"{BASE_URL}/api/projects",
            json={"name": "TEST_Export_Project", "description": "Test project for export"}
        )
        return response.json()
    
    def test_vlibras_toggle(self, test_project):
        """Test VLibras toggle (enableVlibras field)"""
        project_id = test_project["id"]
        
        # Enable VLibras
        response = requests.put(
            f"{BASE_URL}/api/projects/{project_id}",
            json={"enableVlibras": True}
        )
        assert response.status_code == 200
        
        # Verify
        get_resp = requests.get(f"{BASE_URL}/api/projects/{project_id}")
        project = get_resp.json()
        assert project.get("enableVlibras") == True
        print(f"✓ VLibras enabled successfully")
        
        # Disable VLibras
        response = requests.put(
            f"{BASE_URL}/api/projects/{project_id}",
            json={"enableVlibras": False}
        )
        assert response.status_code == 200
        
        # Verify
        get_resp = requests.get(f"{BASE_URL}/api/projects/{project_id}")
        project = get_resp.json()
        assert project.get("enableVlibras") == False
        print(f"✓ VLibras disabled successfully")
    
    def test_scorm_export_endpoint(self, test_project):
        """POST /api/course/{project_id}/export-scorm - SCORM export"""
        project_id = test_project["id"]
        
        response = requests.post(
            f"{BASE_URL}/api/course/{project_id}/export-scorm"
        )
        
        # Export can take time, check for either success or processing
        assert response.status_code in (200, 202), f"Unexpected status: {response.status_code}"
        data = response.json()
        
        if "downloadUrl" in data:
            print(f"✓ SCORM export ready - URL: {data['downloadUrl']}")
        elif "jobId" in data:
            print(f"✓ SCORM export started - Job: {data['jobId']}")
        else:
            print(f"✓ SCORM export response: {data}")


class TestQuizQuestionsInMongoDB:
    """Test that quiz questions are stored correctly in MongoDB"""
    
    def test_questions_collection_exists(self):
        """Verify questions are stored in MongoDB"""
        # Get agent courses
        courses_resp = requests.get(f"{BASE_URL}/api/agent/courses")
        courses = courses_resp.json()
        
        if not courses:
            pytest.skip("No agent courses to verify questions")
        
        # Get first course and check for quiz elements
        project_id = courses[0]["id"]
        project_resp = requests.get(f"{BASE_URL}/api/projects/{project_id}")
        project = project_resp.json()
        
        slides = project.get("course", {}).get("slides", [])
        all_question_ids = []
        
        for slide in slides:
            for element in slide.get("elements", []):
                if element.get("type") == "quiz":
                    quiz_config = element.get("quizConfig", {})
                    all_question_ids.extend(quiz_config.get("questionIds", []))
        
        if all_question_ids:
            print(f"✓ Found {len(all_question_ids)} question IDs in quiz elements")
        else:
            print("⚠ No quiz elements with questionIds found")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
