"""
Test New Media Types: Flipbook, HTML, and Button with external link
Features tested in iteration 53:
- GET /api/agent/sessions/by-project/{project_id} returns session for a project
- POST /api/agent/sessions/{session_id}/media-config accepts flipbook, html, button types
- New media config fields: flipbookSource, htmlSource, htmlCode, buttonText, buttonColor, url
- Backend builder functions for flipbook/html and button types
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials and session from main agent
EXISTING_SESSION_ID = "3c7aba89-3c78-47af-992a-8f350ef194fd"
EXISTING_PROJECT_ID = "9a5a07ea-1dd5-477f-b026-c8e396a05ccc"


class TestByProjectEndpoint:
    """Test GET /api/agent/sessions/by-project/{project_id}"""

    def test_by_project_returns_session(self):
        """Test that by-project endpoint returns the session associated with a project"""
        response = requests.get(f"{BASE_URL}/api/agent/sessions/by-project/{EXISTING_PROJECT_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "id" in data, "Response should have 'id' field"
        assert "storyboard" in data or data.get("step") is not None, "Response should have session data"
        print(f"✓ Found session for project {EXISTING_PROJECT_ID}")
        print(f"  Session ID: {data.get('id')}")
        print(f"  Step: {data.get('step')}")

    def test_by_project_nonexistent_returns_404(self):
        """Test that nonexistent project returns 404"""
        response = requests.get(f"{BASE_URL}/api/agent/sessions/by-project/nonexistent-project-123")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ 404 returned for nonexistent project")

    def test_by_project_session_has_required_fields(self):
        """Test that session returned by by-project has required fields"""
        response = requests.get(f"{BASE_URL}/api/agent/sessions/by-project/{EXISTING_PROJECT_ID}")
        assert response.status_code == 200
        
        data = response.json()
        # Check for fields needed for media editing
        session_fields = list(data.keys())
        print(f"  Session fields: {session_fields}")
        
        # Should NOT include contentText (excluded in projection)
        assert "contentText" not in data, "contentText should be excluded"
        # Should NOT include MongoDB _id
        assert "_id" not in data, "_id should be excluded"
        print("✓ Session has proper field exclusions")


class TestMediaConfigWithNewTypes:
    """Test POST /api/agent/sessions/{session_id}/media-config with new media types"""

    def test_media_config_accepts_flipbook_type(self):
        """Test that media-config accepts flipbook type with extra fields"""
        payload = {
            "mediaConfig": {
                "0": {
                    "type": "flipbook",
                    "url": "https://flipbook-example.com/embed/123",
                    "flipbookSource": "url"
                }
            },
            "bgConfig": {}
        }
        response = requests.post(
            f"{BASE_URL}/api/agent/sessions/{EXISTING_SESSION_ID}/media-config",
            json=payload
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("status") == "ok"
        assert data.get("configured") == 1
        print("✓ Flipbook type accepted in media-config")

    def test_media_config_accepts_html_url_type(self):
        """Test that media-config accepts html type with URL source"""
        payload = {
            "mediaConfig": {
                "1": {
                    "type": "html",
                    "url": "https://embed.example.com/widget",
                    "htmlSource": "url"
                }
            },
            "bgConfig": {}
        }
        response = requests.post(
            f"{BASE_URL}/api/agent/sessions/{EXISTING_SESSION_ID}/media-config",
            json=payload
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("status") == "ok"
        print("✓ HTML type with URL source accepted")

    def test_media_config_accepts_html_code_type(self):
        """Test that media-config accepts html type with code source"""
        payload = {
            "mediaConfig": {
                "2": {
                    "type": "html",
                    "htmlSource": "code",
                    "htmlCode": "<div style='color:red;'>Custom HTML Content</div>"
                }
            },
            "bgConfig": {}
        }
        response = requests.post(
            f"{BASE_URL}/api/agent/sessions/{EXISTING_SESSION_ID}/media-config",
            json=payload
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("status") == "ok"
        print("✓ HTML type with code source accepted")

    def test_media_config_accepts_button_type(self):
        """Test that media-config accepts button type with all config fields"""
        payload = {
            "mediaConfig": {
                "3": {
                    "type": "button",
                    "url": "https://external-link.com/resource",
                    "buttonText": "Saiba Mais",
                    "buttonColor": "#10b981"
                }
            },
            "bgConfig": {}
        }
        response = requests.post(
            f"{BASE_URL}/api/agent/sessions/{EXISTING_SESSION_ID}/media-config",
            json=payload
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("status") == "ok"
        print("✓ Button type with all config fields accepted")

    def test_media_config_accepts_mixed_new_types(self):
        """Test that media-config accepts all new types together"""
        payload = {
            "mediaConfig": {
                "0": {"type": "flipbook", "url": "https://flipbook.example.com", "flipbookSource": "url"},
                "1": {"type": "html", "url": "https://html-embed.example.com", "htmlSource": "url"},
                "2": {"type": "html", "htmlSource": "code", "htmlCode": "<p>Custom HTML</p>"},
                "3": {"type": "button", "url": "https://link.com", "buttonText": "Click Here", "buttonColor": "#ff5500"},
                "4": {"type": "ai_image"},
                "5": {"type": "youtube", "url": "https://youtube.com/watch?v=dQw4w9WgXcQ"},
            },
            "bgConfig": {
                "0": {"type": "gradient", "gradientStart": "#1e3a5f", "gradientEnd": "#0f2027"},
            }
        }
        response = requests.post(
            f"{BASE_URL}/api/agent/sessions/{EXISTING_SESSION_ID}/media-config",
            json=payload
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("status") == "ok"
        assert data.get("configured") == 6
        assert data.get("backgrounds") == 1
        print("✓ Mixed new and existing media types accepted")
        print(f"  Configured slides: {data.get('configured')}")
        print(f"  Custom backgrounds: {data.get('backgrounds')}")

    def test_media_config_invalid_session_returns_404(self):
        """Test that invalid session returns 404"""
        response = requests.post(
            f"{BASE_URL}/api/agent/sessions/nonexistent-session-123/media-config",
            json={"mediaConfig": {}, "bgConfig": {}}
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ 404 returned for nonexistent session")


class TestSessionDataRetrieval:
    """Test retrieving session data with new media config"""

    def test_get_session_includes_media_config(self):
        """Test that GET session includes mediaConfig with new types"""
        response = requests.get(f"{BASE_URL}/api/agent/sessions/{EXISTING_SESSION_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        media_config = data.get("mediaConfig", {})
        print(f"  Current mediaConfig: {media_config}")
        
        # Verify structure after previous tests set config
        if media_config:
            for key, config in media_config.items():
                media_type = config.get("type")
                print(f"    Slide {key}: type={media_type}")
                
                # Verify extra fields are preserved
                if media_type == "flipbook":
                    assert "flipbookSource" in config or "url" in config
                elif media_type == "html":
                    assert "htmlSource" in config or "htmlCode" in config or "url" in config
                elif media_type == "button":
                    assert "buttonText" in config or "buttonColor" in config or "url" in config
        
        print("✓ Session data includes mediaConfig with new types")


class TestAPIHealth:
    """Basic API health checks"""

    def test_api_health(self):
        """Test that API is healthy"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ API health check passed")

    def test_agent_templates_available(self):
        """Test that templates endpoint works"""
        response = requests.get(f"{BASE_URL}/api/agent/templates")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert isinstance(data, list), "Templates should be a list"
        print(f"✓ Templates available: {len(data)} templates")


class TestFlipbookUploadConfig:
    """Test flipbook with upload configuration"""

    def test_flipbook_with_upload_source(self):
        """Test flipbook config with upload source type"""
        payload = {
            "mediaConfig": {
                "0": {
                    "type": "flipbook",
                    "flipbookSource": "upload",
                    "fileName": "test-document.pdf"
                }
            },
            "bgConfig": {}
        }
        response = requests.post(
            f"{BASE_URL}/api/agent/sessions/{EXISTING_SESSION_ID}/media-config",
            json=payload
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ Flipbook with upload source accepted")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
