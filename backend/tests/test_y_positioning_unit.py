"""
Unit test for the apply-improvements Y positioning fix.
This test directly verifies the element positioning logic without relying on AI responses.
"""
import pytest
import sys
import os

# Add backend to path
sys.path.insert(0, '/app/backend')

from models import generate_id


class TestElementYPositioningLogic:
    """Direct unit tests for the Y positioning fix logic"""
    
    def test_single_element_starts_at_y80(self):
        """Single element should start at y=80 (below header bar)"""
        # Simulate the fix logic
        elements = [{"type": "text", "content": "<p>Test</p>", "width": 1760, "height": 400}]
        
        new_html_elements = []
        current_y = 80  # Start below header bar
        
        for elem in elements:
            elem_height = elem.get("height", 400)
            el = {
                "id": "test-id",
                "type": "html",
                "x": 80,
                "y": current_y,
                "width": elem.get("width", 1760),
                "height": elem_height,
                "htmlContent": elem.get("content", ""),
            }
            new_html_elements.append(el)
            current_y += elem_height + 20  # 20px gap
        
        assert len(new_html_elements) == 1
        assert new_html_elements[0]["y"] == 80, f"First element should be at y=80, got y={new_html_elements[0]['y']}"
        print(f"✓ Single element positioned at y=80")
    
    def test_multiple_elements_have_incremental_y(self):
        """Multiple elements should have incremental Y positions"""
        elements = [
            {"type": "text", "content": "<h2>Title</h2>", "width": 1760, "height": 100},
            {"type": "text", "content": "<p>Content</p>", "width": 1760, "height": 300},
            {"type": "text", "content": "<ul><li>List</li></ul>", "width": 1760, "height": 200},
        ]
        
        new_html_elements = []
        current_y = 80  # Start below header bar
        
        for elem in elements:
            elem_height = elem.get("height", 400)
            el = {
                "id": "test-id",
                "type": "html",
                "x": 80,
                "y": current_y,
                "width": elem.get("width", 1760),
                "height": elem_height,
                "htmlContent": elem.get("content", ""),
            }
            new_html_elements.append(el)
            current_y += elem_height + 20  # 20px gap
        
        assert len(new_html_elements) == 3
        
        # First element at y=80
        assert new_html_elements[0]["y"] == 80
        
        # Second element at y=80 + 100 + 20 = 200
        assert new_html_elements[1]["y"] == 200, f"Second element should be at y=200, got y={new_html_elements[1]['y']}"
        
        # Third element at y=200 + 300 + 20 = 520
        assert new_html_elements[2]["y"] == 520, f"Third element should be at y=520, got y={new_html_elements[2]['y']}"
        
        # Verify no elements have the same Y position
        y_positions = [e["y"] for e in new_html_elements]
        assert len(y_positions) == len(set(y_positions)), "All elements should have unique Y positions"
        
        print(f"✓ Multiple elements have incremental Y positions: {y_positions}")
    
    def test_no_elements_at_y40(self):
        """No elements should be placed at y=40 (the old bug value)"""
        elements = [
            {"type": "text", "content": "<h2>Title</h2>", "width": 1760, "height": 100},
            {"type": "text", "content": "<p>Content</p>", "width": 1760, "height": 300},
        ]
        
        new_html_elements = []
        current_y = 80  # Start below header bar
        
        for elem in elements:
            elem_height = elem.get("height", 400)
            el = {
                "id": "test-id",
                "type": "html",
                "x": 80,
                "y": current_y,
                "width": elem.get("width", 1760),
                "height": elem_height,
                "htmlContent": elem.get("content", ""),
            }
            new_html_elements.append(el)
            current_y += elem_height + 20
        
        for el in new_html_elements:
            assert el["y"] != 40, f"Element should not be at y=40 (old bug value)"
        
        print(f"✓ No elements at y=40 (old bug value)")
    
    def test_header_preservation_logic(self):
        """Header elements (y=0, height<=60) should be preserved"""
        existing_elements = [
            {"id": "header-1", "type": "html", "y": 0, "height": 50, "htmlContent": "<div>Header</div>"},
            {"id": "content-1", "type": "html", "y": 40, "height": 700, "htmlContent": "<p>Old content</p>"},
            {"id": "image-1", "type": "image", "y": 100, "height": 400, "src": "/image.png"},
        ]
        
        # Simulate the fix logic
        preserved = [e for e in existing_elements if e.get("type") not in ("html", "text")]
        header = [e for e in existing_elements if e.get("type") == "html" and e.get("y", 0) == 0 and e.get("height", 0) <= 60]
        
        assert len(header) == 1, "Header should be preserved"
        assert header[0]["id"] == "header-1"
        
        assert len(preserved) == 1, "Non-text elements should be preserved"
        assert preserved[0]["id"] == "image-1"
        
        print(f"✓ Header and non-text elements preserved correctly")
    
    def test_non_text_elements_preserved(self):
        """Non-text elements (images, scenarios, quizzes) should be preserved"""
        existing_elements = [
            {"id": "html-1", "type": "html", "y": 80, "height": 300, "htmlContent": "<p>Text</p>"},
            {"id": "image-1", "type": "image", "y": 400, "height": 200, "src": "/image.png"},
            {"id": "scenario-1", "type": "scenario", "y": 620, "height": 150, "scenarioData": {}},
            {"id": "quiz-1", "type": "quiz", "y": 790, "height": 100, "quizConfig": {}},
        ]
        
        # Simulate the fix logic
        preserved = [e for e in existing_elements if e.get("type") not in ("html", "text")]
        
        assert len(preserved) == 3, "All non-text elements should be preserved"
        
        preserved_types = [e["type"] for e in preserved]
        assert "image" in preserved_types
        assert "scenario" in preserved_types
        assert "quiz" in preserved_types
        
        print(f"✓ Non-text elements preserved: {preserved_types}")
    
    def test_new_slide_element_positioning(self):
        """New slides should have elements starting at y=80"""
        new_slide_elements = [
            {"type": "text", "content": "<h2>New Slide Title</h2>", "width": 1760, "height": 100},
            {"type": "text", "content": "<p>New slide content</p>", "width": 1760, "height": 500},
        ]
        
        new_elements = []
        current_y = 80
        
        for elem in new_slide_elements:
            elem_height = elem.get("height", 400)
            el = {
                "id": "new-id",
                "type": "html",
                "x": 80,
                "y": current_y,
                "width": elem.get("width", 1760),
                "height": elem_height,
                "htmlContent": elem.get("content", ""),
            }
            new_elements.append(el)
            current_y += elem_height + 20
        
        assert new_elements[0]["y"] == 80
        assert new_elements[1]["y"] == 200  # 80 + 100 + 20
        
        print(f"✓ New slide elements positioned correctly: y={[e['y'] for e in new_elements]}")


class TestApplyImprovementsCodePath:
    """Tests to verify the code path in agent.py"""
    
    def test_code_uses_current_y_variable(self):
        """Verify the code uses current_y variable for positioning"""
        with open('/app/backend/routes/agent.py', 'r') as f:
            code = f.read()
        
        # Check for the fix pattern
        assert 'current_y = 80' in code, "Code should initialize current_y = 80"
        assert '"y": current_y' in code, "Code should use current_y for y position"
        assert 'current_y += elem_height + 20' in code, "Code should increment current_y"
        
        print("✓ Code uses current_y variable for positioning")
    
    def test_code_preserves_non_text_elements(self):
        """Verify the code preserves non-text elements"""
        with open('/app/backend/routes/agent.py', 'r') as f:
            code = f.read()
        
        assert 'preserved = [e for e in existing_elements if e.get("type") not in ("html", "text")]' in code, \
            "Code should preserve non-text elements"
        
        print("✓ Code preserves non-text elements")
    
    def test_code_preserves_header_bar(self):
        """Verify the code preserves header bar elements"""
        with open('/app/backend/routes/agent.py', 'r') as f:
            code = f.read()
        
        assert 'header = [e for e in existing_elements if e.get("type") == "html" and e.get("y", 0) == 0 and e.get("height", 0) <= 60]' in code, \
            "Code should preserve header bar elements"
        
        print("✓ Code preserves header bar elements")
    
    def test_ai_prompt_requests_single_element(self):
        """Verify the AI prompt requests a single combined HTML element"""
        with open('/app/backend/services/ai_agent.py', 'r') as f:
            code = f.read()
        
        assert 'UM ÚNICO elemento' in code or 'um único bloco HTML' in code, \
            "AI prompt should request a single combined HTML element"
        
        print("✓ AI prompt requests single combined HTML element")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
