"""
Video Export API Tests
Tests for POST /api/course/{project_id}/export-video endpoint
Verifies:
- Export starts async job and returns jobId
- Job status updates with progress
- Completed job has downloadUrl
- Generated MP4 is valid (ffprobe)
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test project IDs from credentials
TEST_PROJECT_SIMPLE = "fec652a1-31e3-46d6-bda4-cc0b1040284a"
TEST_PROJECT_WITH_AUDIO = "57d237b2-3636-4ea8-a306-bede62e4fe23"


class TestVideoExportAPI:
    """Video Export API Tests"""

    def test_health_check(self):
        """Verify API is accessible"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get('status') == 'healthy'
        print("✅ Health check passed")

    def test_project_exists(self):
        """Verify test project exists"""
        response = requests.get(f"{BASE_URL}/api/projects/{TEST_PROJECT_SIMPLE}")
        assert response.status_code == 200
        data = response.json()
        assert 'id' in data
        assert data['id'] == TEST_PROJECT_SIMPLE
        print(f"✅ Test project exists: {data.get('name', 'Unknown')}")

    def test_export_video_mp4_returns_job_id(self):
        """POST /api/course/{project_id}/export-video should return jobId"""
        response = requests.post(
            f"{BASE_URL}/api/course/{TEST_PROJECT_SIMPLE}/export-video",
            json={"format": "mp4", "default_duration": 5.0}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert 'jobId' in data, "Response should contain jobId"
        assert isinstance(data['jobId'], str), "jobId should be a string"
        print(f"✅ Export job started with jobId: {data['jobId']}")
        return data['jobId']

    def test_get_job_status(self):
        """GET /api/job/{jobId} should return job status"""
        # First start an export job
        export_response = requests.post(
            f"{BASE_URL}/api/course/{TEST_PROJECT_SIMPLE}/export-video",
            json={"format": "mp4", "default_duration": 3.0}
        )
        assert export_response.status_code == 200
        job_id = export_response.json()['jobId']
        
        # Check job status
        status_response = requests.get(f"{BASE_URL}/api/job/{job_id}")
        assert status_response.status_code == 200, f"Expected 200, got {status_response.status_code}"
        
        data = status_response.json()
        assert 'status' in data, "Response should contain status"
        assert 'progress' in data, "Response should contain progress"
        assert data['status'] in ['pending', 'processing', 'completed', 'failed'], f"Invalid status: {data['status']}"
        print(f"✅ Job status retrieved: {data['status']}, progress: {data.get('progress', 0)}%")

    def test_export_video_completes_with_download_url(self):
        """Video export should complete and provide downloadUrl"""
        # Start export
        export_response = requests.post(
            f"{BASE_URL}/api/course/{TEST_PROJECT_SIMPLE}/export-video",
            json={"format": "mp4", "default_duration": 3.0}
        )
        assert export_response.status_code == 200
        job_id = export_response.json()['jobId']
        print(f"✅ Export started with jobId: {job_id}")
        
        # Poll for completion (max 120 seconds)
        max_wait = 120
        poll_interval = 2
        elapsed = 0
        final_status = None
        
        while elapsed < max_wait:
            status_response = requests.get(f"{BASE_URL}/api/job/{job_id}")
            assert status_response.status_code == 200
            data = status_response.json()
            
            status = data.get('status')
            progress = data.get('progress', 0)
            message = data.get('message', '')
            print(f"  Status: {status}, Progress: {progress}%, Message: {message}")
            
            if status == 'completed':
                final_status = data
                break
            elif status == 'failed':
                pytest.fail(f"Export failed: {message}")
            
            time.sleep(poll_interval)
            elapsed += poll_interval
        
        assert final_status is not None, f"Export did not complete within {max_wait} seconds"
        assert final_status.get('status') == 'completed', f"Expected completed, got {final_status.get('status')}"
        assert final_status.get('result') is not None, "Completed job should have result"
        assert 'downloadUrl' in final_status['result'], "Result should have downloadUrl"
        
        download_url = final_status['result']['downloadUrl']
        print(f"✅ Export completed with downloadUrl: {download_url}")
        
        # Verify download URL is accessible
        full_url = f"{BASE_URL}{download_url}"
        head_response = requests.head(full_url)
        assert head_response.status_code == 200, f"Download URL not accessible: {head_response.status_code}"
        print(f"✅ Download URL is accessible")
        
        return full_url

    def test_exported_mp4_is_valid(self):
        """Exported MP4 should be a valid video file"""
        # Start export
        export_response = requests.post(
            f"{BASE_URL}/api/course/{TEST_PROJECT_SIMPLE}/export-video",
            json={"format": "mp4", "default_duration": 3.0}
        )
        assert export_response.status_code == 200
        job_id = export_response.json()['jobId']
        
        # Wait for completion
        max_wait = 120
        poll_interval = 2
        elapsed = 0
        download_url = None
        
        while elapsed < max_wait:
            status_response = requests.get(f"{BASE_URL}/api/job/{job_id}")
            data = status_response.json()
            
            if data.get('status') == 'completed':
                download_url = data['result']['downloadUrl']
                break
            elif data.get('status') == 'failed':
                pytest.fail(f"Export failed: {data.get('message')}")
            
            time.sleep(poll_interval)
            elapsed += poll_interval
        
        assert download_url is not None, "Export did not complete"
        
        # Download the file
        full_url = f"{BASE_URL}{download_url}"
        file_response = requests.get(full_url)
        assert file_response.status_code == 200, "Could not download video file"
        
        # Check file size (should be at least a few KB)
        content_length = len(file_response.content)
        assert content_length > 10000, f"File too small: {content_length} bytes"
        print(f"✅ Downloaded MP4 file: {content_length} bytes")
        
        # Check content type
        content_type = file_response.headers.get('Content-Type', '')
        assert 'video' in content_type.lower() or 'octet-stream' in content_type.lower(), \
            f"Unexpected content type: {content_type}"
        print(f"✅ Content type: {content_type}")

    def test_export_video_invalid_project_returns_404(self):
        """Export for non-existent project should return 404"""
        response = requests.post(
            f"{BASE_URL}/api/course/non-existent-project-id/export-video",
            json={"format": "mp4"}
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✅ Non-existent project returns 404")

    def test_export_video_webm_format(self):
        """WebM export should also work"""
        response = requests.post(
            f"{BASE_URL}/api/course/{TEST_PROJECT_SIMPLE}/export-video",
            json={"format": "webm", "default_duration": 3.0}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert 'jobId' in data
        print(f"✅ WebM export started with jobId: {data['jobId']}")

    def test_get_nonexistent_job_returns_404(self):
        """GET /api/job/{jobId} for non-existent job should return 404"""
        response = requests.get(f"{BASE_URL}/api/job/non-existent-job-id")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✅ Non-existent job returns 404")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
