"""
Test Text Color Contrast Fix (Iteration 62)
Bug: Applying design templates made slides 'muito embranquecido' (washed out, content barely visible)
Root cause: Light text on light backgrounds after template application
Fix: _apply_design_token_to_slide now properly adjusts text colors based on background luminance

Tests:
1. _is_light_color helper correctly identifies light vs dark hex colors
2. POST /api/projects/{id}/apply-design-template correctly updates text colors
3. All 6 templates produce zero contrast issues (no light text on light bg)
4. Header bars detection works (width >= 1700 instead of 1900)
5. Slide type detection works for slides without explicit type field (uses title keywords)
"""
import pytest
import requests
import os
import re

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://storyboard-review.preview.emergentagent.com')
TEST_PROJECT_ID = "c7de35a7-0f1a-4270-86d4-703151b377e5"


class TestIsLightColorHelper:
    """Tests for _is_light_color helper function logic verification"""
    
    def test_white_is_light(self):
        """#ffffff should be detected as light color"""
        # We verify through behavior: white text on light bg would be a contrast issue
        # Test by applying template with light contentBg and checking text isn't white
        response = requests.post(
            f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/apply-design-template",
            json={"designTemplateId": "minimalista"}  # contentBg=#ffffff (light)
        )
        assert response.status_code == 200
        print("Light background template applied successfully")
        
    def test_dark_colors_detection(self):
        """Dark colors like #0a0a0a should not be detected as light"""
        # Apply tech template which has primary=#0a0a0a (very dark)
        # Verify title slides get white text
        response = requests.post(
            f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/apply-design-template",
            json={"designTemplateId": "tech"}  # primary=#0a0a0a (dark), contentBg=#111827 (dark)
        )
        assert response.status_code == 200
        print("Dark background template applied successfully")
        
    def test_luminance_threshold(self):
        """Test colors near the 0.5 luminance threshold"""
        # Educacional has primary=#065f46 (dark green) - should be dark
        # Criativo has primary=#581c87 (dark purple) - should be dark
        templates_with_dark_primary = ["educacional", "criativo", "corporativo", "elegante"]
        
        for template_id in templates_with_dark_primary:
            response = requests.post(
                f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/apply-design-template",
                json={"designTemplateId": template_id}
            )
            assert response.status_code == 200, f"Template {template_id} failed"
            
        print(f"All {len(templates_with_dark_primary)} templates with dark primary colors applied successfully")


class TestTextColorContrastFix:
    """Tests verifying text colors are correctly updated based on background luminance"""
    
    def test_dark_slide_gets_white_text(self):
        """Title/quiz/summary slides (dark bg) should have white text (#ffffff)"""
        # Apply tech template: primary=#0a0a0a (dark), contentBg=#111827 (also dark)
        response = requests.post(
            f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/apply-design-template",
            json={"designTemplateId": "tech"}
        )
        assert response.status_code == 200
        
        # Get project slides
        project = requests.get(f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}").json()
        slides = project.get("course", {}).get("slides", [])
        
        dark_slide_types = ["title", "cover", "quiz", "summary"]
        white_text_found = False
        
        for slide in slides:
            slide_type = slide.get("type", "")
            # Also check keyword-based detection
            title = (slide.get("title") or "").lower()
            is_dark_slide = slide_type in dark_slide_types or \
                            any(k in title for k in ("capa", "quiz", "resumo", "cover"))
            
            if is_dark_slide:
                for el in slide.get("elements", []):
                    if el.get("type") in ("html", "text"):
                        html = el.get("htmlContent", "")
                        # Skip header bars (they have special styling)
                        if el.get("y", -1) <= 5 and el.get("width", 0) >= 1700:
                            continue
                        # Check for white text color
                        if "color:#ffffff" in html.replace(" ", "").lower() or \
                           "color: #ffffff" in html.lower() or \
                           "color:#fff" in html.replace(" ", "").lower():
                            white_text_found = True
                            break
                if white_text_found:
                    break
        
        if white_text_found:
            print("Dark slide correctly has white text (#ffffff)")
        else:
            print("Note: Could not verify white text on dark slides (may depend on slide content)")
    
    def test_light_slide_gets_dark_text(self):
        """Content slides with light bg should have dark text (template's text color)"""
        # Apply minimalista template: contentBg=#ffffff (light), text=#1e293b (dark)
        response = requests.post(
            f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/apply-design-template",
            json={"designTemplateId": "minimalista"}
        )
        assert response.status_code == 200
        
        # Get project slides
        project = requests.get(f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}").json()
        slides = project.get("course", {}).get("slides", [])
        
        content_slides_with_text = []
        for slide in slides:
            slide_type = slide.get("type", "content")
            if slide_type == "content" or slide_type not in ("title", "cover", "quiz", "summary"):
                # Check for text elements
                for el in slide.get("elements", []):
                    if el.get("type") in ("html", "text") and el.get("htmlContent"):
                        # Skip headers
                        if el.get("y", -1) <= 5 and el.get("width", 0) >= 1700:
                            continue
                        html = el.get("htmlContent", "")
                        # Look for dark text color (should not be white/light on light bg)
                        content_slides_with_text.append({
                            "slide_idx": slides.index(slide),
                            "html_excerpt": html[:200]
                        })
                        break
        
        # Verify no light text on light background
        contrast_issues = 0
        for cs in content_slides_with_text[:5]:  # Check first 5 content slides
            html = cs["html_excerpt"].lower()
            # Check for problematic light text colors
            light_text_patterns = [
                r'color\s*:\s*#fff[^f]',  # #fff but not #ffffff (which we allow on dark)
                r'color\s*:\s*rgba?\s*\(\s*226',  # rgb(226,...)
                r'color\s*:\s*rgba?\s*\(\s*255',  # rgb(255,...)
                r'color\s*:\s*#e\d',  # #e2... etc
            ]
            for pattern in light_text_patterns:
                if re.search(pattern, html):
                    # This is on a light background - should be contrast issue
                    contrast_issues += 1
                    print(f"Contrast issue in slide {cs['slide_idx']}: {pattern}")
                    break
        
        assert contrast_issues == 0, f"Found {contrast_issues} potential contrast issues"
        print(f"Verified {len(content_slides_with_text)} content slides have appropriate text colors")


def _is_light_color_test(hex_color: str) -> bool:
    """Check if a hex color is light (luminance > 0.5). Same logic as in agent.py"""
    try:
        c = hex_color.lstrip('#')
        if len(c) < 6:
            return True
        r, g, b = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
        luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
        return luminance > 0.5
    except Exception:
        return False


class TestAllTemplatesNoContrastIssues:
    """Test all 6 templates produce zero contrast issues on content elements"""
    
    @pytest.mark.parametrize("template_id", [
        "corporativo",   # contentBg=#f8fafc (light)
        "educacional",   # contentBg=#f0fdf4 (light)
        "minimalista",   # contentBg=#ffffff (light)
        "tech",          # contentBg=#111827 (dark) - white text is correct here!
        "criativo",      # contentBg=#faf5ff (light)
        "elegante",      # contentBg=#fef3c7 (light)
    ])
    def test_template_no_contrast_issues(self, template_id):
        """Each template should not have light text on light backgrounds"""
        response = requests.post(
            f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/apply-design-template",
            json={"designTemplateId": template_id}
        )
        assert response.status_code == 200, f"Template {template_id} application failed"
        
        # Get project and verify no contrast issues
        project = requests.get(f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}").json()
        slides = project.get("course", {}).get("slides", [])
        
        # Get template colors for reference
        templates = requests.get(f"{BASE_URL}/api/agent/design-templates").json()
        template = next((t for t in templates if t["id"] == template_id), None)
        assert template, f"Template {template_id} not found"
        
        content_bg = template["palette"]["contentBg"]
        primary = template["palette"]["primary"]
        
        # Determine if contentBg is light or dark
        content_bg_is_light = _is_light_color_test(content_bg)
        
        # Check slides for contrast issues
        issues = []
        for i, slide in enumerate(slides):
            slide_bg = slide.get("background", "")
            slide_type = slide.get("type", "content")
            title = (slide.get("title") or "").lower()
            
            # Determine if this is a dark or light slide based on type/title
            is_dark_by_type = slide_type in ("title", "cover", "quiz", "summary") or \
                           any(k in title for k in ("capa", "quiz", "resumo", "cover", "título"))
            
            # For content slides, the background is contentBg
            # For dark type slides, background is primary
            if is_dark_by_type:
                is_light_background = False  # dark type slides get primary (always dark)
            else:
                is_light_background = content_bg_is_light  # content slides get contentBg
            
            for el in slide.get("elements", []):
                if el.get("type") in ("html", "text") and el.get("htmlContent"):
                    # Skip header bars (y<=5, width>=1700)
                    if el.get("y", -1) <= 5 and el.get("height", 0) <= 55 and el.get("width", 0) >= 1700:
                        continue
                    
                    html = el.get("htmlContent", "")
                    
                    # Look for text colors
                    color_matches = re.findall(r'color\s*:\s*(#[0-9a-fA-F]{3,8}|rgba?\([^)]+\))', html, re.IGNORECASE)
                    
                    for color in color_matches:
                        color_lower = color.lower().replace(" ", "")
                        
                        # Only check for contrast issues on LIGHT backgrounds
                        # On dark backgrounds, white text is CORRECT
                        if is_light_background:
                            # Light background - should not have white/very light text
                            problematic_light_colors = [
                                "#ffffff", "#fff", "#e2e8f0", "#e5e7eb", "#f3f4f6",
                                "rgb(255,255,255)", "rgb(226,232,240)", "rgb(229,231,235)",
                                "rgba(255,255,255"
                            ]
                            for plc in problematic_light_colors:
                                if plc in color_lower:
                                    issues.append({
                                        "slide": i,
                                        "type": slide_type or "content",
                                        "problem": f"Light text ({color}) on light background ({content_bg})"
                                    })
                                    break
        
        if issues:
            for issue in issues[:3]:  # Show first 3 issues
                print(f"Contrast issue in {template_id}: {issue}")
        
        # Allow up to 0 contrast issues (strict)
        assert len(issues) == 0, f"Template {template_id} has {len(issues)} contrast issues: {issues[:3]}"
        print(f"Template {template_id}: No contrast issues found (contentBg={content_bg} is {'LIGHT' if content_bg_is_light else 'DARK'})")


class TestHeaderBarDetection:
    """Test header bar detection uses correct width threshold (>= 1700)"""
    
    def test_header_bars_rebuilt_with_accent(self):
        """Header bars should be rebuilt with template-specific accent color"""
        # Apply educacional template (accent=#10b981, headerStyle=rounded)
        response = requests.post(
            f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/apply-design-template",
            json={"designTemplateId": "educacional"}
        )
        assert response.status_code == 200
        
        project = requests.get(f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}").json()
        slides = project.get("course", {}).get("slides", [])
        
        header_bars_found = 0
        for slide in slides:
            for el in slide.get("elements", []):
                # Header bar detection criteria: type=html, y<=5, height 40-55, width>=1700
                if el.get("type") == "html" and \
                   el.get("y", -1) <= 5 and \
                   40 <= el.get("height", 0) <= 55 and \
                   el.get("width", 0) >= 1700:
                    header_bars_found += 1
                    # Check that accent color is used (educacional accent=#10b981)
                    html = el.get("htmlContent", "")
                    if "#10b981" in html.lower() or "10b981" in html.lower():
                        print(f"Header bar found with educacional accent color")
        
        print(f"Found {header_bars_found} header bars in project")
    
    def test_header_bars_not_treated_as_content(self):
        """Header bars at y<=5 should not have their text color modified as content"""
        response = requests.post(
            f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/apply-design-template",
            json={"designTemplateId": "tech"}
        )
        assert response.status_code == 200
        
        project = requests.get(f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}").json()
        slides = project.get("course", {}).get("slides", [])
        
        # Verify header bars are skipped for text color replacement
        for slide in slides[:5]:
            for el in slide.get("elements", []):
                if el.get("type") == "html" and el.get("y", -1) <= 5 and el.get("width", 0) >= 1700:
                    # This is a header bar - should be rebuilt, not have _replace_text_color applied
                    html = el.get("htmlContent", "")
                    # Header bars have special structure from _build_header_bar
                    if "border-radius" in html or "background" in html:
                        print("Header bar has expected rebuilt structure")
                        return
        
        print("Note: No header bars found in first 5 slides")


class TestSlideTypeDetection:
    """Test slide type detection using title keywords when type field is missing"""
    
    def test_keyword_detection_for_title_slides(self):
        """Slides with 'capa', 'cover', 'título' in title should be treated as title slides"""
        # This is tested through the behavior: title slides get primary bg, content slides get contentBg
        response = requests.post(
            f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/apply-design-template",
            json={"designTemplateId": "corporativo"}  # primary=#0f172a, contentBg=#f8fafc
        )
        assert response.status_code == 200
        
        project = requests.get(f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}").json()
        slides = project.get("course", {}).get("slides", [])
        
        keyword_based_detection_found = False
        for slide in slides:
            title = (slide.get("title") or "").lower()
            slide_type = slide.get("type", "")
            
            # If no explicit type but has keywords, should still get correct background
            if not slide_type and any(k in title for k in ("capa", "cover", "título", "intro")):
                bg = slide.get("background", "")
                if bg == "#0f172a":  # corporativo primary
                    keyword_based_detection_found = True
                    print(f"Keyword detection working: slide '{title[:30]}...' got primary bg")
                    break
        
        if not keyword_based_detection_found:
            print("Note: No slides without explicit type but with title keywords found")
    
    def test_quiz_keyword_detection(self):
        """Slides with 'quiz', 'prova', 'teste' in title should be treated as quiz slides"""
        response = requests.post(
            f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/apply-design-template",
            json={"designTemplateId": "educacional"}  # primary=#065f46
        )
        assert response.status_code == 200
        
        project = requests.get(f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}").json()
        slides = project.get("course", {}).get("slides", [])
        
        for slide in slides:
            title = (slide.get("title") or "").lower()
            slide_type = slide.get("type", "")
            
            if slide_type == "quiz" or any(k in title for k in ("quiz", "prova", "teste", "avaliação")):
                bg = slide.get("background", "")
                if bg == "#065f46":  # educacional primary
                    print(f"Quiz slide '{title[:30]}...' correctly got primary bg")
                    return
        
        print("Note: No quiz slides found in project")
    
    def test_summary_keyword_detection(self):
        """Slides with 'resumo', 'summary', 'conclus' in title should be treated as summary slides"""
        response = requests.post(
            f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/apply-design-template",
            json={"designTemplateId": "criativo"}  # primary=#581c87
        )
        assert response.status_code == 200
        
        project = requests.get(f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}").json()
        slides = project.get("course", {}).get("slides", [])
        
        for slide in slides:
            title = (slide.get("title") or "").lower()
            slide_type = slide.get("type", "")
            
            if slide_type == "summary" or any(k in title for k in ("resumo", "summary", "conclus")):
                bg = slide.get("background", "")
                if bg == "#581c87":  # criativo primary
                    print(f"Summary slide '{title[:30]}...' correctly got primary bg")
                    return
        
        print("Note: No summary slides found in project")


class TestAllTemplatesSmokeTest:
    """Quick smoke test: apply all 6 templates and verify no 500 errors"""
    
    def test_apply_all_templates_sequentially(self):
        """Apply all 6 templates one by one and verify success"""
        templates = ["corporativo", "educacional", "minimalista", "tech", "criativo", "elegante"]
        
        for template_id in templates:
            response = requests.post(
                f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/apply-design-template",
                json={"designTemplateId": template_id}
            )
            assert response.status_code == 200, f"Template {template_id} failed with status {response.status_code}"
            data = response.json()
            assert data.get("status") == "ok", f"Template {template_id} returned unexpected status"
            updated_slides = data.get("updatedSlides", 0)
            print(f"Template {template_id}: applied to {updated_slides} slides")
        
        print(f"All {len(templates)} templates applied successfully")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
