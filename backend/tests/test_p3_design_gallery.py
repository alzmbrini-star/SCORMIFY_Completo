"""
P3 Feature Tests: Design Templates and AI Image Gallery
Tests for:
1. GET /api/agent/design-templates - returns 6 design templates
2. GET /api/gallery/images - gallery images list (company filtering)
3. POST /api/gallery/images - save image to gallery
4. DELETE /api/gallery/images/{id} - delete image
5. gallery_image type in apply-media-changes
6. designTemplateId in session config
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestDesignTemplates:
    """Test design templates endpoint"""
    
    def test_get_design_templates_returns_six(self):
        """GET /api/agent/design-templates returns 6 templates"""
        response = requests.get(f"{BASE_URL}/api/agent/design-templates")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        templates = response.json()
        assert isinstance(templates, list), "Expected list of templates"
        assert len(templates) == 6, f"Expected 6 templates, got {len(templates)}"
    
    def test_design_template_structure(self):
        """Each template has id, name, description, preview, palette, fonts"""
        response = requests.get(f"{BASE_URL}/api/agent/design-templates")
        assert response.status_code == 200
        
        templates = response.json()
        required_fields = ['id', 'name', 'description', 'preview', 'palette', 'fonts']
        
        for template in templates:
            for field in required_fields:
                assert field in template, f"Template missing field: {field}"
            
            # Verify palette has required color fields
            palette = template.get('palette', {})
            palette_fields = ['primary', 'accent', 'contentBg', 'text']
            for pf in palette_fields:
                assert pf in palette, f"Palette missing field: {pf}"
            
            # Verify fonts has heading and body
            fonts = template.get('fonts', {})
            assert 'heading' in fonts, "Fonts missing heading"
            assert 'body' in fonts, "Fonts missing body"
    
    def test_design_template_ids(self):
        """Verify the 6 expected template IDs exist"""
        response = requests.get(f"{BASE_URL}/api/agent/design-templates")
        assert response.status_code == 200
        
        templates = response.json()
        template_ids = [t['id'] for t in templates]
        
        expected_ids = ['corporativo', 'educacional', 'minimalista', 'tech', 'criativo', 'elegante']
        for eid in expected_ids:
            assert eid in template_ids, f"Missing template ID: {eid}"


class TestGalleryAPI:
    """Test gallery CRUD endpoints"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@scormify.com",
            "password": "admin123"
        })
        if response.status_code == 200:
            return response.json().get("token")
        pytest.skip("Authentication failed")
    
    @pytest.fixture(scope="class")
    def auth_cookies(self, auth_token):
        """Return cookies dict for requests"""
        return {"session_token": auth_token}
    
    def test_get_gallery_images_success(self, auth_cookies):
        """GET /api/gallery/images returns images list"""
        response = requests.get(
            f"{BASE_URL}/api/gallery/images",
            cookies=auth_cookies
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert 'images' in data, "Response missing 'images' field"
        assert 'total' in data, "Response missing 'total' field"
        assert isinstance(data['images'], list), "images should be a list"
    
    def test_get_gallery_requires_auth(self):
        """GET /api/gallery/images requires authentication"""
        response = requests.get(f"{BASE_URL}/api/gallery/images")
        # Should return 401 without auth
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
    
    def test_post_gallery_image_success(self, auth_cookies):
        """POST /api/gallery/images saves image"""
        unique_url = f"/api/projects/test/assets/test_{uuid.uuid4().hex[:8]}.png"
        
        response = requests.post(
            f"{BASE_URL}/api/gallery/images",
            json={
                "imageUrl": unique_url,
                "keywords": "test professional business",
                "projectId": "c7de35a7-0f1a-4270-86d4-703151b377e5",
                "projectName": "Test Project"
            },
            cookies=auth_cookies
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert 'id' in data, "Response missing 'id'"
        assert data['imageUrl'] == unique_url, "imageUrl mismatch"
        assert data['keywords'] == "test professional business", "keywords mismatch"
        assert data['projectId'] == "c7de35a7-0f1a-4270-86d4-703151b377e5", "projectId mismatch"
        
        # Cleanup - delete the test image
        image_id = data['id']
        requests.delete(f"{BASE_URL}/api/gallery/images/{image_id}", cookies=auth_cookies)
    
    def test_post_gallery_requires_image_url(self, auth_cookies):
        """POST /api/gallery/images requires imageUrl"""
        response = requests.post(
            f"{BASE_URL}/api/gallery/images",
            json={"keywords": "test"},
            cookies=auth_cookies
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
    
    def test_delete_gallery_image_success(self, auth_cookies):
        """DELETE /api/gallery/images/{id} deletes image"""
        # First create an image
        unique_url = f"/api/projects/test/assets/delete_test_{uuid.uuid4().hex[:8]}.png"
        create_response = requests.post(
            f"{BASE_URL}/api/gallery/images",
            json={"imageUrl": unique_url, "keywords": "delete test"},
            cookies=auth_cookies
        )
        assert create_response.status_code == 200
        image_id = create_response.json()['id']
        
        # Delete the image
        delete_response = requests.delete(
            f"{BASE_URL}/api/gallery/images/{image_id}",
            cookies=auth_cookies
        )
        assert delete_response.status_code == 200, f"Expected 200, got {delete_response.status_code}"
        
        data = delete_response.json()
        assert data['status'] == 'ok', "Expected status 'ok'"
        assert data['deleted'] == image_id, "Deleted ID mismatch"
        
        # Verify image is gone
        get_response = requests.get(f"{BASE_URL}/api/gallery/images", cookies=auth_cookies)
        images = get_response.json().get('images', [])
        image_ids = [i['id'] for i in images]
        assert image_id not in image_ids, "Image still exists after delete"
    
    def test_delete_nonexistent_image(self, auth_cookies):
        """DELETE /api/gallery/images/{id} returns 404 for nonexistent"""
        response = requests.delete(
            f"{BASE_URL}/api/gallery/images/nonexistent-id-12345",
            cookies=auth_cookies
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"


class TestGalleryImageInMediaConfig:
    """Test gallery_image type in apply-media-changes"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@scormify.com",
            "password": "admin123"
        })
        if response.status_code == 200:
            return response.json().get("token")
        pytest.skip("Authentication failed")
    
    @pytest.fixture(scope="class")
    def auth_cookies(self, auth_token):
        return {"session_token": auth_token}
    
    @pytest.fixture
    def session_with_project(self, auth_cookies):
        """Create a session and a project for testing"""
        # Create session
        session_resp = requests.post(
            f"{BASE_URL}/api/agent/sessions",
            json={},
            cookies=auth_cookies
        )
        if session_resp.status_code != 200:
            pytest.skip("Failed to create session")
        
        session_id = session_resp.json()['id']
        
        # Create a test project with slides
        project_id = f"test_gallery_{uuid.uuid4().hex[:8]}"
        from pymongo import MongoClient
        mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
        db_name = os.environ.get('DB_NAME', 'test_database')
        client = MongoClient(mongo_url)
        db = client[db_name]
        
        # Create project with slides
        db.projects.insert_one({
            "id": project_id,
            "name": "Gallery Test Project",
            "course": {
                "slides": [
                    {
                        "id": "slide1",
                        "title": "Test Slide",
                        "elements": [
                            {"id": "el1", "type": "html", "htmlContent": "<p>Test content</p>", "width": 1800}
                        ]
                    }
                ]
            }
        })
        
        # Update session with storyboard
        db.agent_sessions.update_one(
            {"id": session_id},
            {"$set": {
                "storyboard": {"slides": [{"id": "slide1", "title": "Test Slide", "type": "content"}]},
                "projectId": project_id
            }}
        )
        
        yield {"session_id": session_id, "project_id": project_id}
        
        # Cleanup
        db.projects.delete_one({"id": project_id})
        db.agent_sessions.delete_one({"id": session_id})
        client.close()
    
    def test_gallery_image_uses_provided_url(self, auth_cookies, session_with_project):
        """gallery_image type uses galleryImageUrl directly without generating new image"""
        session_id = session_with_project['session_id']
        project_id = session_with_project['project_id']
        
        gallery_url = "/api/projects/test/assets/gallery_image.png"
        
        # Save media config with gallery_image
        config_resp = requests.post(
            f"{BASE_URL}/api/agent/sessions/{session_id}/media-config",
            json={
                "mediaConfig": {
                    "0": {
                        "type": "gallery_image",
                        "galleryImageUrl": gallery_url
                    }
                },
                "bgConfig": {}
            },
            cookies=auth_cookies
        )
        assert config_resp.status_code == 200, f"Media config failed: {config_resp.text}"
        
        # Apply media changes
        apply_resp = requests.post(
            f"{BASE_URL}/api/agent/sessions/{session_id}/apply-media-changes",
            json={"projectId": project_id, "changedSlides": [0]},
            cookies=auth_cookies
        )
        assert apply_resp.status_code == 200, f"Apply failed: {apply_resp.text}"
        
        # Verify the project slide has the gallery image
        from pymongo import MongoClient
        mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
        db_name = os.environ.get('DB_NAME', 'test_database')
        client = MongoClient(mongo_url)
        db = client[db_name]
        
        project = db.projects.find_one({"id": project_id})
        assert project is not None
        
        slides = project.get('course', {}).get('slides', [])
        assert len(slides) > 0
        
        # Check for image element with gallery URL
        image_elements = [el for el in slides[0].get('elements', []) if el.get('type') == 'image']
        assert len(image_elements) > 0, "No image element found"
        assert image_elements[0].get('src') == gallery_url, f"Expected {gallery_url}, got {image_elements[0].get('src')}"
        
        client.close()


class TestDesignTemplateIdInSession:
    """Test designTemplateId is passed to generate_course_from_storyboard"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@scormify.com",
            "password": "admin123"
        })
        if response.status_code == 200:
            return response.json().get("token")
        pytest.skip("Authentication failed")
    
    @pytest.fixture(scope="class")
    def auth_cookies(self, auth_token):
        return {"session_token": auth_token}
    
    def test_design_template_saved_in_config(self, auth_cookies):
        """designTemplateId is saved when configuring session"""
        # Create session
        session_resp = requests.post(
            f"{BASE_URL}/api/agent/sessions",
            json={},
            cookies=auth_cookies
        )
        assert session_resp.status_code == 200
        session_id = session_resp.json()['id']
        
        try:
            # Configure with design template
            config_resp = requests.post(
                f"{BASE_URL}/api/agent/sessions/{session_id}/configure",
                json={
                    "title": "Test Course",
                    "designTemplateId": "tech"
                },
                cookies=auth_cookies
            )
            assert config_resp.status_code == 200
            
            # Get session and verify config
            get_resp = requests.get(
                f"{BASE_URL}/api/agent/sessions/{session_id}",
                cookies=auth_cookies
            )
            assert get_resp.status_code == 200
            
            session = get_resp.json()
            config = session.get('config', {})
            assert config.get('designTemplateId') == 'tech', f"Expected 'tech', got {config.get('designTemplateId')}"
        
        finally:
            # Cleanup
            from pymongo import MongoClient
            mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
            db_name = os.environ.get('DB_NAME', 'test_database')
            client = MongoClient(mongo_url)
            db = client[db_name]
            db.agent_sessions.delete_one({"id": session_id})
            client.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
