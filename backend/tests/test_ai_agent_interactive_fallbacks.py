from services.ai_agent import (
    _build_case_study_fallback_html,
    _build_storyboard_batches,
    _build_timeline_fallback_html,
    _interactive_html_is_functional,
    _case_study_complexity_score,
    _simulator_complexity_score,
    _timeline_complexity_score,
)


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
        {"id": "c", "type": "content"},
        {"id": "case", "type": "case_study"},
    ]
    batches = _build_storyboard_batches(slides, regular_batch_size=4)
    assert [[slide["id"] for slide in batch] for batch in batches] == [
        ["a", "b"], ["sim"], ["c"], ["case"]
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
    """ + ("// consequence model and conditional phase logic\n" * 60) + "</script></body></html>"
    assert _simulator_complexity_score(basic) < 6
    assert _simulator_complexity_score(rich) >= 6


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
