"""
Test Dashboard Metrics and AI Tutor Chat - New Features
Tests:
1. GET /api/dashboard/metrics - returns totalCourses, totalSlides, totalExports
2. POST /api/tutor/chat - returns AI response with message, courseTopic, courseContext
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestDashboardMetrics:
    """Dashboard metrics endpoint tests"""
    
    def test_get_dashboard_metrics_success(self):
        """Test GET /api/dashboard/metrics returns proper structure"""
        response = requests.get(f"{BASE_URL}/api/dashboard/metrics")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "totalCourses" in data, "Missing totalCourses field"
        assert "totalSlides" in data, "Missing totalSlides field"
        assert "totalExports" in data, "Missing totalExports field"
        
        # Verify numeric types
        assert isinstance(data["totalCourses"], int), "totalCourses should be int"
        assert isinstance(data["totalSlides"], int), "totalSlides should be int"
        assert isinstance(data["totalExports"], int), "totalExports should be int"
        
        print(f"Dashboard Metrics: courses={data['totalCourses']}, slides={data['totalSlides']}, exports={data['totalExports']}")
    
    def test_dashboard_metrics_non_negative(self):
        """Test dashboard metrics are non-negative values"""
        response = requests.get(f"{BASE_URL}/api/dashboard/metrics")
        assert response.status_code == 200
        
        data = response.json()
        assert data["totalCourses"] >= 0, "totalCourses should be >= 0"
        assert data["totalSlides"] >= 0, "totalSlides should be >= 0"
        assert data["totalExports"] >= 0, "totalExports should be >= 0"


class TestAITutorChat:
    """AI Tutor chat endpoint tests"""
    
    def test_tutor_chat_success(self):
        """Test POST /api/tutor/chat with valid input returns AI response"""
        payload = {
            "message": "What is SCORM?",
            "courseTopic": "E-Learning Standards",
            "courseContext": "SCORM stands for Shareable Content Object Reference Model. It is a set of technical standards for e-learning software products."
        }
        
        response = requests.post(f"{BASE_URL}/api/tutor/chat", json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "response" in data, "Missing response field"
        assert isinstance(data["response"], str), "response should be string"
        assert len(data["response"]) > 0, "response should not be empty"
        
        # Verify optional fields
        assert "limitReached" in data, "Missing limitReached field"
        assert isinstance(data["limitReached"], bool), "limitReached should be bool"
        
        print(f"Tutor Response (first 100 chars): {data['response'][:100]}...")
    
    def test_tutor_chat_missing_message(self):
        """Test POST /api/tutor/chat returns 400 when message is missing"""
        payload = {
            "courseTopic": "Test Topic",
            "courseContext": "Test Context"
        }
        
        response = requests.post(f"{BASE_URL}/api/tutor/chat", json=payload)
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
    
    def test_tutor_chat_empty_message(self):
        """Test POST /api/tutor/chat returns 400 when message is empty"""
        payload = {
            "message": "",
            "courseTopic": "Test Topic",
            "courseContext": "Test Context"
        }
        
        response = requests.post(f"{BASE_URL}/api/tutor/chat", json=payload)
        assert response.status_code == 400, f"Expected 400 for empty message, got {response.status_code}"
    
    def test_tutor_chat_with_history(self):
        """Test POST /api/tutor/chat with conversation history"""
        payload = {
            "message": "Can you explain more?",
            "courseTopic": "E-Learning Development",
            "courseContext": "Creating interactive e-learning content.",
            "history": [
                {"role": "user", "content": "What tools do I need?"},
                {"role": "assistant", "content": "You need an authoring tool like Scormify."}
            ]
        }
        
        response = requests.post(f"{BASE_URL}/api/tutor/chat", json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "response" in data
        assert len(data["response"]) > 0
        print(f"Tutor with history response: {data['response'][:100]}...")
    
    def test_tutor_chat_returns_messages_used(self):
        """Test tutor chat returns messagesUsed and messageLimit"""
        payload = {
            "message": "Simple question",
            "courseTopic": "Test",
            "courseContext": "Test context"
        }
        
        response = requests.post(f"{BASE_URL}/api/tutor/chat", json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        # Check optional tracking fields
        if "messagesUsed" in data:
            assert isinstance(data["messagesUsed"], int), "messagesUsed should be int"
        if "messageLimit" in data:
            assert isinstance(data["messageLimit"], int), "messageLimit should be int"


class TestTutorSettings:
    """Tutor settings endpoint tests"""
    
    def test_get_tutor_settings(self):
        """Test GET /api/admin/tutor-settings returns settings"""
        response = requests.get(f"{BASE_URL}/api/admin/tutor-settings")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "enabled" in data, "Missing enabled field"
        assert "tutorName" in data, "Missing tutorName field"
        assert "messageLimit" in data, "Missing messageLimit field"
        
        print(f"Tutor Settings: enabled={data.get('enabled')}, name={data.get('tutorName')}, limit={data.get('messageLimit')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
