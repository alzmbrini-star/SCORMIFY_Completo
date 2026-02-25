"""
Test Font Family Export Feature
Tests that fontFamily is properly included in SCORM and HTML exports
"""
import pytest
import requests
import os
import zipfile
import tempfile
import json

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
PROJECT_ID = "edd87206-484c-45d8-ba4b-5ae9bc24b2fb"  # SCORMIFY - V2


class TestFontFamilyExport:
    """Test font family export in SCORM and HTML"""
    
    def test_google_fonts_in_player_template(self):
        """Verify Google Fonts link is in player_template.html"""
        template_path = "/app/backend/services/export_assets/player_template.html"
        
        with open(template_path, 'r') as f:
            content = f.read()
        
        # Check for Google Fonts link
        assert "fonts.googleapis.com" in content, "Google Fonts link not found in player_template.html"
        
        # Check for specific fonts
        fonts_to_check = ["Inter", "Poppins", "Roboto", "Merriweather", "Playfair Display"]
        for font in fonts_to_check:
            assert font in content, f"Font '{font}' not found in player_template.html"
        
        print("✅ Google Fonts link present in player_template.html")
        print(f"   Fonts verified: {', '.join(fonts_to_check)}")
    
    def test_google_fonts_in_index_html(self):
        """Verify Google Fonts link is in frontend index.html"""
        index_path = "/app/frontend/public/index.html"
        
        with open(index_path, 'r') as f:
            content = f.read()
        
        # Check for Google Fonts link
        assert "fonts.googleapis.com" in content, "Google Fonts link not found in index.html"
        
        # Check for specific fonts
        fonts_to_check = ["Inter", "Poppins", "Roboto", "Merriweather", "Playfair Display"]
        for font in fonts_to_check:
            assert font in content, f"Font '{font}' not found in index.html"
        
        print("✅ Google Fonts link present in index.html")
    
    def test_font_family_in_html_exporter(self):
        """Verify fontFamily is handled in html_exporter.py"""
        exporter_path = "/app/backend/services/html_exporter.py"
        
        with open(exporter_path, 'r') as f:
            content = f.read()
        
        # Check for fontFamily handling
        assert "fontFamily" in content, "fontFamily not found in html_exporter.py"
        assert "font-family:" in content, "font-family CSS not found in html_exporter.py"
        assert "fonts.googleapis.com" in content, "Google Fonts link not found in html_exporter.py"
        
        print("✅ fontFamily handling present in html_exporter.py")
    
    def test_font_family_in_player_js(self):
        """Verify fontFamily is handled in SCORM player.js"""
        player_path = "/app/backend/services/export_assets/player.js"
        
        with open(player_path, 'r') as f:
            content = f.read()
        
        # Check for fontFamily handling
        assert "fontFamily" in content, "fontFamily not found in player.js"
        
        print("✅ fontFamily handling present in player.js")
    
    def test_export_scorm_api_status(self):
        """Test SCORM export API returns correct status"""
        if not BASE_URL:
            pytest.skip("REACT_APP_BACKEND_URL not set")
        
        response = requests.post(f"{BASE_URL}/api/course/{PROJECT_ID}/export-scorm")
        
        # Should return 200 with downloadUrl
        assert response.status_code == 200, f"SCORM export failed: {response.status_code} - {response.text}"
        
        data = response.json()
        assert "downloadUrl" in data, "downloadUrl not in SCORM export response"
        
        print(f"✅ SCORM export API returned: {data}")
    
    def test_export_html_api_status(self):
        """Test HTML export API returns correct status"""
        if not BASE_URL:
            pytest.skip("REACT_APP_BACKEND_URL not set")
        
        response = requests.post(f"{BASE_URL}/api/course/{PROJECT_ID}/export-html")
        
        # Should return 200 with downloadUrl
        assert response.status_code == 200, f"HTML export failed: {response.status_code} - {response.text}"
        
        data = response.json()
        assert "downloadUrl" in data, "downloadUrl not in HTML export response"
        
        print(f"✅ HTML export API returned: {data}")
    
    def test_scorm_export_contains_google_fonts(self):
        """Test that SCORM export ZIP contains Google Fonts link"""
        if not BASE_URL:
            pytest.skip("REACT_APP_BACKEND_URL not set")
        
        # Export SCORM
        response = requests.post(f"{BASE_URL}/api/course/{PROJECT_ID}/export-scorm")
        assert response.status_code == 200
        
        download_url = response.json().get("downloadUrl")
        assert download_url, "No download URL in response"
        
        # Download the ZIP
        zip_response = requests.get(f"{BASE_URL}{download_url}")
        assert zip_response.status_code == 200, f"Failed to download SCORM ZIP: {zip_response.status_code}"
        
        # Save to temp file and extract
        with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp:
            tmp.write(zip_response.content)
            tmp_path = tmp.name
        
        try:
            with zipfile.ZipFile(tmp_path, 'r') as zf:
                # Find the HTML file
                html_files = [f for f in zf.namelist() if f.endswith('.html')]
                assert len(html_files) > 0, "No HTML files found in SCORM ZIP"
                
                # Check each HTML file for Google Fonts
                found_fonts = False
                for html_file in html_files:
                    content = zf.read(html_file).decode('utf-8')
                    if "fonts.googleapis.com" in content:
                        found_fonts = True
                        print(f"✅ Google Fonts found in SCORM: {html_file}")
                        break
                
                assert found_fonts, "Google Fonts link not found in any SCORM HTML file"
        finally:
            os.unlink(tmp_path)
    
    def test_html_export_contains_google_fonts(self):
        """Test that HTML export contains Google Fonts link"""
        if not BASE_URL:
            pytest.skip("REACT_APP_BACKEND_URL not set")
        
        # Export HTML
        response = requests.post(f"{BASE_URL}/api/course/{PROJECT_ID}/export-html")
        assert response.status_code == 200
        
        download_url = response.json().get("downloadUrl")
        assert download_url, "No download URL in response"
        
        # Download the HTML
        html_response = requests.get(f"{BASE_URL}{download_url}")
        assert html_response.status_code == 200, f"Failed to download HTML: {html_response.status_code}"
        
        content = html_response.text
        
        # Check for Google Fonts
        assert "fonts.googleapis.com" in content, "Google Fonts link not found in exported HTML"
        
        # Check for specific font families
        fonts_to_check = ["Inter", "Poppins", "Roboto", "Merriweather"]
        found_fonts = [f for f in fonts_to_check if f in content]
        assert len(found_fonts) > 0, f"No expected fonts found in HTML. Checked: {fonts_to_check}"
        
        print(f"✅ Google Fonts found in HTML export: {found_fonts}")


class TestFontFamilyAPI:
    """Test font family via API"""
    
    def test_create_text_element_with_font(self):
        """Test creating a text element with fontFamily"""
        if not BASE_URL:
            pytest.skip("REACT_APP_BACKEND_URL not set")
        
        # First get project to find a slide
        project_response = requests.get(f"{BASE_URL}/api/projects/{PROJECT_ID}")
        assert project_response.status_code == 200
        
        project = project_response.json()
        slides = project.get('course', {}).get('slides', [])
        assert len(slides) > 0, "No slides found in project"
        
        slide_id = slides[0].get('id')
        
        # Create text element with fontFamily
        element_data = {
            "type": "text",
            "x": 50,
            "y": 50,
            "width": 300,
            "height": 100,
            "content": "TEST_FontFamilyTest",
            "style": {
                "fontFamily": "Poppins",
                "fontSize": 24,
                "fontColor": "#333333"
            }
        }
        
        create_response = requests.post(
            f"{BASE_URL}/api/projects/{PROJECT_ID}/slides/{slide_id}/elements",
            json=element_data
        )
        
        assert create_response.status_code == 200, f"Failed to create element: {create_response.text}"
        
        created_element = create_response.json()
        element_id = created_element.get('id')
        
        # Verify fontFamily was saved
        assert created_element.get('style', {}).get('fontFamily') == "Poppins", \
            f"fontFamily not saved correctly: {created_element}"
        
        print(f"✅ Created text element with fontFamily='Poppins': {element_id}")
        
        # Cleanup - delete test element
        delete_response = requests.delete(
            f"{BASE_URL}/api/projects/{PROJECT_ID}/slides/{slide_id}/elements/{element_id}"
        )
        assert delete_response.status_code == 200, f"Failed to delete test element: {delete_response.text}"
        print("✅ Test element cleaned up")
    
    def test_update_text_element_font(self):
        """Test updating fontFamily on existing text element"""
        if not BASE_URL:
            pytest.skip("REACT_APP_BACKEND_URL not set")
        
        # Get project
        project_response = requests.get(f"{BASE_URL}/api/projects/{PROJECT_ID}")
        assert project_response.status_code == 200
        
        project = project_response.json()
        slides = project.get('course', {}).get('slides', [])
        slide_id = slides[0].get('id')
        
        # Create element first
        element_data = {
            "type": "text",
            "x": 100,
            "y": 100,
            "width": 200,
            "height": 50,
            "content": "TEST_UpdateFontTest",
            "style": {
                "fontFamily": "Arial",
                "fontSize": 16
            }
        }
        
        create_response = requests.post(
            f"{BASE_URL}/api/projects/{PROJECT_ID}/slides/{slide_id}/elements",
            json=element_data
        )
        assert create_response.status_code == 200
        element_id = create_response.json().get('id')
        
        # Update fontFamily
        update_data = {
            "style": {
                "fontFamily": "Merriweather",
                "fontSize": 16
            }
        }
        
        update_response = requests.put(
            f"{BASE_URL}/api/projects/{PROJECT_ID}/slides/{slide_id}/elements/{element_id}",
            json=update_data
        )
        assert update_response.status_code == 200
        
        updated_element = update_response.json()
        assert updated_element.get('style', {}).get('fontFamily') == "Merriweather", \
            f"fontFamily not updated: {updated_element}"
        
        print(f"✅ Updated element fontFamily to 'Merriweather'")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/projects/{PROJECT_ID}/slides/{slide_id}/elements/{element_id}")
        print("✅ Test element cleaned up")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
