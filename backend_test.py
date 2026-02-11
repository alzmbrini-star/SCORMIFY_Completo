#!/usr/bin/env python3

import requests
import sys
import json
from datetime import datetime

class ScormifyAPITester:
    def __init__(self, base_url="https://scormify-rtf-fix.preview.emergentagent.com"):
        self.base_url = base_url
        self.tests_run = 0
        self.tests_passed = 0
        self.test_results = []
        self.created_project_id = None

    def run_test(self, name, method, endpoint, expected_status, data=None, files=None):
        """Run a single API test"""
        url = f"{self.base_url}/{endpoint}"
        headers = {'Content-Type': 'application/json'} if not files else {}

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        print(f"   URL: {url}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=30)
            elif method == 'POST':
                if files:
                    response = requests.post(url, files=files, data=data, timeout=30)
                else:
                    response = requests.post(url, json=data, headers=headers, timeout=30)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers, timeout=30)

            success = response.status_code == expected_status
            
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                try:
                    response_data = response.json() if response.content else {}
                    print(f"   Response: {json.dumps(response_data, indent=2)[:200]}...")
                except:
                    response_data = {}
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                try:
                    error_data = response.json() if response.content else {}
                    print(f"   Error: {json.dumps(error_data, indent=2)}")
                except:
                    print(f"   Raw response: {response.text[:200]}")
                response_data = {}

            self.test_results.append({
                'name': name,
                'success': success,
                'status_code': response.status_code,
                'expected_status': expected_status,
                'response_data': response_data
            })

            return success, response_data

        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            self.test_results.append({
                'name': name,
                'success': False,
                'error': str(e)
            })
            return False, {}

    def test_health_check(self):
        """Test API health endpoint"""
        return self.run_test("API Health Check", "GET", "api/health", 200)

    def test_root_endpoint(self):
        """Test root API endpoint"""
        return self.run_test("Root API Endpoint", "GET", "api/", 200)

    def test_list_projects_empty(self):
        """Test listing projects (should be empty initially)"""
        success, response = self.run_test("List Projects (Empty)", "GET", "api/projects", 200)
        if success and isinstance(response, list):
            print(f"   Found {len(response)} existing projects")
        return success, response

    def test_create_project(self):
        """Test creating a new project"""
        project_data = {
            "name": f"Test Project {datetime.now().strftime('%H%M%S')}",
            "description": "Test project created by automated testing"
        }
        success, response = self.run_test("Create Project", "POST", "api/projects", 200, data=project_data)
        if success and 'id' in response:
            self.created_project_id = response['id']
            print(f"   Created project ID: {self.created_project_id}")
        return success, response

    def test_get_project(self):
        """Test getting a specific project"""
        if not self.created_project_id:
            print("❌ Skipping - No project ID available")
            return False, {}
        
        return self.run_test("Get Project", "GET", f"api/projects/{self.created_project_id}", 200)

    def test_list_projects_with_data(self):
        """Test listing projects after creating one"""
        success, response = self.run_test("List Projects (With Data)", "GET", "api/projects", 200)
        if success and isinstance(response, list) and len(response) > 0:
            print(f"   Found {len(response)} projects")
        return success, response

    def test_add_slide(self):
        """Test adding a slide to the project"""
        if not self.created_project_id:
            print("❌ Skipping - No project ID available")
            return False, {}
        
        slide_data = {
            "title": "Test Slide",
            "background": "#FFFFFF"
        }
        return self.run_test("Add Slide", "POST", f"api/projects/{self.created_project_id}/slides", 200, data=slide_data)

    def test_add_text_element(self):
        """Test adding a text element to a slide"""
        if not self.created_project_id:
            print("❌ Skipping - No project ID available")
            return False, {}
        
        # First get the project to find slide ID
        success, project = self.run_test("Get Project for Element Test", "GET", f"api/projects/{self.created_project_id}", 200)
        if not success or 'course' not in project or 'slides' not in project['course'] or len(project['course']['slides']) == 0:
            print("❌ No slides found in project")
            return False, {}
        
        slide_id = project['course']['slides'][0]['id']
        element_data = {
            "type": "text",
            "x": 100,
            "y": 100,
            "width": 300,
            "height": 100,
            "content": "Test Text Element"
        }
        return self.run_test("Add Text Element", "POST", f"api/projects/{self.created_project_id}/slides/{slide_id}/elements", 200, data=element_data)

    def test_add_shape_element(self):
        """Test adding a shape element to a slide"""
        if not self.created_project_id:
            print("❌ Skipping - No project ID available")
            return False, {}
        
        # Get the project to find slide ID
        success, project = self.run_test("Get Project for Shape Test", "GET", f"api/projects/{self.created_project_id}", 200)
        if not success or 'course' not in project or 'slides' not in project['course'] or len(project['course']['slides']) == 0:
            print("❌ No slides found in project")
            return False, {}
        
        slide_id = project['course']['slides'][0]['id']
        element_data = {
            "type": "shape",
            "x": 200,
            "y": 200,
            "width": 200,
            "height": 200,
            "shapeType": "rectangle",
            "style": {"fill": "#7C3AED", "stroke": "#5B21B6"}
        }
        return self.run_test("Add Shape Element", "POST", f"api/projects/{self.created_project_id}/slides/{slide_id}/elements", 200, data=element_data)

    def test_save_course(self):
        """Test saving course data"""
        if not self.created_project_id:
            print("❌ Skipping - No project ID available")
            return False, {}
        
        course_data = {
            "title": "Updated Test Course",
            "description": "Course updated via API test"
        }
        return self.run_test("Save Course", "POST", f"api/course/{self.created_project_id}/save", 200, data=course_data)

    def test_export_scorm(self):
        """Test SCORM export functionality"""
        if not self.created_project_id:
            print("❌ Skipping - No project ID available")
            return False, {}
        
        return self.run_test("Export SCORM", "POST", f"api/course/{self.created_project_id}/export-scorm", 200)

    def test_delete_slide(self):
        """Test deleting a slide"""
        if not self.created_project_id:
            print("❌ Skipping - No project ID available")
            return False, {}
        
        # Get the project to find slide ID
        success, project = self.run_test("Get Project for Delete Test", "GET", f"api/projects/{self.created_project_id}", 200)
        if not success or 'course' not in project or 'slides' not in project['course'] or len(project['course']['slides']) == 0:
            print("❌ No slides found in project")
            return False, {}
        
        # Only delete if there are multiple slides
        if len(project['course']['slides']) > 1:
            slide_id = project['course']['slides'][-1]['id']  # Delete the last slide
            return self.run_test("Delete Slide", "DELETE", f"api/projects/{self.created_project_id}/slides/{slide_id}", 200)
        else:
            print("❌ Skipping - Cannot delete the only slide")
            return False, {}

def main():
    print("🚀 Starting Scormify API Tests")
    print("=" * 50)
    
    tester = ScormifyAPITester()
    
    # Run all tests in sequence
    test_methods = [
        tester.test_health_check,
        tester.test_root_endpoint,
        tester.test_list_projects_empty,
        tester.test_create_project,
        tester.test_get_project,
        tester.test_list_projects_with_data,
        tester.test_add_slide,
        tester.test_add_text_element,
        tester.test_add_shape_element,
        tester.test_save_course,
        tester.test_export_scorm,
        tester.test_delete_slide,
    ]
    
    for test_method in test_methods:
        try:
            test_method()
        except Exception as e:
            print(f"❌ Test {test_method.__name__} failed with exception: {e}")
    
    # Print summary
    print("\n" + "=" * 50)
    print(f"📊 Test Results: {tester.tests_passed}/{tester.tests_run} passed")
    
    if tester.tests_passed == tester.tests_run:
        print("🎉 All tests passed!")
        return 0
    else:
        print("⚠️  Some tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())