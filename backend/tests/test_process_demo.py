import asyncio,json,copy,re,unittest
from unittest.mock import patch,AsyncMock
from services.rule_simulators import validate_rules,render_rules,generate_rule_simulator,PROCESS_DEMO
from services.rule_visuals import validate_visual
from test_rule_simulators import var,action,op,ref


def process_demo():
    return {'didacticMode':PROCESS_DEMO,'title':'Observe o processo','subtitle':'Demonstração qualitativa.',
        'mission':'Observe as três posições.','briefing':'Avance para observar cada etapa.','courseConnection':'Relação com o conteúdo do curso.',
        'debrief':'Compare o início e o final.','layout':'process','maxSteps':3,
        'variables':[var('etapa','Etapa',0,2,'etapas')],
        'actions':[action('avancar','Avançar etapa',op('lt',ref('etapa'),2),{'etapa':op('add',ref('etapa'),1)})],
        'scenes':[{'id':'processo','when':True,'title':'Observe o movimento','description':'A peça acompanha as etapas.',
                   'facts':['Representação ilustrativa, não cálculo de engenharia.']}],
        'goal':{'when':op('eq',ref('etapa'),2),'message':'Demonstração concluída. Você pode reiniciar para observar novamente.'}}


class ProcessDemo(unittest.TestCase):
    def test_one_state_one_control_and_no_failure_are_a_valid_process_not_an_exam(self):
        raw=process_demo();before=copy.deepcopy(raw);data=validate_rules(raw)
        self.assertEqual(raw,before);self.assertEqual(data['failure']['when'],False)
        self.assertEqual(data['checks'][0]['actions'],['avancar','avancar'])
        self.assertEqual(len(data['checks']),1)
        self.assertEqual(validate_rules(data),data)
        document=render_rules(data)
        self.assertIn('DEMONSTRAÇÃO DIDÁTICA',document)
        self.assertIn('sem precis',document)
        self.assertIn('process-demo-v1',document)
        strict=dict(raw);strict.pop('didacticMode')
        with self.assertRaises(ValueError):validate_rules(strict)

    def test_read_only_information_is_preserved_without_a_fake_state_effect(self):
        raw=process_demo();raw['actions'].append(action('ler','Consultar orientação',True,{}))
        data=validate_rules(raw)
        self.assertEqual([a['id'] for a in data['actions']],['avancar'])
        self.assertEqual(len(data['observationNotes']),1)
        self.assertEqual(validate_rules(data)['observationNotes'],data['observationNotes'])
        payload=json.loads(re.search(r'id="scormify-simulator-plan" type="application/json">(.*?)</script>',render_rules(data),re.S)[1])
        self.assertIn('Informações de apoio',payload['briefing'])

    def test_typed_references_reachability_and_initial_state_are_still_checked(self):
        for change in (lambda p:p['actions'][0]['effects'].update(missing=1),
            lambda p:p['actions'][0]['effects'].update(etapa='eval(1)'),
            lambda p:p['actions'][0].update(requires=False),
            lambda p:p['goal'].update(when=True),
            lambda p:p['actions'][0]['effects'].update(etapa=0)):
            raw=process_demo();change(raw)
            with self.assertRaises(ValueError):validate_rules(raw)

    def test_guided_generation_uses_dedicated_process_instructions_without_challenge_gates(self):
        calls=[]
        class Chat:
            def __init__(self,**kwargs):calls.append(kwargs['system_message'])
            def with_model(self,*args):return self
            def with_params(self,**kwargs):return self
            async def send_message(self,message):return json.dumps(process_demo())
        with patch('emergentintegrations.llm.chat.LlmChat',Chat),patch('services.rule_visuals.generate_visual',AsyncMock(return_value=(None,''))):
            result=asyncio.run(generate_rule_simulator('Tema novo','Curso','qa','openai','fake','model'))
        self.assertEqual(len(calls),1);self.assertIn('Não há número mínimo artificial',calls[0])
        self.assertFalse(result['spec']['verification']['noSingleActionShortcut'])
        self.assertTrue(result['spec']['verification']['solutionVerified'])
        self.assertEqual(result['spec']['didacticMode'],PROCESS_DEMO)

    def test_applied_author_choice_cannot_be_overridden_by_model_claiming_demo(self):
        class Chat:
            def __init__(self,**kwargs):pass
            def with_model(self,*args):return self
            def with_params(self,**kwargs):return self
            async def send_message(self,message):return json.dumps(process_demo())
        with patch('emergentintegrations.llm.chat.LlmChat',Chat),patch('services.rule_visuals.generate_visual',AsyncMock()) as draw:
            with self.assertRaises(ValueError):asyncio.run(generate_rule_simulator('Tema',json.dumps({'simulatorOptions':{'complexity':'applied'}}),'qa','openai','fake','model'))
        draw.assert_not_awaited()

    def test_visual_scene_can_illustrate_one_stage_without_inventing_metrics(self):
        spec=validate_rules(process_demo())
        visual={'version':1,'title':'Peça em movimento','description':'Posições qualitativas do processo.',
            'background':'#10243b','nodes':[{'id':'peca','type':'rect','label':'Peça',
                'attrs':{'x':40,'y':100,'width':100,'height':60,'fill':'#f7a744'},
                'bindings':[{'property':'x','var':'etapa','input':[0,2],'output':[40,500]}]}]}
        visual['nodes'] += [{'id':'apoio_'+str(i),'type':'rect','label':'Estrutura de apoio',
            'attrs':{'x':20+i*120,'y':350,'width':100,'height':20,'fill':'#65778a'}} for i in range(5)]
        self.assertEqual(validate_visual(visual,spec)['version'],1)

    def test_demo_mode_survives_offline_export(self):
        import base64
        from services.single_page_exporter import _render_html_element_inner
        exported=_render_html_element_inner({'type':'html','htmlContent':render_rules(process_demo()),'height':540},'qa','','',0,0)
        encoded=re.search(r'data:text/html;charset=utf-8;base64,([^\"]+)',exported)[1]
        frame=base64.b64decode(encoded).decode()
        self.assertIn('process-demo-v1',frame);self.assertIn('process-art-finish',frame)
        self.assertNotIn('scormify-visualization-plan',frame)  # Still interactive, not an animation-only switch.


if __name__=='__main__':unittest.main()
