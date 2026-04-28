"""Tests: Gamification engine integration in Single Page export.

Cobre:
- Engine .js é injetado quando gamification_config tem enabled=true
- GAMIFICATION_CONFIG é serializado corretamente como JSON window-global
- Hook Gamification.onQuizComplete é chamado após submit do quiz
- Hook Gamification.onScenarioComplete é chamado no ending node + fallback
- Hook Gamification.onCourseComplete é chamado ao alcançar end-card
- Quando gamification_config é None ou enabled=false, NADA é injetado
"""
import json
from services.single_page_exporter import generate_single_page_html


_BASE_PROJECT = {
    "id": "p1",
    "name": "Curso de Teste",
    "course": {
        "title": "Curso",
        "slides": [
            {
                "id": "s1",
                "title": "Intro",
                "elements": [{"type": "text", "content": "Bem-vindo"}],
            },
            {
                "id": "s2",
                "title": "Quiz",
                "elements": [{"type": "quiz", "quizConfig": {"questionIds": []}}],
            },
        ],
    },
}

_GAM_CONFIG_ENABLED = {
    "enabled": True,
    "showBadgesAfterQuiz": True,
    "showBadgesAfterScenario": True,
    "showFinalSummary": True,
    "badges": [
        {
            "id": "quiz_master",
            "name": "Mestre dos Quizzes",
            "description": "Acertou 80%+",
            "icon": "trophy",
            "iconColor": "#facc15",
            "criteria": {"type": "quiz_score", "operator": "gte", "threshold": 80},
        }
    ],
    "quizFeedbackRanges": [
        {"id": "q_high", "minScore": 80, "maxScore": 100, "title": "Excelente!", "message": "Parabens", "emoji": "🎉"}
    ],
    "scenarioFeedbackRanges": [],
    "completionFeedback": {"id": "comp", "minScore": 0, "maxScore": 100, "title": "Concluido", "message": "ok", "emoji": "🎓"},
}


def test_gamification_engine_injected_when_enabled():
    html = generate_single_page_html(_BASE_PROJECT, "/tmp", "", gamification_config=_GAM_CONFIG_ENABLED)
    # Engine inline (Gamification = (function() ... )())
    assert "var Gamification = (function()" in html
    # Config serialized as window-global JSON
    assert "window.GAMIFICATION_CONFIG = " in html
    # Init wired to DOMContentLoaded
    assert "Gamification.init(window.GAMIFICATION_CONFIG)" in html
    # Badge config preserved (proves JSON serialization works)
    assert "Mestre dos Quizzes" in html


def test_gamification_NOT_injected_when_disabled():
    cfg = dict(_GAM_CONFIG_ENABLED)
    cfg["enabled"] = False
    html = generate_single_page_html(_BASE_PROJECT, "/tmp", "", gamification_config=cfg)
    assert "var Gamification = (function()" not in html
    assert "window.GAMIFICATION_CONFIG" not in html


def test_gamification_NOT_injected_when_config_is_none():
    html = generate_single_page_html(_BASE_PROJECT, "/tmp", "")
    assert "var Gamification = (function()" not in html
    assert "window.GAMIFICATION_CONFIG" not in html


def test_quiz_completion_calls_gamification_hook():
    html = generate_single_page_html(_BASE_PROJECT, "/tmp", "", gamification_config=_GAM_CONFIG_ENABLED)
    # Hook present in JS runtime even if gamification engine not present (graceful degrade)
    assert "Gamification.onQuizComplete(pct, total, correct)" in html


def test_scenario_completion_calls_gamification_hook():
    html = generate_single_page_html(_BASE_PROJECT, "/tmp", "", gamification_config=_GAM_CONFIG_ENABLED)
    # Hook present at the ending-node path
    assert "Gamification.onScenarioComplete(pct, scenarioTitle)" in html


def test_course_completion_calls_gamification_hook():
    html = generate_single_page_html(_BASE_PROJECT, "/tmp", "", gamification_config=_GAM_CONFIG_ENABLED)
    # Hook present in advance() when reaching end-card
    assert "Gamification.onCourseComplete()" in html


def test_hooks_present_even_without_engine():
    """Os hooks JS são incondicionais (runtime sempre os tem) — eles fazem
    feature detection com `if (window.Gamification && typeof X === 'function')`.
    Isso garante que cursos exportados SEM gamificação continuam funcionando,
    e cursos exportados COM gamificação acionam os modais."""
    html_off = generate_single_page_html(_BASE_PROJECT, "/tmp", "")
    assert "Gamification.onQuizComplete" in html_off
    assert "Gamification.onScenarioComplete" in html_off
    assert "Gamification.onCourseComplete" in html_off
    # but the engine itself is NOT loaded
    assert "var Gamification = (function()" not in html_off


def test_scorm_single_page_passes_gamification():
    """SCORM single-page deve repassar gamification_config para HTML."""
    from services.scorm_single_page_exporter import export_single_page_scorm_package
    import tempfile, zipfile, os
    with tempfile.TemporaryDirectory() as tmp:
        zip_path = export_single_page_scorm_package(
            _BASE_PROJECT,
            storage_dir=tmp,
            output_dir=tmp,
            questions=[],
            tutor_config=None,
            backend_url="",
            gamification_config=_GAM_CONFIG_ENABLED,
        )
        assert os.path.exists(zip_path)
        with zipfile.ZipFile(zip_path) as zf:
            html = zf.read("index.html").decode("utf-8")
            assert "var Gamification = (function()" in html
            assert "Mestre dos Quizzes" in html
