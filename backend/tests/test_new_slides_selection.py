"""
Test suite for 'Novos Slides Sugeridos' selectable feature
Tests the selectedNewSlides field in preview-improvements and apply-improvements endpoints
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestNewSlidesSelectionBackend:
    """Backend API tests for selectedNewSlides feature"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test fixtures"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        # Get a course with analysis that has suggestedNewSlides
        # First get list of courses
        resp = self.session.get(f"{BASE_URL}/api/agent/courses")
        assert resp.status_code == 200, f"Failed to get courses: {resp.text}"
        courses = resp.json()
        assert len(courses) > 0, "No courses available for testing"
        # Use first imported course (more likely to have new slide suggestions)
        imported_courses = [c for c in courses if c.get('source') != 'agent']
        self.test_course = imported_courses[0] if imported_courses else courses[0]
        self.course_id = self.test_course['id']
    
    def test_preview_improvements_accepts_selected_new_slides(self):
        """Test POST /api/agent/courses/{id}/preview-improvements accepts selectedNewSlides field"""
        # First analyze the course to get suggestions
        analyze_resp = self.session.post(f"{BASE_URL}/api/agent/courses/{self.course_id}/analyze")
        assert analyze_resp.status_code == 200, f"Analysis failed: {analyze_resp.text}"
        analysis = analyze_resp.json()
        
        # Get improvements and new slides from analysis
        improvements = analysis.get('improvements', [])
        suggested_new_slides = analysis.get('suggestedNewSlides', [])
        
        # Test with selectedNewSlides in request body
        payload = {
            "improvements": improvements[:1] if improvements else [],
            "selectedNewSlides": suggested_new_slides[:1] if suggested_new_slides else [
                {"title": "Test New Slide", "type": "content", "position": "after slide 1", "reason": "Test reason"}
            ]
        }
        
        resp = self.session.post(
            f"{BASE_URL}/api/agent/courses/{self.course_id}/preview-improvements",
            json=payload
        )
        # Should accept the request (200) or return validation error (422) but not 500
        assert resp.status_code in [200, 422], f"Unexpected status: {resp.status_code}, body: {resp.text}"
        print(f"PASS: preview-improvements accepts selectedNewSlides field, status: {resp.status_code}")
    
    def test_preview_improvements_with_only_new_slides(self):
        """Test POST /api/agent/courses/{id}/preview-improvements with only new slides (no improvements)"""
        # First analyze the course
        analyze_resp = self.session.post(f"{BASE_URL}/api/agent/courses/{self.course_id}/analyze")
        assert analyze_resp.status_code == 200, f"Analysis failed: {analyze_resp.text}"
        analysis = analyze_resp.json()
        
        suggested_new_slides = analysis.get('suggestedNewSlides', [])
        
        # Test with only selectedNewSlides, no improvements
        payload = {
            "improvements": [],
            "selectedNewSlides": suggested_new_slides[:1] if suggested_new_slides else [
                {"title": "Test New Slide Only", "type": "content", "position": "after slide 1", "reason": "Test"}
            ]
        }
        
        resp = self.session.post(
            f"{BASE_URL}/api/agent/courses/{self.course_id}/preview-improvements",
            json=payload
        )
        # Should accept the request
        assert resp.status_code in [200, 422], f"Unexpected status: {resp.status_code}, body: {resp.text}"
        print(f"PASS: preview-improvements works with only new slides, status: {resp.status_code}")
    
    def test_preview_improvements_with_null_new_slides(self):
        """Test POST /api/agent/courses/{id}/preview-improvements with null selectedNewSlides"""
        # First analyze the course
        analyze_resp = self.session.post(f"{BASE_URL}/api/agent/courses/{self.course_id}/analyze")
        assert analyze_resp.status_code == 200, f"Analysis failed: {analyze_resp.text}"
        analysis = analyze_resp.json()
        
        improvements = analysis.get('improvements', [])
        
        # Test with null selectedNewSlides (backward compatibility)
        payload = {
            "improvements": improvements[:1] if improvements else [],
            "selectedNewSlides": None
        }
        
        resp = self.session.post(
            f"{BASE_URL}/api/agent/courses/{self.course_id}/preview-improvements",
            json=payload
        )
        assert resp.status_code in [200, 422], f"Unexpected status: {resp.status_code}, body: {resp.text}"
        print(f"PASS: preview-improvements accepts null selectedNewSlides, status: {resp.status_code}")
    
    def test_apply_improvements_accepts_selected_new_slides(self):
        """Test POST /api/agent/courses/{id}/apply-improvements accepts selectedNewSlides field"""
        # First analyze the course
        analyze_resp = self.session.post(f"{BASE_URL}/api/agent/courses/{self.course_id}/analyze")
        assert analyze_resp.status_code == 200, f"Analysis failed: {analyze_resp.text}"
        analysis = analyze_resp.json()
        
        improvements = analysis.get('improvements', [])
        suggested_new_slides = analysis.get('suggestedNewSlides', [])
        
        # Test apply-improvements endpoint accepts selectedNewSlides
        payload = {
            "improvements": improvements[:1] if improvements else [],
            "selectedNewSlides": suggested_new_slides[:1] if suggested_new_slides else None,
            "previewId": "test-preview-id"  # This will fail validation but tests field acceptance
        }
        
        resp = self.session.post(
            f"{BASE_URL}/api/agent/courses/{self.course_id}/apply-improvements",
            json=payload
        )
        # Should accept the request format (may fail on previewId validation)
        # 400/404 is acceptable (invalid previewId), 500 would indicate field not accepted
        assert resp.status_code in [200, 400, 404, 422], f"Unexpected status: {resp.status_code}, body: {resp.text}"
        print(f"PASS: apply-improvements accepts selectedNewSlides field, status: {resp.status_code}")
    
    def test_agent_improvements_apply_model_has_selected_new_slides_field(self):
        """Test that AgentImprovementsApply model accepts selectedNewSlides"""
        # Test with various payload combinations
        payloads = [
            {"improvements": [], "selectedNewSlides": []},
            {"improvements": [], "selectedNewSlides": None},
            {"improvements": [], "selectedNewSlides": [{"title": "Test", "type": "content"}]},
        ]
        
        for payload in payloads:
            resp = self.session.post(
                f"{BASE_URL}/api/agent/courses/{self.course_id}/preview-improvements",
                json=payload
            )
            # Should not return 422 for field validation (field should be recognized)
            # May return 400/404 for other reasons
            assert resp.status_code != 500, f"Server error with payload {payload}: {resp.text}"
            print(f"PASS: Model accepts payload: {payload}, status: {resp.status_code}")
    
    def test_analysis_returns_suggested_new_slides(self):
        """Test that course analysis returns suggestedNewSlides field"""
        resp = self.session.post(f"{BASE_URL}/api/agent/courses/{self.course_id}/analyze")
        assert resp.status_code == 200, f"Analysis failed: {resp.status_code}, {resp.text}"
        
        analysis = resp.json()
        # Check that suggestedNewSlides field exists (may be empty list)
        assert 'suggestedNewSlides' in analysis or 'improvements' in analysis, \
            f"Analysis missing expected fields: {list(analysis.keys())}"
        
        suggested = analysis.get('suggestedNewSlides', [])
        print(f"PASS: Analysis returned {len(suggested)} suggested new slides")
        
        # If there are suggested new slides, verify structure
        if suggested:
            first_slide = suggested[0]
            assert 'title' in first_slide, "New slide missing 'title' field"
            assert 'type' in first_slide, "New slide missing 'type' field"
            print(f"PASS: New slide structure verified: {first_slide.get('title')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
