import base64
import re

from services.player_theme import (
    DEFAULTS,
    TUTOR_DEFAULTS,
    build_single_page_player_theme_css,
    build_tutor_theme_css,
    resolve_player_theme,
    resolve_tutor_theme,
)
from services.single_page_exporter import generate_single_page_html
from services.ai_agent import _required_game_mechanic


def test_single_page_css_uses_resolved_company_colors():
    project = {"brandKit": {
        "playerCanvasColor": "#112233",
        "playerHeaderColor": "#223344",
        "playerNavigationColor": "#334455",
        "playerAccentColor": "#ffcc00",
        "playerSidebarColor": "#445566",
        "playerSidebarItemColor": "#556677",
        "playerSidebarActiveColor": "#667788",
    }}
    css = build_single_page_player_theme_css(resolve_player_theme(project))
    assert "html, body { background: #112233; }" in css
    assert ".sp-header { background: #223344;" in css
    assert ".sp-progress { background: #334455; }" in css
    assert ".sp-progress-fill { background: #ffcc00; }" in css
    assert ".sp-drawer { background: #445566;" in css
    assert "background: #556677" in css
    assert "background: #667788" in css


def test_single_page_and_tutor_share_the_company_brand_kit():
    project = {"brandKit": {
        "playerAccentColor": "#123456",
        "playerNavigationColor": "#234567",
        "tutorHeaderColor": "#345678",
        "tutorPanelColor": "#456789",
    }}
    player_css = build_single_page_player_theme_css(resolve_player_theme(project))
    tutor = resolve_tutor_theme(project)
    assert "#123456" in player_css
    assert tutor["header"] == "#345678"
    assert tutor["panel"] == "#456789"


def test_player_theme_preserves_legacy_defaults_when_company_has_no_override():
    theme = resolve_player_theme({"brandKit": {}})
    assert theme["canvas"] == DEFAULTS["canvas"]
    assert theme["header"] == DEFAULTS["header"]
    assert theme["navigation"] == DEFAULTS["navigation"]
    assert theme["sidebar"] == DEFAULTS["sidebar"]
    assert theme["sidebarHeader"] == DEFAULTS["sidebarHeader"]


def test_company_can_customize_each_player_surface_and_text_contrast_is_automatic():
    theme = resolve_player_theme({
        "brandKit": {
            "playerCanvasColor": "#f1f5f9",
            "playerHeaderColor": "#ffffff",
            "playerNavigationColor": "#123456",
            "playerAccentColor": "#facc15",
            "playerSidebarColor": "#f8fafc",
            "playerSidebarHeaderColor": "#fde68a",
            "playerSidebarItemColor": "#1e3a8a",
            "playerSidebarActiveColor": "#fef3c7",
        }
    })
    assert theme["canvas"] == "#f1f5f9"
    assert theme["header"] == "#ffffff"
    assert theme["navigation"] == "#123456"
    assert theme["accent"] == "#facc15"
    assert theme["headerText"] == "#0f172a"
    assert theme["navigationText"] == "#f8fafc"
    assert theme["accentText"] == "#0f172a"
    assert theme["sidebarText"] == "#0f172a"
    assert theme["sidebarHeaderText"] == "#0f172a"
    assert theme["sidebarItemText"] == "#f8fafc"
    assert theme["sidebarActiveText"] == "#0f172a"


def test_invalid_player_color_falls_back_safely():
    theme = resolve_player_theme({
        "brandKit": {"playerCanvasColor": "red; display:none"}
    })
    assert theme["canvas"] == DEFAULTS["canvas"]


def test_tutor_inherits_company_player_colors_and_calculates_contrast():
    theme = resolve_tutor_theme({
        "brandKit": {
            "playerAccentColor": "#ef4444",
            "playerNavigationColor": "#fee2e2",
            "playerSidebarItemColor": "#7f1d1d",
        }
    })
    assert theme["header"] == "#ef4444"
    assert theme["panel"] == "#fee2e2"
    assert theme["message"] == "#7f1d1d"
    assert theme["panelText"] == "#0f172a"
    assert theme["messageText"] == "#f8fafc"


def test_dedicated_tutor_colors_override_player_and_generate_scoped_css():
    theme = resolve_tutor_theme({
        "brandKit": {
            "playerAccentColor": "#ef4444",
            "tutorHeaderColor": "#112233",
            "tutorPanelColor": "#ffffff",
            "tutorAccentColor": "#facc15",
            "tutorMessageColor": "#334155",
        }
    })
    assert theme["header"] == "#112233"
    assert theme["panel"] == "#ffffff"
    assert theme["accent"] == "#facc15"
    css = build_tutor_theme_css(theme)
    assert ".tutor-fab" in css
    assert ".tutor-contrast-light" in css
    assert "#112233" in css
    assert "#facc15" in css


def test_tutor_preserves_legacy_palette_without_brand_kit():
    theme = resolve_tutor_theme({"brandKit": {}})
    assert theme["header"] == TUTOR_DEFAULTS["header"]
    assert theme["panel"] == TUTOR_DEFAULTS["panel"]
    assert theme["customized"] is False
    assert build_tutor_theme_css(theme) == ""


def test_visual_journey_uses_cinematic_single_page_chapters():
    project = {
        "id": "journey-1",
        "name": "NR-1 na Prática",
        "playerTemplate": "visual_journey",
        "course": {
            "metadata": {
                "title": "NR-1 na Prática",
                "visualCourseMode": "illustrated_journey",
                "playerTemplate": "visual_journey",
            },
            "slides": [{
                "id": "s1", "title": "Uma situação de risco", "moduleName": "Capítulo 1",
                "narrativeBeat": "observe", "elements": [], "width": 1920, "height": 820,
            }],
        },
    }
    html = generate_single_page_html(project, "/tmp/no-assets", "")
    assert 'body class="sp-visual-journey"' in html
    assert "sp-journey-section" in html
    assert "Capítulo 1" in html
    assert "sp-journey-beat" in html
    assert "fotografia" not in html  # internal prompt metadata never leaks to learners


def test_visual_journey_renders_distinct_layout_and_explorable_scene():
    project = {
        "id": "journey-interactive-1",
        "name": "Jornada aplicada",
        "playerTemplate": "visual_journey",
        "course": {
            "metadata": {"visualCourseMode": "illustrated_journey"},
            "slides": [{
                "id": "s1", "title": "Investigue a cena", "moduleName": "Missão 1",
                "narrativeBeat": "observe", "journeyLayout": "guided_observation",
                "width": 1920, "height": 820,
                "elements": [{
                    "id": "img1", "type": "image",
                    "src": "data:image/png;base64,iVBORw0KGgo=",
                    "journeyInteractive": True,
                    "observationPrompt": "Localize os riscos antes de decidir.",
                    "visualEvidence": ["saída obstruída", "piso molhado", "proteção ausente"],
                }],
            }],
        },
    }
    html = generate_single_page_html(project, "/tmp/no-assets", "")
    assert "sp-layout-guided-observation" in html
    assert "sp-evidence-scene" in html
    assert "Localize os riscos antes de decidir." in html
    assert "saída obstruída" in html
    assert html.count("sp-evidence-pin sp-evidence-pin-") == 3
    assert "grid-template-columns: minmax(0, 1.12fr) minmax(420px, .88fr)" in html
    assert "@media (max-width: 1450px) and (min-width: 721px)" in html
    assert "html:has(body.sp-visual-journey) { scroll-padding-top: 72px; }" in html


def test_guided_observation_never_squeezes_iframe_into_side_rail():
    project = {
        "id": "journey-observation-app", "name": "Curso", "playerTemplate": "visual_journey",
        "course": {"metadata": {"visualCourseMode": "illustrated_journey"}, "slides": [{
            "id": "o1", "title": "Observe e explore", "narrativeBeat": "observe",
            "journeyLayout": "guided_observation", "width": 1920, "height": 820,
            "elements": [
                {"type": "image", "src": "data:image/png;base64,iVBORw0KGgo="},
                {"type": "html", "width": 960, "height": 540, "htmlDisplayMode": "fit",
                 "htmlContent": "<!doctype html><html><body><button>Explorar conceito</button><script>document.querySelector('button').onclick=function(){}</script></body></html>"},
            ],
        }]},
    }
    html = generate_single_page_html(project, "/tmp/no-assets", "")
    assert ".sp-layout-guided-observation .sp-section-body:has(iframe)" in html
    assert "minmax(520px, .92fr)" in html
    assert "@media (max-width: 1199px)" in html
    assert "aspect-ratio: 16 / 9" in html


def test_quiz_autostarts_and_scenario_uses_accessible_contrast():
    project = {
        "id": "interactive-accessibility", "name": "Curso", "playerTemplate": "visual_journey",
        "course": {"metadata": {"visualCourseMode": "illustrated_journey"}, "slides": [{
            "id": "q1", "title": "Quiz", "type": "quiz", "elements": [{
                "type": "quiz", "quizConfig": {"title": "Teste", "questionIds": ["x"]},
            }],
        }, {
            "id": "s1", "title": "Cenário", "type": "scenario", "elements": [{
                "type": "scenario", "scenarioData": {"title": "Decisão", "description": "Escolha com cuidado"},
            }],
        }]},
    }
    questions = [{"id": "x", "question": "Pergunta?", "alternatives": [{"text": "Sim", "isCorrect": True}]}]
    html = generate_single_page_html(project, "/tmp/no-assets", "", questions=questions)
    assert 'data-autostart="true"' in html
    assert "SP.startQuiz(quiz)" in html
    assert "#0f172a 0%,#173b63 58%,#0f766e 100%" in html
    assert "color:#f8fafc!important" in html


def test_visual_journey_infographic_uses_stable_contextual_template():
    project = {
        "id": "stable-infographic", "name": "Curso", "playerTemplate": "visual_journey",
        "course": {"metadata": {"visualCourseMode": "illustrated_journey"}, "slides": [{
            "id": "i1", "title": "Ciclo do Design Thinking", "type": "infographic",
            "contentType": "infographic", "elements": [{
                "type": "html", "width": 1920, "height": 820, "htmlDisplayMode": "fit",
                "htmlContent": "<!doctype html><html><body><div class='chaotic-node'>Nó solto</div></body></html>",
            }],
        }]},
    }
    html = generate_single_page_html(project, "/tmp/no-assets", "")
    encoded = re.search(r'data:text/html;charset=utf-8;base64,([^"\']+)', html).group(1)
    iframe_html = base64.b64decode(encoded).decode("utf-8")
    assert "Síntese visual interativa" in iframe_html
    assert "chaotic-node" not in iframe_html


def test_legacy_infographic_without_type_is_repaired_during_export():
    project = {
        "id": "legacy-infographic", "name": "Curso antigo",
        "course": {"slides": [{
            "id": "i-old", "title": "Ciclo do Design Thinking", "elements": [{
                "type": "html", "width": 500, "height": 900,
                "htmlContent": "<!doctype html><html><body><div class='cycle-node'>Empatia</div><button>Explore o Ciclo</button></body></html>",
            }],
        }]},
    }
    html = generate_single_page_html(project, "/tmp/no-assets", "")
    encoded = re.search(r'data:text/html;charset=utf-8;base64,([^"\']+)', html).group(1)
    iframe_html = base64.b64decode(encoded).decode("utf-8")
    assert "Síntese visual interativa" in iframe_html
    assert "Explore o Ciclo" not in iframe_html


def test_visual_journey_fullbleed_game_never_uses_split_column():
    project = {
        "id": "journey-game-1", "name": "Curso",
        "playerTemplate": "visual_journey",
        "course": {"metadata": {"visualCourseMode": "illustrated_journey"}, "slides": [{
            "id": "g1", "title": "Penalty Quest", "narrativeBeat": "decide",
            "journeyLayout": "decision_split", "width": 1920, "height": 820,
            "elements": [{
                "id": "game", "type": "html", "width": 1920, "height": 820,
                "htmlDisplayMode": "fit",
                "htmlContent": "<!doctype html><html><body><button>Começar</button><script>document.querySelector('button').onclick=function(){}</script></body></html>",
            }],
        }]},
    }
    html = generate_single_page_html(project, "/tmp/no-assets", "")
    assert "sp-layout-interactive-stage" in html
    assert 'aspect-ratio: 16 / 9' in html
    assert "calc((100dvh - 238px) * 1.77778)" in html
    assert ".sp-layout-interactive-stage .sp-iframe-done" in html
    assert "position: sticky; bottom: 10px" in html


def test_visual_journey_upgrades_legacy_game_scaling_cap():
    legacy_fit = "var s=Math.min((innerWidth-pad*2)/cw,(innerHeight-pad*2)/ch,1);s=Math.max(.1,s);"
    project = {
        "id": "journey-legacy-game", "name": "Curso", "playerTemplate": "visual_journey",
        "course": {"metadata": {"visualCourseMode": "illustrated_journey"}, "slides": [{
            "id": "g1", "title": "Jogo", "type": "game", "width": 1920, "height": 820,
            "elements": [{
                "id": "game", "type": "html", "width": 1920, "height": 820,
                "htmlDisplayMode": "fit",
                "htmlContent": (
                    "<!doctype html><html><body><main>Jogo educativo interativo</main>"
                    "<script>const marker='__scormify_fit_v3';" + legacy_fit + "</script></body></html>"
                ),
            }],
        }]},
    }
    html = generate_single_page_html(project, "/tmp/no-assets", "")
    encoded = re.search(r'data:text/html;charset=utf-8;base64,([^"\']+)', html).group(1)
    iframe_html = base64.b64decode(encoded).decode("utf-8")
    assert "(innerHeight-pad*2)/ch,1.35);s=Math.max(.1,s);" in iframe_html
    assert legacy_fit not in iframe_html


def test_generated_games_use_deterministic_full_stage_fit():
    from services.single_page_exporter import _inject_fixed_game_stage_fit

    game = """<!doctype html><html><body><main class="game"><div class="hud">XP coins lives combo</div></main>
    <script>const QuestionEngine={};</script><div id="__stage"></div></body></html>"""
    fitted = _inject_fixed_game_stage_fit(game)
    assert "__scormify_game_fit_v7" in fitted
    assert "(window.innerWidth-p*2)/960" in fitted
    assert "(window.innerHeight-p*2)/540" in fitted
    assert "max-width:none!important" in fitted
    assert "/540));" in fitted
    assert "/540,1.55)" not in fitted

    ordinary = '<html><body><main class="app">Relatório</main></body></html>'
    assert _inject_fixed_game_stage_fit(ordinary) == ordinary


def test_wide_editor_header_does_not_turn_regular_slide_into_game_stage():
    project = {
        "id": "journey-content-1", "name": "Curso", "playerTemplate": "visual_journey",
        "course": {"metadata": {"visualCourseMode": "illustrated_journey"}, "slides": [{
            "title": "Responsabilidades", "narrativeBeat": "context", "width": 1920, "height": 820,
            "elements": [
                {"type": "html", "width": 1680, "height": 40, "htmlContent": "<div>Módulo 1</div>"},
                {"type": "html", "width": 960, "height": 600, "htmlContent": "<h2>Deveres</h2><p>Texto legível.</p>"},
            ],
        }]},
    }
    html = generate_single_page_html(project, "/tmp/no-assets", "")
    section_open = html.split("<section class=", 1)[1].split(">", 1)[0]
    assert "sp-layout-interactive-stage" not in section_open
    assert "sp-layout-reflection" in section_open


def test_visual_journey_replaces_game_shell_saved_as_simulator():
    project = {
        "id": "journey-simulator-repair", "name": "Curso", "playerTemplate": "visual_journey",
        "course": {"metadata": {"visualCourseMode": "illustrated_journey"}, "slides": [{
            "id": "s1", "title": "Simulador: Prototipação Rápida",
            "type": "simulator", "contentType": "simulator", "width": 1920, "height": 820,
            "elements": [{
                "id": "wrong-game", "type": "html", "width": 1920, "height": 820,
                "htmlDisplayMode": "fit",
                "htmlContent": (
                    "<!doctype html><html><body><main>KNOWLEDGE LEAGUE</main>"
                    "<script>const QuestionEngine={};</script></body></html>"
                ),
            }],
        }]},
    }
    html = generate_single_page_html(project, "/tmp/no-assets", "")
    encoded = re.search(r'data:text/html;charset=utf-8;base64,([^"\']+)', html).group(1)
    iframe_html = base64.b64decode(encoded).decode("utf-8")
    assert "Simulação interativa" in iframe_html
    assert "Classifique cada situação" in iframe_html
    assert "KNOWLEDGE LEAGUE" not in iframe_html


def test_export_uses_title_to_repair_generic_flashcard_game_shell():
    project = {
        "id": "legacy-flashcard-repair", "name": "Curso",
        "course": {"slides": [{
            "id": "f1", "title": "Flashcards: Pesquisa Visual Efetiva",
            "type": "content", "elements": [{
                "type": "html", "width": 1920, "height": 820,
                "htmlContent": (
                    "<!doctype html><html><body><main>KNOWLEDGE LEAGUE</main>"
                    "<script>const QuestionEngine={};</script></body></html>"
                ),
            }],
        }]},
    }
    html = generate_single_page_html(project, "/tmp/no-assets", "")
    encoded = re.search(r'data:text/html;charset=utf-8;base64,([^"\']+)', html).group(1)
    iframe_html = base64.b64decode(encoded).decode("utf-8")
    assert "Clique no cartão para ver a resposta" in iframe_html
    assert "rotateY(180deg)" in iframe_html
    assert "KNOWLEDGE LEAGUE" not in iframe_html


def test_export_uses_title_to_repair_generic_simulator_game_shell():
    project = {
        "id": "legacy-simulator-repair", "name": "Curso",
        "course": {"slides": [{
            "id": "s1", "title": "Simulador: Prototipação Rápida",
            "type": "content", "elements": [{
                "type": "html", "width": 1920, "height": 820,
                "htmlContent": (
                    "<!doctype html><html><body><main>KNOWLEDGE LEAGUE</main>"
                    "<script>const QuestionEngine={};</script></body></html>"
                ),
            }],
        }]},
    }
    html = generate_single_page_html(project, "/tmp/no-assets", "")
    encoded = re.search(r'data:text/html;charset=utf-8;base64,([^"\']+)', html).group(1)
    iframe_html = base64.b64decode(encoded).decode("utf-8")
    assert "Simulação interativa" in iframe_html
    assert "Classifique cada situação" in iframe_html
    assert "KNOWLEDGE LEAGUE" not in iframe_html


def test_visual_journey_sections_are_continuous_viewport_pages():
    project = {
        "id": "journey-continuous", "name": "Curso", "playerTemplate": "visual_journey",
        "course": {"metadata": {"visualCourseMode": "illustrated_journey"}, "slides": [
            {"id": "a", "title": "Primeira", "elements": [{"type": "text", "content": "Conteúdo A"}]},
            {"id": "b", "title": "Segunda", "elements": [{"type": "text", "content": "Conteúdo B"}]},
        ]},
    }
    html = generate_single_page_html(project, "/tmp/no-assets", "")
    assert "min-height: calc(100dvh - 70px)" in html
    assert "scroll-snap-align: start" in html
    assert ".sp-journey-section + .sp-journey-section" in html
    assert "margin: 0 auto 44px" not in html


def test_export_repairs_legacy_game_stage_and_preserves_questions():
    legacy = '''<!doctype html><html><head><style>
    /* Transitional exports had the new selectors but retained the old arena DOM. */
    .word-stage{background:#fff}.penalty-stage{background:#090}
    </style></head><body>
    <div class="brand">ARENA DAS PALAVRAS</div><div class="arena" id="arena"><div class="goal"></div></div>
    <script>const questionBank=[{"id":"old1","topic":"Criatividade","difficulty":"medio","question":"Pergunta preservada?","alternatives":["Sim","Não"],"correct":0,"explanation":"Explicação preservada."}];
    const QuestionEngine={questions:questionBank};</script></body></html>'''
    project = {
        "id": "legacy-game-repair", "name": "Curso", "playerTemplate": "visual_journey",
        "course": {"metadata": {"visualCourseMode": "illustrated_journey"}, "slides": [{
            # Legacy Agent projects did not always persist type/contentType.
            "id": "g1", "title": "Jogo: Criatividade",
            "width": 1920, "height": 820,
            "elements": [{"type": "html", "width": 1920, "height": 820,
                          "htmlDisplayMode": "fit", "htmlContent": legacy}],
        }]},
    }
    html = generate_single_page_html(project, "/tmp/no-assets", "")
    encoded = re.search(r'data:text/html;charset=utf-8;base64,([^"\']+)', html).group(1)
    iframe_html = base64.b64decode(encoded).decode("utf-8")
    expected_mechanic = _required_game_mechanic({"id": "g1", "title": "Jogo: Criatividade"})
    assert ("word-stage" in iframe_html) if expected_mechanic == "word_challenge" else ('data-agent-game-template="editor-v1"' in iframe_html)
    assert "Pergunta preservada?" in iframe_html
    assert "Explicação preservada." in iframe_html


def test_export_repairs_game_saved_as_simulator_element():
    legacy = '''<!doctype html><html><body>
    <div>EXPEDIÇÃO DO SABER</div>
    <div class="arena climb-stage" id="arena"><div class="mountain"></div></div>
    <script>const questionBank=[{"id":"q1","question":"Subir?","alternatives":["Sim","Não"],"correct":0}];
    const QuestionEngine={questions:questionBank};</script></body></html>'''
    project = {
        "id": "legacy-game-as-simulator", "name": "Curso", "playerTemplate": "visual_journey",
        "course": {"slides": [{
            "id": "climb1", "title": "Escalada do conhecimento", "gameMechanic": "knowledge_climb",
            "width": 1920, "height": 820,
            "elements": [{"type": "simulator", "width": 1920, "height": 820,
                          "htmlDisplayMode": "fit", "htmlContent": legacy}],
        }]},
    }
    html = generate_single_page_html(project, "/tmp/no-assets", "")
    encoded = re.search(r'data:text/html;charset=utf-8;base64,([^"\']+)', html).group(1)
    iframe_html = base64.b64decode(encoded).decode("utf-8")
    assert 'data-agent-game-template="editor-v1"' in iframe_html
    assert 'class="mountain"' in iframe_html
    assert "Subir?" in iframe_html
