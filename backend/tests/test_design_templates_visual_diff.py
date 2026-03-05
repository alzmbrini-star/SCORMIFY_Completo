"""
Test Design Templates Visual Differentiation

Tests for verifying that the 6 design templates produce visually distinct course outputs:
1. API returns 6 templates with distinct headerStyle, cornerRadius, fonts and palette
2. _build_header_bar function generates different HTML based on headerStyle
3. _style_content_html and _style_summary_html use palette fonts
4. Session config saves designTemplateId and passes it to course generation

Main agent context: Previous bug was that header bars were all the same solid accent color,
fonts were only on element style but not in HTML content. This fix adds:
- _build_header_bar() function with 6 distinct header styles
- fonts applied consistently in _style_content_html and _style_summary_html
- cornerRadius from template applied to image elements
"""

import pytest
import requests
import os
import sys

# Add backend to path for direct imports
sys.path.insert(0, '/app/backend')

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


# ==========================================================================
# Test 1: GET /api/agent/design-templates returns 6 templates with correct structure
# ==========================================================================
class TestDesignTemplatesAPI:
    """Test design templates API endpoint"""

    def test_design_templates_returns_6_templates(self):
        """Verify that /api/agent/design-templates returns exactly 6 templates"""
        response = requests.get(f"{BASE_URL}/api/agent/design-templates")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        templates = response.json()
        assert isinstance(templates, list), "Response should be a list"
        assert len(templates) == 6, f"Expected 6 templates, got {len(templates)}"
        print(f"✓ API returns 6 templates")

    def test_each_template_has_distinct_headerStyle(self):
        """Verify each template has a distinct headerStyle value"""
        response = requests.get(f"{BASE_URL}/api/agent/design-templates")
        templates = response.json()
        
        expected_styles = {"solid", "rounded", "minimal", "neon", "gradient", "elegant"}
        actual_styles = set()
        
        for t in templates:
            assert "headerStyle" in t, f"Template {t.get('id')} missing headerStyle"
            actual_styles.add(t["headerStyle"])
            print(f"  Template '{t['id']}' has headerStyle: {t['headerStyle']}")
        
        assert actual_styles == expected_styles, f"Expected styles {expected_styles}, got {actual_styles}"
        print(f"✓ All 6 headerStyles are distinct and correct")

    def test_each_template_has_cornerRadius(self):
        """Verify each template has a cornerRadius value"""
        response = requests.get(f"{BASE_URL}/api/agent/design-templates")
        templates = response.json()
        
        corner_radii = {}
        for t in templates:
            assert "cornerRadius" in t, f"Template {t.get('id')} missing cornerRadius"
            corner_radii[t["id"]] = t["cornerRadius"]
        
        # Verify they have different values
        values = list(corner_radii.values())
        unique_values = set(values)
        # At least 4 different cornerRadius values expected (some may be similar but not all same)
        assert len(unique_values) >= 4, f"Expected at least 4 different cornerRadius values, got {len(unique_values)}"
        print(f"✓ Templates have distinct cornerRadius values: {corner_radii}")

    def test_each_template_has_fonts(self):
        """Verify each template has fonts.heading and fonts.body"""
        response = requests.get(f"{BASE_URL}/api/agent/design-templates")
        templates = response.json()
        
        for t in templates:
            assert "fonts" in t, f"Template {t.get('id')} missing fonts"
            assert "heading" in t["fonts"], f"Template {t.get('id')} missing fonts.heading"
            assert "body" in t["fonts"], f"Template {t.get('id')} missing fonts.body"
            print(f"  Template '{t['id']}': heading='{t['fonts']['heading'][:30]}...' body='{t['fonts']['body'][:30]}...'")
        
        print(f"✓ All templates have fonts.heading and fonts.body")

    def test_templates_have_distinct_palettes(self):
        """Verify templates have distinct palette colors"""
        response = requests.get(f"{BASE_URL}/api/agent/design-templates")
        templates = response.json()
        
        accents = set()
        primaries = set()
        
        for t in templates:
            assert "palette" in t, f"Template {t.get('id')} missing palette"
            p = t["palette"]
            assert "accent" in p, f"Template {t.get('id')} missing palette.accent"
            assert "primary" in p, f"Template {t.get('id')} missing palette.primary"
            accents.add(p["accent"])
            primaries.add(p["primary"])
        
        # All accents should be unique
        assert len(accents) == 6, f"Expected 6 unique accent colors, got {len(accents)}"
        print(f"✓ All 6 templates have unique accent colors")


# ==========================================================================
# Test 2: _build_header_bar generates DIFFERENT HTML for each headerStyle
# ==========================================================================
class TestBuildHeaderBarFunction:
    """Test _build_header_bar function produces distinct HTML for each style"""

    def test_header_bar_solid_style(self):
        """Test solid headerStyle generates correct HTML"""
        from services.ai_agent import _build_header_bar
        
        palette = {
            "accent": "#c9a227",
            "primary": "#0f172a",
            "fontHeading": "'Georgia', serif",
            "headerStyle": "solid"
        }
        
        result = _build_header_bar(palette, "Test Module", "Slide Title")
        
        assert f'background:{palette["accent"]}' in result, "Solid style should have accent background"
        assert 'linear-gradient' not in result, "Solid style should NOT have gradient"
        assert 'border-radius' not in result.split('display:')[0], "Solid style should not have rounded corners on main div"
        print(f"✓ Solid style generates correct HTML with accent background")

    def test_header_bar_rounded_style(self):
        """Test rounded headerStyle generates correct HTML"""
        from services.ai_agent import _build_header_bar
        
        palette = {
            "accent": "#10b981",
            "primary": "#065f46",
            "fontHeading": "'Nunito', sans-serif",
            "headerStyle": "rounded"
        }
        
        result = _build_header_bar(palette, "Test Module")
        
        assert 'border-radius:0 0 16px 16px' in result, "Rounded style should have bottom rounded corners"
        assert 'width:calc(100% - 40px)' in result, "Rounded style should have margin effect"
        print(f"✓ Rounded style generates correct HTML with rounded corners")

    def test_header_bar_minimal_style(self):
        """Test minimal headerStyle generates correct HTML"""
        from services.ai_agent import _build_header_bar
        
        palette = {
            "accent": "#64748b",
            "primary": "#334155",
            "fontHeading": "'Outfit', sans-serif",
            "headerStyle": "minimal"
        }
        
        result = _build_header_bar(palette, "Test Module")
        
        assert f'border-bottom:2px solid {palette["accent"]}40' in result, "Minimal style should have thin border"
        assert f'color:{palette["accent"]}' in result, "Minimal style text should be accent color"
        assert f'background:{palette["accent"]}' not in result, "Minimal style should NOT have accent background"
        print(f"✓ Minimal style generates correct HTML with border only")

    def test_header_bar_neon_style(self):
        """Test neon headerStyle generates correct HTML"""
        from services.ai_agent import _build_header_bar
        
        palette = {
            "accent": "#06b6d4",
            "primary": "#0a0a0a",
            "fontHeading": "'JetBrains Mono', monospace",
            "headerStyle": "neon"
        }
        
        result = _build_header_bar(palette, "Test Module")
        
        assert f'background:{palette["primary"]}' in result, "Neon style should have primary background"
        assert f'text-shadow:0 0 8px {palette["accent"]}66' in result, "Neon style should have text shadow"
        assert f'box-shadow:0 2px 12px {palette["accent"]}44' in result, "Neon style should have box shadow"
        print(f"✓ Neon style generates correct HTML with glow effects")

    def test_header_bar_gradient_style(self):
        """Test gradient headerStyle generates correct HTML"""
        from services.ai_agent import _build_header_bar
        
        palette = {
            "accent": "#ec4899",
            "primary": "#4c1d95",
            "fontHeading": "'Poppins', sans-serif",
            "headerStyle": "gradient"
        }
        
        result = _build_header_bar(palette, "Test Module")
        
        assert f'linear-gradient(90deg, {palette["primary"]}, {palette["accent"]})' in result, "Gradient style should have gradient background"
        print(f"✓ Gradient style generates correct HTML with linear gradient")

    def test_header_bar_elegant_style(self):
        """Test elegant headerStyle generates correct HTML"""
        from services.ai_agent import _build_header_bar
        
        palette = {
            "accent": "#d97706",
            "primary": "#1c1917",
            "fontHeading": "'Playfair Display', serif",
            "headerStyle": "elegant"
        }
        
        result = _build_header_bar(palette, "Test Module")
        
        assert f'background:{palette["primary"]}' in result, "Elegant style should have primary background"
        assert f'border-bottom:3px solid {palette["accent"]}' in result, "Elegant style should have thick accent border"
        assert 'width:4px;height:24px' in result, "Elegant style should have vertical accent bar"
        print(f"✓ Elegant style generates correct HTML with vertical accent bar")

    def test_all_styles_produce_different_html(self):
        """Verify all 6 styles produce distinctly different HTML"""
        from services.ai_agent import _build_header_bar
        
        styles = ["solid", "rounded", "minimal", "neon", "gradient", "elegant"]
        results = {}
        
        for style in styles:
            palette = {
                "accent": "#10b981",
                "primary": "#0f172a",
                "fontHeading": "'Inter', sans-serif",
                "headerStyle": style
            }
            results[style] = _build_header_bar(palette, "Test Module", "Slide Title")
        
        # Verify all results are different
        unique_results = set(results.values())
        assert len(unique_results) == 6, f"Expected 6 unique HTML outputs, got {len(unique_results)}"
        
        # Print first 100 chars of each for comparison
        for style, html in results.items():
            print(f"  {style}: {html[:100]}...")
        
        print(f"✓ All 6 header styles produce distinct HTML output")


# ==========================================================================
# Test 3: _style_content_html uses palette fonts in HTML
# ==========================================================================
class TestStyleContentHtmlFonts:
    """Test that _style_content_html applies template fonts to HTML content"""

    def test_style_content_html_applies_heading_font(self):
        """Verify _style_content_html applies fontHeading to h1, h2, h3 tags"""
        from services.ai_agent import _style_content_html
        
        palette = {
            "fontHeading": "'Playfair Display', 'Georgia', serif",
            "fontBody": "'Lato', 'Helvetica', sans-serif"
        }
        
        raw_html = "<h1>Title</h1><h2>Subtitle</h2><h3>Section</h3>"
        result = _style_content_html(raw_html, "#1e293b", palette)
        
        # Count occurrences of heading font in result
        heading_font = palette["fontHeading"]
        h1_match = f'font-family:{heading_font}' in result
        assert h1_match, "h1 should have heading font applied"
        
        # Verify all heading levels have the font
        assert result.count(heading_font) >= 3, "All 3 heading levels should have heading font"
        print(f"✓ _style_content_html applies heading font to h1, h2, h3")

    def test_style_content_html_applies_body_font(self):
        """Verify _style_content_html applies fontBody to p and li tags"""
        from services.ai_agent import _style_content_html
        
        palette = {
            "fontHeading": "'Georgia', serif",
            "fontBody": "'Nunito', sans-serif"
        }
        
        raw_html = "<p>Paragraph text</p><ul><li>List item</li></ul>"
        result = _style_content_html(raw_html, "#1e293b", palette)
        
        body_font = palette["fontBody"]
        assert body_font in result, "Body font should be in result"
        print(f"✓ _style_content_html applies body font to paragraphs and lists")

    def test_style_content_html_wraps_with_body_font(self):
        """Verify _style_content_html wraps content in div with body font"""
        from services.ai_agent import _style_content_html
        
        palette = {
            "fontHeading": "'Georgia', serif",
            "fontBody": "'Inter', sans-serif"
        }
        
        raw_html = "<p>Test</p>"
        result = _style_content_html(raw_html, "#1e293b", palette)
        
        # Should start with div that has body font
        assert result.startswith('<div style="padding:10px;font-family:'), "Should wrap in div with font"
        assert palette["fontBody"] in result.split('>')[0], "Wrapper div should have body font"
        print(f"✓ _style_content_html wraps content with body font")


# ==========================================================================
# Test 4: _style_summary_html uses palette fonts  
# ==========================================================================
class TestStyleSummaryHtmlFonts:
    """Test that _style_summary_html applies template fonts"""

    def test_style_summary_html_applies_heading_font(self):
        """Verify _style_summary_html applies fontHeading to h1, h2 tags"""
        from services.ai_agent import _style_summary_html
        
        palette = {
            "fontHeading": "'JetBrains Mono', monospace",
            "fontBody": "'Inter', sans-serif"
        }
        
        raw_html = "<h1>Summary Title</h1><h2>Key Points</h2>"
        result = _style_summary_html(raw_html, "#10b981", palette)
        
        heading_font = palette["fontHeading"]
        assert heading_font in result, "Heading font should be in summary HTML"
        print(f"✓ _style_summary_html applies heading font to titles")

    def test_style_summary_html_applies_body_font(self):
        """Verify _style_summary_html applies fontBody to p and li tags"""
        from services.ai_agent import _style_summary_html
        
        palette = {
            "fontHeading": "'Georgia', serif",
            "fontBody": "'Poppins', sans-serif"
        }
        
        raw_html = "<p>Summary text</p><ul><li>Point 1</li><li>Point 2</li></ul>"
        result = _style_summary_html(raw_html, "#10b981", palette)
        
        body_font = palette["fontBody"]
        assert body_font in result, "Body font should be in summary HTML"
        print(f"✓ _style_summary_html applies body font to content")


# ==========================================================================
# Test 5: Session config saves designTemplateId
# ==========================================================================
class TestSessionDesignTemplateConfig:
    """Test that session config saves and uses designTemplateId"""

    def test_configure_endpoint_accepts_designTemplateId(self):
        """Verify POST /api/agent/sessions/{id}/configure accepts designTemplateId"""
        # Login first to get auth token
        login_res = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "admin@scormify.com", "password": "admin123"}
        )
        if login_res.status_code != 200:
            pytest.skip("Authentication failed - skipping authenticated test")
        
        token = login_res.json().get("token")
        headers = {"Authorization": f"Bearer {token}"}
        
        # Create a new session
        create_res = requests.post(f"{BASE_URL}/api/agent/sessions", json={}, headers=headers)
        assert create_res.status_code == 200, f"Session creation failed: {create_res.status_code}"
        session = create_res.json()
        session_id = session["id"]
        
        # Configure with designTemplateId
        config_res = requests.post(
            f"{BASE_URL}/api/agent/sessions/{session_id}/configure",
            json={
                "title": "Test Course",
                "designTemplateId": "tech",
                "modules": 2,
                "duration": 20
            },
            headers=headers
        )
        assert config_res.status_code == 200, f"Configure failed: {config_res.status_code}"
        
        # Verify session now has designTemplateId
        get_res = requests.get(f"{BASE_URL}/api/agent/sessions/{session_id}", headers=headers)
        assert get_res.status_code == 200, f"Get session failed: {get_res.status_code}"
        session_data = get_res.json()
        
        assert "config" in session_data, "Session should have config"
        assert session_data["config"].get("designTemplateId") == "tech", "designTemplateId should be saved"
        print(f"✓ Session config saves designTemplateId: {session_data['config'].get('designTemplateId')}")

    def test_get_design_template_by_id_returns_correct_template(self):
        """Test get_design_template_by_id function returns correct template"""
        from services.ai_agent import get_design_template_by_id
        
        # Test each template ID
        for template_id in ["corporativo", "educacional", "minimalista", "tech", "criativo", "elegante"]:
            template = get_design_template_by_id(template_id)
            assert template["id"] == template_id, f"Expected {template_id}, got {template['id']}"
        
        # Test fallback for unknown ID
        fallback = get_design_template_by_id("unknown_id")
        assert fallback["id"] == "educacional", "Unknown ID should return educacional as default"
        print(f"✓ get_design_template_by_id returns correct templates and fallback")


# ==========================================================================
# Test 6: Corner radius is applied to images
# ==========================================================================
class TestCornerRadiusOnImages:
    """Test that cornerRadius from template is applied to image elements"""

    def test_build_content_slide_applies_corner_radius(self):
        """Verify _build_content_slide applies cornerRadius to images"""
        from services.ai_agent import _build_content_slide
        
        # Palette with specific cornerRadius
        palette = {
            "accent": "#ec4899",
            "primary": "#4c1d95",
            "contentBg": "#fdf4ff",
            "text": "#1e293b",
            "fontHeading": "'Poppins', sans-serif",
            "fontBody": "'Poppins', sans-serif",
            "headerStyle": "gradient",
            "cornerRadius": "16px"
        }
        
        sb_slide = {
            "title": "Test Slide",
            "elements": [{"content": "<h2>Test</h2><p>Content</p>"}]
        }
        
        elements = _build_content_slide(sb_slide, palette, "Module 1", "/test/image.jpg")
        
        # Find image element
        image_element = None
        for el in elements:
            if el.get("type") == "image":
                image_element = el
                break
        
        assert image_element is not None, "Should have image element"
        assert image_element.get("style", {}).get("borderRadius") == "16px", \
            f"Image should have cornerRadius 16px, got {image_element.get('style', {}).get('borderRadius')}"
        print(f"✓ _build_content_slide applies cornerRadius to image element")


# ==========================================================================
# Run all tests
# ==========================================================================
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
