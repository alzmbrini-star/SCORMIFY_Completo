"""Tests for the Tutorial Agent → Scormify slide conversion.

The conversion pipeline is what bridges the external Tutorial Agent format
(steps with action_type, selector, click_x/click_y) and the Scormify slide
schema (background image, text overlay, hotspot circle, narration).
"""
import pytest
from routes.tutorial_integration import (
    _generate_step_description,
    _step_to_slide,
)


class TestGenerateStepDescription:
    def test_uses_explicit_narration_when_present(self):
        step = {"narration": "Diga ola para o mundo"}
        assert _generate_step_description(step, 0) == "Diga ola para o mundo"

    def test_click_action_with_selector_label(self):
        step = {"action_type": "click", "selector": "a:text:Relatorios"}
        out = _generate_step_description(step, 0)
        assert "Clique" in out
        assert "Relatorios" in out

    def test_click_action_no_selector(self):
        step = {"action_type": "click"}
        out = _generate_step_description(step, 0)
        assert "Clique" in out

    def test_type_action_with_text(self):
        step = {"action_type": "type", "typed_text": "joao@exemplo.com"}
        out = _generate_step_description(step, 0)
        assert "Digite" in out
        assert "joao@exemplo.com" in out

    def test_type_action_no_text(self):
        step = {"action_type": "type"}
        out = _generate_step_description(step, 0)
        assert "Preencha" in out or "Digite" in out

    def test_scroll_action(self):
        out = _generate_step_description({"action_type": "scroll"}, 0)
        assert "Role" in out or "tela" in out

    def test_navigate_action_with_url(self):
        out = _generate_step_description({"action_type": "navigate", "url": "https://exemplo.com"}, 0)
        assert "https://exemplo.com" in out

    def test_unknown_action_falls_back(self):
        out = _generate_step_description({"action_type": "weird"}, 4)
        assert "Passo 5" in out  # idx=4 → "Passo 5"


class TestStepToSlide:
    def test_creates_slide_with_screenshot_bg(self):
        step = {"id": "s1", "action_type": "click", "selector": "Login"}
        slide = _step_to_slide(step, "/api/projects/p/assets/x.png", 0)
        assert slide["backgroundImage"] == "/api/projects/p/assets/x.png"
        assert slide["backgroundImageOpacity"] == 1.0
        assert slide["width"] == 1280
        assert slide["height"] == 720

    def test_includes_instruction_text_element(self):
        step = {"action_type": "click", "selector": "Salvar"}
        slide = _step_to_slide(step, None, 0)
        text_els = [e for e in slide["elements"] if e["type"] == "text"]
        assert len(text_els) == 1
        assert "Salvar" in text_els[0]["content"]
        # Should have a contrasting plate so it reads over the screenshot
        assert text_els[0]["style"].get("textBackgroundColor")
        assert text_els[0]["style"].get("padding")

    def test_includes_hotspot_when_click_coords_present(self):
        step = {"action_type": "click", "click_x": 500, "click_y": 300}
        slide = _step_to_slide(step, None, 0)
        shape_els = [e for e in slide["elements"] if e["type"] == "shape"]
        assert len(shape_els) == 1
        hotspot = shape_els[0]
        # Hotspot centered on the click point (56x56 with -28 offset = centered)
        assert hotspot["x"] == 500 - 28
        assert hotspot["y"] == 300 - 28
        assert hotspot["width"] == 56
        assert hotspot["height"] == 56
        assert hotspot["style"]["borderColor"] == "#f472b6"  # pink ring

    def test_skips_hotspot_when_coords_missing(self):
        step = {"action_type": "click"}
        slide = _step_to_slide(step, None, 0)
        shape_els = [e for e in slide["elements"] if e["type"] == "shape"]
        assert len(shape_els) == 0

    def test_sets_narration_from_description(self):
        step = {"action_type": "click", "selector": "Confirmar"}
        slide = _step_to_slide(step, None, 0)
        # Narration falls back to the generated description
        assert "Confirmar" in slide["narrationScript"]

    def test_default_title_when_missing(self):
        slide = _step_to_slide({"action_type": "click"}, None, 4)
        assert slide["title"] == "Passo 5"

    def test_explicit_title_kept(self):
        slide = _step_to_slide({"title": "Tela de Login", "action_type": "click"}, None, 0)
        assert slide["title"] == "Tela de Login"

    def test_invalid_click_coords_ignored(self):
        step = {"action_type": "click", "click_x": "abc", "click_y": "def"}
        slide = _step_to_slide(step, None, 0)
        shape_els = [e for e in slide["elements"] if e["type"] == "shape"]
        assert len(shape_els) == 0  # invalid coords don't crash, just skip hotspot
