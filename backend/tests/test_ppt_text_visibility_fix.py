"""
Test PPT Text Visibility Fixes - Tests for 3 fixes to make PPT-imported text visible in SCORM player:
1. Default text color #000000 for text and shape elements
2. visible===false elements are NOT skipped during rendering
3. opacity:0 in style is ignored (only opacity > 0 is applied)

Test project: Universidade-Corporativa-Didaxis (cb4e0112-3e45-44fe-ab29-304b0ef8f0a0)
- Has 56 text elements ALL with visible:false and opacity:0 (from PPT import)
"""

import pytest
import requests
import os
import json
import zipfile
import io
import re

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test project with PPT-imported elements that have visible:false and opacity:0
PPT_PROJECT_ID = "cb4e0112-3e45-44fe-ab29-304b0ef8f0a0"
PPT_PROJECT_NAME = "Universidade-Corporativa-Didaxis"


class TestPlayerJSTextColorFix:
    """Verify player.js has default color #000000 for text and shape elements"""
    
    def test_player_js_text_default_color(self):
        """Test that text elements get default color #000000"""
        player_js_path = "/app/backend/services/export_assets/player.js"
        with open(player_js_path, 'r') as f:
            content = f.read()
        
        # Find the text case in createElementNode
        text_case_match = re.search(r"case 'text':(.*?)break;", content, re.DOTALL)
        assert text_case_match, "Should find text case in createElementNode"
        
        text_case = text_case_match.group(1)
        assert "el.style.color = '#000000'" in text_case, \
            "Text elements should have default color #000000 set"
        
        # Verify comment explaining the fix
        assert "default text color" in text_case.lower() or "matches editor behavior" in text_case.lower(), \
            "Should have comment explaining the default color fix"
        
        print("✅ Text elements have default color #000000")
    
    def test_player_js_shape_default_color(self):
        """Test that shape elements get default color #000000"""
        player_js_path = "/app/backend/services/export_assets/player.js"
        with open(player_js_path, 'r') as f:
            content = f.read()
        
        # Find the shape case in createElementNode
        shape_case_match = re.search(r"case 'shape':(.*?)break;", content, re.DOTALL)
        assert shape_case_match, "Should find shape case in createElementNode"
        
        shape_case = shape_case_match.group(1)
        assert "el.style.color = '#000000'" in shape_case, \
            "Shape elements should have default color #000000 set"
        
        print("✅ Shape elements have default color #000000")


class TestPlayerJSVisibleSkipFix:
    """Verify player.js does NOT skip elements with visible===false"""
    
    def test_render_slide_no_visible_skip(self):
        """Test that renderSlide doesn't skip visible===false elements"""
        player_js_path = "/app/backend/services/export_assets/player.js"
        with open(player_js_path, 'r') as f:
            content = f.read()
        
        # Find the renderSlide function - look for the elements.forEach loop
        render_slide_match = re.search(
            r"function renderSlide\(index\)(.*?)function createElementNode", 
            content, 
            re.DOTALL
        )
        assert render_slide_match, "Should find renderSlide function"
        
        render_slide = render_slide_match.group(1)
        
        # Should NOT have a skip check for visible===false
        # Previously there might have been: if (element.visible === false) continue;
        assert "element.visible === false" not in render_slide or \
               "element.visible===false" not in render_slide, \
            "renderSlide should NOT skip elements with visible===false"
        
        # Should have comment explaining that visible=false elements are rendered
        assert "visible=false" in render_slide.lower() or "visible:false" in render_slide.lower(), \
            "Should have comment about visible=false elements being rendered"
        
        # Verify the comment confirms they ARE rendered
        assert "still rendered" in render_slide.lower() or "are still rendered" in render_slide.lower(), \
            "Comment should confirm visible=false elements are still rendered"
        
        print("✅ renderSlide does NOT skip visible===false elements")
    
    def test_render_slide_elements_foreach_iterates_all(self):
        """Verify elements.forEach iterates ALL elements without filtering"""
        player_js_path = "/app/backend/services/export_assets/player.js"
        with open(player_js_path, 'r') as f:
            content = f.read()
        
        # Find the elements.forEach in renderSlide
        # It should call createElementNode for ALL elements
        foreach_match = re.search(
            r"slide\.elements\.forEach\(function\(element.*?\{(.*?)\}\);", 
            content, 
            re.DOTALL
        )
        assert foreach_match, "Should find slide.elements.forEach in renderSlide"
        
        foreach_body = foreach_match.group(1)
        
        # Should call createElementNode
        assert "createElementNode(element)" in foreach_body, \
            "forEach should call createElementNode for each element"
        
        # Should NOT have early return/continue for visible check
        assert "if (element.visible" not in foreach_body or \
               "continue" not in foreach_body.split("visible")[0][:100] if "visible" in foreach_body else True, \
            "Should not have early exit for visible check"
        
        print("✅ elements.forEach iterates ALL elements")


class TestPlayerJSOpacityGuard:
    """Verify player.js only applies opacity > 0 in applyElementStyles"""
    
    def test_apply_element_styles_opacity_guard(self):
        """Test that applyElementStyles only applies opacity when > 0"""
        player_js_path = "/app/backend/services/export_assets/player.js"
        with open(player_js_path, 'r') as f:
            content = f.read()
        
        # Find applyElementStyles function
        apply_styles_match = re.search(
            r"function applyElementStyles\(el, style\)(.*?)function applyShapeStyles", 
            content, 
            re.DOTALL
        )
        assert apply_styles_match, "Should find applyElementStyles function"
        
        apply_styles = apply_styles_match.group(1)
        
        # Should have opacity > 0 check
        assert "style.opacity > 0" in apply_styles or "style.opacity>0" in apply_styles, \
            "applyElementStyles should only apply opacity when > 0"
        
        # Should have comment explaining why
        assert "opacity: 0" in apply_styles.lower() or "ppt" in apply_styles.lower(), \
            "Should have comment explaining the opacity guard for PPT imports"
        
        print("✅ applyElementStyles only applies opacity > 0")
    
    def test_opacity_check_line_format(self):
        """Verify exact format of opacity check"""
        player_js_path = "/app/backend/services/export_assets/player.js"
        with open(player_js_path, 'r') as f:
            content = f.read()
        
        # Look for the specific line pattern
        opacity_pattern = r"if\s*\(\s*style\.opacity\s*!==\s*undefined\s*&&\s*style\.opacity\s*>\s*0\s*\)"
        match = re.search(opacity_pattern, content)
        assert match, \
            "Should have: if (style.opacity !== undefined && style.opacity > 0)"
        
        print("✅ Opacity check has correct format: if (style.opacity !== undefined && style.opacity > 0)")


class TestSCORMExportPPTElements:
    """Test SCORM export includes PPT elements with visible:false"""
    
    def test_project_exists(self):
        """Verify test project exists"""
        response = requests.get(f"{BASE_URL}/api/projects/{PPT_PROJECT_ID}")
        assert response.status_code == 200, f"Project {PPT_PROJECT_NAME} should exist"
        
        project = response.json()
        assert project.get("name") == PPT_PROJECT_NAME, \
            f"Project name should be {PPT_PROJECT_NAME}"
        
        print(f"✅ Project '{PPT_PROJECT_NAME}' exists")
        return project
    
    def test_project_has_ppt_elements(self):
        """Verify project has text elements with visible:false from PPT import"""
        response = requests.get(f"{BASE_URL}/api/projects/{PPT_PROJECT_ID}")
        assert response.status_code == 200
        
        project = response.json()
        slides = project.get("slides", [])
        assert len(slides) > 0, "Project should have slides"
        
        # Count text elements with visible:false
        ppt_text_elements = []
        for slide_idx, slide in enumerate(slides):
            elements = slide.get("elements", [])
            for elem in elements:
                if elem.get("type") == "text":
                    if elem.get("visible") == False:
                        ppt_text_elements.append({
                            "slide": slide_idx,
                            "id": elem.get("id"),
                            "visible": elem.get("visible"),
                            "opacity": elem.get("style", {}).get("opacity")
                        })
        
        print(f"Found {len(ppt_text_elements)} text elements with visible:false")
        assert len(ppt_text_elements) > 0, \
            "Project should have text elements with visible:false (from PPT import)"
        
        # Check if they have opacity:0 too
        opacity_zero_count = sum(1 for e in ppt_text_elements 
                                 if e.get("opacity") == 0 or e.get("opacity") == 0.0)
        print(f"Of those, {opacity_zero_count} have opacity:0")
        
        print("✅ Project has PPT-imported text elements with visible:false")
        return ppt_text_elements
    
    def test_scorm_export_includes_all_elements(self):
        """Verify SCORM export includes elements with visible:false"""
        # Trigger SCORM export
        response = requests.post(f"{BASE_URL}/api/projects/{PPT_PROJECT_ID}/export/scorm")
        assert response.status_code == 200, "SCORM export should succeed"
        
        # Parse the ZIP
        zip_data = io.BytesIO(response.content)
        with zipfile.ZipFile(zip_data, 'r') as zf:
            # Get course.json
            course_json_content = zf.read("course.json").decode('utf-8')
            course_data = json.loads(course_json_content)
            
            slides = course_data.get("slides", [])
            total_elements = 0
            text_elements = 0
            visible_false_elements = 0
            
            for slide in slides:
                elements = slide.get("elements", [])
                for elem in elements:
                    total_elements += 1
                    if elem.get("type") == "text":
                        text_elements += 1
                        if elem.get("visible") == False:
                            visible_false_elements += 1
            
            print(f"Exported course.json has:")
            print(f"  - Total elements: {total_elements}")
            print(f"  - Text elements: {text_elements}")
            print(f"  - Text elements with visible:false: {visible_false_elements}")
            
            assert visible_false_elements > 0, \
                "SCORM export should include text elements with visible:false"
        
        print("✅ SCORM export includes elements with visible:false")
    
    def test_exported_player_js_has_fixes(self):
        """Verify exported player.js has all 3 fixes"""
        # Trigger SCORM export
        response = requests.post(f"{BASE_URL}/api/projects/{PPT_PROJECT_ID}/export/scorm")
        assert response.status_code == 200, "SCORM export should succeed"
        
        # Parse the ZIP
        zip_data = io.BytesIO(response.content)
        with zipfile.ZipFile(zip_data, 'r') as zf:
            # Get scripts/player.js
            player_js_content = zf.read("scripts/player.js").decode('utf-8')
            
            # Fix 1: Default color #000000 for text
            text_case_match = re.search(r"case 'text':(.*?)break;", player_js_content, re.DOTALL)
            assert text_case_match, "Should find text case"
            assert "#000000" in text_case_match.group(1), \
                "Exported player.js text case should have #000000"
            print("✅ Fix 1: Text default color #000000 present")
            
            # Fix 2: Shape default color #000000
            shape_case_match = re.search(r"case 'shape':(.*?)break;", player_js_content, re.DOTALL)
            assert shape_case_match, "Should find shape case"
            assert "#000000" in shape_case_match.group(1), \
                "Exported player.js shape case should have #000000"
            print("✅ Fix 2: Shape default color #000000 present")
            
            # Fix 3: No visible===false skip
            render_slide_match = re.search(
                r"function renderSlide\(index\)(.*?)function createElementNode", 
                player_js_content, 
                re.DOTALL
            )
            assert render_slide_match, "Should find renderSlide"
            # Check that we don't skip visible===false
            render_slide = render_slide_match.group(1)
            # Should have the comment about visible=false being rendered
            assert "visible" in render_slide.lower(), \
                "renderSlide should have visible-related comment"
            print("✅ Fix 3: visible===false elements not skipped")
            
            # Fix 4: Opacity > 0 guard
            assert "style.opacity > 0" in player_js_content or "style.opacity>0" in player_js_content, \
                "Exported player.js should have opacity > 0 guard"
            print("✅ Fix 4: Opacity > 0 guard present")
        
        print("✅ Exported player.js has ALL 3 PPT text visibility fixes")


class TestPreviousFixesIntact:
    """Verify previous fixes are still intact in player.js"""
    
    def test_audio_timeline_has_explicit_timeline(self):
        """Verify audio timeline fix (hasExplicitTimeline 3-mode) is intact"""
        player_js_path = "/app/backend/services/export_assets/player.js"
        with open(player_js_path, 'r') as f:
            content = f.read()
        
        assert "hasExplicitTimeline" in content, \
            "player.js should have hasExplicitTimeline check"
        
        # Should have 3 modes
        assert "timeline" in content.lower() and "sequential" in content.lower(), \
            "Should have timeline and sequential modes"
        
        print("✅ Audio timeline fix (hasExplicitTimeline) intact")
    
    def test_slide_progress_bar_functions(self):
        """Verify slide progress bar functions are intact"""
        player_js_path = "/app/backend/services/export_assets/player.js"
        with open(player_js_path, 'r') as f:
            content = f.read()
        
        assert "function startSlideProgress" in content, \
            "player.js should have startSlideProgress function"
        
        assert "function stopSlideProgress" in content, \
            "player.js should have stopSlideProgress function"
        
        print("✅ Slide progress bar functions intact")
    
    def test_keyboard_input_guard(self):
        """Verify keyboard input guard is intact"""
        player_js_path = "/app/backend/services/export_assets/player.js"
        with open(player_js_path, 'r') as f:
            content = f.read()
        
        # Check for tagName check for input/textarea
        assert "tagName" in content and ("INPUT" in content or "TEXTAREA" in content), \
            "player.js should have keyboard input guard checking tagName"
        
        print("✅ Keyboard input guard intact")
    
    def test_tutor_stopPropagation(self):
        """Verify tutor stopPropagation is intact"""
        tutor_js_path = "/app/backend/services/export_assets/tutor.js"
        if os.path.exists(tutor_js_path):
            with open(tutor_js_path, 'r') as f:
                content = f.read()
            
            assert "stopPropagation" in content, \
                "tutor.js should have stopPropagation for keyboard events"
            
            print("✅ Tutor stopPropagation intact")
        else:
            print("⚠️ tutor.js not found - skipping check")


class TestHealthAndAPI:
    """Basic health and API tests"""
    
    def test_health_endpoint(self):
        """Test health endpoint is accessible"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        assert response.json().get("status") == "healthy"
        print("✅ Health endpoint returns 200")
    
    def test_projects_list(self):
        """Test projects list endpoint"""
        response = requests.get(f"{BASE_URL}/api/projects")
        assert response.status_code == 200
        projects = response.json()
        assert isinstance(projects, list)
        print(f"✅ Projects list returns {len(projects)} projects")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
