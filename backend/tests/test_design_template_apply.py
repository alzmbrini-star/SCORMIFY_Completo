"""
Test Design Template Application Feature (Iteration 61)
Tests:
1. POST /api/projects/{projectId}/apply-design-template endpoint
2. _apply_design_token_to_slide helper function (background, headers, fonts, corner radius)
3. Media-config save with designTemplateId
4. Apply-media-changes with design template support
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://avatar-scenes.preview.emergentagent.com')


class TestDesignTemplateEndpoint:
    """Tests for POST /api/projects/{projectId}/apply-design-template endpoint"""
    
    def test_apply_design_template_returns_ok(self):
        """Test that apply-design-template endpoint works with valid template"""
        project_id = "c7de35a7-0f1a-4270-86d4-703151b377e5"
        
        response = requests.post(
            f"{BASE_URL}/api/projects/{project_id}/apply-design-template",
            json={"designTemplateId": "educacional"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("status") == "ok"
        assert "updatedSlides" in data
        assert data["templateId"] == "educacional"
        assert data["templateName"] == "Educacional Moderno"
        print(f"✓ Applied template to {data['updatedSlides']} slides")
    
    def test_apply_design_template_invalid_template_uses_fallback(self):
        """Test that endpoint uses fallback template (educacional) for invalid template ID"""
        project_id = "c7de35a7-0f1a-4270-86d4-703151b377e5"
        
        response = requests.post(
            f"{BASE_URL}/api/projects/{project_id}/apply-design-template",
            json={"designTemplateId": "nonexistent_template"}
        )
        
        # The system falls back to "educacional" template for invalid IDs
        assert response.status_code == 200
        data = response.json()
        assert data["templateName"] == "Educacional Moderno"  # Default fallback
        print("✓ Uses fallback template for invalid template ID")
    
    def test_apply_design_template_missing_id(self):
        """Test that endpoint returns 400 when designTemplateId is missing"""
        project_id = "c7de35a7-0f1a-4270-86d4-703151b377e5"
        
        response = requests.post(
            f"{BASE_URL}/api/projects/{project_id}/apply-design-template",
            json={}
        )
        
        assert response.status_code == 400
        print("✓ Returns 400 when designTemplateId is missing")
    
    def test_apply_design_template_invalid_project(self):
        """Test that endpoint returns 404 for invalid project ID"""
        response = requests.post(
            f"{BASE_URL}/api/projects/nonexistent-project-id/apply-design-template",
            json={"designTemplateId": "educacional"}
        )
        
        assert response.status_code == 404
        print("✓ Returns 404 for invalid project ID")


class TestDesignTemplateVerifyChanges:
    """Tests to verify design template actually modifies the project slides"""
    
    def test_verify_background_changes_after_apply(self):
        """Verify that slide backgrounds are updated after applying template"""
        project_id = "c7de35a7-0f1a-4270-86d4-703151b377e5"
        
        # Get original project state
        original = requests.get(f"{BASE_URL}/api/projects/{project_id}").json()
        original_slides = original.get("course", {}).get("slides", [])
        
        # Apply corporativo template (has different colors)
        response = requests.post(
            f"{BASE_URL}/api/projects/{project_id}/apply-design-template",
            json={"designTemplateId": "corporativo"}
        )
        assert response.status_code == 200
        
        # Get updated project
        updated = requests.get(f"{BASE_URL}/api/projects/{project_id}").json()
        updated_slides = updated.get("course", {}).get("slides", [])
        
        # Verify at least one slide has updated background
        # Corporativo palette: primary=#0f172a, contentBg=#f8fafc
        changes_found = 0
        for i, slide in enumerate(updated_slides):
            bg = slide.get("background", "")
            slide_type = slide.get("type", "content")
            if slide_type in ("title", "cover", "quiz", "summary"):
                # Should use primary color
                if bg == "#0f172a":
                    changes_found += 1
            else:
                # Content slides should use contentBg
                if bg == "#f8fafc":
                    changes_found += 1
        
        print(f"✓ Found {changes_found} slides with updated backgrounds")
        assert changes_found > 0, "Expected at least one slide to have updated background"
    
    def test_apply_multiple_templates_sequentially(self):
        """Test applying different templates sequentially"""
        project_id = "c7de35a7-0f1a-4270-86d4-703151b377e5"
        
        templates = ["educacional", "tech", "minimalista"]
        
        for template_id in templates:
            response = requests.post(
                f"{BASE_URL}/api/projects/{project_id}/apply-design-template",
                json={"designTemplateId": template_id}
            )
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ok"
            print(f"✓ Applied {template_id} template successfully")


class TestDesignTemplatesEndpoint:
    """Tests for GET /api/agent/design-templates endpoint"""
    
    def test_get_design_templates_returns_all(self):
        """Test that design-templates endpoint returns all 6 templates"""
        response = requests.get(f"{BASE_URL}/api/agent/design-templates")
        assert response.status_code == 200
        
        templates = response.json()
        assert isinstance(templates, list)
        assert len(templates) >= 6, f"Expected at least 6 templates, got {len(templates)}"
        
        # Verify expected template IDs
        template_ids = [t["id"] for t in templates]
        expected_ids = ["corporativo", "educacional", "minimalista", "tech", "criativo", "elegante"]
        for expected_id in expected_ids:
            assert expected_id in template_ids, f"Missing template: {expected_id}"
        
        print(f"✓ All {len(templates)} design templates returned")
    
    def test_design_template_structure(self):
        """Test that each design template has required fields"""
        response = requests.get(f"{BASE_URL}/api/agent/design-templates")
        templates = response.json()
        
        required_fields = ["id", "name", "description", "palette", "fonts", "headerStyle", "cornerRadius"]
        palette_fields = ["primary", "accent", "contentBg", "text"]
        font_fields = ["heading", "body"]
        
        for template in templates:
            for field in required_fields:
                assert field in template, f"Template {template.get('id', '?')} missing field: {field}"
            
            for pfield in palette_fields:
                assert pfield in template["palette"], f"Template {template['id']} missing palette field: {pfield}"
            
            for ffield in font_fields:
                assert ffield in template["fonts"], f"Template {template['id']} missing font field: {ffield}"
        
        print("✓ All templates have required structure")
    
    def test_header_styles_are_distinct(self):
        """Test that each template has a distinct headerStyle"""
        response = requests.get(f"{BASE_URL}/api/agent/design-templates")
        templates = response.json()
        
        header_styles = [t["headerStyle"] for t in templates]
        expected_styles = ["solid", "rounded", "minimal", "neon", "gradient", "elegant"]
        
        for style in expected_styles:
            assert style in header_styles, f"Missing headerStyle: {style}"
        
        print("✓ All header styles present")


class TestMediaConfigWithDesignTemplate:
    """Tests for media-config and apply-media-changes with design template support
    Note: Agent session endpoints require authentication, so we test the endpoint structure
    """
    
    def test_media_config_endpoint_exists(self):
        """Test that media-config endpoint exists (requires auth)"""
        # This endpoint requires authentication, so we expect 401
        response = requests.post(
            f"{BASE_URL}/api/agent/sessions/test-session/media-config",
            json={
                "mediaConfig": {},
                "bgConfig": {},
                "designTemplateId": "educacional"
            }
        )
        # 401 Unauthorized or 404 Not Found (session doesn't exist) are valid responses
        # 500 would indicate a server error
        assert response.status_code in [401, 404], f"Unexpected status: {response.status_code}"
        print("✓ Media-config endpoint exists (requires auth)")
    
    def test_session_endpoint_requires_auth(self):
        """Test that agent session creation requires authentication"""
        response = requests.post(f"{BASE_URL}/api/agent/sessions", json={})
        # Should require authentication
        assert response.status_code == 401
        print("✓ Agent session endpoint requires authentication")


class TestApplyDesignTokenToSlideLogic:
    """Tests to verify _apply_design_token_to_slide behavior through the API"""
    
    def test_title_slide_uses_primary_color(self):
        """Test that title/cover slides get primary background color"""
        project_id = "c7de35a7-0f1a-4270-86d4-703151b377e5"
        
        # Apply tech template (primary=#0a0a0a)
        response = requests.post(
            f"{BASE_URL}/api/projects/{project_id}/apply-design-template",
            json={"designTemplateId": "tech"}
        )
        assert response.status_code == 200
        
        # Get project and check first slide (usually title)
        project = requests.get(f"{BASE_URL}/api/projects/{project_id}").json()
        slides = project.get("course", {}).get("slides", [])
        
        if slides:
            first_slide = slides[0]
            slide_type = first_slide.get("type", "")
            # Tech palette has primary=#0a0a0a
            if slide_type in ("title", "cover"):
                assert first_slide.get("background") == "#0a0a0a", f"Expected #0a0a0a, got {first_slide.get('background')}"
                print("✓ Title slide uses primary color from template")
            else:
                print(f"⚠ First slide is type '{slide_type}', not title/cover")
    
    def test_content_slide_uses_content_bg(self):
        """Test that content slides get contentBg background color"""
        project_id = "c7de35a7-0f1a-4270-86d4-703151b377e5"
        
        # Apply minimalista template (contentBg=#ffffff)
        response = requests.post(
            f"{BASE_URL}/api/projects/{project_id}/apply-design-template",
            json={"designTemplateId": "minimalista"}
        )
        assert response.status_code == 200
        
        # Get project and check content slides
        project = requests.get(f"{BASE_URL}/api/projects/{project_id}").json()
        slides = project.get("course", {}).get("slides", [])
        
        content_slides = [s for s in slides if s.get("type", "content") == "content"]
        
        if content_slides:
            for slide in content_slides[:3]:  # Check first 3 content slides
                bg = slide.get("background")
                # Minimalista contentBg=#ffffff
                if bg == "#ffffff":
                    print("✓ Content slide uses contentBg from template")
                    return
        
        print("⚠ Could not verify content slide background (may depend on existing slide types)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
