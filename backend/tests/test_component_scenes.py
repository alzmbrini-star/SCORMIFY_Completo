import copy,json,re,unittest
from services.component_catalog import catalog
from services.component_scenes import compile_project
from services.rule_simulators import validate_rules,render_rules,trace_rules
from services.rule_visuals import visual_state
from test_rule_visuals import lock_fixture


def component_fixture(style='blueprint'):
    raw=lock_fixture();raw.pop('visual')
    raw['title']='Bancada de componentes — prova de conceito'
    raw['experience']={'complexity':'advanced','visualStyle':'technical'}
    def source(var,lo,hi):return {'var':var,'range':[lo,hi]}
    def instance(key,kind,x,y,inputs,actions=None):
        return {'id':key,'component':kind,'version':1,'label':{'chamber':'Câmara de água','entry':'Comporta de entrada','boat':'Embarcação','alarm':'Sinal de risco'}[key],
                'position':{'x':x,'y':y},'inputs':inputs,'actions':actions or {}}
    raw['visualProject']={'version':1,'catalogVersion':1,'renderer':'svg-v1','style':style,
        'title':'Bancada de componentes reativos',
        'description':'Prova de conceito de componentes sobre as mesmas regras da eclusa. A bancada isola as peças; não representa a geografia completa nem dimensões físicas.',
        'instances':[
            instance('chamber','liquid_vessel',40 if style=='blueprint' else 500,120,{'level':source('nivel',0,2)}),
            instance('entry','lift_gate',350,120,{'opening':source('entrada',0,1)},{'activate':'abrir_entrada'}),
            instance('boat','floating_carrier',490 if style=='blueprint' else 40,120,{'position':source('barco',0,2),'elevation':source('nivel',0,2)}),
            instance('alarm','status_marker',650,20,{'severity':source('risco',0,1)})],
        'teaching':{'focus':'Compare a superfície do líquido, a passagem e a posição da embarcação.',
            'readScene':'A bancada isola três componentes. O recipiente acompanha o nível, a comporta acompanha a abertura e a embarcação acompanha posição e elevação. O sinal indica a condição de risco declarada. Use a comporta ou os botões alternativos. É uma representação esquemática, não um modelo de engenharia.',
            'links':[
                {'instance':'chamber','input':'level','whatChanges':'A superfície sobe ou desce com o nível da câmara.','whyItMatters':'Permite observar a mudança de nível, não apenas o número.'},
                {'instance':'entry','input':'opening','whatChanges':'A lâmina libera ou fecha a passagem.','whyItMatters':'A abertura passa a ser uma condição visível.'},
                {'instance':'boat','input':'position','whatChanges':'A embarcação muda de posição horizontal.','whyItMatters':'A posição acompanha o estágio real da travessia.'},
                {'instance':'alarm','input':'severity','whatChanges':'O sinal aumenta conforme a condição de risco.','whyItMatters':'O alerta distingue a trajetória insegura sem fingir uma medição física.'}]}}
    return raw


class ComponentSceneTests(unittest.TestCase):
    def test_two_presentations_preserve_every_rule_and_state(self):
        raw=lock_fixture();raw.pop('visual');base=validate_rules(raw)
        visuals=[]
        for style in ('blueprint','studio'):
            candidate=component_fixture(style);before=copy.deepcopy(candidate)
            data=validate_rules(candidate);self.assertEqual(candidate,before)
            for key in ('variables','actions','goal','failure','scenes','checks','maxSteps'):
                self.assertEqual(data[key],base[key],key)
            initial={v['id']:v['initial'] for v in data['variables']}
            for check in data['checks']:
                self.assertEqual(trace_rules(data,check['actions']),trace_rules(base,check['actions']))
                self.assertNotEqual(visual_state(data['visual'],initial),visual_state(data['visual'],check['expected']))
            visuals.append(data['visual'])
            self.assertEqual(validate_rules(data)['visualProject'],data['visualProject'])
        self.assertNotEqual(visuals[0],visuals[1])

    def test_catalog_is_detached_and_declares_capabilities(self):
        first=catalog();first['components']['lift_gate']['actions'].append('unsafe')
        self.assertEqual(catalog()['components']['lift_gate']['actions'],['activate'])
        self.assertEqual(catalog()['renderer'],'svg-v1')

    def test_project_not_compiled_visual_is_authority(self):
        data=validate_rules(component_fixture());expected=copy.deepcopy(data['visual'])
        data['visual']['nodes'][0]['attrs']['onload']='alert(1)'
        result=validate_rules(data)
        self.assertEqual(result['visual'],expected)
        self.assertNotIn('onload',json.dumps(result))

    def test_rejects_code_unknown_references_versions_and_oversized_inputs(self):
        good=component_fixture();logic=copy.deepcopy(good);logic.pop('visualProject');spec=validate_rules(logic)
        for mutate in [lambda p:p.update(script='alert(1)'),lambda p:p.update(version=True),
                       lambda p:p.update(renderer='remote'),lambda p:p.update(catalogVersion=99),
                       lambda p:p['instances'][0].update(component='unknown'),
                       lambda p:p['instances'][0].update(version=2),
                       lambda p:p['instances'][0].update(effects={'nivel':2}),
                       lambda p:p['instances'][0]['inputs']['level'].update(var='missing'),
                       lambda p:p['instances'][0]['inputs']['level'].update(range=[0,0]),
                       lambda p:p['instances'][0]['inputs']['level'].update(range=[0,100]),
                       lambda p:p['instances'][0]['inputs']['level'].update(value=1),
                       lambda p:p['instances'][0]['position'].update(x=float('nan')),
                       lambda p:p['instances'][0]['position'].update(x=790),
                       lambda p:p['instances'][1]['actions'].update(activate='invented'),
                       lambda p:p['instances'][0]['actions'].update(activate='forcar'),
                       lambda p:p['teaching']['links'][0].update(input='missing'),
                       lambda p:p.update(description='x'*25000),
                       lambda p:p.update(instances=p['instances']*2)]:
            with self.subTest(mutate=mutate):
                bad=copy.deepcopy(good['visualProject']);mutate(bad)
                with self.assertRaises(ValueError):compile_project(bad,spec)

    def test_missing_teaching_changes_are_rejected_and_constants_are_bounded(self):
        raw=component_fixture();raw['visualProject']['instances'][0]['inputs']['level']={'value':0,'range':[0,2]}
        with self.assertRaisesRegex(ValueError,'entrada de variável'):validate_rules(raw)
        raw=component_fixture();raw['visualProject']['instances'][2]['inputs']['elevation']={'value':1,'range':[0,2]}
        self.assertIn('visual',validate_rules(raw))
        raw['visualProject']['instances'][2]['inputs']['elevation']['value']=3
        with self.assertRaises(ValueError):validate_rules(raw)

    def test_public_document_roundtrip_and_offline_assets(self):
        document=render_rules(component_fixture())
        data=json.loads(re.search(r'<script[^>]*id="scormify-simulator-plan"[^>]*>(.*?)</script>',document,re.S)[1])
        self.assertIn('visualProject',data);self.assertNotIn('checks',data)
        self.assertEqual(validate_rules(data)['visual'],validate_rules(component_fixture())['visual'])
        self.assertNotIn('<script src=',document)
        self.assertNotIn('fetch(',document)

    def test_single_page_export_keeps_project_and_compiled_scene(self):
        import base64
        from services.single_page_exporter import _render_html_element_inner
        document=render_rules(component_fixture())
        exported=_render_html_element_inner({'type':'html','htmlContent':document,'height':540},'qa','','',0,0)
        encoded=re.search(r'data:text/html;charset=utf-8;base64,([^\"]+)',exported)[1]
        frame=base64.b64decode(encoded).decode()
        self.assertIn('"visualProject"',frame)
        self.assertIn('scormify-simulator-slide-v3',frame)
        data=json.loads(re.search(r'<script[^>]*id="scormify-simulator-plan"[^>]*>(.*?)</script>',frame,re.S)[1])
        self.assertEqual(validate_rules(data)['checks'],validate_rules(component_fixture())['checks'])

    def test_visual_refinement_replaces_only_presentation_not_existing_logic(self):
        import asyncio
        from unittest.mock import patch,AsyncMock
        from services.simulator_visual_refinement import refine_visual
        raw=component_fixture();data=validate_rules(raw);captured={}
        async def draw(spec,*args):captured.update(copy.deepcopy(spec));return data['visual'],''
        with patch('services.llm_config.simulator_generation_config',return_value=('openai','test','test')), \
             patch('services.rule_visuals.generate_visual',new_callable=AsyncMock,side_effect=draw):
            result=asyncio.run(refine_visual(json.dumps(raw),'Trocar apresentação','Contexto'))
        self.assertNotIn('visualProject',captured)
        for key in ('actions','variables','goal','failure','maxSteps','checks'):self.assertEqual(captured[key],data[key])
        self.assertNotIn('"visualProject"',result['html'])


if __name__=='__main__':unittest.main()
