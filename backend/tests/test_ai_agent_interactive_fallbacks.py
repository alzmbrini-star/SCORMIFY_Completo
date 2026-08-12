from services.ai_agent import (
    _build_case_study_fallback_html,
    _build_storyboard_batches,
    _build_timeline_fallback_html,
    _interactive_html_is_functional,
    _case_study_complexity_score,
    _required_simulator_mechanic,
    _simulator_complexity_score,
    _simulator_mechanic_is_functional,
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
