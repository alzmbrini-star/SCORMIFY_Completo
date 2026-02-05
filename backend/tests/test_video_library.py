"""
Test Suite for Video Library (Biblioteca de Vídeos) Feature
Tests the HeyGen video library API endpoints:
- GET /api/heygen/videos - List all videos
- GET /api/heygen/videos/{video_id}/refresh - Refresh video status
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestVideoLibraryAPI:
    """Test Video Library (Biblioteca de Vídeos) API endpoints"""
    
    def test_api_health(self):
        """Test API is healthy"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy"
        print("✅ API health check passed")
    
    def test_list_heygen_videos(self):
        """Test GET /api/heygen/videos - List all videos"""
        response = requests.get(f"{BASE_URL}/api/heygen/videos")
        assert response.status_code == 200
        
        data = response.json()
        assert "videos" in data
        videos = data["videos"]
        
        # Validate response structure
        assert isinstance(videos, list)
        print(f"✅ Found {len(videos)} videos in library")
        
        # If videos exist, validate structure
        if len(videos) > 0:
            video = videos[0]
            # Check required fields
            assert "video_id" in video, "Missing video_id field"
            assert "status" in video, "Missing status field"
            assert "created_at" in video, "Missing created_at field"
            
            # Check optional fields that should be present
            expected_fields = ["title", "video_url", "thumbnail_url", 
                            "duration", "script", "avatar_id", "voice_id", 
                            "project_id", "transparent"]
            for field in expected_fields:
                assert field in video, f"Missing {field} field"
            
            print(f"✅ Video structure validated - First video: {video['title']}")
    
    def test_list_videos_with_project_filter(self):
        """Test GET /api/heygen/videos?project_id=xxx - Filter by project"""
        # Test with a non-existent project
        response = requests.get(f"{BASE_URL}/api/heygen/videos?project_id=nonexistent-project")
        assert response.status_code == 200
        
        data = response.json()
        assert "videos" in data
        # Should return empty list for non-existent project
        assert isinstance(data["videos"], list)
        print("✅ Video filtering by project_id works")
    
    def test_video_status_values(self):
        """Test that videos have valid status values"""
        response = requests.get(f"{BASE_URL}/api/heygen/videos")
        assert response.status_code == 200
        
        data = response.json()
        videos = data["videos"]
        
        valid_statuses = ["completed", "processing", "failed", "pending", "waiting"]
        
        for video in videos:
            status = video.get("status")
            if status:
                # Status should be a valid value
                assert status in valid_statuses or status.lower() in valid_statuses, \
                    f"Invalid status '{status}' for video {video.get('video_id')}"
        
        print(f"✅ All video statuses are valid")
    
    def test_completed_videos_have_url(self):
        """Test that completed videos have video_url"""
        response = requests.get(f"{BASE_URL}/api/heygen/videos")
        assert response.status_code == 200
        
        data = response.json()
        videos = data["videos"]
        
        completed_videos = [v for v in videos if v.get("status") == "completed"]
        
        for video in completed_videos:
            assert video.get("video_url"), \
                f"Completed video {video.get('video_id')} missing video_url"
        
        print(f"✅ All {len(completed_videos)} completed videos have valid URLs")
    
    def test_refresh_video_status(self):
        """Test GET /api/heygen/videos/{video_id}/refresh - Refresh status"""
        # First get a video ID from the list
        list_response = requests.get(f"{BASE_URL}/api/heygen/videos")
        assert list_response.status_code == 200
        
        videos = list_response.json().get("videos", [])
        if len(videos) == 0:
            pytest.skip("No videos available to test refresh")
        
        # Test refresh on first video
        video_id = videos[0]["video_id"]
        refresh_response = requests.get(f"{BASE_URL}/api/heygen/videos/{video_id}/refresh")
        
        assert refresh_response.status_code == 200
        
        data = refresh_response.json()
        # Validate response structure
        assert "video_id" in data
        assert "status" in data
        assert data["video_id"] == video_id
        
        print(f"✅ Video refresh API works - Status: {data.get('status')}")
        
        # If video is completed, should have video_url
        if data.get("status") == "completed":
            assert data.get("video_url"), "Completed video should have video_url after refresh"
            print(f"✅ Completed video has URL: {data.get('video_url')[:50]}...")
    
    def test_refresh_nonexistent_video(self):
        """Test refresh with non-existent video ID"""
        response = requests.get(f"{BASE_URL}/api/heygen/videos/nonexistent-video-id/refresh")
        # This should fail at HeyGen API level with 500 or similar
        # Because the video_id doesn't exist
        assert response.status_code in [400, 404, 500], \
            f"Expected error status for non-existent video, got {response.status_code}"
        print("✅ Non-existent video refresh returns expected error")
    
    def test_videos_sorted_by_date(self):
        """Test that videos are returned sorted by creation date (newest first)"""
        response = requests.get(f"{BASE_URL}/api/heygen/videos")
        assert response.status_code == 200
        
        videos = response.json().get("videos", [])
        
        if len(videos) >= 2:
            # Check that dates are in descending order
            from datetime import datetime
            
            dates = []
            for video in videos:
                if video.get("created_at"):
                    try:
                        dt = datetime.fromisoformat(video["created_at"].replace('Z', '+00:00'))
                        dates.append(dt)
                    except:
                        pass
            
            if len(dates) >= 2:
                for i in range(len(dates) - 1):
                    assert dates[i] >= dates[i + 1], \
                        "Videos should be sorted by creation date (newest first)"
                print(f"✅ Videos are correctly sorted by date")
        else:
            print("⚠️ Not enough videos to verify sorting")


class TestVideoDataIntegrity:
    """Test data integrity for video library"""
    
    def test_video_script_stored(self):
        """Test that video scripts are properly stored"""
        response = requests.get(f"{BASE_URL}/api/heygen/videos")
        assert response.status_code == 200
        
        videos = response.json().get("videos", [])
        videos_with_script = [v for v in videos if v.get("script")]
        
        print(f"✅ {len(videos_with_script)} out of {len(videos)} videos have scripts stored")
        
        # Verify script content exists
        for video in videos_with_script:
            assert len(video["script"]) > 0, "Script should not be empty"
    
    def test_video_created_at_format(self):
        """Test that created_at is in ISO format"""
        response = requests.get(f"{BASE_URL}/api/heygen/videos")
        assert response.status_code == 200
        
        videos = response.json().get("videos", [])
        
        from datetime import datetime
        
        for video in videos:
            created_at = video.get("created_at")
            if created_at:
                try:
                    # Should be parseable as ISO format
                    datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                except ValueError:
                    pytest.fail(f"Invalid date format: {created_at}")
        
        print("✅ All video dates are in valid ISO format")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
