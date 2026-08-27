import re

from services.ai_agent import (
    _build_simulator_fallback_html,
    _build_game_fallback_html,
    _build_fallback_structure,
    _build_case_study_fallback_html,
    _build_flashcard_fallback_html,
    _build_infographic_fallback_html,
    _infographic_html_needs_repair,
    _build_storyboard_batches,
    _build_timeline_fallback_html,
    _interactive_html_is_functional,
    _normalize_interactive_storyboard_slide,
    _normalize_visual_content_slide,
    _premium_image_prompt,
    _premiumize_course_structure,
    _repair_legacy_game_html,
    _case_study_complexity_score,
    _flashcard_complexity_score,
    _game_complexity_score,
    _interactive_visual_direction,
    _required_simulator_mechanic,
    _required_game_mechanic,
    _simulator_complexity_score,
    _simulator_mechanic_is_functional,
    _timeline_complexity_score,
    _wrap_interactive_fullbleed,
    _derive_fallback_course_title,
    get_design_template_by_id,
)


def test_premium_structure_replaces_text_monotony_with_enabled_experiences():
    structure = {
        "modules": [{
            "title": "Autoconfiança na prática",
            "slides": [
                {"id": "s1", "type": "title", "title": "Capa"},
                {"id": "s2", "type": "content", "title": "Conceito"},
                {"id": "s3", "type": "content", "title": "Sinais"},
                {"id": "s4", "type": "content", "title": "Aplicação"},
                {"id": "s5", "type": "content", "title": "Prática"},
                {"id": "s6", "type": "summary", "title": "Síntese"},
            ],
        }],
    }
    config = {
        "resourceBalance": "alta",
        "enabledResources": {
            "infographic": True, "simulator": True, "flashcard": True,
            "game": False, "timeline": False, "case_study": False,
        },
    }

    result = _premiumize_course_structure(structure, config)
    body = result["modules"][0]["slides"][1:-1]
    interactive = [slide for slide in body if slide["type"] != "content"]

    assert len(interactive) >= 2
    assert all(slide["type"] in {"infographic", "simulator", "flashcard"} for slide in interactive)
    assert all(slide.get("experienceIntent") for slide in body)
    assert result["experienceQuality"]["profile"] == "premium"


def test_premium_content_receives_a_contextual_image_brief():
    structure = {"modules": [{"title": "Módulo", "slides": [
        {"type": "content", "title": "Conversa difícil", "purpose": "Comparar escuta e confronto"},
    ]}]}

    result = _premiumize_course_structure(
        structure,
        {"visualCourseMode": "standard", "resourceBalance": "baixa", "title": "Autoconfiança"},
    )
    prompt = result["modules"][0]["slides"][0]["requiredImagePrompt"]

    assert prompt == _premium_image_prompt(result["modules"][0]["slides"][0], {
        "visualCourseMode": "standard", "resourceBalance": "baixa", "title": "Autoconfiança"
    })
    assert "Conversa difícil" in prompt
    assert "16:9" in prompt
    assert "no written text" in prompt


def test_text_heavy_slide_is_converted_to_visual_cards():
    verbose = " ".join(["explicação detalhada do conceito e sua aplicação prática"] * 25)
    slide = {
        "type": "content",
        "title": "Pilares da autoconfiança",
        "purpose": "Reconheça evidências. Teste uma ação possível. Registre o aprendizado.",
        "elements": [{"type": "text", "content": f"<h2>Título</h2><p>{verbose}</p>"}],
    }

    result = _normalize_visual_content_slide(slide)

    assert result["qualityAdjusted"] == "visual-density"
    assert 'data-visual-pattern="insight-cards"' in result["elements"][0]["content"]
    assert result["contentBudgetWords"] == 70


def test_legacy_games_toggle_produces_real_game_in_every_module():
    structure = {
        "modules": [
            {"title": "M1", "slides": [
                {"type": "content", "title": "Conceito"},
                {"type": "content", "title": "Aplicação"},
                {"type": "quiz", "title": "Quiz"},
            ]},
            {"title": "M2", "slides": [
                {"type": "content", "title": "Conceito 2"},
                {"type": "simulator", "title": "Prática 2"},
                {"type": "quiz", "title": "Quiz 2"},
            ]},
        ],
    }
    # Old saved sessions used simulator=true for the label Jogos Educativos.
    config = {"resourceBalance": "media", "enabledResources": {"simulator": True, "quiz": True}}

    result = _premiumize_course_structure(structure, config)

    assert all(
        any(slide["type"] == "game" for slide in module["slides"])
        for module in result["modules"]
    )


def test_illustrated_journey_adds_narrative_and_action_image_metadata():
    structure = {"modules": [{"slides": [
        {"type": "title", "title": "Capa"},
        {"type": "content", "title": "Observe o ambiente"},
        {"type": "content", "title": "Escolha uma ação"},
        {"type": "content", "title": "Veja a consequência"},
        {"type": "summary", "title": "Síntese"},
    ]}]}
    config = {
        "visualCourseMode": "illustrated_journey",
        "resourceBalance": "media",
        "enabledResources": {"quiz": True},
    }

    result = _premiumize_course_structure(structure, config)
    body = result["modules"][0]["slides"][1:-1]

    assert result["experienceQuality"]["profile"] == "illustrated_journey"
    assert result["visualStoryBible"]["cast"]
    assert result["experienceQuality"]["requiredJourneyPattern"] == [
        "context", "observe", "decide", "practice", "reflect"
    ]
    assert all(slide.get("narrativeBeat") for slide in body)
    assert all(slide.get("imageRole") for slide in body)
    assert all("16:9" in slide.get("requiredImagePrompt", "") for slide in body)
    assert all("Marina" in slide.get("requiredImagePrompt", "") for slide in body)
    assert all(slide.get("storyContext", {}).get("continuityRule") for slide in body)
    assert any(slide["type"] == "game" for slide in body)


def test_legacy_flashcard_html_is_normalized_from_content_field():
    legacy_html = _build_flashcard_fallback_html({"title": "Escuta ativa"})
    slide = {
        "type": "flashcard",
        "title": "Técnicas de observação",
        "elements": [{"type": "html", "content": legacy_html}],
    }

    normalized = _normalize_interactive_storyboard_slide(slide)

    assert normalized["elements"][0]["type"] == "html"
    assert "htmlContent" in normalized["elements"][0]
    assert _interactive_html_is_functional(
        normalized["elements"][0]["htmlContent"], "flashcard"
    )


def test_empty_simulator_is_replaced_before_storyboard_preview():
    slide = {
        "type": "simulator",
        "title": "Simulação de atendimento",
        "moduleName": "Comunicação",
        "elements": [],
    }

    normalized = _normalize_interactive_storyboard_slide(slide)

    html = normalized["elements"][0]["htmlContent"]
    assert _interactive_html_is_functional(html, "simulator")
    assert "<script>" in html


def test_empty_game_becomes_a_premium_question_engine_experience():
    slide = {
        "type": "game",
        "title": "Jogo: Liderança em Ação",
        "moduleName": "Desenvolvimento de líderes",
        "purpose": (
            "A liderança situacional adapta a abordagem ao contexto. "
            "Decisões devem considerar evidências, pessoas e consequências."
        ),
        "elements": [],
    }
    normalized = _normalize_interactive_storyboard_slide(slide)
    generated = normalized["elements"][0]["htmlContent"]

    assert any(name in generated for name in (
        "Penalty Quest", "Quiz Show", "Memory Mission",
        "Escalada do Conhecimento", "Forca Inteligente", "Desafio ao Alvo",
    ))
    assert any(stage in generated for stage in (
        "penalty-stage", "quiz-stage", "memory-stage",
        "climb-stage", "word-stage", "target-stage",
    ))
    assert "const QuestionEngine=" in generated
    for method in (
        "getQuestion", "getRandomQuestion", "getQuestionsByTopic",
        "getQuestionsByDifficulty", "validateAnswer", "saveResult",
    ):
        assert method in generated
    assert "particles" in generated
    assert "XP total" in generated
    assert _game_complexity_score(generated) >= 8


def test_each_game_mechanic_has_its_own_visual_stage():
    expected = {
        "penalty_quest": "penalty-stage",
        "quiz_show": "quiz-stage",
        "memory_match": "memory-stage",
        "knowledge_climb": "climb-stage",
        "word_challenge": "word-stage",
        "target_challenge": "target-stage",
    }
    for mechanic, stage_class in expected.items():
        generated = _build_game_fallback_html({
            "type": "game",
            "title": "Jogo educativo",
            "purpose": "Aplicar conceitos em uma atividade desafiadora.",
            "gameMechanic": mechanic,
        })
        arena = re.search(r'<div class="arena[^>]*" id="arena"[^>]*>[\s\S]*?</div><div class="panel">', generated)
        assert arena is not None
        assert f'class="arena {stage_class}"' in arena.group(0)
        if mechanic != "penalty_quest":
            assert '<div class="goal"></div>' not in generated
        assert "stage-caption" in generated


def test_legacy_game_repair_keeps_the_explicit_mechanic():
    legacy = """<!doctype html><html><body>
    <h1>ARENA DAS PALAVRAS</h1><div class="arena" id="arena"><div class="goal"></div></div>
    <div class="panel"></div><script>const questionBank=[]; const QuestionEngine={};</script>
    </body></html>"""

    repaired = _repair_legacy_game_html(
        {"type": "game", "title": "Memória", "gameMechanic": "memory_match"},
        legacy,
    )

    assert 'class="arena memory-stage"' in repaired
    assert 'class="arena word-stage"' not in repaired


def test_generic_legacy_arena_heading_does_not_force_every_game_to_hangman():
    slide = {"type": "game", "id": "legacy-42", "title": "Escape dos bloqueios criativos"}
    legacy = """<!doctype html><html><body>
    <h1>ARENA DAS PALAVRAS</h1><div class="arena" id="arena"><div class="goal"></div></div>
    <div class="panel"></div><script>const questionBank=[]; const QuestionEngine={};</script>
    </body></html>"""

    repaired = _repair_legacy_game_html(slide, legacy)
    expected_stage = {
        "penalty_quest": "penalty-stage", "quiz_show": "quiz-stage",
        "memory_match": "memory-stage", "knowledge_climb": "climb-stage",
        "word_challenge": "word-stage", "target_challenge": "target-stage",
    }[_required_game_mechanic(slide)]

    assert f'class="arena {expected_stage}"' in repaired


def test_word_challenge_reveals_the_hangman_only_after_wrong_answers():
    generated = _build_game_fallback_html({
        "type": "game",
        "title": "Jogo: Conceitos essenciais",
        "gameMechanic": "word_challenge",
    })

    assert generated.count('class="hangman-part"') == 6
    assert "const MAX_LIVES=6" in generated
    assert "revealPenalty()" in generated
    assert "mistakes=MAX_LIVES-this.lives" in generated
    assert 'class="letter-preview"' not in generated
    assert 'class="word-slots"' not in generated
    assert "Cada resposta incorreta acrescenta uma parte" in generated


def test_empty_infographic_is_replaced_with_contextual_visual():
    slide = {
        "type": "infographic",
        "title": "Neurociência da criatividade",
        "moduleName": "Fundamentos da criatividade",
        "purpose": "Relacionar observação, repertório, associação, incubação e experimentação.",
        "elements": [],
    }

    normalized = _normalize_interactive_storyboard_slide(slide)
    html = normalized["elements"][0]["htmlContent"]

    assert _interactive_html_is_functional(html, "infographic")
    assert "Síntese visual interativa" in html
    assert "Neurociência da criatividade" in html


def test_legacy_free_floating_infographic_is_replaced_even_when_html_exists():
    legacy = """<!doctype html><html><body>
      <div class='cycle-node'>Empatia</div><button>Explore o Ciclo</button>
    </body></html>"""
    slide = {
        "type": "infographic",
        "title": "Ciclo do Design Thinking",
        "purpose": "Empatia. Definição. Ideação. Protótipo. Teste.",
        "elements": [{"type": "html", "htmlContent": legacy}],
    }

    assert _infographic_html_needs_repair(legacy)
    normalized = _normalize_interactive_storyboard_slide(slide)
    generated = normalized["elements"][0]["htmlContent"]
    assert "Síntese visual interativa" in generated
    assert "Explore o Ciclo" not in generated


def test_analysis_fallback_derives_title_from_uploaded_filename():
    assert _derive_fallback_course_title("Conteúdo do treinamento", "Guia_de_Seguranca.pdf") == "Guia de Seguranca"


def test_structure_fallback_is_complete_and_respects_enabled_resources():
    structure = _build_fallback_structure(
        "Segurança no trabalho reduz riscos. A prevenção depende de análise e boas práticas.",
        {
            "title": "Curso sem título",
            "modules": 2,
            "duration": 25,
            "enabledResources": {"quiz": True, "simulator": True},
        },
        "temporary upstream failure",
    )
    assert structure["fallbackUsed"] is True
    assert structure["courseTitle"] != "Curso sem título"
    assert len(structure["modules"]) == 2
    slides = [slide for module in structure["modules"] for slide in module["slides"]]
    assert slides[0]["type"] == "title"
    assert slides[-1]["type"] == "summary"
    assert any(slide["type"] == "simulator" for slide in slides)
    assert any(slide["type"] == "quiz" for slide in slides)


def test_failed_simulator_gets_a_complete_interactive_fallback():
    generated = _build_simulator_fallback_html({
        "title": "Simulação: Diagnóstico de Autoconfiança",
        "purpose": "Avaliar decisões e aplicar estratégias de autoconfiança em situações reais.",
    })
    assert _interactive_html_is_functional(generated, "simulator")
    assert "draggable=true" in generated
    assert "ondrop" in generated
    assert "Verificar estratégia" in generated
    assert "Reiniciar" in generated
    assert "Diagnóstico de Autoconfiança" in generated


def test_clean_dark_template_uses_stable_heading_font():
    template = get_design_template_by_id("clean-dark")
    assert "Manrope" in template["fonts"]["heading"]
    assert "Space Grotesk" not in template["fonts"]["heading"]


def test_export_font_bundles_do_not_request_broken_space_grotesk_asset():
    root = __import__("pathlib").Path(__file__).resolve().parents[2]
    files = (
        root / "frontend" / "src" / "utils" / "htmlUtils.js",
        root / "backend" / "services" / "export_assets" / "player_template.html",
        root / "backend" / "services" / "html_exporter.py",
        root / "backend" / "services" / "single_page_exporter.py",
    )
    for file in files:
        assert "Space+Grotesk" not in file.read_text(encoding="utf-8")


def _slide(kind):
    return {
        "type": kind,
        "title": "Evolução da energia solar",
        "moduleName": "Energia e eficiência",
        "elements": [
            {
                "type": "text",
                "content": (
                    "A tecnologia começou com aplicações experimentais. "
                    "A redução de custos ampliou o uso residencial. "
                    "Novas políticas incentivaram projetos corporativos. "
                    "Sistemas de armazenamento aumentaram a confiabilidade. "
                    "A integração à rede consolidou a adoção em larga escala."
                ),
            }
        ],
    }


def test_rejects_large_but_visually_empty_html():
    skeleton = "<!doctype html><html><head><style>" + (".x{color:red}" * 80) + "</style></head><body><div></div><script>const ready=true;</script></body></html>"
    assert not _interactive_html_is_functional(skeleton, "timeline")


def test_timeline_fallback_is_visible_and_interactive():
    result = _build_timeline_fallback_html(_slide("timeline"))
    assert "Evolução da energia solar" in result
    assert "const events=" in result
    assert "show(0)" in result
    assert _interactive_html_is_functional(result, "timeline")


def test_case_study_fallback_is_visible_and_interactive():
    result = _build_case_study_fallback_html(_slide("case_study"))
    assert "Evolução da energia solar" in result
    assert "Contexto" in result
    assert "Que decisão você tomaria" in result
    assert _interactive_html_is_functional(result, "case_study")


def test_rich_interactives_get_an_exclusive_storyboard_batch():
    slides = [
        {"id": "a", "type": "content"},
        {"id": "b", "type": "content"},
        {"id": "sim", "type": "simulator"},
        {"id": "game", "type": "game"},
        {"id": "c", "type": "content"},
        {"id": "case", "type": "case_study"},
    ]
    batches = _build_storyboard_batches(slides, regular_batch_size=4)
    assert [[slide["id"] for slide in batch] for batch in batches] == [
        ["a", "b"], ["sim"], ["game"], ["c"], ["case"]
    ]


def test_simulator_complexity_score_rejects_a_basic_quiz_and_accepts_stateful_simulation():
    basic = """<!doctype html><html><body><button>Sim</button><button>Nao</button>
    <script>function answer(value){ document.body.dataset.answer=value; }</script></body></html>"""
    rich = """<!doctype html><html><body>
    <label>Orcamento <input type='range'></label><select><option>Estrategia A</option></select>
    <button>Decisao 1</button><button>Decisao 2</button><button>Proxima rodada</button><button>Reiniciar</button>
    <div id='feedback'>Feedback e debrief das consequencias e trade-offs</div>
    <script>
    const state={score:0,risco:50,custo:100,prazo:10,qualidade:70,rodada:1};
    function decidir(impacto){state.score+=impacto;state.risco-=impacto;state.rodada++;render();}
    function render(){document.body.dataset.progress=state.rodada;document.body.dataset.state=JSON.stringify(state);}
    function reiniciar(){state.score=0;state.risco=50;state.rodada=1;render();}
    document.querySelector('input').addEventListener('input',render);
    """ + ("// consequence model and conditional phase logic\n" * 60) + "</script></body></html>"
    assert _simulator_complexity_score(basic) < 6
    assert _simulator_complexity_score(rich) >= 6


def test_drag_drop_requires_real_browser_events_not_instructional_copy():
    fake = """<!doctype html><html><body><p>Arraste e solte os itens</p>
    <button>Confirmar</button><script>const state={score:0};</script></body></html>"""
    real = """<!doctype html><html><body>
    <div draggable='true' id='card'>Etapa</div><div id='zone'>Destino</div>
    <script>card.addEventListener('dragstart',e=>e.dataTransfer.setData('text/plain','card'));
    zone.addEventListener('dragover',e=>e.preventDefault());
    zone.addEventListener('drop',e=>{e.preventDefault();zone.appendChild(card);});</script></body></html>"""
    assert not _simulator_mechanic_is_functional(fake, "drag_drop")
    assert _simulator_mechanic_is_functional(real, "drag_drop")


def test_required_mechanics_are_stable_and_varied_between_slides():
    slides = [
        {"id": str(i), "title": f"Desafio {i}", "purpose": "Aplicacao", "moduleName": "Modulo"}
        for i in range(12)
    ]
    first_pass = [_required_simulator_mechanic(slide) for slide in slides]
    second_pass = [_required_simulator_mechanic(slide) for slide in slides]
    assert first_pass == second_pass
    assert len(set(first_pass)) >= 3


def test_interactive_catalog_supports_distinct_professional_experiences():
    source = (__import__("pathlib").Path(__file__).resolve().parents[1] / "services" / "ai_agent.py").read_text(encoding="utf-8")
    for mechanic in (
        "timed_challenge", "physics_controls", "tool_workspace",
        "network_explorer", "memory_match", "word_challenge",
    ):
        assert mechanic in source
    slides = [
        {"id": str(i), "title": title, "purpose": purpose, "moduleName": "Laboratorio"}
        for i, (title, purpose) in enumerate((
            ("Penalti educativo", "quiz cronometrado"),
            ("Bomba hidraulica", "fluxo pressao capacidade"),
            ("Conversor de medidas", "ferramenta calculadora"),
            ("Mapa de processos", "rede conceitual"),
            ("Memoria de conceitos", "associacao"),
            ("Forca de vocabulario", "termos tecnicos"),
            ("Motor e combustao", "controle fisico"),
            ("Diagnostico de riscos", "painel de indicadores"),
        ))
    ]
    assert len({_interactive_visual_direction(slide) for slide in slides}) >= 4


def test_flashcard_fallback_meets_mastery_and_visual_quality_gate():
    generated = _build_flashcard_fallback_html({
        "title": "Gestao de riscos",
        "purpose": "Identificar riscos. Avaliar impactos. Definir controles. Monitorar indicadores. Comunicar desvios. Melhorar continuamente.",
    })
    assert _flashcard_complexity_score(generated) >= 6
    assert "Revisar não dominados" in generated
    assert "Embaralhar e reiniciar" in generated


def test_requested_mechanic_caps_otherwise_rich_but_wrong_simulator():
    allocation = """<!doctype html><html><body>
    <input type='range'><input type='range'><input type='range'><select><option>Plano</option></select>
    <button>Decisao</button><button>Rodada</button><button>Reiniciar</button><button>Debrief</button>
    <p>Orcamento, recurso, risco, impacto, consequencia, feedback e progresso.</p>
    <script>const state={score:0,risco:40,custo:10,rodada:1};
    document.querySelectorAll('input').forEach(x=>x.addEventListener('input',render));
    function render(){state.custo++;state.score++;} function reset(){state.rodada=1;}
    """ + ("// detailed conditional consequence model\n" * 80) + "</script></body></html>"
    assert _simulator_complexity_score(allocation, "resource_allocation") >= 6
    assert _simulator_complexity_score(allocation, "drag_drop") <= 5


def test_last_generation_attempt_cannot_bypass_the_quality_gate():
    source = (__import__("pathlib").Path(__file__).resolve().parents[1] / "services" / "ai_agent.py").read_text(encoding="utf-8")
    assert "if complexity < 6:" in source
    assert "if complexity < 6 and retries < max_retries:" not in source


def test_new_simulator_fit_measures_full_content_and_centers_after_scaling():
    html = "<!doctype html><html><body><main style='height:900px'>Simulador</main></body></html>"
    fitted = _wrap_interactive_fullbleed(html)
    assert "__scormify_fit_v3" in fitted
    assert "st.querySelectorAll('*')" in fitted
    assert "r.bottom-sr.top" in fitted
    assert "translate('+tx+'px,'+ty+'px) scale(" in fitted
    assert "display:block!important" in fitted


def test_legacy_stage_is_upgraded_without_recreating_the_simulator():
    legacy = "<!doctype html><html><body><div id='__stage'>Conteudo salvo</div></body></html>"
    upgraded = _wrap_interactive_fullbleed(legacy)
    assert upgraded.count("id='__stage'") == 1
    assert "__scormify_fit_v3" in upgraded
    assert "st.style.position='absolute'" in upgraded


def test_v2_stage_is_upgraded_to_descendant_bounds_fit():
    legacy = "<!doctype html><html><body><div id='__stage'>Antigo</div><style id='__scormify_fit_v2'></style></body></html>"
    upgraded = _wrap_interactive_fullbleed(legacy)
    assert "__scormify_fit_v3" in upgraded
    assert "querySelectorAll('*')" in upgraded


def test_timeline_quality_requires_milestones_navigation_and_details():
    basic = "<!doctype html><html><body><h1>Historia</h1><script>const ready=true;</script></body></html>"
    events = "".join(
        f"<button class='timeline-item milestone' data-event='{i}'>Marco {i}</button>"
        for i in range(1, 6)
    )
    rich = f"""<!doctype html><html><body>{events}<div id='details'>Detalhes, contexto e impacto</div>
    <button onclick='previous()'>Anterior</button><button onclick='next()'>Proximo</button>
    <div class='progress active selected'>Progresso</div>
    <script>function showEvent(i){{document.body.dataset.active=i;}}
    function next(){{showEvent(2)}} function previous(){{showEvent(1)}}
    document.querySelectorAll('.milestone').forEach(x=>x.addEventListener('click',()=>showEvent(x.dataset.event)));
    </script>{'Descricao historica detalhada com causas e consequencias. ' * 20}</body></html>"""
    assert _timeline_complexity_score(basic) < 6
    assert _timeline_complexity_score(rich) >= 6


def test_case_study_quality_requires_evidence_decisions_and_debrief():
    basic = "<!doctype html><html><body><h1>Caso</h1><p>Leia o caso.</p><script>const ready=true;</script></body></html>"
    questions = "".join(
        f"<button class='question reflection' onclick='toggle({i})'>Pergunta de reflexao {i}</button>"
        for i in range(1, 4)
    )
    rich = f"""<!doctype html><html><body><h1>Estudo de caso</h1>
    <p>Contexto, dados, evidencias, indicadores 42% e metricas do resultado.</p>{questions}
    <p>Escolha uma decisao entre alternativas e avalie trade-off, impacto e consequencia.</p>
    <section id='debrief'>Debrief, analise final e licoes aprendidas.</section>
    <button onclick='reveal()'>Revelar analise</button>
    <script>function toggle(i){{document.body.dataset.question=i;}}
    function reveal(){{document.getElementById('debrief').classList.toggle('active');}}
    </script>{'Evidencia contextual e explicacao pedagogica aprofundada. ' * 25}</body></html>"""
    assert _case_study_complexity_score(basic) < 6
    assert _case_study_complexity_score(rich) >= 6
