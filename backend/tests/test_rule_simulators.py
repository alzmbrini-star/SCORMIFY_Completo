import asyncio
import ast
import copy
import json
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

from services.rule_simulators import (ENGINE, evaluate, expression, outcome,
    render_rules, solve_rules, transition, trace_rules, validate_rules, single_action_shortcuts)


def ref(key): return {'var':key}
def op(name,*args): return {'op':name,'args':list(args)}
def var(key,label,initial=0,high=5,unit='pontos'):
    return {'id':key,'label':label,'description':'Estado observado: '+label,
            'min':0,'max':high,'initial':initial,'unit':unit}
def action(key,label,guard,effects):
    return {'id':key,'label':label,'description':'Experimente esta intervenção e observe seus custos e consequências.',
            'requires':guard,'unavailable':'A condição desta intervenção ainda não está satisfeita.',
            'effects':effects,'feedback':'A decisão modifica os indicadores e as possibilidades seguintes conforme as regras do caso.'}
def base(title,variables,actions,goal,failure,success_path,bad_path,layout='workbench'):
    data={'title':title,'subtitle':'Investigue, experimente e compare estratégias.',
        'mission':'Alcance o objetivo preservando as restrições do cenário.',
        'briefing':'Dados fictícios para prática: observe as condições, custos e consequências.',
        'courseConnection':'Aplicar os conceitos do curso ao problema de '+title,
        'debrief':'Que consequências das decisões anteriores determinaram seu resultado?',
        'layout':layout,'maxSteps':8,'variables':variables,'actions':actions,
        'goal':{'when':goal,'message':'As condições do objetivo foram cumpridas neste modelo didático.'},
        'failure':{'when':failure,'message':'As restrições foram violadas. Reflita sobre a estratégia e reinicie.'},
        'scenes':[{'id':'avanco','when':op('gt',ref(variables[0]['id']),variables[0]['initial']),
                   'title':'O cenário mudou','description':'Suas decisões abriram novas possibilidades.',
                   'facts':['Consulte o estado atual antes de decidir.']},
                  {'id':'inicio','when':True,'title':'Situação inicial',
                   'description':'Há mais de uma intervenção disponível e restrições a respeitar.',
                   'facts':['Investigue antes de comprometer recursos.']}], 'checks':[]}
    for path,result in [(success_path,'success'),(bad_path,'failure')]:
        state={v['id']:v['initial'] for v in variables}
        for key in path: state=transition(data,state,next(a for a in actions if a['id']==key))
        data['checks'].append({'actions':path,'outcome':result,'expected':state})
    return data


def fixtures():
    # Four different rule topologies; no change to interpreter or renderer.
    sales=base('Venda consultiva com evidências',
        [var('descoberta','Necessidade compreendida',0,2),var('confianca','Confiança',1,4),var('acordo','Acordo',0,1)],
        [action('investigar','Investigar o problema',op('eq',ref('descoberta'),0),{'descoberta':1,'confianca':2}),
         action('implicar','Explorar a consequência do problema',op('eq',ref('descoberta'),1),{'descoberta':2,'confianca':3}),
         action('negociar','Vincular a solução à necessidade',op('all',op('eq',ref('descoberta'),2),op('ge',ref('confianca'),3)),{'acordo':1}),
         action('pressionar','Pressionar por uma assinatura imediata',True,{'confianca':0})],
        op('all',op('eq',ref('acordo'),1),op('ge',ref('confianca'),3)),op('eq',ref('confianca'),0),
        ['investigar','implicar','negociar'],['pressionar'],'conversation')
    time=base('Planejamento com orçamento de tempo',
        [var('fase','Etapa concluída',0,3),var('tempo','Tempo disponível',6,6,'blocos'),var('qualidade','Qualidade',0,4)],
        [action('planejar','Analisar dependências',op('eq',ref('fase'),0),{'fase':1,'tempo':op('sub',ref('tempo'),1),'qualidade':1}),
         action('executar','Executar o trabalho prioritário',op('eq',ref('fase'),1),{'fase':2,'tempo':op('sub',ref('tempo'),3),'qualidade':2}),
         action('revisar','Revisar a entrega',op('eq',ref('fase'),2),{'fase':3,'tempo':op('sub',ref('tempo'),1),'qualidade':4}),
         action('dispersar','Atender uma interrupção não prioritária',True,{'tempo':op('sub',ref('tempo'),2)})],
        op('all',op('eq',ref('fase'),3),op('ge',ref('qualidade'),4)),op('eq',ref('tempo'),0),
        ['planejar','executar','revisar'],['dispersar','dispersar','dispersar'],'process')
    safety=base('Inspeção e liberação de uma atividade',
        [var('inspecao','Inspeção',0,1),var('protecao','Proteções verificadas',0,1),var('liberacao','Liberação',0,1),var('risco','Risco ilustrativo',1,2)],
        [action('inspecionar','Inspecionar o local',True,{'inspecao':1}),
         action('proteger','Conferir as proteções indicadas no caso',op('eq',ref('inspecao'),1),{'protecao':1,'risco':0}),
         action('liberar','Registrar a liberação',op('all',op('eq',ref('protecao'),1),op('eq',ref('inspecao'),1)),{'liberacao':1}),
         action('ignorar','Prosseguir sem verificação',True,{'risco':2})],
        op('all',op('eq',ref('liberacao'),1),op('eq',ref('risco'),0)),op('eq',ref('risco'),2),
        ['inspecionar','proteger','liberar'],['ignorar'],'process')
    creative=base('Refinamento de um briefing criativo',
        [var('evidencia','Referências analisadas',0,2),var('diversidade','Diversidade das propostas',0,3),var('coerencia','Coerência com o briefing',0,3),var('recurso','Esforço disponível',5,5)],
        [action('observar','Investigar referências contrastantes',op('lt',ref('evidencia'),2),{'evidencia':op('add',ref('evidencia'),1),'recurso':op('sub',ref('recurso'),1)}),
         action('combinar','Combinar perspectivas distintas',op('ge',ref('evidencia'),1),{'diversidade':3,'recurso':op('sub',ref('recurso'),1)}),
         action('criticar','Avaliar as ideias com o briefing',op('ge',ref('diversidade'),2),{'coerencia':3,'recurso':op('sub',ref('recurso'),1)}),
         action('copiar','Repetir uma solução sem analisar o contexto',True,{'recurso':0})],
        op('all',op('ge',ref('coerencia'),3),op('ge',ref('diversidade'),3)),op('eq',ref('recurso'),0),
        ['observar','combinar','criticar'],['copiar'])
    return [sales,time,safety,creative,experiment_fixture()]


def experiment_fixture():
    return base('Experimento de equilíbrio',
        [dict(var('x','Indicador X',0,5),min=-5),dict(var('y','Indicador Y',0,5),min=-5),var('recurso','Recurso',3,3)],
        [action('ajustar_x','Aumentar X com custo em Y',True,{'x':op('add',ref('x'),2),'y':op('sub',ref('y'),1)}),
         action('ajustar_y','Aumentar Y com custo em X',True,{'y':op('add',ref('y'),2),'x':op('sub',ref('x'),1)}),
         action('reforcar','Reforçar X consumindo recurso',True,{'x':op('add',ref('x'),1),'recurso':op('sub',ref('recurso'),1)}),
         action('esgotar','Consumir o recurso restante',True,{'recurso':0})],
        op('all',op('ge',ref('x'),3),op('ge',ref('y'),3)),op('eq',ref('recurso'),0),
        ['ajustar_x','ajustar_y']*3,['esgotar'])


class RuleTests(unittest.TestCase):
    def test_different_mechanics_use_exact_same_interpreter(self):
        for raw in fixtures():
            data=validate_rules(raw);proof=solve_rules(data)
            self.assertTrue(data['verification']['solutionVerified'])
            self.assertGreaterEqual(len(proof['success']),3)
            state={v['id']:v['initial'] for v in data['variables']}
            for key in proof['success']:
                state=transition(data,state,next(a for a in data['actions'] if a['id']==key))
            self.assertEqual(outcome(data,state,len(proof['success'])),'success')

    def test_bounded_search_reports_unknown_not_impossible(self):
        data=fixtures()[0]
        self.assertEqual(solve_rules(data,budget=0)['status'],'budget')
        with self.assertRaisesRegex(ValueError,'orçamento'):validate_rules(data,budget=0)

    def test_deadlocks_and_step_limit_are_recoverable_terminal_outcomes(self):
        data=fixtures()[0]
        state={'descoberta':0,'confianca':1,'acordo':0}
        for action in data['actions']:action['requires']=False
        self.assertEqual(outcome(data,state,0),'failure')
        self.assertEqual(outcome(fixtures()[0],state,8),'failure')

    def test_unreachable_objective_is_not_accepted_as_valid(self):
        data=fixtures()[0]
        data['actions'][2]['effects']['acordo']=0
        proof=solve_rules(data)
        self.assertEqual(proof['status'],'exhausted');self.assertIsNone(proof['success'])

    def test_single_page_and_classic_exports_keep_readable_workspace(self):
        import base64, re
        from services.single_page_exporter import _render_html_element_inner
        document=render_rules(fixtures()[0])
        exported=_render_html_element_inner({'type':'html','htmlContent':document,'height':540},'qa','', '',0,0)
        payload=re.search(r'data:text/html;charset=utf-8;base64,([^\"]+)',exported).group(1)
        frame=base64.b64decode(payload).decode()
        self.assertIn('data-sim-engine="finite-rules-v1"',frame)
        self.assertNotIn('height:100%;overflow:hidden;box-sizing:border-box',frame)
        self.assertIn('createRuleEngine',frame)
        services=Path(__file__).resolve().parents[1]/'services'
        self.assertIn("wrappedHtml.indexOf('data-sim-engine=\"finite-rules-v1\"') === -1",(services/'html_exporter.py').read_text(encoding='utf-8'))
        self.assertIn("wrappedHtml.indexOf('data-sim-engine=\"finite-rules-v1\"') === -1",(services/'export_assets/player.js').read_text(encoding='utf-8'))

    def test_typed_expressions_reject_code_unknown_variables_and_wrong_types(self):
        for expr,boolean in [('state.x++',False),({'var':'missing'},False),(True,False),
            (op('add',True,2),False),(op('eq',1,1),False),(op('add',1,1),True),
            ({'var':'x','evil':'x'},False),(op('__proto__',1,2),False)]:
            with self.assertRaises(ValueError):expression(expr,{'x'},boolean)
        deep=1
        for i in range(10):deep=op('add',deep,1)
        with self.assertRaisesRegex(ValueError,'profundidade'):expression(deep,{'x'})

    def test_minimum_and_maximum_of_multiple_criteria_are_safe_numeric_expressions(self):
        for name,value in [('min',2),('max',8)]:
            node=expression(op(name,ref('x'),ref('y'),ref('z')),{'x','y','z'})
            self.assertEqual(evaluate(node,{'x':5,'y':2,'z':8}),value)
        with self.assertRaises(ValueError):expression(op('min',1,True,2),set())
        with self.assertRaises(ValueError):expression(op('min',*range(11)),set())
        raw=fixtures()[0];raw['actions'][0]['effects']['confianca']=op('sub',1,2,3)
        with self.assertRaisesRegex(ValueError,'actions.investigar.effects.confianca.*sub.*3 argumentos'):
            validate_rules(raw)

    def test_atomic_effects_bounds_and_failure_precedence(self):
        raw=fixtures()[0];state={'descoberta':0,'confianca':1,'acordo':0}
        a=action('swap','Trocar',True,{'descoberta':ref('confianca'),'confianca':ref('descoberta')})
        self.assertEqual(transition(raw,state,a),{'descoberta':1,'confianca':0,'acordo':0})
        a['effects']['descoberta']=100
        self.assertIsNone(transition(raw,state,a));self.assertEqual(state['descoberta'],0)
        self.assertEqual(outcome(raw,{'descoberta':2,'confianca':0,'acordo':1},3),'failure')

    def test_schema_rejects_unreachable_trivial_or_false_tests(self):
        for mutate in [lambda d:d['variables'][0].update(initial=True),
            lambda d:d['actions'][0]['effects'].update(unknown=1),
            lambda d:d['actions'][1].update(id=d['actions'][0]['id']),
            lambda d:d['goal'].update(when=True),
            lambda d:d['actions'][0]['effects'].update(descoberta='eval(1)')]:
            raw=fixtures()[0];mutate(raw)
            with self.assertRaises(ValueError):validate_rules(raw)
        raw=fixtures()[0];raw['goal']['when']=op('all',op('eq',ref('acordo'),1),op('ge',ref('confianca'),4))
        raw['checks'][0]['outcome']='failure'
        with self.assertRaises(ValueError):validate_rules(raw)

    def test_engine_derives_checks_instead_of_trusting_model_arithmetic(self):
        raw=fixtures()[0];raw['checks'][0]['expected']['acordo']=0
        data=validate_rules(raw)
        self.assertEqual(data['verification']['recomputedProposedChecks'],1)
        self.assertEqual(data['checks'][0]['expected']['acordo'],1)
        raw.pop('checks');data=validate_rules(raw)
        self.assertEqual({c['outcome'] for c in data['checks']},{'success','failure'})

    def test_indirect_goal_dependency_is_valid_and_scene_coverage_is_compiled(self):
        raw=fixtures()[0];raw['goal']['when']=op('eq',ref('acordo'),1)
        raw['scenes'].reverse()  # An unconditional scene cannot shadow all others.
        data=validate_rules(raw)
        self.assertTrue(data['verification']['solutionVerified'])
        self.assertIs(data['scenes'][-1]['when'],True)
        raw['scenes']=[s for s in raw['scenes'] if s['when'] is not True]
        raw['scenes'].append({'id':'outro','when':False,'title':'Outra condição','description':'Nunca cobre todos os estados.','facts':['Uma condição específica.']})
        self.assertIs(validate_rules(raw)['scenes'][-1]['when'],True)

    def test_repairs_receive_independent_faults_together(self):
        raw=fixtures()[0]
        raw['goal']['when']=op('ge',ref('acordo'),1)
        raw['failure']['when']=op('lt',ref('acordo'),1)
        for a in raw['actions']:a['requires']=True
        raw['goal']['when']=op('eq',ref('acordo'),1)
        with self.assertRaisesRegex(ValueError,'objetivo só é influenciado.*Estado inicial já é terminal'):
            validate_rules(raw)

    def test_parameter_experiment_can_alternate_two_controls_without_artificial_locks(self):
        data=experiment_fixture()
        spec=validate_rules(data);proof=solve_rules(spec)
        self.assertEqual(len(proof['success']),6)
        self.assertEqual(spec['verification']['stateGuardedActions'],0)
        self.assertEqual(spec['verification']['actionKindsInWitness'],2)
        self.assertEqual(trace_rules(spec,proof['success'])['outcome'],'success')

    def test_generation_policy_detects_click_spam_without_rejecting_two_control_experiments(self):
        for raw in fixtures():
            self.assertEqual(single_action_shortcuts(validate_rules(raw)),[])
        raw=fixtures()[0]
        raw['actions'][0].update(requires=True,effects={
            'descoberta':op('min',2,op('add',ref('descoberta'),1)),
            'confianca':op('min',4,op('add',ref('confianca'),1)),
            'acordo':op('min',1,op('max',0,op('sub',ref('descoberta'),1)))})
        data=validate_rules(raw)
        self.assertTrue(data['verification']['solutionVerified'])
        self.assertEqual(single_action_shortcuts(data)[0]['action'],'investigar')
        self.assertEqual(single_action_shortcuts(data)[0]['count'],3)

    def test_renderer_escapes_untrusted_text_and_omits_answer_traces(self):
        raw=fixtures()[0];raw['title']='</script><img src=x onerror=alert(1)>'
        raw['briefing']='__RULE_ENGINE__ fetch localStorage'
        document=render_rules(raw)
        self.assertNotIn(raw['title'],document)
        payload=json.loads(document.split('type="application/json">')[1].split('</script>')[0])
        self.assertEqual(payload['title'],raw['title']);self.assertNotIn('checks',payload)
        self.assertNotIn('verification',payload);self.assertEqual(payload['briefing'],raw['briefing'])
        self.assertNotIn('eval(',document);self.assertNotIn('new Function',document)

    def test_generator_repairs_data_without_falling_back_to_ai_code(self):
        from services.rule_simulators import generate_rule_simulator
        class Chat:
            calls=0
            def __init__(self,**kwargs):self.system=kwargs['system_message']
            def with_model(self,*args):return self
            def with_params(self,**kwargs):return self
            async def send_message(self,message):
                Chat.calls+=1
                return '<script>bad code</script>' if Chat.calls==1 else json.dumps(fixtures()[3])
        with patch('emergentintegrations.llm.chat.LlmChat',Chat),patch('services.rule_visuals.generate_visual',AsyncMock(return_value=(None,'Diagrama conceitual para este teste'))):
            result=asyncio.run(generate_rule_simulator('Criatividade','Contexto','test','openai','fake','model'))
        self.assertEqual(Chat.calls,2);self.assertEqual(result['spec']['mechanic'],ENGINE)

    def test_canonical_agent_and_editor_path_is_not_routed_by_theme(self):
        from services.visual_simulators import generate_visual_simulator
        for theme in ['Cronograma','Vendas','Segurança','Criatividade']:
            with patch('services.visual_simulators.simulator_generation_config',return_value=('openai','fake','model')),patch(
                'services.rule_simulators.generate_rule_simulator',AsyncMock(return_value={'html':'trusted','spec':{'mechanic':ENGINE}})) as generate:
                result=asyncio.run(generate_visual_simulator(theme,'course','same'))
                generate.assert_awaited_once_with(theme,'course','same','openai','fake','model')
                self.assertEqual(result['spec']['mechanic'],ENGINE)

    def test_editor_keeps_compiled_rules_html_and_topic_text(self):
        import re, uuid
        source=Path(__file__).resolve().parents[1]/'routes/agent.py'
        node=next(n for n in ast.parse(source.read_text(encoding='utf-8')).body if isinstance(n,ast.AsyncFunctionDef) and n.name=='generate_html_with_ai')
        node.decorator_list=[]
        ns={'GenerateHtmlRequest':SimpleNamespace,'Depends':lambda v:None,'require_auth':None,
            '_html_generation_credentials':lambda:('test','test'),'re':re,'uuid':uuid,
            '_clean_generated_interactive_html':Mock(side_effect=AssertionError('Compiled text is not generated code')),
            'HTTPException':Exception,'logger':Mock()}
        exec(compile(ast.Module(body=[node],type_ignores=[]),str(source),'exec'),ns)
        document=render_rules(fixtures()[0]);generated={'html':document,'spec':{'mechanic':ENGINE}}
        with patch.dict(os.environ,{'OPENAI_API_KEY':'test-only','SIMULATOR_AI_PROVIDER':'openai'}),patch('services.visual_simulators.generate_visual_simulator',AsyncMock(return_value=generated)):
            result=asyncio.run(ns['generate_html_with_ai'](SimpleNamespace(prompt='Simulador',courseContext='Programação fetch'),{}))
        self.assertEqual(result['html'],document)


if __name__=='__main__':unittest.main()
