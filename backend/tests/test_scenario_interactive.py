"""Tests for the interactive AI-generated learning scenarios.

The scenarios have a "Choose Your Own Adventure" structure with:
- nodes[]: each with narrative, choices, character_speaking, is_ending
- choices[]: each with text, feedback, is_optimal, points, next_node_id

This must be rendered as an interactive flow in the single-page export.
"""
import json
import re
import html as _html

import pytest

from services.single_page_exporter import generate_single_page_html


SAMPLE_SCENARIO = {
    "title": "O Feedback Difícil",
    "description": "Cenário sobre liderança",
    "context": "Você é gestor de RH",
    "characters": [
        {"name": "Você", "role": "Gestor"},
        {"name": "Sofia Mendes", "role": "Liderada"},
    ],
    "nodes": [
        {
            "id": "n1",
            "title": "Nó Inicial",
            "narrative": "Você precisa dar feedback para Sofia.",
            "character_speaking": "Sofia Mendes",
            "choices": [
                {"id": "c1a", "text": "Falar diretamente", "next_node_id": "n2",
                 "feedback": "Bom! Direto.", "is_optimal": True, "points": 10},
                {"id": "c1b", "text": "Adiar a conversa", "next_node_id": "n3",
                 "feedback": "Procrastinar piora a situação.", "is_optimal": False, "points": 2},
            ],
        },
        {
            "id": "n2",
            "title": "Bom caminho",
            "narrative": "Sofia entendeu o feedback.",
            "is_ending": True,
            "ending_type": "positive",
            "choices": [],
        },
        {
            "id": "n3",
            "title": "Caminho difícil",
            "narrative": "A situação ficou pior.",
            "is_ending": True,
            "ending_type": "negative",
            "choices": [],
        },
    ],
}


def _project_with_scenario():
    return {
        "id": "p", "name": "T",
        "course": {"metadata": {"title": "T"}, "slides": [
            {"id": "s1", "title": "Cenário", "elements": [
                {"id": "sc1", "type": "scenario", "scenarioData": SAMPLE_SCENARIO}
            ]}
        ]}
    }


def test_scenario_serializes_full_node_graph():
    out = generate_single_page_html(_project_with_scenario(), "/none")
    m = re.search(r'data-scenario="([^"]*)"', out)
    assert m, "data-scenario attribute missing"
    payload = json.loads(_html.unescape(m.group(1)))
    assert "nodes" in payload
    assert len(payload["nodes"]) == 3
    n1 = payload["nodes"][0]
    assert n1["id"] == "n1"
    assert "Sofia" in n1["character_speaking"]
    assert len(n1["choices"]) == 2
    assert n1["choices"][0]["is_optimal"] is True
    assert n1["choices"][0]["points"] == 10
    # Endings carry ending_type
    n2 = payload["nodes"][1]
    assert n2["is_ending"] is True
    assert n2["ending_type"] == "positive"


def test_scenario_renders_iniciar_button_when_nodes_present():
    out = generate_single_page_html(_project_with_scenario(), "/none")
    assert "▶ Iniciar Cenário Interativo" in out
    # Mark as concluído fallback should NOT be present
    assert "Marcar como concluído ✓" not in out


def test_scenario_without_nodes_falls_back_to_simple_mark_done():
    project = {
        "id": "p", "name": "T",
        "course": {"metadata": {"title": "T"}, "slides": [
            {"id": "s1", "title": "C", "elements": [
                {"id": "sc1", "type": "scenario", "scenarioData": {
                    "title": "Cenário Simples", "description": "Sem ramificação"
                }}
            ]}
        ]}
    }
    out = generate_single_page_html(project, "/none")
    assert "Marcar como concluído ✓" in out
    assert "▶ Iniciar Cenário Interativo" not in out


def test_scenario_js_runtime_exposes_startScenario():
    """The window.SP must expose startScenario function in the runtime JS."""
    out = generate_single_page_html(_project_with_scenario(), "/none")
    assert "startScenario: function" in out
    assert "renderNode" in out  # internal helper
    assert "showFeedback" in out


def test_scenario_apostrophes_in_narrative_do_not_break_attribute():
    """Regression: apostrophes in narrative should not break the
    data-scenario JSON attribute."""
    project = {
        "id": "p", "name": "T",
        "course": {"metadata": {"title": "T"}, "slides": [
            {"id": "s1", "title": "C", "elements": [
                {"id": "sc1", "type": "scenario", "scenarioData": {
                    "title": "C",
                    "nodes": [{
                        "id": "n1",
                        "narrative": "Sofia diz: 'Não estou bem'.",
                        "choices": [{"id": "a", "text": "Diga 'tudo bem'", "feedback": "É ok", "is_optimal": True}]
                    }]
                }}
            ]}
        ]}
    }
    out = generate_single_page_html(project, "/none")
    m = re.search(r'data-scenario="([^"]*)"', out)
    assert m
    decoded = _html.unescape(m.group(1))
    parsed = json.loads(decoded)  # must not raise
    assert "Não estou bem" in parsed["nodes"][0]["narrative"]
