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

from services.visual_simulators import generate_visual_simulator, render_simulator, validate_spec

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


class VisualSimulatorTests(unittest.TestCase):
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
                return '{}' if FakeChat.calls == 1 else json.dumps(PUMP)
        with patch.dict(os.environ, {'OPENAI_API_KEY':'test-only','SIMULATOR_AI_PROVIDER':'openai'}), patch('services.visual_simulators.LlmChat', FakeChat):
            result = asyncio.run(generate_visual_simulator('Simulador de bomba'))
            self.assertEqual(FakeChat.calls, 2)
            self.assertEqual(result['spec']['template'], 'pump')
            self.assertIn('<svg', result['html'])


if __name__ == '__main__':
    unittest.main()
