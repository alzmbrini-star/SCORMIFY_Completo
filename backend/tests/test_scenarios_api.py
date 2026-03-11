"""
Test Scenarios API - CRUD and AI Generation
Tests the new interactive learning scenarios feature (decision tree).

Endpoints tested:
- POST /api/scenarios/generate - AI-generated scenario
- POST /api/scenarios - Manual create
- GET /api/scenarios/project/{id} - List by project
- GET /api/scenarios/{id} - Get single
- PUT /api/scenarios/{id} - Update
- DELETE /api/scenarios/{id} - Delete
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

class TestScenariosAPI:
    """Scenario CRUD API tests"""
    
    created_scenario_id = None
    
    def test_health_check(self):
        """Verify API is accessible"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy"
        print("PASS: Health check passed")
    
    def test_create_scenario_manual(self):
        """POST /api/scenarios - Create scenario manually"""
        payload = {
            "project_id": "test-project-123",
            "title": "Test Scenario: Leadership Challenge",
            "description": "A scenario about leadership decisions",
            "context": "You are a manager facing a team conflict",
            "characters": [
                {
                    "name": "Carlos",
                    "role": "Team Lead",
                    "personality": "Assertive but fair"
                },
                {
                    "name": "Ana",
                    "role": "Developer",
                    "personality": "Detail-oriented"
                }
            ],
            "learning_objectives": ["Develop conflict resolution skills", "Practice decision making"],
            "competencies_evaluated": ["Leadership", "Communication"],
            "nodes": [
                {
                    "id": "node_1",
                    "type": "narrative",
                    "title": "The Conflict Begins",
                    "narrative": "Your team members are in a heated argument about project priorities.",
                    "character_speaking": "Carlos",
                    "is_ending": False,
                    "ending_type": None,
                    "score": None,
                    "choices": [
                        {
                            "id": "choice_1_1",
                            "text": "Intervene immediately",
                            "next_node_id": "node_2",
                            "feedback": "Quick action shows leadership",
                            "is_optimal": True,
                            "points": 10
                        },
                        {
                            "id": "choice_1_2",
                            "text": "Let them resolve it themselves",
                            "next_node_id": "node_3",
                            "feedback": "Sometimes autonomy is good, but this may escalate",
                            "is_optimal": False,
                            "points": 5
                        }
                    ]
                },
                {
                    "id": "node_2",
                    "type": "ending",
                    "title": "Good Resolution",
                    "narrative": "You mediated the conflict successfully.",
                    "character_speaking": None,
                    "is_ending": True,
                    "ending_type": "good",
                    "score": 90,
                    "choices": []
                },
                {
                    "id": "node_3",
                    "type": "ending",
                    "title": "Mixed Outcome",
                    "narrative": "The conflict eventually resolved but left some tension.",
                    "character_speaking": None,
                    "is_ending": True,
                    "ending_type": "neutral",
                    "score": 60,
                    "choices": []
                }
            ],
            "config": {
                "theme": "Leadership",
                "complexity": "beginner"
            }
        }
        
        response = requests.post(f"{BASE_URL}/api/scenarios", json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") is True, "Response should have success=True"
        assert "scenario" in data, "Response should have scenario object"
        
        scenario = data["scenario"]
        assert "id" in scenario, "Scenario should have an ID"
        assert scenario["title"] == payload["title"], "Title should match"
        assert len(scenario["nodes"]) == 3, "Should have 3 nodes"
        assert len(scenario["characters"]) == 2, "Should have 2 characters"
        
        # Store for later tests
        TestScenariosAPI.created_scenario_id = scenario["id"]
        print(f"PASS: Created scenario with ID: {scenario['id']}")
    
    def test_get_scenario_by_id(self):
        """GET /api/scenarios/{id} - Get single scenario"""
        if not TestScenariosAPI.created_scenario_id:
            pytest.skip("No scenario created in previous test")
        
        response = requests.get(f"{BASE_URL}/api/scenarios/{TestScenariosAPI.created_scenario_id}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        scenario = response.json()
        assert scenario["id"] == TestScenariosAPI.created_scenario_id
        assert "nodes" in scenario
        assert "characters" in scenario
        print(f"PASS: Retrieved scenario by ID")
    
    def test_list_scenarios_by_project(self):
        """GET /api/scenarios/project/{project_id} - List by project"""
        response = requests.get(f"{BASE_URL}/api/scenarios/project/test-project-123")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        scenarios = response.json()
        assert isinstance(scenarios, list), "Should return a list"
        assert len(scenarios) >= 1, "Should have at least 1 scenario"
        
        # Verify our created scenario is in the list
        ids = [s["id"] for s in scenarios]
        if TestScenariosAPI.created_scenario_id:
            assert TestScenariosAPI.created_scenario_id in ids, "Created scenario should be in list"
        print(f"PASS: Listed {len(scenarios)} scenarios for project")
    
    def test_update_scenario(self):
        """PUT /api/scenarios/{id} - Update scenario"""
        if not TestScenariosAPI.created_scenario_id:
            pytest.skip("No scenario created in previous test")
        
        update_payload = {
            "title": "Updated: Leadership Challenge v2",
            "description": "Updated description"
        }
        
        response = requests.put(
            f"{BASE_URL}/api/scenarios/{TestScenariosAPI.created_scenario_id}",
            json=update_payload
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") is True
        assert data["scenario"]["title"] == update_payload["title"]
        print("PASS: Updated scenario successfully")
    
    def test_get_scenario_404(self):
        """GET /api/scenarios/{id} - Should return 404 for non-existent"""
        response = requests.get(f"{BASE_URL}/api/scenarios/non-existent-id-12345")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("PASS: 404 returned for non-existent scenario")
    
    def test_update_scenario_404(self):
        """PUT /api/scenarios/{id} - Should return 404 for non-existent"""
        response = requests.put(
            f"{BASE_URL}/api/scenarios/non-existent-id-12345",
            json={"title": "Test"}
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("PASS: 404 returned for updating non-existent scenario")
    
    def test_delete_scenario(self):
        """DELETE /api/scenarios/{id} - Delete scenario"""
        if not TestScenariosAPI.created_scenario_id:
            pytest.skip("No scenario created in previous test")
        
        response = requests.delete(f"{BASE_URL}/api/scenarios/{TestScenariosAPI.created_scenario_id}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") is True
        print("PASS: Deleted scenario successfully")
        
        # Verify deletion
        response = requests.get(f"{BASE_URL}/api/scenarios/{TestScenariosAPI.created_scenario_id}")
        assert response.status_code == 404, "Deleted scenario should return 404"
        print("PASS: Verified scenario is deleted")
    
    def test_delete_scenario_404(self):
        """DELETE /api/scenarios/{id} - Should return 404 for non-existent"""
        response = requests.delete(f"{BASE_URL}/api/scenarios/non-existent-id-12345")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("PASS: 404 returned for deleting non-existent scenario")


class TestScenarioAIGeneration:
    """Test AI-generated scenarios (slower, uses Gemini)"""
    
    generated_scenario_id = None
    
    def test_generate_scenario_with_ai(self):
        """POST /api/scenarios/generate - Generate scenario with Gemini AI
        
        NOTE: This test takes 40-60 seconds due to AI generation.
        Using beginner complexity for faster generation.
        """
        payload = {
            "project_id": "test-ai-project",
            "theme": "Liderança em crise",
            "objectives": "Desenvolver tomada de decisão sob pressão",
            "audience": "Gestores de nível médio",
            "complexity": "beginner",  # Faster generation
            "industry": "Tecnologia",
            "duration_minutes": 5,
            "language": "pt-BR"
        }
        
        print("Starting AI scenario generation (this may take 40-60 seconds)...")
        start_time = time.time()
        
        response = requests.post(
            f"{BASE_URL}/api/scenarios/generate",
            json=payload,
            timeout=120  # 2 minute timeout
        )
        
        elapsed = time.time() - start_time
        print(f"AI generation completed in {elapsed:.1f} seconds")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") is True, "Response should have success=True"
        assert "scenario" in data, "Response should have scenario object"
        
        scenario = data["scenario"]
        
        # Validate structure
        assert "id" in scenario, "Scenario should have an ID"
        assert "title" in scenario, "Should have a title"
        assert "nodes" in scenario, "Should have nodes array"
        assert len(scenario["nodes"]) >= 3, f"Should have at least 3 nodes (beginner), got {len(scenario['nodes'])}"
        
        # Validate nodes structure
        for node in scenario["nodes"]:
            assert "id" in node, "Each node should have an ID"
            assert "narrative" in node, "Each node should have narrative"
            assert "choices" in node, "Each node should have choices array"
            
            # Check ending nodes
            if node.get("is_ending"):
                assert node.get("score") is not None, "Ending nodes should have a score"
        
        # Check for multiple endings
        endings = [n for n in scenario["nodes"] if n.get("is_ending")]
        assert len(endings) >= 2, f"Should have at least 2 endings, got {len(endings)}"
        
        # Store for cleanup
        TestScenarioAIGeneration.generated_scenario_id = scenario["id"]
        
        print(f"PASS: AI generated scenario '{scenario['title']}' with {len(scenario['nodes'])} nodes and {len(endings)} endings")
    
    def test_cleanup_generated_scenario(self):
        """Cleanup the AI-generated scenario"""
        if TestScenarioAIGeneration.generated_scenario_id:
            response = requests.delete(f"{BASE_URL}/api/scenarios/{TestScenarioAIGeneration.generated_scenario_id}")
            assert response.status_code == 200
            print("PASS: Cleaned up AI-generated scenario")
        else:
            pytest.skip("No generated scenario to cleanup")
    
    def test_generate_scenario_validation_error(self):
        """POST /api/scenarios/generate - Should fail without required fields"""
        payload = {
            "project_id": "test-project",
            # Missing required theme and objectives
        }
        
        response = requests.post(f"{BASE_URL}/api/scenarios/generate", json=payload)
        # FastAPI returns 422 for validation errors
        assert response.status_code == 422, f"Expected 422 for validation error, got {response.status_code}"
        print("PASS: Validation error returned for missing required fields")


class TestScenarioDataStructure:
    """Test scenario data structure validation"""
    
    def test_scenario_node_structure(self):
        """Verify scenario nodes have correct structure"""
        # Create a scenario with specific structure
        payload = {
            "project_id": "structure-test",
            "title": "Structure Test Scenario",
            "nodes": [
                {
                    "id": "node_start",
                    "type": "narrative",
                    "title": "Start",
                    "narrative": "Starting point",
                    "is_ending": False,
                    "choices": [
                        {
                            "id": "c1",
                            "text": "Choice A",
                            "next_node_id": "node_end",
                            "feedback": "Good choice",
                            "is_optimal": True,
                            "points": 10
                        }
                    ]
                },
                {
                    "id": "node_end",
                    "type": "ending",
                    "title": "The End",
                    "narrative": "Conclusion",
                    "is_ending": True,
                    "ending_type": "good",
                    "score": 100,
                    "choices": []
                }
            ]
        }
        
        response = requests.post(f"{BASE_URL}/api/scenarios", json=payload)
        assert response.status_code == 200
        
        scenario = response.json()["scenario"]
        
        # Verify start_node_id is set
        assert scenario.get("start_node_id") == "node_start", "start_node_id should be first node"
        
        # Verify nodes are preserved correctly
        assert len(scenario["nodes"]) == 2
        
        start_node = next(n for n in scenario["nodes"] if n["id"] == "node_start")
        assert start_node["type"] == "narrative"
        assert len(start_node["choices"]) == 1
        assert start_node["choices"][0]["next_node_id"] == "node_end"
        
        end_node = next(n for n in scenario["nodes"] if n["id"] == "node_end")
        assert end_node["is_ending"] is True
        assert end_node["score"] == 100
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/scenarios/{scenario['id']}")
        print("PASS: Scenario node structure validated")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
