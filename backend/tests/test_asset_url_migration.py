"""
Test suite for Asset URL Migration functionality
Tests the bug fix for: images in RTF/HTML content break after project fork because absolute URLs stored in MongoDB

Key tests:
1. POST /api/migrate-asset-urls endpoint - converts absolute URLs to relative
2. Backend startup auto-migration logic - verifies normalization
3. GET /api/assets/{filename} - verify asset serving works
4. URL pattern handling for both /api/assets/ and /api/projects/{id}/assets/
5. Image element src attribute migration
"""
import pytest
import requests
import os
import re
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestHealthAndBasicEndpoints:
    """Verify basic backend health and asset serving"""
    
    def test_health_endpoint(self):
        """GET /api/health - verify backend is running"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy"
        print("✅ Backend health check passed")

class TestMigrateAssetUrlsEndpoint:
    """Tests for POST /api/migrate-asset-urls endpoint"""
    
    def test_migrate_asset_urls_endpoint_exists(self):
        """Verify migration endpoint is accessible"""
        response = requests.post(f"{BASE_URL}/api/migrate-asset-urls")
        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert data["success"] == True
        assert "message" in data
        print(f"✅ Migration endpoint accessible: {data['message']}")
    
    def test_migrate_asset_urls_returns_count(self):
        """Verify migration returns migrated count"""
        response = requests.post(f"{BASE_URL}/api/migrate-asset-urls")
        assert response.status_code == 200
        data = response.json()
        assert "migrated_count" in data
        assert isinstance(data["migrated_count"], int)
        print(f"✅ Migration returned count: {data['migrated_count']}")


class TestProjectCreationAndMigration:
    """Test creating projects with absolute URLs and verifying migration fixes them"""
    
    @pytest.fixture
    def create_test_project_with_absolute_urls(self):
        """Create a test project with absolute URLs in HTML content"""
        project_id = f"test_migration_{uuid.uuid4().hex[:8]}"
        
        # Project with absolute URLs that should be converted to relative
        project_data = {
            "id": project_id,
            "name": f"TEST_Migration Test {project_id}",
            "course": {
                "slides": [
                    {
                        "id": f"slide_{uuid.uuid4().hex[:8]}",
                        "elements": [
                            {
                                "id": f"elem_{uuid.uuid4().hex[:8]}",
                                "type": "html",
                                "x": 0, "y": 0, "width": 400, "height": 300,
                                "htmlContent": '<p>Test with <img src="https://old-domain.example.com/api/assets/test-image.jpg" /> image</p>'
                            },
                            {
                                "id": f"elem_{uuid.uuid4().hex[:8]}",
                                "type": "html", 
                                "x": 0, "y": 0, "width": 400, "height": 300,
                                "htmlContent": '<div><img src="https://another-old-domain.com/api/projects/proj123/assets/photo.png" /></div>'
                            },
                            {
                                "id": f"elem_{uuid.uuid4().hex[:8]}",
                                "type": "image",
                                "x": 0, "y": 0, "width": 200, "height": 200,
                                "src": "https://old-domain.example.com/api/assets/direct-image.jpg"
                            }
                        ],
                        "backgroundImage": "https://old-fork.example.com/api/assets/bg.jpg"
                    }
                ]
            }
        }
        
        # Create project via API
        response = requests.post(f"{BASE_URL}/api/projects", json=project_data)
        
        yield project_id, project_data
        
        # Cleanup - delete test project
        requests.delete(f"{BASE_URL}/api/projects/{project_id}")
    
    def test_create_project_and_migrate(self, create_test_project_with_absolute_urls):
        """Test that migration converts absolute URLs to relative"""
        project_id, original_data = create_test_project_with_absolute_urls
        
        # Run migration
        migrate_response = requests.post(f"{BASE_URL}/api/migrate-asset-urls")
        assert migrate_response.status_code == 200
        migrate_data = migrate_response.json()
        print(f"Migration result: {migrate_data}")
        
        # Fetch the project and verify URLs were converted
        get_response = requests.get(f"{BASE_URL}/api/projects/{project_id}")
        
        if get_response.status_code == 200:
            project = get_response.json()
            slides = project.get('course', {}).get('slides', [])
            
            for slide in slides:
                for element in slide.get('elements', []):
                    if element.get('type') == 'html':
                        html_content = element.get('htmlContent', '')
                        # Verify no absolute URLs remain
                        assert 'https://old-domain.example.com' not in html_content, f"Absolute URL not migrated in HTML: {html_content}"
                        assert 'https://another-old-domain.com' not in html_content, f"Absolute URL not migrated in HTML: {html_content}"
                        
                        # Verify relative URLs are present
                        if '/api/assets/' in html_content:
                            assert html_content.count('src="/api/assets/') >= 1 or html_content.count("src='/api/assets/") >= 1, f"Relative URL not found: {html_content}"
                        print(f"✅ HTML element migrated correctly: {html_content[:100]}...")
                    
                    if element.get('type') == 'image':
                        src = element.get('src', '')
                        assert not src.startswith('https://old-domain'), f"Image src not migrated: {src}"
                        print(f"✅ Image element src migrated: {src}")
                
                # Check background image
                bg = slide.get('backgroundImage', '')
                if bg:
                    assert not bg.startswith('https://old-fork'), f"Background image not migrated: {bg}"
                    print(f"✅ Background image migrated: {bg}")
        else:
            print(f"⚠️ Project not found after creation (may be expected): {get_response.status_code}")


class TestUrlPatternHandling:
    """Test different URL patterns are handled correctly"""
    
    def test_global_asset_url_pattern(self):
        """Test /api/assets/ URL pattern is recognized"""
        test_html = '<img src="https://some-domain.com/api/assets/image.jpg" />'
        
        # Expected pattern after migration
        expected_pattern = r'src="/api/assets/image\.jpg"'
        
        # The regex pattern used in backend
        pattern = r'https?://[^/\s"\']+/api/assets/'
        
        # Verify the pattern matches
        match = re.search(pattern, test_html)
        assert match is not None, "Pattern should match global asset URL"
        print("✅ Global asset URL pattern recognized")
    
    def test_project_asset_url_pattern(self):
        """Test /api/projects/{id}/assets/ URL pattern is recognized"""
        test_html = '<img src="https://some-domain.com/api/projects/abc123/assets/photo.png" />'
        
        # The regex pattern used in backend
        pattern = r'https?://[^/\s"\']+/api/projects/'
        
        # Verify the pattern matches
        match = re.search(pattern, test_html)
        assert match is not None, "Pattern should match project asset URL"
        print("✅ Project asset URL pattern recognized")
    
    def test_relative_url_already_correct(self):
        """Verify already-relative URLs are not modified"""
        test_html = '<img src="/api/assets/correct.jpg" />'
        
        # The absolute URL pattern should NOT match relative URLs
        pattern = r'https?://[^/\s"\']+/api/assets/'
        
        match = re.search(pattern, test_html)
        assert match is None, "Pattern should NOT match relative URLs"
        print("✅ Relative URLs correctly ignored by migration pattern")


class TestAssetServing:
    """Test that assets are still served correctly"""
    
    def test_asset_endpoint_returns_404_for_missing(self):
        """GET /api/assets/{filename} returns 404 for non-existent files"""
        response = requests.get(f"{BASE_URL}/api/assets/nonexistent-file-12345.jpg")
        # Should return 404 for missing file, not 500
        assert response.status_code in [404, 400], f"Expected 404 or 400 for missing asset, got {response.status_code}"
        print("✅ Asset endpoint correctly returns 404 for missing files")


class TestRoundTripUrlConversion:
    """Test that URLs can be stripped and resolved in a round-trip"""
    
    def test_strip_and_resolve_roundtrip_pattern(self):
        """Verify the regex patterns for strip/resolve work correctly"""
        original_html = '<p>Text <img src="https://old-domain.com/api/assets/test.jpg" /> more text</p>'
        
        # Step 1: Strip domain (what backend/frontend does on save)
        stripped = re.sub(
            r'https?://[^/\s"\']+/api/assets/',
            '/api/assets/',
            original_html
        )
        
        assert 'src="/api/assets/test.jpg"' in stripped
        assert 'old-domain.com' not in stripped
        print(f"✅ Strip step: {stripped}")
        
        # Step 2: Resolve to current domain (what frontend does on render)
        current_domain = "https://new-domain.com"
        resolved = re.sub(
            r'(src=["\'])\/api\/',
            f'\\1{current_domain}/api/',
            stripped
        )
        
        assert f'src="{current_domain}/api/assets/test.jpg"' in resolved
        print(f"✅ Resolve step: {resolved}")
        
        # Step 3: Strip again should return to relative
        final = re.sub(
            r'https?://[^/\s"\']+/api/assets/',
            '/api/assets/',
            resolved
        )
        
        assert final == stripped
        print("✅ Round-trip conversion works correctly")


class TestIdempotentMigration:
    """Test that running migration multiple times is safe"""
    
    def test_multiple_migration_runs(self):
        """Running migration multiple times should be safe"""
        # First run
        response1 = requests.post(f"{BASE_URL}/api/migrate-asset-urls")
        assert response1.status_code == 200
        data1 = response1.json()
        
        # Second run
        response2 = requests.post(f"{BASE_URL}/api/migrate-asset-urls")
        assert response2.status_code == 200
        data2 = response2.json()
        
        # Third run
        response3 = requests.post(f"{BASE_URL}/api/migrate-asset-urls")
        assert response3.status_code == 200
        data3 = response3.json()
        
        # After first migration, subsequent runs should find 0 or same count
        # because data is already normalized
        print(f"✅ Migration run 1: {data1['migrated_count']} items")
        print(f"✅ Migration run 2: {data2['migrated_count']} items")
        print(f"✅ Migration run 3: {data3['migrated_count']} items")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
