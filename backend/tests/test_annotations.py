"""
Test suite for annotation functionality
Tests arrow, circle, rectangle annotation creation and persistence
"""
import pytest
import requests
import os
import json

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestAnnotationAPI:
    """Test annotation CRUD operations"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get existing project for testing"""
        response = requests.get(f"{BASE_URL}/api/projects")
        assert response.status_code == 200
        projects = response.json()
        assert len(projects) > 0, "No projects found for testing"
        self.project = projects[0]
        self.project_id = self.project['id']
        
        # Get first slide
        slides = self.project.get('course', {}).get('slides', [])
        assert len(slides) > 0, "No slides found in project"
        self.slide_id = slides[0]['id']
        
    def test_get_project_with_annotations(self):
        """Test that project returns with existing annotations"""
        response = requests.get(f"{BASE_URL}/api/projects/{self.project_id}")
        assert response.status_code == 200
        
        project = response.json()
        slides = project.get('course', {}).get('slides', [])
        
        # Check first slide has annotations
        first_slide = slides[0]
        annotations = first_slide.get('annotations', [])
        
        print(f"Found {len(annotations)} annotations on first slide")
        assert len(annotations) > 0, "Expected annotations on first slide"
        
        # Verify annotation structure
        for ann in annotations:
            assert 'id' in ann
            assert 'type' in ann
            assert 'points' in ann
            assert ann['type'] in ['arrow', 'circle', 'rectangle', 'freehand']
            assert len(ann['points']) >= 2
            
    def test_create_arrow_annotation(self):
        """Test creating an arrow annotation"""
        annotation_data = {
            "type": "arrow",
            "points": [{"x": 100, "y": 100}, {"x": 300, "y": 200}],
            "color": "#EF4444",
            "strokeWidth": 3,
            "includeInExport": True
        }
        
        response = requests.post(
            f"{BASE_URL}/api/projects/{self.project_id}/slides/{self.slide_id}/annotations",
            json=annotation_data
        )
        
        assert response.status_code == 200
        result = response.json()
        
        assert 'id' in result
        assert result['type'] == 'arrow'
        assert len(result['points']) == 2
        assert result['color'] == '#EF4444'
        print(f"✅ Created arrow annotation: {result['id']}")
        
    def test_create_circle_annotation(self):
        """Test creating a circle annotation"""
        annotation_data = {
            "type": "circle",
            "points": [{"x": 200, "y": 200}, {"x": 350, "y": 350}],
            "color": "#3B82F6",
            "strokeWidth": 2,
            "includeInExport": True
        }
        
        response = requests.post(
            f"{BASE_URL}/api/projects/{self.project_id}/slides/{self.slide_id}/annotations",
            json=annotation_data
        )
        
        assert response.status_code == 200
        result = response.json()
        
        assert 'id' in result
        assert result['type'] == 'circle'
        assert len(result['points']) == 2
        print(f"✅ Created circle annotation: {result['id']}")
        
    def test_create_rectangle_annotation(self):
        """Test creating a rectangle annotation"""
        annotation_data = {
            "type": "rectangle",
            "points": [{"x": 400, "y": 100}, {"x": 550, "y": 250}],
            "color": "#10B981",
            "strokeWidth": 3,
            "includeInExport": True
        }
        
        response = requests.post(
            f"{BASE_URL}/api/projects/{self.project_id}/slides/{self.slide_id}/annotations",
            json=annotation_data
        )
        
        assert response.status_code == 200
        result = response.json()
        
        assert 'id' in result
        assert result['type'] == 'rectangle'
        assert len(result['points']) == 2
        print(f"✅ Created rectangle annotation: {result['id']}")
        
    def test_annotation_persistence(self):
        """Test that annotations persist after creation"""
        # Create a test annotation
        annotation_data = {
            "type": "arrow",
            "points": [{"x": 50, "y": 50}, {"x": 150, "y": 150}],
            "color": "#F59E0B",
            "strokeWidth": 2,
            "includeInExport": True
        }
        
        create_response = requests.post(
            f"{BASE_URL}/api/projects/{self.project_id}/slides/{self.slide_id}/annotations",
            json=annotation_data
        )
        assert create_response.status_code == 200
        created_annotation = create_response.json()
        annotation_id = created_annotation['id']
        
        # Fetch project and verify annotation exists
        get_response = requests.get(f"{BASE_URL}/api/projects/{self.project_id}")
        assert get_response.status_code == 200
        
        project = get_response.json()
        slides = project.get('course', {}).get('slides', [])
        first_slide = slides[0]
        annotations = first_slide.get('annotations', [])
        
        # Find our created annotation
        found = any(ann['id'] == annotation_id for ann in annotations)
        assert found, f"Created annotation {annotation_id} not found in project"
        print(f"✅ Annotation {annotation_id} persisted successfully")
        
    def test_delete_annotation(self):
        """Test deleting an annotation"""
        # First create an annotation to delete
        annotation_data = {
            "type": "rectangle",
            "points": [{"x": 600, "y": 100}, {"x": 700, "y": 200}],
            "color": "#8B5CF6",
            "strokeWidth": 2,
            "includeInExport": True
        }
        
        create_response = requests.post(
            f"{BASE_URL}/api/projects/{self.project_id}/slides/{self.slide_id}/annotations",
            json=annotation_data
        )
        assert create_response.status_code == 200
        annotation_id = create_response.json()['id']
        
        # Delete the annotation
        delete_response = requests.delete(
            f"{BASE_URL}/api/projects/{self.project_id}/slides/{self.slide_id}/annotations/{annotation_id}"
        )
        assert delete_response.status_code == 200
        
        # Verify it's deleted
        get_response = requests.get(f"{BASE_URL}/api/projects/{self.project_id}")
        project = get_response.json()
        slides = project.get('course', {}).get('slides', [])
        first_slide = slides[0]
        annotations = first_slide.get('annotations', [])
        
        found = any(ann['id'] == annotation_id for ann in annotations)
        assert not found, f"Annotation {annotation_id} should have been deleted"
        print(f"✅ Annotation {annotation_id} deleted successfully")


class TestSCORMExportWithAnnotations:
    """Test SCORM export includes annotations"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get existing project for testing"""
        response = requests.get(f"{BASE_URL}/api/projects")
        assert response.status_code == 200
        projects = response.json()
        assert len(projects) > 0
        self.project = projects[0]
        self.project_id = self.project['id']
        
    def test_scorm_export_endpoint(self):
        """Test SCORM export endpoint returns download URL"""
        response = requests.post(f"{BASE_URL}/api/course/{self.project_id}/export-scorm")
        
        assert response.status_code == 200
        result = response.json()
        
        assert 'jobId' in result
        assert 'downloadUrl' in result
        assert result['downloadUrl'].endswith('.zip')
        print(f"✅ SCORM export successful: {result['downloadUrl']}")
        
    def test_scorm_package_download(self):
        """Test that SCORM package can be downloaded"""
        # First export
        export_response = requests.post(f"{BASE_URL}/api/course/{self.project_id}/export-scorm")
        assert export_response.status_code == 200
        download_url = export_response.json()['downloadUrl']
        
        # Download the package
        download_response = requests.get(f"{BASE_URL}{download_url}")
        assert download_response.status_code == 200
        assert download_response.headers.get('content-type') == 'application/zip'
        
        # Verify it's a valid zip file (starts with PK)
        assert download_response.content[:2] == b'PK'
        print(f"✅ SCORM package downloaded successfully ({len(download_response.content)} bytes)")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
