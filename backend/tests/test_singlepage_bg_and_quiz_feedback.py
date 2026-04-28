"""Tests for per-slide background color/image and quiz visual feedback."""
import re
import pytest

from services.single_page_exporter import generate_single_page_html


def test_each_section_has_its_own_background_color():
    """Slide.background (solid color) must be applied to the corresponding
    <section> as inline background-color style. Bug: previously only the
    first slide's backgroundImage was used as a global course bg."""
    project = {
        "id": "p", "name": "Test",
        "course": {"metadata": {"title": "T"}, "slides": [
            {"id": "s1", "title": "Slide Dark", "background": "#1c1917", "elements": []},
            {"id": "s2", "title": "Slide Light", "background": "#fefce8", "elements": []},
            {"id": "s3", "title": "Slide Blue", "background": "#1e3a8a", "elements": []},
        ]}
    }
    out = generate_single_page_html(project, "/none")
    assert 'background-color:#1c1917' in out
    assert 'background-color:#fefce8' in out
    assert 'background-color:#1e3a8a' in out
    # Each section must have its OWN style attribute
    sections = re.findall(r'<section class="sp-section"[^>]+style="([^"]+)"', out)
    assert len(sections) == 3, f"Expected 3 sections with style, got {len(sections)}"
    assert "1c1917" in sections[0]
    assert "fefce8" in sections[1]
    assert "1e3a8a" in sections[2]


def test_section_with_no_background_has_no_style_attr():
    project = {
        "id": "p", "name": "Test",
        "course": {"metadata": {"title": "T"}, "slides": [
            {"id": "s1", "title": "Plain", "elements": []},
        ]}
    }
    out = generate_single_page_html(project, "/none")
    # The first section should not have a background style if slide has no background fields
    m = re.search(r'<section class="sp-section" data-index="0"[^>]*>', out)
    assert m
    assert "background-color" not in m.group(0)
    assert "background-image" not in m.group(0)


def test_quiz_has_visual_feedback_classes_in_html():
    """The startQuiz JS must reference the visual feedback elements:
    sp-quiz-opt, sp-quiz-question, sp-quiz-explanation."""
    project = {
        "id": "p", "name": "Test",
        "course": {"metadata": {"title": "T"}, "slides": [
            {"id": "s1", "title": "Q", "elements": [
                {"id": "q", "type": "quiz", "quizConfig": {"title": "Q", "questionIds": ["x"]}}
            ]}
        ]}
    }
    questions = [{
        "id": "x", "text": "Q?",
        "alternatives": [{"text": "A", "isCorrect": True}, {"text": "B", "isCorrect": False}],
        "explanation": "Esta é a explicação detalhada.",
    }]
    out = generate_single_page_html(project, "/none", questions=questions)
    assert "sp-quiz-opt" in out
    assert "sp-quiz-question" in out
    assert "sp-quiz-explanation" in out
    # Visual feedback markers
    assert "✓ Correta" in out  # green checkmark for correct answer
    assert "✗ Sua resposta" in out  # red X for student's wrong pick
    assert "Aprovado" in out or "Revise" in out  # final result banner
    # The explanation text must be rendered somewhere
    assert "Esta é a explicação detalhada." in out
