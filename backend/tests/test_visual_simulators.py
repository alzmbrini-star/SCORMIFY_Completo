"""Offline regression tests for visual scenarios and safe rendering."""
import asyncio
import ast
import copy
import json
import os
import re
from pathlib import Path
import unittest
from unittest.mock import patch

from services.visual_simulators import generate_visual_simulator, render_simulator, validate_spec, validate_custom_html, validate_custom_plan, render_navigation_lock

BASE = dict(title="Laboratório de decisões", subtitle="Experimente, observe e compare.",
            mission="Compare estratégias para alcançar o objetivo com os recursos disponíveis.",
            briefing="Altere os controles e observe as consequências. Os valores são ilustrativos.",
            debrief="Qual estratégia equilibrou os resultados? Explique o custo de oportunidade.")
PUMP = dict(BASE, template="pump", title="Estação de bombeamento", subtitle="Da captação ao abastecimento: explore o circuito hidráulico.",
            mission="Encha 50 L com vazão de pelo menos 30 L/min e potência de no máximo 1,2 kW.")
RESOURCES = dict(BASE, template="resources", title="Planeje um treinamento eficaz",
    areas=[dict(name=n, description=d) for n, d in [
        ("Prática", "Mais prática fortalece a aplicação, mas reduz a verba para acompanhamento."),
        ("Conteúdo", "Conteúdo amplia a cobertura, mas consome recursos disponíveis para prática."),
        ("Acompanhamento", "Acompanhamento sustenta o progresso, mas exige tempo da equipe.")]],
    metrics=[dict(name=n, weights=w) for n, w in [("Aplicação", [90,30,50]), ("Cobertura", [30,90,40]), ("Continuidade", [40,30,95])]])
DECISIONS = dict(BASE, template="decisions", title="Liderança sob pressão",
    metrics=[dict(name=n) for n in ["Confiança", "Entrega", "Fôlego da equipe"]],
    steps=[dict(title=t, context="O prazo está próximo e a equipe precisa de uma decisão sobre prioridades.", choices=[
        dict(label="Negociar o escopo com o cliente", effects=[10,-5,15], feedback="O prazo fica mais realista, mas parte da entrega será adiada."),
        dict(label="Concentrar a equipe na entrega urgente", effects=[-5,15,-15], feedback="A entrega avança, mas o esforço concentrado aumenta o desgaste."),
        dict(label="Dividir o trabalho com outra equipe", effects=[-5,10,5], feedback="A carga é compartilhada, mas a coordenação inicial reduz a confiança no processo.")])
        for t in ["Um prazo apertado", "Uma demanda inesperada", "O fechamento do projeto"]])

LOCK_PLAN = dict(BASE, title="Operação de eclusa para navegação",
    scene="Barco flutuante dentro da câmara entre comportas de montante e jusante.",
    mechanism="Encher/esvaziar a câmara e abrir as comportas somente após igualar os níveis. Reiniciar restaura o barco a jusante.",
    controls=[dict(label="Encher câmara", action="Aumenta o nível e eleva o barco"),
              dict(label="Comporta de montante", action="Abre se os níveis forem compatíveis"),
              dict(label="Esvaziar câmara", action="Reduz gradualmente o nível")],
    indicators=[dict(label="Nível da câmara", meaning="Altura da água em metros"),
                dict(label="Etapa da travessia", meaning="Posição do barco e bloqueios")])


def custom_document(title):
    return '''<!DOCTYPE html><html lang="pt-BR"><head><meta charset="utf-8"><style>
    body{font-family:system-ui;background:#edf3f8;color:#123;padding:20px}
    main{display:grid;gap:18px;max-width:960px;margin:auto}
    svg{width:100%;background:#163e62;border-radius:16px}
    button{padding:12px;background:#2563eb;color:white;border:0;border-radius:8px}
    label{display:block}input{width:100%}aside{padding:20px;background:white}
    </style></head><body><main><h1>''' + title + '''</h1>
    <p>Experimente as comportas e observe o barco ao equalizar os níveis de água.</p>
    <svg viewBox="0 0 600 300" role="img" aria-label="Barco e comportas">
    <rect x="10" y="150" width="180" height="140" fill="#38bdf8"/>
    <rect x="200" y="180" width="200" height="110" fill="#38bdf8"/>
    <rect x="410" y="100" width="180" height="190" fill="#38bdf8"/>
    <path d="M250 170H340L330 190H260Z" fill="#fff"/>
    <rect x="195" y="40" width="8" height="250" fill="#f59e0b"/>
    <rect x="400" y="40" width="8" height="250" fill="#f59e0b"/>
    <text x="220" y="30" fill="white">Câmara de navegação</text></svg>
    <aside><label for="level">Nível da câmara</label><input id="level" type="range" min="0" max="10" value="3">
    <button id="fill">Encher câmara</button><button id="reset">Reiniciar</button>
    <button id="gate">Comporta de montante</button><button id="drain">Esvaziar câmara</button>
    <p id="feedback" role="status">Equalize os níveis antes de abrir a comporta.</p></aside></main>
    <script>const level=document.getElementById('level');
    document.getElementById('fill').addEventListener('click',()=>{level.value=Number(level.value)+1});
    document.getElementById('reset').addEventListener('click',()=>{level.value=3});
    document.getElementById('gate').addEventListener('click',()=>{document.getElementById('feedback').textContent='Verifique o nível de montante'});
    document.getElementById('drain').addEventListener('click',()=>{level.value=Number(level.value)-1});
    setInterval(()=>{document.getElementById('feedback').textContent='Nível: '+level.value+' m'},1000);
    level.addEventListener('input',()=>{document.getElementById('feedback').textContent='Nível: '+level.value+' m'});
    </script></body></html>'''


class VisualSimulatorTests(unittest.TestCase):
    def test_bespoke_scenario_does_not_select_a_pump_template(self):
        spec = validate_custom_plan(LOCK_PLAN)
        result = validate_custom_html(custom_document(spec['title']), spec)
        self.assertEqual(spec['template'], 'custom')
        self.assertIn('data-simulator-version="3"', result)
        self.assertIn('Câmara de navegação', result)
        self.assertNotIn('tank-water', result)
        self.assertNotIn('Velocidade da bomba', result)

    def test_detailed_operating_briefing_is_preserved(self):
        long_plan = dict(LOCK_PLAN, briefing=LOCK_PLAN['briefing'] * 12)
        self.assertGreater(len(long_plan['briefing']), 500)
        self.assertEqual(validate_custom_plan(long_plan)['briefing'], long_plan['briefing'])

    def test_custom_output_rejects_missing_scene_and_remote_dependencies(self):
        spec = validate_custom_plan(LOCK_PLAN)
        good = custom_document(spec['title'])
        for bad in (good.replace('<svg ', '<div ').replace('</svg>', '</div>'),
                    good.replace('<script>', '<script src="https://example.com/a.js">'),
                    good.replace('<main>', '<main><img src="https://example.com/a.png">'),
                    good.replace('const level=', 'fetch("https://example.com");const level='),
                    good.replace('level.value=3', '// Closing logic if needed\n'),
                    good.replace('<button id="reset">Reiniciar</button>', '').replace("document.getElementById('reset').addEventListener('click',()=>{level.value=3});", ''),
                    good[:-10]):
            with self.assertRaises(ValueError):
                validate_custom_html(bad, spec)

    def test_svg_namespace_does_not_hide_compact_animation_script(self):
        spec = validate_custom_plan(LOCK_PLAN)
        compact = re.sub(r'<script>([\s\S]*?)</script>',
            lambda m: "<script>const ns='http://www.w3.org/2000/svg';" + m[1].replace('\n', '') + '</script>',
            custom_document(spec['title']))
        self.assertIn('setInterval', validate_custom_html(compact, spec))

    def test_accessible_icon_reset_is_accepted(self):
        spec = validate_custom_plan(LOCK_PLAN)
        code = custom_document(spec['title']).replace('<button id="reset">Reiniciar</button>', '<button id="reset" aria-label="Reiniciar">↻</button>')
        self.assertIn('aria-label="Reiniciar"', validate_custom_html(code, spec))

    def test_editor_sanitizer_and_agent_keep_runtime(self):
        from services.ai_agent import _normalize_interactive_storyboard_slide
        # Load the pure sanitizer without requiring the API server dependencies.
        route = Path(__file__).resolve().parents[1] / 'routes' / 'agent.py'
        tree = ast.parse(route.read_text(encoding='utf-8'))
        names = {'_HTML_FENCE_RE', '_UNSAFE_HTML_PATTERNS', '_UNSAFE_JS_TOKEN_RE'}
        nodes = [node for node in tree.body if
            (isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in names for t in node.targets))
            or (isinstance(node, ast.FunctionDef) and node.name == '_clean_generated_interactive_html')]
        scope = {'re': re}
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(route), 'exec'), scope)
        for spec in (PUMP, RESOURCES, DECISIONS):
            rendered = render_simulator(spec)
            self.assertEqual(scope['_clean_generated_interactive_html'](rendered), rendered.strip())
            slide = {'type': 'simulator', 'elements': [{'type': 'html', 'htmlContent': rendered}]}
            self.assertEqual(_normalize_interactive_storyboard_slide(slide)['elements'][0]['htmlContent'], rendered)
        rendered = render_navigation_lock(validate_custom_plan(LOCK_PLAN))['html']
        self.assertEqual(scope['_clean_generated_interactive_html'](rendered), rendered.strip())
        slide = {'type': 'simulator', 'elements': [{'type': 'html', 'htmlContent': rendered}]}
        self.assertEqual(_normalize_interactive_storyboard_slide(slide)['elements'][0]['htmlContent'], rendered)

    def test_templates_are_self_contained_and_keep_data_out_of_code(self):
        for spec in (PUMP, RESOURCES, DECISIONS):
            raw = render_simulator(spec)
            self.assertIn('data-simulator-version="2"', raw)
            self.assertNotIn('__SIMULATOR_SPEC__', raw)
            self.assertNotIn('<script src=', raw)
            self.assertNotIn('fetch(', raw)
        hostile = dict(PUMP, title='</script><img src=x onerror=alert(1)>')
        self.assertNotIn(hostile['title'], render_simulator(hostile))

    def test_rejects_empty_and_dominated_scenarios(self):
        for bad in ({}, dict(PUMP, title=""), dict(PUMP, template="quiz"), dict(DECISIONS, steps=[])):
            with self.assertRaises(ValueError):
                validate_spec(bad)
        bad = copy.deepcopy(RESOURCES)
        for metric in bad['metrics']:
            metric['weights'] = [100,50,0]
        with self.assertRaises(ValueError):
            validate_spec(bad)

    def test_rejects_non_finite_and_consequence_free_decisions(self):
        for effects in ([float('nan'),5,-2], [10,10,10], [True,5,-2]):
            bad = copy.deepcopy(DECISIONS)
            bad['steps'][0]['choices'][0]['effects'] = effects
            with self.assertRaises(ValueError):
                validate_spec(bad)

    def test_provider_and_one_repair_attempt(self):
        class FakeChat:
            calls = 0
            def __init__(self, **kwargs): pass
            def with_model(self, provider, model):
                self.provider = provider
                assert provider == 'openai'
                return self
            def with_params(self, **kwargs): return self
            async def send_message(self, message):
                FakeChat.calls += 1
                if FakeChat.calls == 1: return '{}'
                if FakeChat.calls == 2: return json.dumps(LOCK_PLAN)
                if FakeChat.calls == 4: return json.dumps({'pass': True, 'issues': []})
                return custom_document(LOCK_PLAN['title'])
        with patch.dict(os.environ, {'OPENAI_API_KEY':'test-only','SIMULATOR_AI_PROVIDER':'openai'}), patch('services.visual_simulators.LlmChat', FakeChat):
            result = asyncio.run(generate_visual_simulator('Simulador de operação portuária'))
            self.assertEqual(FakeChat.calls, 4)
            self.assertEqual(result['spec']['template'], 'custom')
            self.assertIn('<svg', result['html'])

    def test_review_requests_correction_before_accepting_output(self):
        class ReviewedChat:
            renders = reviews = 0
            def __init__(self, **kwargs): self.session = kwargs['session_id']
            def with_model(self, *args): return self
            def with_params(self, **kwargs): return self
            async def send_message(self, message):
                if self.session.endswith('-plan'): return json.dumps(LOCK_PLAN)
                if self.session.endswith('-scene'):
                    ReviewedChat.renders += 1
                    return custom_document(LOCK_PLAN['title'])
                ReviewedChat.reviews += 1
                return json.dumps({'pass': ReviewedChat.reviews > 1,
                                   'issues': [] if ReviewedChat.reviews > 1 else ['O barco está abaixo da superfície; alinhe o casco.']})
        with patch.dict(os.environ, {'OPENAI_API_KEY':'test-only','SIMULATOR_AI_PROVIDER':'openai'}), patch('services.visual_simulators.LlmChat', ReviewedChat):
            result = asyncio.run(generate_visual_simulator('Simulador de operação portuária'))
            self.assertEqual(ReviewedChat.renders, 2)
            self.assertEqual(ReviewedChat.reviews, 2)
            self.assertEqual(result['spec']['template'], 'custom')

    def test_navigation_uses_verified_operation_without_regenerating_code(self):
        class PlannerOnly:
            def __init__(self, **kwargs):
                self.session = kwargs['session_id']
                assert self.session.endswith('-plan')
            def with_model(self, *args): return self
            def with_params(self, **kwargs): return self
            async def send_message(self, message): return json.dumps(LOCK_PLAN)
        with patch.dict(os.environ, {'OPENAI_API_KEY':'test-only','SIMULATOR_AI_PROVIDER':'openai'}), patch('services.visual_simulators.LlmChat', PlannerOnly):
            result = asyncio.run(generate_visual_simulator('Gere um simulador de Comportas para níveis para barcos de grande calado'))
            self.assertEqual(result['spec']['mechanic'], 'navigation-lock')
            self.assertIn('hull-shape', result['html'])
            self.assertIn('Reiniciar travessia', result['html'])
            self.assertNotIn('tank-water', result['html'])


if __name__ == '__main__':
    unittest.main()
