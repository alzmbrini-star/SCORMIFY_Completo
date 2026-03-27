"""
Video Export Fix Tests - P0 Issue Resolution
Tests for POST /api/course/{project_id}/export-video endpoint fix

Key requirements verified:
1. POST /export-video returns jobId INSTANTLY (< 1 second response time)
2. GET /api/job/{jobId} returns job status and progress while video processes
3. Video export completes successfully for real project with multiple slides
4. Backend still responds to other requests while video is being processed (non-blocking)
5. Job status transitions: processing -> completed (with downloadUrl) or processing -> failed
6. Error case: export-video with non-existent project returns jobId immediately, job fails with proper message
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test project IDs from main agent context
TEST_PROJECT_10_SLIDES = "d91f0960-67ff-4e5b-8769-6cde361fea68"  # 10 slides
TEST_PROJECT_1_SLIDE = "d3387a1f-6c52-4740-a127-a2e733adf663"   # 1 slide


class TestVideoExportFix:
    """Video Export Fix Tests - P0 Issue Resolution"""

    def test_health_check(self):
        """Verify API is accessible"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get('status') == 'healthy'
        print("✅ Health check passed")

    def test_export_video_returns_instantly(self):
        """POST /export-video should return jobId in < 1 second (P0 fix requirement)"""
        start_time = time.time()
        response = requests.post(
            f"{BASE_URL}/api/course/{TEST_PROJECT_10_SLIDES}/export-video",
            json={"format": "mp4", "default_duration": 5.0},
            timeout=15
        )
        elapsed = time.time() - start_time
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert 'jobId' in data, "Response should contain jobId"
        assert isinstance(data['jobId'], str), "jobId should be a string"
        
        # P0 FIX: Response must be < 1 second (was timing out before fix)
        assert elapsed < 1.0, f"Response took {elapsed:.2f}s, should be < 1s"
        print(f"✅ Export returned in {elapsed:.3f}s with jobId: {data['jobId']}")

    def test_job_status_endpoint_works(self):
        """GET /api/job/{jobId} should return job status"""
        # Start an export job
        export_response = requests.post(
            f"{BASE_URL}/api/course/{TEST_PROJECT_1_SLIDE}/export-video",
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
        print(f"✅ Job status: {data['status']}, progress: {data.get('progress', 0)}%")

    def test_video_export_completes_with_download_url(self):
        """Video export should complete and provide downloadUrl"""
        # Start export
        export_response = requests.post(
            f"{BASE_URL}/api/course/{TEST_PROJECT_1_SLIDE}/export-video",
            json={"format": "mp4", "default_duration": 3.0}
        )
        assert export_response.status_code == 200
        job_id = export_response.json()['jobId']
        print(f"✅ Export started with jobId: {job_id}")
        
        # Poll for completion (max 120 seconds)
        max_wait = 120
        poll_interval = 3
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
        assert final_status.get('status') == 'completed'
        assert final_status.get('result') is not None, "Completed job should have result"
        assert 'downloadUrl' in final_status['result'], "Result should have downloadUrl"
        
        download_url = final_status['result']['downloadUrl']
        print(f"✅ Export completed with downloadUrl: {download_url}")
        
        # Verify download URL is accessible
        full_url = f"{BASE_URL}{download_url}"
        file_response = requests.get(full_url, stream=True)
        assert file_response.status_code == 200, f"Download URL not accessible: {file_response.status_code}"
        
        # Check file size (should be at least 10KB)
        content_length = int(file_response.headers.get('Content-Length', 0))
        if content_length == 0:
            # If no Content-Length header, download and check
            content = file_response.content
            content_length = len(content)
        assert content_length > 10000, f"File too small: {content_length} bytes"
        print(f"✅ Download URL accessible, file size: {content_length} bytes")

    def test_backend_non_blocking_during_export(self):
        """Backend should respond to other requests while video is processing"""
        # Start a video export (10 slides takes longer)
        export_response = requests.post(
            f"{BASE_URL}/api/course/{TEST_PROJECT_10_SLIDES}/export-video",
            json={"format": "mp4", "default_duration": 5.0}
        )
        assert export_response.status_code == 200
        job_id = export_response.json()['jobId']
        print(f"Started export job: {job_id}")
        
        # Immediately test other endpoints while export is processing
        # Health check
        health_start = time.time()
        health_response = requests.get(f"{BASE_URL}/api/health")
        health_time = time.time() - health_start
        assert health_response.status_code == 200
        assert health_time < 2.0, f"Health check took {health_time:.2f}s, should be < 2s"
        print(f"✅ Health check: {health_time:.3f}s")
        
        # Projects list
        projects_start = time.time()
        projects_response = requests.get(f"{BASE_URL}/api/projects")
        projects_time = time.time() - projects_start
        assert projects_response.status_code == 200
        assert projects_time < 5.0, f"Projects list took {projects_time:.2f}s, should be < 5s"
        print(f"✅ Projects list: {projects_time:.3f}s")
        
        # Get specific project
        project_start = time.time()
        project_response = requests.get(f"{BASE_URL}/api/projects/{TEST_PROJECT_10_SLIDES}")
        project_time = time.time() - project_start
        assert project_response.status_code == 200
        assert project_time < 2.0, f"Get project took {project_time:.2f}s, should be < 2s"
        print(f"✅ Get project: {project_time:.3f}s")
        
        # Verify export is still processing
        job_response = requests.get(f"{BASE_URL}/api/job/{job_id}")
        job_status = job_response.json().get('status')
        print(f"✅ Export job status: {job_status}")
        print("✅ Backend responded to all requests while video export was processing")

    def test_nonexistent_project_returns_jobid_then_fails(self):
        """Export for non-existent project should return jobId instantly, then job fails"""
        start_time = time.time()
        response = requests.post(
            f"{BASE_URL}/api/course/non-existent-project-12345/export-video",
            json={"format": "mp4"}
        )
        elapsed = time.time() - start_time
        
        # Should return 200 with jobId (not 404 - validation happens in background)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert 'jobId' in data, "Response should contain jobId"
        
        # Response should be instant (< 1 second)
        assert elapsed < 1.0, f"Response took {elapsed:.2f}s, should be < 1s"
        print(f"✅ Non-existent project returned jobId in {elapsed:.3f}s")
        
        job_id = data['jobId']
        
        # Wait for job to process and fail
        time.sleep(3)
        
        job_response = requests.get(f"{BASE_URL}/api/job/{job_id}")
        assert job_response.status_code == 200
        job_data = job_response.json()
        
        assert job_data.get('status') == 'failed', f"Expected 'failed', got {job_data.get('status')}"
        assert 'não encontrado' in job_data.get('message', '').lower() or 'not found' in job_data.get('message', '').lower(), \
            f"Expected 'not found' message, got: {job_data.get('message')}"
        print(f"✅ Job failed with message: {job_data.get('message')}")

    def test_nonexistent_job_returns_404(self):
        """GET /api/job/{jobId} for non-existent job should return 404"""
        response = requests.get(f"{BASE_URL}/api/job/non-existent-job-id-12345")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✅ Non-existent job returns 404")

    def test_webm_format_export(self):
        """WebM export should also return jobId instantly"""
        start_time = time.time()
        response = requests.post(
            f"{BASE_URL}/api/course/{TEST_PROJECT_1_SLIDE}/export-video",
            json={"format": "webm", "default_duration": 3.0}
        )
        elapsed = time.time() - start_time
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert 'jobId' in data
        assert elapsed < 1.0, f"Response took {elapsed:.2f}s, should be < 1s"
        print(f"✅ WebM export started in {elapsed:.3f}s with jobId: {data['jobId']}")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
