"""
Quiz Generator API Tests
Tests for quiz question CRUD, AI generation, .doc parsing, and quiz submission endpoints
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test data tracking
test_question_ids = []
test_project_id = None


class TestQuizApiHealth:
    """Basic health and connectivity tests"""
    
    def test_api_health(self):
        """Test API health endpoint"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get('status') == 'healthy'
        print("✅ API Health check passed")


class TestQuestionsCRUD:
    """Test question CRUD operations"""
    
    def test_create_multiple_choice_question(self):
        """Create a multiple choice question"""
        payload = {
            "projectId": "TEST_project_quiz_001",
            "type": "multiple_choice",
            "text": "TEST_Qual é a capital do Brasil?",
            "alternatives": [
                {"text": "Rio de Janeiro", "isCorrect": False},
                {"text": "Brasília", "isCorrect": True},
                {"text": "São Paulo", "isCorrect": False},
                {"text": "Salvador", "isCorrect": False}
            ],
            "explanation": "Brasília é a capital federal do Brasil desde 1960.",
            "points": 1.0,
            "tags": ["geography", "test"]
        }
        
        response = requests.post(f"{BASE_URL}/api/questions", json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "id" in data
        assert data["text"] == payload["text"]
        assert data["type"] == "multiple_choice"
        assert len(data["alternatives"]) == 4
        
        # Verify alternatives have IDs
        for alt in data["alternatives"]:
            assert "id" in alt
            assert "text" in alt
            assert "isCorrect" in alt
        
        # Store for later tests
        test_question_ids.append(data["id"])
        print(f"✅ Created multiple choice question: {data['id']}")
        return data["id"]
    
    def test_create_true_false_question(self):
        """Create a true/false question"""
        payload = {
            "projectId": "TEST_project_quiz_001",
            "type": "true_false",
            "text": "TEST_O Sol gira em torno da Terra.",
            "alternatives": [
                {"text": "Verdadeiro", "isCorrect": False},
                {"text": "Falso", "isCorrect": True}
            ],
            "explanation": "A Terra gira em torno do Sol, não o contrário.",
            "points": 1.0,
            "tags": ["science", "test"]
        }
        
        response = requests.post(f"{BASE_URL}/api/questions", json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "id" in data
        assert data["type"] == "true_false"
        assert len(data["alternatives"]) == 2
        
        test_question_ids.append(data["id"])
        print(f"✅ Created true/false question: {data['id']}")
        return data["id"]
    
    def test_list_questions(self):
        """List all questions"""
        response = requests.get(f"{BASE_URL}/api/questions")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        print(f"✅ Listed {len(data)} questions")
        return data
    
    def test_list_questions_by_project(self):
        """List questions filtered by project"""
        response = requests.get(f"{BASE_URL}/api/questions", params={"project_id": "TEST_project_quiz_001"})
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        # Should contain our test questions
        for q in data:
            assert q.get("projectId") == "TEST_project_quiz_001"
        print(f"✅ Listed {len(data)} questions for project TEST_project_quiz_001")
    
    def test_get_single_question(self):
        """Get a single question by ID"""
        if not test_question_ids:
            pytest.skip("No test questions created")
        
        question_id = test_question_ids[0]
        response = requests.get(f"{BASE_URL}/api/questions/{question_id}")
        assert response.status_code == 200
        
        data = response.json()
        assert data["id"] == question_id
        print(f"✅ Retrieved question: {question_id}")
    
    def test_get_nonexistent_question(self):
        """Test getting a question that doesn't exist"""
        response = requests.get(f"{BASE_URL}/api/questions/nonexistent-id-12345")
        assert response.status_code == 404
        print("✅ 404 returned for nonexistent question")
    
    def test_update_question(self):
        """Update an existing question"""
        if not test_question_ids:
            pytest.skip("No test questions created")
        
        question_id = test_question_ids[0]
        update_payload = {
            "text": "TEST_Qual é a capital do Brasil? (ATUALIZADA)",
            "points": 2.0
        }
        
        response = requests.put(f"{BASE_URL}/api/questions/{question_id}", json=update_payload)
        assert response.status_code == 200
        
        data = response.json()
        assert "ATUALIZADA" in data["text"]
        assert data["points"] == 2.0
        
        # Verify via GET
        get_response = requests.get(f"{BASE_URL}/api/questions/{question_id}")
        assert get_response.status_code == 200
        get_data = get_response.json()
        assert "ATUALIZADA" in get_data["text"]
        print(f"✅ Updated question: {question_id}")


class TestAIQuestionGeneration:
    """Test AI-powered question generation"""
    
    def test_generate_questions_from_prompt(self):
        """Generate questions using AI from a prompt"""
        payload = {
            "projectId": "TEST_project_ai_gen",
            "source": "prompt",
            "prompt": "Segurança no trabalho e uso de EPIs",
            "questionType": "multiple_choice",
            "count": 2
        }
        
        response = requests.post(f"{BASE_URL}/api/questions/generate", json=payload, timeout=60)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") is True
        assert "questions" in data
        assert data["count"] >= 1  # Should generate at least 1 question
        
        # Validate question structure
        for q in data["questions"]:
            assert "id" in q
            assert "text" in q
            assert "alternatives" in q
            assert len(q["alternatives"]) >= 2
            # Store for cleanup
            test_question_ids.append(q["id"])
        
        print(f"✅ AI generated {data['count']} questions")
        return data["questions"]
    
    def test_generate_true_false_questions(self):
        """Generate true/false questions using AI"""
        payload = {
            "projectId": "TEST_project_ai_gen",
            "source": "prompt",
            "prompt": "Primeiros socorros básicos",
            "questionType": "true_false",
            "count": 2
        }
        
        response = requests.post(f"{BASE_URL}/api/questions/generate", json=payload, timeout=60)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") is True
        
        # Check that questions are true/false type
        for q in data["questions"]:
            assert q["type"] == "true_false"
            assert len(q["alternatives"]) == 2
            test_question_ids.append(q["id"])
        
        print(f"✅ AI generated {data['count']} true/false questions")
    
    def test_generate_mixed_questions(self):
        """Generate mixed type questions using AI"""
        payload = {
            "projectId": "TEST_project_ai_gen",
            "source": "prompt",
            "prompt": "Ergonomia no ambiente de trabalho",
            "questionType": "mixed",
            "count": 3
        }
        
        response = requests.post(f"{BASE_URL}/api/questions/generate", json=payload, timeout=60)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") is True
        
        for q in data["questions"]:
            test_question_ids.append(q["id"])
        
        print(f"✅ AI generated {data['count']} mixed questions")


class TestDocumentParsing:
    """Test .doc/.docx file parsing for quiz generation"""
    
    def test_parse_doc_invalid_format(self):
        """Test that non-doc files are rejected"""
        # Create a simple text file to test
        files = {'file': ('test.txt', b'This is a test file', 'text/plain')}
        
        response = requests.post(f"{BASE_URL}/api/questions/parse-doc", files=files)
        assert response.status_code == 400
        print("✅ Invalid file format correctly rejected")


class TestQuizSubmission:
    """Test quiz submission and scoring"""
    
    def test_submit_quiz_all_correct(self):
        """Submit a quiz with all correct answers"""
        # First, create questions for the quiz
        q1_payload = {
            "projectId": "TEST_submission",
            "type": "multiple_choice",
            "text": "TEST_2+2=?",
            "alternatives": [
                {"text": "3", "isCorrect": False},
                {"text": "4", "isCorrect": True},
                {"text": "5", "isCorrect": False},
                {"text": "6", "isCorrect": False}
            ],
            "points": 1.0
        }
        
        q1_response = requests.post(f"{BASE_URL}/api/questions", json=q1_payload)
        assert q1_response.status_code == 200
        q1 = q1_response.json()
        test_question_ids.append(q1["id"])
        
        q2_payload = {
            "projectId": "TEST_submission",
            "type": "true_false",
            "text": "TEST_5>3 é verdadeiro?",
            "alternatives": [
                {"text": "Verdadeiro", "isCorrect": True},
                {"text": "Falso", "isCorrect": False}
            ],
            "points": 1.0
        }
        
        q2_response = requests.post(f"{BASE_URL}/api/questions", json=q2_payload)
        assert q2_response.status_code == 200
        q2 = q2_response.json()
        test_question_ids.append(q2["id"])
        
        # Find the correct alternative IDs
        q1_correct_id = next(a["id"] for a in q1["alternatives"] if a["isCorrect"])
        q2_correct_id = next(a["id"] for a in q2["alternatives"] if a["isCorrect"])
        
        # Submit quiz with correct answers
        submit_payload = {
            "quizId": "TEST_quiz_001",
            "answers": [
                {"questionId": q1["id"], "selectedAlternativeId": q1_correct_id},
                {"questionId": q2["id"], "selectedAlternativeId": q2_correct_id}
            ]
        }
        
        response = requests.post(f"{BASE_URL}/api/quiz/submit", json=submit_payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") is True
        assert data["correctAnswers"] == 2
        assert data["totalQuestions"] == 2
        assert data["score"] == 10.0  # Perfect score
        assert data["percentage"] == 100.0
        assert data["passed"] is True
        
        print(f"✅ Quiz submitted with 100% score: {data['score']}/10")
    
    def test_submit_quiz_partial_correct(self):
        """Submit a quiz with some incorrect answers"""
        # Create questions
        q1_payload = {
            "projectId": "TEST_submission2",
            "type": "multiple_choice",
            "text": "TEST_3*3=?",
            "alternatives": [
                {"text": "6", "isCorrect": False},
                {"text": "9", "isCorrect": True},
                {"text": "12", "isCorrect": False},
                {"text": "15", "isCorrect": False}
            ],
            "points": 1.0
        }
        
        q1_response = requests.post(f"{BASE_URL}/api/questions", json=q1_payload)
        q1 = q1_response.json()
        test_question_ids.append(q1["id"])
        
        q2_payload = {
            "projectId": "TEST_submission2",
            "type": "true_false",
            "text": "TEST_10<5 é verdadeiro?",
            "alternatives": [
                {"text": "Verdadeiro", "isCorrect": False},
                {"text": "Falso", "isCorrect": True}
            ],
            "points": 1.0
        }
        
        q2_response = requests.post(f"{BASE_URL}/api/questions", json=q2_payload)
        q2 = q2_response.json()
        test_question_ids.append(q2["id"])
        
        # Find the correct and wrong alternative IDs
        q1_wrong_id = next(a["id"] for a in q1["alternatives"] if not a["isCorrect"])
        q2_correct_id = next(a["id"] for a in q2["alternatives"] if a["isCorrect"])
        
        # Submit quiz with one wrong answer
        submit_payload = {
            "quizId": "TEST_quiz_002",
            "answers": [
                {"questionId": q1["id"], "selectedAlternativeId": q1_wrong_id},
                {"questionId": q2["id"], "selectedAlternativeId": q2_correct_id}
            ]
        }
        
        response = requests.post(f"{BASE_URL}/api/quiz/submit", json=submit_payload)
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("success") is True
        assert data["correctAnswers"] == 1
        assert data["totalQuestions"] == 2
        assert data["percentage"] == 50.0
        assert data["score"] == 5.0
        assert data["passed"] is False  # Below 60% passing score
        
        # Check results contain details
        assert "results" in data
        for result in data["results"]:
            assert "questionId" in result
            assert "isCorrect" in result
        
        print(f"✅ Quiz submitted with 50% score: {data['score']}/10")


class TestCleanup:
    """Cleanup test data"""
    
    def test_delete_test_questions(self):
        """Delete all test questions"""
        deleted_count = 0
        for qid in test_question_ids:
            try:
                response = requests.delete(f"{BASE_URL}/api/questions/{qid}")
                if response.status_code in [200, 404]:
                    deleted_count += 1
            except Exception:
                pass
        
        # Also clean up any remaining TEST_ prefixed questions
        list_response = requests.get(f"{BASE_URL}/api/questions")
        if list_response.status_code == 200:
            questions = list_response.json()
            for q in questions:
                if q.get("text", "").startswith("TEST_"):
                    requests.delete(f"{BASE_URL}/api/questions/{q['id']}")
                    deleted_count += 1
        
        print(f"✅ Cleaned up {deleted_count} test questions")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
