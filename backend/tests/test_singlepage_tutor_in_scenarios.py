"""Tests: Tutor IA integration in Scenarios (Single Page export).

Cobre:
- Tutor JS + CSS são injetados quando tutor_config.enabled=true
- Tutor NÃO é injetado quando tutor_config.enabled=false ou None
- Botão "💡 Pedir dica do Tutor IA" aparece nos nós de cenário
- Botão "🤖 Quer entender melhor por quê?" aparece após escolha sub-ótima (logic in JS, verified by string presence)
- Helpers `wireRescueBtn` e ScenarioController.askTutor existem
- Detecção condicional `if (window.AiTutor)` evita crashes quando tutor desabilitado
"""
from services.single_page_exporter import generate_single_page_html


_PROJECT = {
    "id": "p1",
    "name": "Curso Teste",
    "course": {
        "title": "Curso",
        "slides": [
            {"id": "s1", "title": "Intro", "elements": [{"type": "text", "content": "x"}]},
        ],
    },
}

_TUTOR_ENABLED = {
    "enabled": True,
    "apiUrl": "https://example.com",
    "tutorName": "Tutor Teste",
    "courseTopic": "Liderança",
    "messageLimit": 50,
    "suggestedQuestions": ["O que é liderança?"],
    "courseContext": "Conteúdo geral",
    "slideContexts": [],
}


def test_tutor_js_and_css_inlined_when_enabled():
    html = generate_single_page_html(_PROJECT, "/tmp", "", tutor_config=_TUTOR_ENABLED)
    # tutor.js engine
    assert "var AiTutor = (function()" in html
    # tutor.css inline (the FAB style)
    assert ".tutor-fab" in html
    assert "data-tutor-css" in html
    # config & init wired
    assert "window.TUTOR_CONFIG = " in html
    assert "AiTutor.init(window.TUTOR_CONFIG)" in html
    # cssInlined forced true (so widget skips fetching styles/tutor.css)
    assert '"cssInlined": true' in html or '"cssInlined":true' in html


def test_tutor_NOT_injected_when_disabled():
    html = generate_single_page_html(_PROJECT, "/tmp", "", tutor_config={"enabled": False})
    assert "var AiTutor = (function()" not in html
    assert ".tutor-fab" not in html
    assert "window.TUTOR_CONFIG" not in html


def test_tutor_NOT_injected_when_config_is_none():
    html = generate_single_page_html(_PROJECT, "/tmp", "")
    assert "var AiTutor = (function()" not in html
    assert ".tutor-fab" not in html


def test_scenario_hint_button_in_runtime():
    """Hint button is rendered conditionally on `if (window.AiTutor)` inside the
    scenario JS engine — guarantees no broken state when tutor disabled."""
    html = generate_single_page_html(_PROJECT, "/tmp", "", tutor_config=_TUTOR_ENABLED)
    # The hint button HTML markup is in the JS string
    assert "sp-scenario-hint" in html
    assert "💡 Pedir dica do Tutor IA" in html
    # Conditional on window.AiTutor presence
    assert "if (window.AiTutor)" in html


def test_scenario_rescue_button_after_suboptimal():
    """Rescue button appears only if `!choice.is_optimal && window.AiTutor`."""
    html = generate_single_page_html(_PROJECT, "/tmp", "", tutor_config=_TUTOR_ENABLED)
    assert "sp-scenario-rescue" in html
    assert "🤖 Quer entender melhor por quê?" in html
    assert "!choice.is_optimal && window.AiTutor" in html
    # Helper function to wire it
    assert "function wireRescueBtn(choice)" in html


def test_tutor_integration_works_without_tutor_loaded():
    """Critical: the scenario JS must NOT crash when AiTutor is absent.
    The hint button + rescue button code paths must be guarded by `window.AiTutor` checks."""
    html = generate_single_page_html(_PROJECT, "/tmp", "")  # no tutor
    # Engine NOT loaded
    assert "var AiTutor = (function()" not in html
    # But the JS runtime still has the conditional checks (safe to deploy)
    assert "if (window.AiTutor)" in html
    assert "!choice.is_optimal && window.AiTutor" in html


def test_traditional_scenario_controller_has_tutor_buttons():
    """The traditional export's scenario-controller.js (also used by SCORM
    classic) must have the same hint + rescue buttons."""
    from pathlib import Path
    js = (Path(__file__).parent.parent / "services" / "export_assets" / "scenario-controller.js").read_text()
    assert "💡 Pedir dica do Tutor IA" in js
    assert "🤖 Quer entender melhor por quê?" in js
    assert "ScenarioController.askTutor" in js
    assert "function askTutor(elementId, mode, nodeId, choiceId)" in js
    # Public API exposes askTutor
    assert "askTutor: askTutor" in js
    # Conditional on AiTutor presence
    assert "window.AiTutor" in js


def test_hint_prompt_serializes_node_context():
    """When the hint button is clicked, the prompt should include node title,
    narrative, and choices to give the tutor context."""
    html = generate_single_page_html(_PROJECT, "/tmp", "", tutor_config=_TUTOR_ENABLED)
    # Prompt template uses node.title, node.narrative and node.choices
    assert "Estou em um cenário interativo" in html
    assert "Minhas opções são:" in html
    assert "não me dê a resposta direta" in html


def test_rescue_prompt_serializes_choice_feedback():
    html = generate_single_page_html(_PROJECT, "/tmp", "", tutor_config=_TUTOR_ENABLED)
    assert "O sistema disse que essa não é a melhor escolha" in html
    assert "por que essa decisão é problemática" in html
