"""Regression test: quiz options must be normalized from the DB schema
(`alternatives[].text/isCorrect`) to the JS runtime schema (`options[].text/correct`).

User report: Quiz aparecia sem opções (radios) no SCORM single-page exportado
em projetos NR35 — porque o renderer Python passava `q.alternatives` direto
e o JS procurava por `q.options`.
"""
import json
import re
import zipfile
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def quiz_html():
    """Return generated single-page HTML containing at least one quiz block."""
    from services.single_page_exporter import generate_single_page_html

    project = {
        "id": "test-quiz-proj",
        "name": "Quiz Test",
        "course": {
            "metadata": {"title": "Quiz Test"},
            "slides": [
                {
                    "id": "s1",
                    "title": "Quiz",
                    "elements": [
                        {
                            "id": "q1",
                            "type": "quiz",
                            "quizConfig": {
                                "title": "Avaliação",
                                "questionIds": ["qq1", "qq2"],
                            },
                        }
                    ],
                }
            ],
        },
    }
    questions = [
        {
            "id": "qq1",
            "text": "Qual a altura mínima para trabalho em altura segundo a NR 35?",
            "alternatives": [
                {"id": "a1", "text": "1,50 metros", "isCorrect": False},
                {"id": "a2", "text": "1,80 metros", "isCorrect": False},
                {"id": "a3", "text": "2,00 metros", "isCorrect": True},
                {"id": "a4", "text": "2,50 metros", "isCorrect": False},
            ],
            "explanation": "A NR 35 define 2 metros.",
        },
        {
            "id": "qq2",
            "text": "EPI é obrigatório?",
            "alternatives": [
                {"id": "b1", "text": "Sim", "isCorrect": True},
                {"id": "b2", "text": "Não", "isCorrect": False},
            ],
        },
    ]
    return generate_single_page_html(project, "/nonexistent", questions=questions)


def test_quiz_data_questions_attribute_uses_options_key(quiz_html):
    """The data-questions JSON in the DOM must use 'options' (what the JS expects),
    not 'alternatives' (what the DB has)."""
    m = re.search(r"data-questions='(\[.*?\])'", quiz_html)
    assert m, "data-questions attribute not found in generated quiz block"
    data = json.loads(m.group(1))
    assert len(data) == 2, f"Expected 2 questions, got {len(data)}"
    for q in data:
        assert "options" in q, f"Question {q.get('id')} missing 'options' key (still using 'alternatives'?)"
        assert "alternatives" not in q, f"Question {q.get('id')} still has raw 'alternatives' — should be normalized away"
        assert isinstance(q["options"], list) and len(q["options"]) > 0
        for opt in q["options"]:
            assert "text" in opt and "correct" in opt, f"Option missing text/correct: {opt}"
            assert isinstance(opt["correct"], bool)


def test_correct_answer_marked_from_isCorrect(quiz_html):
    m = re.search(r"data-questions='(\[.*?\])'", quiz_html)
    data = json.loads(m.group(1))
    # Question 1: 3rd option (2,00 metros) is correct
    correct_idx = [i for i, o in enumerate(data[0]["options"]) if o["correct"]]
    assert correct_idx == [2], f"Expected correct option at index 2, got {correct_idx}"
    assert data[0]["options"][2]["text"] == "2,00 metros"


def test_question_count_in_meta_matches(quiz_html):
    """The 'X questões' meta text must reflect actual loaded questions."""
    assert "2 questões" in quiz_html or "2 quest" in quiz_html


def test_quiz_with_string_alternatives_normalized():
    """Some legacy questions might use string alternatives instead of dicts."""
    from services.single_page_exporter import generate_single_page_html

    project = {
        "id": "p", "name": "p",
        "course": {"metadata": {"title": "t"}, "slides": [
            {"id": "s1", "title": "Q", "elements": [
                {"id": "q1", "type": "quiz", "quizConfig": {"title": "Q", "questionIds": ["x1"]}}
            ]}
        ]}
    }
    questions = [{"id": "x1", "text": "?", "alternatives": ["A", "B", "C"]}]
    html = generate_single_page_html(project, "/none", questions=questions)
    m = re.search(r"data-questions='(\[.*?\])'", html)
    data = json.loads(m.group(1))
    assert data[0]["options"] == [
        {"text": "A", "correct": False},
        {"text": "B", "correct": False},
        {"text": "C", "correct": False},
    ]
