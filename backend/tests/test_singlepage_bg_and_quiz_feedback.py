"""Tests for per-slide background color/image and quiz visual feedback."""
import re
import pytest

from services.single_page_exporter import generate_single_page_html


def test_each_section_has_its_own_background_color():
    """Slide.background (solid color) must be applied to the corresponding
    .sp-section-inner card (not the <section> wrapper) so editor-defined
    text colors stay readable. Bug: previously only the first slide's
    backgroundImage was used as a global course bg, AND text white-on-white
    was unreadable when card was forced white."""
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
    # Card-inner must have the inline style now (not the outer <section>)
    cards = re.findall(r'<div class="sp-section-inner"[^>]+style="([^"]+)"', out)
    assert len(cards) == 3, f"Expected 3 cards with style, got {len(cards)}"
    assert "1c1917" in cards[0]
    assert "fefce8" in cards[1]
    assert "1e3a8a" in cards[2]
    # Dark backgrounds must auto-apply light text color (sp-dark class)
    assert out.count("sp-section sp-dark") >= 2  # #1c1917 and #1e3a8a are dark
    assert "color:#f1f5f9" in cards[0]  # auto light text


def test_section_with_no_background_has_no_style_attr():
    project = {
        "id": "p", "name": "Test",
        "course": {"metadata": {"title": "T"}, "slides": [
            {"id": "s1", "title": "Plain", "elements": []},
        ]}
    }
    out = generate_single_page_html(project, "/none")
    # The card should not have a background style if slide has no background fields
    m = re.search(r'<div class="sp-section-inner"[^>]*>', out)
    assert m
    assert "background-color" not in m.group(0)
    assert "background-image" not in m.group(0)


def test_iframe_data_uri_declares_utf8_charset_for_accents():
    """Bug: iframes with data:text/html;base64 (no charset) caused mojibake
    (â□Œ instead of ❌, InspeÃ§Ã£o instead of Inspeção)."""
    project = {
        "id": "p", "name": "Test",
        "course": {"metadata": {"title": "T"}, "slides": [
            {"id": "s1", "title": "S", "elements": [
                {"id": "h1", "type": "html",
                 "htmlContent": "<style>body{margin:0}</style><div>Aprovação ✅ Inspeção</div>"},
                {"id": "sm1", "type": "simulator",
                 "htmlContent": "<button>Aprovar ✓</button>"},
            ]}
        ]}
    }
    out = generate_single_page_html(project, "/none")
    # All iframe data: URIs MUST include charset=utf-8 explicitly
    assert "data:text/html;charset=utf-8;base64" in out
    # No iframe should fall back to plain data:text/html;base64 (without charset)
    assert "data:text/html;base64" not in out, "Found iframe without explicit charset (will cause mojibake)"


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
