import asyncio,copy,json,unittest
from unittest.mock import patch,AsyncMock
from services.visual_teaching import validate_scene_plan,validate_teaching,validate_review,generate_teaching_visual,observed_changes,binding_guidance
from services.rule_simulators import validate_rules,render_rules
from services.rule_visuals import validate_visual
from test_rule_visuals import lock_fixture


def teaching_fixture():
    raw=lock_fixture()
    raw['experience']={'complexity':'advanced','visualStyle':'technical'}
    raw['visual']['teaching']={'version':1,'focus':'Observe a equalização antes de abrir as comportas.',
      'readScene':'Compare as superfícies da água e a posição das comportas. Use os objetos acionáveis ou os botões alternativos.',
      'links':[{'node':'agua_camara','var':'nivel','whatChanges':'A superfície da água acompanha o nível da câmara.',
                'whyItMatters':'A diferença entre superfícies ajuda a interpretar a equalização.'},
               {'node':'gate_in','var':'entrada','whatChanges':'A abertura da entrada é representada pela posição da comporta.',
                'whyItMatters':'Observe a passagem antes de movimentar o barco.'}]}
    return raw


def scene_plan():
    return {'setting':'Eclusa com duas bacias e uma câmara.','focus':'Comparar superfícies e comportas.',
      'composition':'Cena operacional predominante e controles à direita.','artDirection':'Esquema técnico com volumes, componentes e rótulos grandes.',
      'mechanisms':[{'var':'nivel','object':'Água da câmara','change':'Altura da superfície','meaning':'Comparar níveis'},
                    {'var':'entrada','object':'Comporta','change':'Abertura da passagem','meaning':'Identificar a condição de entrada'}]}


class TeachingTests(unittest.TestCase):
    def test_visual_samples_include_optional_actions_not_only_solver_witnesses(self):
        from services.visual_teaching import visual_transitions
        data=validate_rules(teaching_fixture());data['checks']=[]
        data['variables'].append({'id':'optional','initial':0,'min':0,'max':1})
        data['actions'].append({'id':'optional_choice','requires':True,'effects':{'optional':1}})
        self.assertIn([0,1],observed_changes(data)['optional']['observedChanges'])
        initial={v['id']:v['initial'] for v in data['variables']}
        from services.rule_simulators import evaluate
        self.assertTrue(all(not evaluate(data['goal']['when'],before) and not evaluate(data['failure']['when'],before)
                            for before,after in visual_transitions(data)))

    def test_art_receives_executed_changes_without_solution_sequences(self):
        data=validate_rules(teaching_fixture());changes=observed_changes(data)
        self.assertIn([0,1],changes['entrada']['observedChanges'])
        self.assertIn([0,2],changes['nivel']['observedChanges'])
        self.assertNotIn('actions',json.dumps(changes))

    def test_composition_repairs_invalid_ids_before_drawing_any_art(self):
        data=validate_rules(teaching_fixture());data.pop('visual')
        bad=scene_plan();bad['mechanisms'][0]['var']='invented'
        responses=[bad,scene_plan(),teaching_fixture()['visual'],{'approved':True,'issues':[],'summary':'Coerente com o modelo.'}]
        messages=[]
        class Chat:
            def __init__(self,**kwargs):pass
            def with_model(self,*args):return self
            def with_params(self,**kwargs):return self
            async def send_message(self,message):messages.append(message.text);return json.dumps(responses[len(messages)-1])
        with patch('emergentintegrations.llm.chat.LlmChat',Chat):
            visual,notice=asyncio.run(generate_teaching_visual(data,'tema','referência','qa','openai','test','test'))
        self.assertFalse(notice);self.assertIn('teaching',visual)
        self.assertIn('availableVariableIds',messages[1]);self.assertIn('repairError',messages[1])

    def test_refinement_revalidates_and_preserves_rules_without_generating_new_logic(self):
        from services.simulator_visual_refinement import refine_visual
        raw=teaching_fixture();expected=validate_rules(raw)
        captured={}
        async def draw_scene(data,*args):
            captured.update(copy.deepcopy(data));return expected['visual'],''
        with patch('services.llm_config.simulator_generation_config',return_value=('openai','test','test')), \
             patch('services.rule_visuals.generate_visual',new_callable=AsyncMock,side_effect=draw_scene) as draw:
            result=asyncio.run(refine_visual(json.dumps(raw),'Refinar','Contexto','advanced','technical'))
        self.assertEqual(draw.await_count,1)
        sent=captured
        self.assertNotIn('visual',sent)
        self.assertEqual(sent['_refinementVisual'],expected['visual'])
        for key in ('variables','actions','goal','failure','checks','maxSteps'):
            self.assertEqual(sent[key],expected[key])
        self.assertIn('scormify-simulator-plan',result['html'])
        with patch('services.rule_visuals.generate_visual',new_callable=AsyncMock) as draw:
            with self.assertRaises(ValueError):asyncio.run(refine_visual('<script>alert(1)</script>','Refinar',''))
            draw.assert_not_awaited()

    def test_failed_refinement_returns_no_replacement_document(self):
        from services.simulator_visual_refinement import refine_visual
        with patch('services.llm_config.simulator_generation_config',return_value=('openai','test','test')), \
             patch('services.rule_visuals.generate_visual',new_callable=AsyncMock,return_value=(None,'Arte não aprovada.')):
            with self.assertRaisesRegex(ValueError,'prévia anterior foram preservadas'):
                asyncio.run(refine_visual(json.dumps(teaching_fixture()),'Refinar',''))

    def test_small_movements_report_all_links_and_repair_hints_without_changing_rules(self):
        data=validate_rules(teaching_fixture());visual=copy.deepcopy(data['visual'])
        for node in visual['nodes']:
            if node['id']=='gate_in':node['bindings'][0]['output']=[200,199]
            if node['id']=='agua_camara':
                for binding in node['bindings']:binding['output']=[100,101]
        with self.assertRaises(ValueError) as error:validate_teaching(teaching_fixture()['visual']['teaching'],visual,data)
        self.assertIn('gate_in',str(error.exception));self.assertIn('agua_camara',str(error.exception))
        before=copy.deepcopy(data);hint=binding_guidance(data,visual)
        gate=next(b for b in hint['candidateBindings'] if b['node']=='gate_in')
        self.assertEqual(gate['minimumOutputSpanForThisInput'],8)
        self.assertLess(gate['smallestStepProjectedDelta'],gate['minimumPerceptibleDelta'])
        self.assertEqual(data,before)

    def test_art_repair_receives_numeric_hints_and_validated_previous_scene(self):
        raw=teaching_fixture();data=validate_rules(raw);data['_refinementVisual']=data.pop('visual')
        bad=copy.deepcopy(raw['visual'])
        next(n for n in bad['nodes'] if n['id']=='gate_in')['bindings'][0]['output']=[200,199]
        responses=[scene_plan(),bad,raw['visual'],{'approved':True,'issues':[],'summary':'Coerente.'}];messages=[]
        class Chat:
            def __init__(self,**kwargs):pass
            def with_model(self,*args):return self
            def with_params(self,**kwargs):return self
            async def send_message(self,message):messages.append(json.loads(message.text));return json.dumps(responses[len(messages)-1])
        with patch('emergentintegrations.llm.chat.LlmChat',Chat):
            visual,notice=asyncio.run(generate_teaching_visual(data,'Refinar','Contexto','qa','openai','fake','test'))
        self.assertFalse(notice);self.assertIn('teaching',visual)
        self.assertEqual(messages[1]['existingScene'],data['_refinementVisual'])
        self.assertNotIn('_refinementVisual',messages[1]['model'])
        hint=next(b for b in messages[2]['bindingGuidance']['candidateBindings'] if b['node']=='gate_in')
        self.assertEqual(hint['minimumOutputSpanForThisInput'],8)

    def test_invalid_previous_art_is_not_forwarded_as_reference(self):
        from services.simulator_visual_refinement import refine_visual
        raw=teaching_fixture();raw['visual']['nodes'][0]['attrs']['onclick']='alert(1)';captured={}
        async def draw(data,*args):captured.update(data);return teaching_fixture()['visual'],''
        with patch('services.llm_config.simulator_generation_config',return_value=('openai','fake','test')),patch('services.rule_visuals.generate_visual',side_effect=draw):
            asyncio.run(refine_visual(json.dumps(raw),'Refinar','Contexto'))
        self.assertNotIn('_refinementVisual',captured)

    def test_reported_four_pixel_pattern_gets_an_eighty_pixel_span_hint(self):
        data={'variables':[{'id':'nivel_agua','min':0,'max':100,'initial':50}]}
        candidate={'nodes':[{'id':'comporta_esquerda','bindings':[{'var':'nivel_agua','property':'x','input':[0,100],'output':[100,60]}]}]}
        transitions=[({'nivel_agua':50},{'nivel_agua':60}),({'nivel_agua':60},{'nivel_agua':70})]
        with patch('services.visual_teaching.visual_transitions',return_value=transitions):
            hint=binding_guidance(data,candidate)['candidateBindings'][0]
        self.assertEqual(hint['smallestStepProjectedDelta'],4)
        self.assertEqual(hint['minimumOutputSpanForThisInput'],80)
        self.assertEqual(candidate['nodes'][0]['bindings'][0]['output'],[100,60])

    def test_teaching_preserves_exact_rules_and_exports_with_the_scene(self):
        original=validate_rules(lock_fixture());compiled=validate_rules(teaching_fixture())
        self.assertEqual(compiled['checks'],original['checks'])
        self.assertEqual(compiled['actions'],original['actions'])
        self.assertEqual(compiled['visual']['teaching']['version'],1)
        self.assertIn('Como interpretar',render_rules(teaching_fixture()))

    def test_plan_requires_existing_distinct_variables_and_bounded_explanations(self):
        data=validate_rules(lock_fixture());plan=scene_plan()
        self.assertEqual(validate_scene_plan(plan,data),plan)
        for change in [lambda p:p['mechanisms'][0].update(var='invented'),lambda p:p['mechanisms'][1].update(var='nivel'),
                       lambda p:p.update(composition='x'*801)]:
            candidate=copy.deepcopy(plan);change(candidate)
            with self.assertRaises(ValueError):validate_scene_plan(candidate,data)

    def test_disconnected_text_only_and_imperceptible_changes_are_rejected(self):
        raw=teaching_fixture();data=validate_rules(lock_fixture())
        for mutate in [lambda r:r['teaching']['links'][0].update(node='valor'),
                       lambda r:r['teaching']['links'][0].update(var='saida'),
                       lambda r:r['teaching']['links'][0].update(node='missing')]:
            candidate=copy.deepcopy(raw['visual']);mutate(candidate)
            with self.assertRaises(ValueError):validate_visual(candidate,data)
        visual=copy.deepcopy(data['visual'])
        for node in visual['nodes']:
            if node['id']=='gate_in':node['bindings'][0]['output']=[200,199]
        with self.assertRaisesRegex(ValueError,'mudança observável'):
            validate_teaching(raw['visual']['teaching'],visual,data)

    def test_review_cannot_invent_nodes_or_approve_known_blockers(self):
        visual=validate_rules(lock_fixture())['visual']
        self.assertTrue(validate_review({'approved':True,'issues':[],'summary':'Relações coerentes com os estados.'},visual)['approved'])
        with self.assertRaises(ValueError):validate_review({'approved':True,'summary':'ok','issues':[{'nodes':['missing'],'problem':'Problema','correction':'Corrigir'}]},visual)
        with self.assertRaises(ValueError):validate_review({'approved':False,'summary':'ok','issues':[]},visual)

    def test_independent_art_repair_does_not_change_or_regenerate_proven_rules(self):
        raw=teaching_fixture();data=validate_rules(raw);data.pop('visual');before=copy.deepcopy(data)
        responses=[scene_plan(),raw['visual'],{'approved':False,'summary':'Corrigir a representação.',
           'issues':[{'nodes':['gate_in'],'problem':'A abertura não está destacada.','correction':'Melhore o contraste do objeto.'}]},
           raw['visual'],{'approved':True,'issues':[],'summary':'Cenário, relações e orientação são coerentes.'}]
        messages=[]
        class Chat:
            def __init__(self,**kwargs):pass
            def with_model(self,*args):return self
            def with_params(self,**kwargs):return self
            async def send_message(self,message):
                messages.append(message.text);return json.dumps(responses[len(messages)-1])
        with patch('emergentintegrations.llm.chat.LlmChat',Chat):
            visual,notice=asyncio.run(generate_teaching_visual(data,'tema','referência','qa','openai','test','test'))
        self.assertFalse(notice);self.assertIn('teaching',visual)
        self.assertEqual(len(messages),5);self.assertIn('Revisão didática da arte',messages[3])
        self.assertEqual(data,before)


if __name__=='__main__':unittest.main()
