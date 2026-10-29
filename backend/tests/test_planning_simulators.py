import asyncio
import ast
import copy
import json
import os
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, AsyncMock, Mock

from services.planning_simulators import planning_request, validate_planning, solve_planning, render_planning


def fixture(theme='Gestão do Tempo'):
    return {'title':'Planejamento: '+theme,'subtitle':'Organize o trabalho e compare consequências.',
        'mission':'Monte um plano viável com prazos, dependências e capacidade limitada.',
        'briefing':'Dados fictícios para prática. Selecione as tarefas, escolha horários e recursos. Revele o imprevisto antes da análise final.',
        'debrief':'Compare as versões: que decisão reduziu os atrasos e os conflitos?',
        'courseConnection':'Aplicar priorização e planejamento ao contexto de '+theme+'.','unit':'horas','horizon':16,
        'resources':[{'id':'equipe','label':'Equipe do caso','capacity':1},{'id':'apoio','label':'Apoio','capacity':1}],
        'tasks':[
            {'id':'t1','label':'Diagnóstico de '+theme,'description':'Identifique as necessidades do caso.','duration':2,'due':5,'priority':3,'resourceId':'equipe','allowedResources':['equipe'],'dependencies':[]},
            {'id':'t2','label':'Preparação','description':'Prepare os insumos após o diagnóstico.','duration':3,'due':11,'priority':2,'resourceId':'equipe','allowedResources':['equipe','apoio'],'dependencies':['t1']},
            {'id':'t3','label':'Verificação','description':'Confira as informações com o recurso de apoio.','duration':2,'due':10,'priority':1,'resourceId':'apoio','allowedResources':['apoio'],'dependencies':[]},
            {'id':'t4','label':'Entrega revisada','description':'Consolide o trabalho após a preparação.','duration':2,'due':15,'priority':3,'resourceId':'equipe','allowedResources':['equipe'],'dependencies':['t2']}],
        'event':{'title':'Indisponibilidade parcial','message':'Uma demanda imprevista ocupa a equipe por duas horas. Reorganize as tarefas.','resourceId':'equipe','start':3,'duration':2}}


class PlanningTests(unittest.TestCase):
    def test_capability_is_selected_by_mechanic_not_subject(self):
        for text in ['Simulador: Montando Seu Cronograma','Crie um cronograma de manutenção industrial','Organizar as tarefas da equipe','Planning scheduling workshop']:
            self.assertTrue(planning_request(text),text)
        self.assertTrue(planning_request(json.dumps({'title':'Meu cronograma','purpose':'Montar o planejamento'})))
        for text in ['Simule uma negociação SPIN','Simule vendas, sem cronograma','Cronômetro','Operar uma bomba hidráulica',json.dumps({'title':'Dar feedback','courseTitle':'Gestão do Tempo com Cronogramas'})]:
            self.assertFalse(planning_request(text),text)

    def test_same_operations_accept_different_themes_and_have_feasible_witness(self):
        for theme in ['Gestão do Tempo','Manutenção Industrial','Produção de Conteúdo','Organização de Eventos']:
            data=validate_planning(fixture(theme))
            solution=solve_planning(data)
            self.assertEqual(len(solution),4)
            self.assertTrue(data['verification']['feasibleWithEvent'])
            self.assertIn(theme,data['courseConnection'])
            for task in data['tasks']:
                slot=solution[task['id']]
                self.assertLessEqual(slot['start']+slot['duration'],task['due'])
                for dependency in task['dependencies']:
                    before=solution[dependency]
                    self.assertGreaterEqual(slot['start'],before['start']+before['duration'])

    def test_impossible_cycle_missing_reference_and_boolean_numbers_are_rejected(self):
        for mutate in [lambda p:p['tasks'][0].update(dependencies=['t4']),
                       lambda p:p['tasks'][0].update(dependencies=['unknown']),
                       lambda p:p['tasks'][0].update(duration=True),
                       lambda p:p['resources'][0].update(capacity=0),
                       lambda p:p['tasks'][0].update(allowedResources=['unknown'])]:
            data=fixture();mutate(data)
            with self.assertRaises(ValueError):validate_planning(data)
        data=fixture()
        for task in data['tasks']:
            task.update(duration=4,due=4,dependencies=[])
        data['tasks'][2]['dependencies']=['t1'];data['tasks'][3]['dependencies']=['t2']
        with self.assertRaisesRegex(ValueError,'solução'):validate_planning(data)

    def test_render_is_offline_safe_and_does_not_embed_the_solver_answer(self):
        data=fixture();data['title']='</script><img src=x onerror=alert(1)>'
        html=render_planning(data)
        self.assertIn('entity-planning-v1',html)
        self.assertNotIn('</script><img src=x',html)
        self.assertNotIn('__PLANNING_',html)
        self.assertNotIn('"solution"',html)
        self.assertNotIn('localStorage',html)
        self.assertNotIn('fetch(',html)
        data['title']='__PLANNING_ENGINE__'
        html=render_planning(data)
        embedded=html.split('type="application/json">',1)[1].split('</script>',1)[0]
        self.assertEqual(json.loads(embedded)['title'],'__PLANNING_ENGINE__')
        self.assertEqual(html.count('function createPlanningEngine('),1)

    def test_decorative_interruption_and_premature_success_text_are_rejected(self):
        data=fixture();data['event'].update(resourceId='apoio',start=14,duration=2)
        with self.assertRaisesRegex(ValueError,'imprevisto não pode afetar'):
            validate_planning(data)
        data=fixture();data['debrief']='Parabéns! Você concluiu com sucesso.'
        with self.assertRaisesRegex(ValueError,'reflexivo e neutro'):
            validate_planning(data)

    def test_legacy_planning_generator_requests_only_data(self):
        from services.visual_simulators import _generate_legacy_visual_simulator as generate_visual_simulator
        class Chat:
            sessions=[]
            def __init__(self,**kwargs):Chat.sessions.append(kwargs['session_id'])
            def with_model(self,*args):return self
            def with_params(self,**kwargs):return self
            async def send_message(self,message):return json.dumps(fixture())
        with patch.dict(os.environ,{'OPENAI_API_KEY':'test-only','SIMULATOR_AI_PROVIDER':'openai'}),patch('emergentintegrations.llm.chat.LlmChat',Chat):
            result=asyncio.run(generate_visual_simulator('Monte um cronograma de trabalho','Gestão do Tempo','case'))
        self.assertEqual(Chat.sessions,['case-planning-data'])
        self.assertEqual(result['spec']['mechanic'],'entity-planning-v1')
        self.assertIn('createPlanningEngine',result['html'])

    def test_editor_preserves_safe_topic_text_mentioning_browser_api_names(self):
        from services.planning_simulators import render_planning
        import re, uuid
        source=Path(__file__).resolve().parents[1]/'routes/agent.py'
        node=next(node for node in ast.parse(source.read_text(encoding='utf-8')).body if isinstance(node,ast.AsyncFunctionDef) and node.name=='generate_html_with_ai')
        node.decorator_list=[]
        ns={'GenerateHtmlRequest':SimpleNamespace,'Depends':lambda value:None,'require_auth':None,
            '_html_generation_credentials':lambda:('test','test'),'re':re,'uuid':uuid,
            '_clean_generated_interactive_html':Mock(side_effect=AssertionError('Trusted data must not be scanned as code')),
            'HTTPException':Exception,'logger':Mock()}
        exec(compile(ast.Module(body=[node],type_ignores=[]),str(source),'exec'),ns)
        data=fixture('Programação: fetch e localStorage')
        html=render_planning(data)
        generated={'html':html,'spec':dict(data,mechanic='entity-planning-v1')}
        with patch.dict(os.environ,{'OPENAI_API_KEY':'test-only','SIMULATOR_AI_PROVIDER':'openai'}),patch('services.visual_simulators.generate_visual_simulator',AsyncMock(return_value=generated)):
            result=asyncio.run(ns['generate_html_with_ai'](SimpleNamespace(prompt='Simulador de cronograma',courseContext='Programação'),{}))
        self.assertEqual(result['html'],html)
        ns['_clean_generated_interactive_html'].assert_not_called()


if __name__=='__main__':unittest.main()
