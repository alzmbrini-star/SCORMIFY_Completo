"""
Test per-slide narration control and cost estimation endpoints (P0 feature iteration 63)

Features tested:
1. POST /api/agent/sessions/{session_id}/save-narration-config - save narration config per slide
2. POST /api/agent/sessions/{session_id}/cost-estimate - calculate ElevenLabs narration cost
3. GET /api/elevenlabs/voices - fetch available voices

ElevenLabs Starter pricing: $5/30,000 characters
"""
import pytest
import requests
import os
from datetime import datetime
import uuid
from pymongo import MongoClient

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://scormify-preview.preview.emergentagent.com').rstrip('/')
MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
DB_NAME = os.environ.get('DB_NAME', 'test_database')

# Module-level setup
_api_client = requests.Session()
_api_client.headers.update({"Content-Type": "application/json"})


def create_test_session():
    """Create a test session with storyboard data in MongoDB"""
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]
    
    test_session_id = f"TEST_narration_{uuid.uuid4().hex[:8]}"
    
    mock_storyboard = {
        "slides": [
            {
                "title": "Introdução ao Curso",
                "type": "title",
                "narrationScript": "Bem-vindos ao curso de Design Instrucional. Neste módulo, vamos explorar os fundamentos.",
                "elements": [{"content": "Slide 1"}]
            },
            {
                "title": "Objetivos",
                "type": "content",
                "narrationScript": "Ao final deste módulo, você será capaz de: criar estruturas de curso claras.",
                "elements": [{"content": "Slide 2"}]
            },
            {
                "title": "Metodologias",
                "type": "content",
                "narrationScript": "As metodologias ativas colocam o aluno no centro do processo educacional.",
                "elements": [{"content": "Slide 3"}]
            },
            {
                "title": "Quiz",
                "type": "quiz",
                "narrationScript": "",  # Quiz without narration
                "elements": []
            },
            {
                "title": "Conclusão",
                "type": "summary",
                "narrationScript": "Parabéns por concluir este módulo. Revise os principais conceitos.",
                "elements": [{"content": "Slide 5"}]
            }
        ]
    }
    
    # Calculate expected chars for slides with scripts (0,1,2,4 have scripts)
    expected_chars = sum(len(s.get("narrationScript", "")) for s in mock_storyboard["slides"])
    
    session_doc = {
        "_id": test_session_id,
        "id": test_session_id,
        "storyboard": mock_storyboard,
        "step": "storyboarded",
        "config": {
            "title": "Curso de Design Instrucional",
            "narrationEnabled": False,  # Start disabled
            "narrationVoiceId": "",
            "narrationSlides": {}
        },
        "contentText": "Test content for course generation",
        "structure": {
            "modules": [{
                "title": "Módulo 1",
                "slides": [
                    {"title": "Slide 1", "type": "content"},
                    {"title": "Slide 2", "type": "content"},
                    {"title": "Quiz", "type": "quiz"}
                ]
            }]
        },
        "mediaConfig": {},
        "createdAt": datetime.utcnow().isoformat(),
        "updatedAt": datetime.utcnow().isoformat(),
    }
    
    # Clean up any existing test session with this ID
    db.agent_sessions.delete_one({"id": test_session_id})
    db.agent_sessions.insert_one(session_doc)
    
    client.close()
    
    return {"session_id": test_session_id, "expected_chars": expected_chars, "storyboard": mock_storyboard}


def cleanup_test_session(session_id):
    """Remove test session from MongoDB"""
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]
    db.agent_sessions.delete_one({"id": session_id})
    client.close()


# ========== Test save-narration-config ==========

def test_save_narration_config_endpoint_returns_200():
    """Test save-narration-config returns 200 for valid session"""
    test_data = create_test_session()
    session_id = test_data["session_id"]
    
    try:
        payload = {
            "narrationSlides": {"0": True, "1": True, "2": False, "4": True},
            "narrationVoiceId": "test-voice-id",
            "narrationEnabled": True
        }
        
        response = _api_client.post(
            f"{BASE_URL}/api/agent/sessions/{session_id}/save-narration-config",
            json=payload
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("status") == "ok"
        print(f"✓ save-narration-config endpoint works: {data}")
    finally:
        cleanup_test_session(session_id)


def test_save_narration_config_returns_enabled_count():
    """Test that endpoint returns correct count of enabled slides"""
    test_data = create_test_session()
    session_id = test_data["session_id"]
    
    try:
        # Enable 4 slides
        payload = {
            "narrationSlides": {"0": True, "1": True, "2": True, "4": True},
            "narrationVoiceId": "voice-123",
            "narrationEnabled": True
        }
        
        response = _api_client.post(
            f"{BASE_URL}/api/agent/sessions/{session_id}/save-narration-config",
            json=payload
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data.get("enabledSlides") == 4
        print(f"✓ Enabled count correct: {data['enabledSlides']} slides")
    finally:
        cleanup_test_session(session_id)


def test_save_narration_config_persists_to_mongodb():
    """Test that config is persisted to MongoDB"""
    test_data = create_test_session()
    session_id = test_data["session_id"]
    
    try:
        payload = {
            "narrationSlides": {"0": True, "2": True},
            "narrationVoiceId": "persisted-voice-test",
            "narrationEnabled": True
        }
        
        response = _api_client.post(
            f"{BASE_URL}/api/agent/sessions/{session_id}/save-narration-config",
            json=payload
        )
        assert response.status_code == 200
        
        # Verify in MongoDB directly
        client = MongoClient(MONGO_URL)
        db = client[DB_NAME]
        session = db.agent_sessions.find_one({"id": session_id}, {"_id": 0, "config": 1})
        client.close()
        
        config = session.get("config", {})
        assert config.get("narrationEnabled") == True
        assert config.get("narrationVoiceId") == "persisted-voice-test"
        assert config.get("narrationSlides") == {"0": True, "2": True}
        print(f"✓ Config persisted to MongoDB correctly")
    finally:
        cleanup_test_session(session_id)


def test_save_narration_config_invalid_session_returns_404():
    """Test that invalid session ID returns 404"""
    fake_id = f"FAKE_{uuid.uuid4().hex}"
    
    response = _api_client.post(
        f"{BASE_URL}/api/agent/sessions/{fake_id}/save-narration-config",
        json={"narrationSlides": {}, "narrationVoiceId": "", "narrationEnabled": False}
    )
    
    assert response.status_code == 404
    print("✓ Invalid session returns 404")


# ========== Test cost-estimate ==========

def test_cost_estimate_endpoint_returns_200():
    """Test cost-estimate returns 200 for valid session"""
    test_data = create_test_session()
    session_id = test_data["session_id"]
    
    try:
        response = _api_client.post(f"{BASE_URL}/api/agent/sessions/{session_id}/cost-estimate")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "estimate" in data
        print(f"✓ cost-estimate endpoint works")
    finally:
        cleanup_test_session(session_id)


def test_cost_estimate_returns_full_structure():
    """Test response includes all expected fields"""
    test_data = create_test_session()
    session_id = test_data["session_id"]
    
    try:
        response = _api_client.post(f"{BASE_URL}/api/agent/sessions/{session_id}/cost-estimate")
        
        assert response.status_code == 200
        data = response.json()
        estimate = data.get("estimate", {})
        
        # Verify structure
        required_fields = ["totalSlides", "contentSlides", "aiImages", "narrationEnabled", "costs", "comparison", "models"]
        for field in required_fields:
            assert field in estimate, f"Missing field: {field}"
        
        costs = estimate["costs"]
        cost_fields = ["text", "images", "narration", "total"]
        for field in cost_fields:
            assert field in costs, f"Missing cost field: {field}"
        
        print(f"✓ Full structure returned with all required fields")
    finally:
        cleanup_test_session(session_id)


def test_cost_estimate_narration_cost_when_enabled():
    """Test narration cost is calculated when narration is enabled"""
    test_data = create_test_session()
    session_id = test_data["session_id"]
    
    try:
        # First enable narration with specific slides
        save_payload = {
            "narrationSlides": {"0": True, "1": True, "4": True},  # 3 slides with scripts
            "narrationVoiceId": "test-voice",
            "narrationEnabled": True
        }
        _api_client.post(
            f"{BASE_URL}/api/agent/sessions/{session_id}/save-narration-config",
            json=save_payload
        )
        
        # Get cost estimate
        response = _api_client.post(f"{BASE_URL}/api/agent/sessions/{session_id}/cost-estimate")
        
        assert response.status_code == 200
        data = response.json()
        estimate = data.get("estimate", {})
        
        assert estimate.get("narrationEnabled") == True
        narration_cost = estimate["costs"]["narration"]
        assert narration_cost > 0, "Narration cost should be > 0 when enabled with scripts"
        print(f"✓ Narration cost calculated: ${narration_cost:.4f}")
    finally:
        cleanup_test_session(session_id)


def test_cost_estimate_elevenlabs_starter_pricing():
    """Test cost uses ElevenLabs Starter pricing: $5/30,000 chars"""
    test_data = create_test_session()
    session_id = test_data["session_id"]
    storyboard = test_data["storyboard"]
    
    try:
        # Enable specific slides and calculate expected cost
        enabled_slides = {"0": True, "1": True, "2": True, "4": True}
        expected_chars = 0
        for i, slide in enumerate(storyboard["slides"]):
            if enabled_slides.get(str(i), False):
                script = slide.get("narrationScript", "")
                expected_chars += len(script)
        
        # Enable narration
        save_payload = {
            "narrationSlides": enabled_slides,
            "narrationVoiceId": "test-voice",
            "narrationEnabled": True
        }
        _api_client.post(
            f"{BASE_URL}/api/agent/sessions/{session_id}/save-narration-config",
            json=save_payload
        )
        
        response = _api_client.post(f"{BASE_URL}/api/agent/sessions/{session_id}/cost-estimate")
        
        assert response.status_code == 200
        data = response.json()
        estimate = data.get("estimate", {})
        
        # Expected: $5/30,000 chars = $0.000167/char
        cost_per_char = 5.0 / 30000.0
        expected_cost = expected_chars * cost_per_char
        actual_cost = estimate["costs"]["narration"]
        
        # Allow small floating point difference (rounding)
        assert abs(actual_cost - expected_cost) < 0.01, f"Expected ~${expected_cost:.4f}, got ${actual_cost:.4f}"
        print(f"✓ Pricing verified: {expected_chars} chars = ${expected_cost:.4f} (actual: ${actual_cost:.4f})")
    finally:
        cleanup_test_session(session_id)


def test_cost_estimate_narration_zero_when_disabled():
    """Test narration cost is 0 when disabled"""
    test_data = create_test_session()
    session_id = test_data["session_id"]
    
    try:
        # Ensure narration is disabled
        save_payload = {
            "narrationSlides": {},
            "narrationVoiceId": "",
            "narrationEnabled": False
        }
        _api_client.post(
            f"{BASE_URL}/api/agent/sessions/{session_id}/save-narration-config",
            json=save_payload
        )
        
        response = _api_client.post(f"{BASE_URL}/api/agent/sessions/{session_id}/cost-estimate")
        
        assert response.status_code == 200
        data = response.json()
        estimate = data.get("estimate", {})
        
        assert estimate.get("narrationEnabled") == False
        assert estimate["costs"]["narration"] == 0
        print("✓ Narration cost is 0 when disabled")
    finally:
        cleanup_test_session(session_id)


def test_cost_estimate_invalid_session_returns_404():
    """Test invalid session returns 404"""
    fake_id = f"FAKE_{uuid.uuid4().hex}"
    
    response = _api_client.post(f"{BASE_URL}/api/agent/sessions/{fake_id}/cost-estimate")
    
    assert response.status_code == 404
    print("✓ Invalid session returns 404")


# ========== Test ElevenLabs voices ==========

def test_elevenlabs_voices_endpoint_returns_200():
    """Test ElevenLabs voices endpoint returns 200"""
    response = _api_client.get(f"{BASE_URL}/api/elevenlabs/voices")
    
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    data = response.json()
    assert "voices" in data
    print(f"✓ ElevenLabs voices endpoint works")


def test_elevenlabs_voices_returns_list_with_fields():
    """Test voices list has required fields"""
    response = _api_client.get(f"{BASE_URL}/api/elevenlabs/voices")
    
    assert response.status_code == 200
    data = response.json()
    voices = data.get("voices", [])
    
    assert isinstance(voices, list)
    
    if len(voices) > 0:
        voice = voices[0]
        assert "voice_id" in voice
        assert "name" in voice
        print(f"✓ {len(voices)} voices returned with voice_id and name fields")
    else:
        print("⚠ No voices returned (API may not be configured)")


# ========== Cost calculation unit tests ==========

def test_cost_per_char_formula():
    """Verify $5/30,000 chars formula"""
    cost_per_char = 5.0 / 30000.0
    
    # ~$0.000167/char
    assert abs(cost_per_char - 0.000166666666) < 0.00001
    print(f"✓ Cost per char: ${cost_per_char:.6f}")


def test_sample_cost_calculations():
    """Test various character counts"""
    cost_per_char = 5.0 / 30000.0
    
    test_cases = [
        (100, 0.0167),
        (1000, 0.167),
        (10000, 1.667),
        (30000, 5.0),
    ]
    
    for chars, expected in test_cases:
        actual = chars * cost_per_char
        assert abs(actual - expected) < 0.01, f"{chars} chars: expected ${expected}, got ${actual}"
    
    print("✓ Sample cost calculations verified")


def test_quota_percentage_calculation():
    """Test monthly quota percentage"""
    monthly_quota = 30000
    
    test_cases = [
        (0, 0.0),
        (3000, 10.0),
        (15000, 50.0),
        (30000, 100.0),
    ]
    
    for chars, expected_pct in test_cases:
        pct = (chars / monthly_quota) * 100
        assert abs(pct - expected_pct) < 0.1
    
    print("✓ Quota percentage calculations verified")
