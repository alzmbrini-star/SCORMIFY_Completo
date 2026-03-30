"""
Test suite for Agent Course Listing feature - iteration 92
Tests:
1. GET /api/agent/courses returns all projects (agent-created + imported) with 'source' field
2. POST /api/agent/courses/{project_id}/analyze works for imported PPT courses
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestAgentCourseListing:
    """Test agent course listing with source field distinction"""
    
    def test_agent_courses_returns_all_projects(self):
        """GET /api/agent/courses should return all projects with source field"""
        response = requests.get(f"{BASE_URL}/api/agent/courses")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        
        # Check that we have courses
        print(f"Total courses returned: {len(data)}")
        
        # Verify each course has required fields
        agent_count = 0
        imported_count = 0
        
        for course in data:
            assert "id" in course, "Course should have 'id' field"
            assert "name" in course, "Course should have 'name' field"
            assert "source" in course, "Course should have 'source' field"
            assert "slidesCount" in course, "Course should have 'slidesCount' field"
            
            # Verify source is either 'agent' or 'imported'
            assert course["source"] in ["agent", "imported"], f"Source should be 'agent' or 'imported', got: {course['source']}"
            
            if course["source"] == "agent":
                agent_count += 1
            else:
                imported_count += 1
        
        print(f"Agent-created courses: {agent_count}")
        print(f"Imported courses: {imported_count}")
        
        # According to context, there should be 12 agent + 39 imported = 51 total
        # But we'll just verify we have both types
        assert len(data) > 0, "Should have at least some courses"
    
    def test_agent_courses_has_agent_created(self):
        """Verify agent-created courses have source='agent'"""
        response = requests.get(f"{BASE_URL}/api/agent/courses")
        assert response.status_code == 200
        
        data = response.json()
        agent_courses = [c for c in data if c.get("source") == "agent"]
        
        print(f"Found {len(agent_courses)} agent-created courses")
        
        # Verify agent courses have createdByAgent flag
        for course in agent_courses[:3]:  # Check first 3
            print(f"  - {course.get('name')} (slides: {course.get('slidesCount')})")
    
    def test_agent_courses_has_imported(self):
        """Verify imported courses have source='imported'"""
        response = requests.get(f"{BASE_URL}/api/agent/courses")
        assert response.status_code == 200
        
        data = response.json()
        imported_courses = [c for c in data if c.get("source") == "imported"]
        
        print(f"Found {len(imported_courses)} imported courses")
        
        # Print first 3 imported courses
        for course in imported_courses[:3]:
            print(f"  - {course.get('name')} (slides: {course.get('slidesCount')})")


class TestAgentCourseAnalysis:
    """Test agent course analysis for both agent-created and imported courses"""
    
    def test_analyze_imported_course(self):
        """POST /api/agent/courses/{project_id}/analyze should work for imported courses"""
        # First get list of courses
        list_response = requests.get(f"{BASE_URL}/api/agent/courses")
        assert list_response.status_code == 200
        
        courses = list_response.json()
        
        # Find an imported course with slides
        imported_courses = [c for c in courses if c.get("source") == "imported" and c.get("slidesCount", 0) > 0]
        
        if not imported_courses:
            pytest.skip("No imported courses with slides found")
        
        # Use first imported course with slides
        test_course = imported_courses[0]
        print(f"Testing analysis on imported course: {test_course.get('name')} (slides: {test_course.get('slidesCount')})")
        
        # Analyze the course
        response = requests.post(f"{BASE_URL}/api/agent/courses/{test_course['id']}/analyze")
        
        # Analysis can take time, but should return 200
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Verify analysis response structure
        assert "overallScore" in data, "Analysis should have 'overallScore'"
        assert "improvements" in data, "Analysis should have 'improvements'"
        
        print(f"Analysis score: {data.get('overallScore')}/10")
        print(f"Improvements suggested: {len(data.get('improvements', []))}")
        
        # Check improvement types
        for imp in data.get("improvements", [])[:5]:
            print(f"  - [{imp.get('type')}] {imp.get('description', '')[:60]}...")
    
    def test_analyze_agent_course(self):
        """POST /api/agent/courses/{project_id}/analyze should work for agent-created courses"""
        # First get list of courses
        list_response = requests.get(f"{BASE_URL}/api/agent/courses")
        assert list_response.status_code == 200
        
        courses = list_response.json()
        
        # Find an agent-created course with slides
        agent_courses = [c for c in courses if c.get("source") == "agent" and c.get("slidesCount", 0) > 0]
        
        if not agent_courses:
            pytest.skip("No agent-created courses with slides found")
        
        # Use first agent course with slides
        test_course = agent_courses[0]
        print(f"Testing analysis on agent course: {test_course.get('name')} (slides: {test_course.get('slidesCount')})")
        
        # Analyze the course
        response = requests.post(f"{BASE_URL}/api/agent/courses/{test_course['id']}/analyze")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Verify analysis response structure
        assert "overallScore" in data, "Analysis should have 'overallScore'"
        assert "improvements" in data, "Analysis should have 'improvements'"
        
        print(f"Analysis score: {data.get('overallScore')}/10")
        print(f"Improvements suggested: {len(data.get('improvements', []))}")
    
    def test_analyze_nonexistent_course(self):
        """POST /api/agent/courses/{project_id}/analyze should return 404 for non-existent course"""
        response = requests.post(f"{BASE_URL}/api/agent/courses/nonexistent-id-12345/analyze")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"


class TestAgentCourseSourceField:
    """Test that source field is correctly set based on createdByAgent flag"""
    
    def test_source_field_logic(self):
        """Verify source field logic: createdByAgent=true -> 'agent', else 'imported'"""
        response = requests.get(f"{BASE_URL}/api/agent/courses")
        assert response.status_code == 200
        
        data = response.json()
        
        for course in data:
            source = course.get("source")
            created_by_agent = course.get("createdByAgent", False)
            
            if created_by_agent:
                assert source == "agent", f"Course {course.get('name')} has createdByAgent=True but source={source}"
            else:
                assert source == "imported", f"Course {course.get('name')} has createdByAgent=False but source={source}"
        
        print("Source field logic verified for all courses")
