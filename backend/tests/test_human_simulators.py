import copy
import json
import os
import unittest
from unittest.mock import patch
from services.human_simulators import validate_dialogue, render_dialogue


def dialogue_fixture():
    return {'profile':{'name':'Marina','role':'Analista','goal':'Entregar com clareza de prioridades',
        'constraint':'Duas demandas urgentes','opening':'Quero conversar sobre os últimos prazos.'},
        'metrics':['Confiança','Clareza','Compromisso'],
        'facts':[{'id':f'f{i}','text':f'Informação descoberta {i}'} for i in range(4)],
        'milestones':[{'title':f'Etapa {i}','factIds':[f'f{i}']} for i in range(3)],
        'turns':[{'title':f'Conversa {i}','openPrompt':f'Posso explicar o contexto {i}.',
            'guardedPrompt':f'Não estou à vontade para explicar o contexto {i}.',
            'choices':[{'label':f'Ação {i}.{q}', 'openResponse':f'Reação aberta {i}.{q}',
                'guardedResponse':f'Reação defensiva {i}.{q}', 'feedback':f'Consequência da estratégia {i}.{q}',
                'quality':q,'effects':[[-15,-5,0],[0,5,2],[15,10,10]][q],
                'reveals':[f'f{min(i,3)}'] if q==2 else (['f0'] if q==1 else []),
                'requiresFact':'f0' if i==1 and q==2 else ''} for q in range(3)]} for i in range(6)]}


def human_plan():
    return {'title':'Feedback corretivo com escuta','mission':'Entenda as causas e combine acompanhamento.',
        'debrief':'Compare a forma de perguntar com as reações e com o acordo alcançado.',
        'subtitle':'Conversa de desenvolvimento','briefing':'Investigue antes de propor uma solução.',
        'scene':'Escritório com colaboradora e líder','mechanism':'A confiança muda as reações e as informações disponíveis.',
        'controls':[{'label':'Escolher resposta','action':'Selecionar uma fala concreta'},
                    {'label':'Reiniciar','action':'Restaurar a conversa'}],
        'indicators':[{'label':'Confiança','meaning':'Disposição para conversar'}, {'label':'Compromisso','meaning':'Acordo alcançado'}],
        'learningDesign':{'kind':'human','audience':'Lideranças','difficulty':'Intermediário: investigar causas e negociar prioridades.',
            'courseConnection':'Feedback baseado em fatos observáveis e acompanhamento.', 'visualHierarchy':'Conversa à esquerda, decisões à direita.',
            'objectives':['Investigar as causas dos atrasos','Combinar acompanhamento verificável'],
            'stages':[{'title':f'Etapa {i}','challenge':f'Investigar aspecto {i}','consequence':f'Atualizar o entendimento {i}'} for i in range(6)],
            'endings':[{'label':'Acordo','condition':'Confiança e compreensão suficientes'},
                       {'label':'Ruptura','condition':'Abordagem acusatória persistente'}]}}


class HumanSimulatorTests(unittest.TestCase):
    def test_history_diagnostics_distinguish_missing_discoveries_and_conditions(self):
        from services.human_simulators import DialogueHistoryError
        broken = dialogue_fixture()
        for turn in broken['turns']:
            for choice in turn['choices']:
                choice['reveals'] = []
                choice['requiresFact'] = ''
        with self.assertRaises(DialogueHistoryError) as caught:
            validate_dialogue(broken, human_plan())
        self.assertEqual(caught.exception.diagnostics['discoverableFactIds'], [])
        self.assertFalse(caught.exception.diagnostics['hasConditionalDecision'])

    def test_union_of_mutually_exclusive_discoveries_is_not_a_viable_history(self):
        from services.human_simulators import DialogueHistoryError
        broken = dialogue_fixture()
        for turn in broken['turns']:
            for choice in turn['choices']:
                choice['reveals'] = []
        for i, choice in enumerate(broken['turns'][0]['choices']): choice['reveals'] = [f'f{i}']
        with self.assertRaises(DialogueHistoryError) as caught:
            validate_dialogue(broken, human_plan())
        self.assertEqual(len(caught.exception.diagnostics['discoverableFactIds']), 3)
        self.assertTrue(caught.exception.diagnostics['hasConditionalDecision'])
        self.assertFalse(caught.exception.diagnostics['hasCompletablePathWithDiscoveriesAndConditionalDecision'])

    def test_history_repair_preserves_facts_and_milestones_and_can_fill_missing_stage(self):
        import asyncio
        from services.visual_simulators import generate_visual_simulator
        plan = human_plan()
        plan['learningDesign']['stages'].append(dict(title='Acompanhar', challenge='Conferir acordo', consequence='Rever plano'))
        original, broken = dialogue_fixture(), dialogue_fixture()
        for turn in broken['turns']:
            for choice in turn['choices']:
                choice['reveals'], choice['requiresFact'] = [], ''
        corrected = original['turns'] + copy.deepcopy(original['turns'][-1:])
        corrected[-1]['title'] = 'Acompanhamento do acordo'
        requests = []
        class Chat:
            def __init__(self, **kwargs): self.session = kwargs['session_id']
            def with_model(self, *args): return self
            def with_params(self, **kwargs): return self
            async def send_message(self, message):
                if self.session.endswith('-plan'): return json.dumps(plan)
                requests.append(json.loads(message.text))
                return json.dumps(broken if len(requests)==1 else {'turns': corrected,
                    'facts':[{'id':'invented','text':'Must not replace facts'}]})
        with patch.dict(os.environ, {'OPENAI_API_KEY':'test-only','SIMULATOR_AI_PROVIDER':'openai'}), patch('services.visual_simulators.LlmChat',Chat):
            result = asyncio.run(generate_visual_simulator('Simulador de feedback', 'Curso: escuta baseada em fatos.'))
        self.assertEqual(len(requests), 2)
        self.assertEqual(requests[1]['requiredTurnCount'], 7)
        self.assertEqual(requests[1]['allowedFacts'], original['facts'])
        self.assertIn('escuta baseada em fatos', requests[1]['courseContext'])
        self.assertIn('Acompanhamento do acordo', result['html'])
        self.assertNotIn('Must not replace facts', result['html'])

    def test_history_repair_budget_does_not_allow_shallow_simulation(self):
        import asyncio
        from services.visual_simulators import generate_visual_simulator
        broken = dialogue_fixture()
        for turn in broken['turns']:
            for choice in turn['choices']: choice['requiresFact'] = ''
        calls = []
        invalid = copy.deepcopy(broken)
        for choice in invalid['turns'][0]['choices']: choice['quality'] = 0
        class Chat:
            def __init__(self, **kwargs): self.session = kwargs['session_id']
            def with_model(self, *args): return self
            def with_params(self, **kwargs): return self
            async def send_message(self, message):
                if self.session.endswith('-plan'): return json.dumps(human_plan())
                calls.append(1)
                return json.dumps(broken if len(calls)==1 else invalid)
        with patch.dict(os.environ, {'OPENAI_API_KEY':'test-only','SIMULATOR_AI_PROVIDER':'openai'}), patch('services.visual_simulators.LlmChat',Chat):
            with self.assertRaisesRegex(ValueError, 'estratégias diferentes'):
                asyncio.run(generate_visual_simulator('Simulador de feedback'))
        self.assertEqual(len(calls), 3)

    def test_compiled_graph_has_executable_paths_and_visible_discoveries_for_all_sizes(self):
        from services.human_simulators import build_history_contract, compile_history_contract
        for turn_count in range(6,11):
            for fact_count in range(4,9):
                with self.subTest(turns=turn_count, facts=fact_count):
                    raw, plan = dialogue_fixture(), human_plan()
                    raw['facts'] = [{'id':f'case_{i}', 'text':f'Descoberta concreta {i}: ' + 'x'*190} for i in range(fact_count)]
                    raw['milestones'] = [{'title':f'Marco {i}','factIds':[f'case_{i}']} for i in range(3)]
                    raw['turns'] += copy.deepcopy(raw['turns'][:turn_count-6])
                    for turn in raw['turns']:
                        for choice in turn['choices']:
                            choice['reveals'],choice['requiresFact'] = ['invalid-from-model'], 'circular'
                    before = copy.deepcopy(raw)
                    contract = build_history_contract(raw, turn_count)
                    compiled = compile_history_contract(raw, contract)
                    validated = validate_dialogue(compiled, plan)
                    self.assertEqual(raw, before, 'Compilation must not mutate source data')
                    acquired = set()
                    for index, turn in enumerate(validated['turns']):
                        best = next(c for c in turn['choices'] if c['quality']==2)
                        self.assertTrue(not best['requiresFact'] or best['requiresFact'] in acquired)
                        self.assertEqual(sum(not c['requiresFact'] for c in turn['choices']), 3 if index==0 else 2)
                        for key in best['reveals']:
                            fact = next(f['text'] for f in raw['facts'] if f['id']==key)
                            self.assertIn(fact, best['openResponse'])
                            self.assertIn(fact, best['guardedResponse'])
                        acquired.update(best['reveals'])
                    self.assertEqual(acquired, {f['id'] for f in raw['facts']})
                    self.assertEqual(compiled['profile'], raw['profile'])
                    self.assertEqual(compiled['milestones'], raw['milestones'])

    def test_contract_compiler_does_not_accept_missing_turns_or_empty_reactions(self):
        from services.human_simulators import build_history_contract, compile_history_contract
        raw = dialogue_fixture(); contract = build_history_contract(raw,6)
        for invalid in ('turns', 'reaction'):
            broken = copy.deepcopy(raw)
            if invalid=='turns': broken['turns'].pop()
            else: broken['turns'][0]['choices'][2]['openResponse'] = ''
            with self.assertRaises(ValueError): compile_history_contract(broken,contract)

    def test_milestone_links_require_exact_existing_fact_ids(self):
        from services.human_simulators import MilestoneLinkError
        for links in ([], ['missing'], [{'id':'f0'}], 'f0', ['Informação descoberta 0']):
            with self.subTest(links=links):
                bad = dialogue_fixture()
                bad['milestones'][1]['factIds'] = links
                with self.assertRaises(MilestoneLinkError) as caught:
                    validate_dialogue(bad, human_plan())
                self.assertEqual(caught.exception.path, 'milestones[1].factIds')
                self.assertEqual(caught.exception.allowed_ids, ['f0','f1','f2','f3'])

    def test_targeted_link_repair_then_missing_stage_completion_preserves_content(self):
        import asyncio
        from services.visual_simulators import generate_visual_simulator
        plan, original = human_plan(), dialogue_fixture()
        plan['learningDesign']['stages'].append(dict(title='Acompanhar', challenge='Verificar acordo', consequence='Rever plano'))
        broken = copy.deepcopy(original)
        broken['milestones'][1]['factIds'] = ['invented-id']
        extra = copy.deepcopy(original['turns'][-1]); extra['title'] = 'Acompanhar o acordo'
        requests = []
        class Chat:
            def __init__(self, **kwargs): self.session = kwargs['session_id']
            def with_model(self, *args): return self
            def with_params(self, **kwargs): return self
            async def send_message(self, message):
                if self.session.endswith('-plan'): return json.dumps(plan)
                requests.append(json.loads(message.text))
                return json.dumps([broken, {'milestones':original['milestones']}, {'turns':[extra]}][len(requests)-1])
        with patch.dict(os.environ, {'OPENAI_API_KEY':'test-only','SIMULATOR_AI_PROVIDER':'openai'}), patch('services.visual_simulators.LlmChat',Chat):
            result = asyncio.run(generate_visual_simulator('Simulador de feedback', 'Curso de feedback com fatos e acompanhamento.'))
        self.assertEqual(len(requests), 3)
        self.assertEqual(requests[1]['invalidPath'], 'milestones[1].factIds')
        self.assertEqual(requests[1]['allowedFactIds'], ['f0','f1','f2','f3'])
        self.assertEqual(requests[1]['existingDialogue']['turns'], original['turns'])
        self.assertEqual(requests[2]['requiredAdditionalTurns'], 1)
        self.assertEqual(requests[2]['existingDialogue']['milestones'], original['milestones'])
        self.assertTrue(all('Curso de feedback' in request['courseContext'] for request in requests))
        self.assertIn('Acompanhar o acordo', result['html'])

    def test_invalid_link_repairs_stay_bounded_and_are_never_silently_accepted(self):
        import asyncio
        from services.visual_simulators import generate_visual_simulator
        broken = dialogue_fixture(); broken['milestones'][0]['factIds'] = ['missing']
        count = []
        class Chat:
            def __init__(self, **kwargs): self.session = kwargs['session_id']
            def with_model(self, *args): return self
            def with_params(self, **kwargs): return self
            async def send_message(self, message):
                if self.session.endswith('-plan'): return json.dumps(human_plan())
                count.append(1)
                return json.dumps(broken if len(count)==1 else {'milestones':broken['milestones']})
        with patch.dict(os.environ, {'OPENAI_API_KEY':'test-only','SIMULATOR_AI_PROVIDER':'openai'}), patch('services.visual_simulators.LlmChat',Chat):
            with self.assertRaisesRegex(ValueError, 'milestones\\[0\\].factIds'):
                asyncio.run(generate_visual_simulator('Simulador de feedback'))
        self.assertEqual(len(count), 3)

    def test_missing_planned_turns_are_completed_without_discarding_valid_dialogue(self):
        import asyncio
        from services.visual_simulators import generate_visual_simulator
        plan = human_plan()
        plan['learningDesign']['stages'] += [dict(title=f'Etapa {i}', challenge=f'Aplicar conceito {i}',
            consequence=f'Verificar acordo {i}') for i in range(6, 8)]
        original = dialogue_fixture()
        additions = copy.deepcopy(original['turns'][-2:])
        for i, turn in enumerate(additions, 6): turn['title'] = f'Etapa {i}'
        calls = []
        class Chat:
            def __init__(self, **kwargs): self.session = kwargs['session_id']
            def with_model(self, *args): return self
            def with_params(self, **kwargs): return self
            async def send_message(self, message):
                if self.session.endswith('-plan'): return json.dumps(plan)
                request = json.loads(message.text)
                calls.append(request)
                if len(calls) == 1: return json.dumps(original)
                return json.dumps({'turns': additions})
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test-only', 'SIMULATOR_AI_PROVIDER': 'openai'}), patch('services.visual_simulators.LlmChat', Chat):
            result = asyncio.run(generate_visual_simulator('Simulador de feedback', 'Curso: escuta e acordo.'))
        self.assertEqual(calls[0]['generationContract']['turnCount'], 8)
        self.assertEqual(calls[1]['requiredAdditionalTurns'], 2)
        self.assertEqual(calls[1]['existingDialogue'], original)
        self.assertEqual(calls[1]['remainingStages'], plan['learningDesign']['stages'][6:])
        self.assertEqual(calls[1]['courseContext'], 'Curso: escuta e acordo.')
        self.assertIn('Etapa 7', result['html'])
        self.assertIn(original['turns'][0]['choices'][0]['label'], result['html'])

    def test_failed_completion_does_not_silently_drop_plan_stages(self):
        import asyncio
        from services.visual_simulators import generate_visual_simulator
        plan = human_plan()
        plan['learningDesign']['stages'] += [dict(title='Acompanhar', challenge='Rever acordo', consequence='Ajustar plano')]
        class Chat:
            def __init__(self, **kwargs): self.session = kwargs['session_id']; self.calls = 0
            def with_model(self, *args): return self
            def with_params(self, **kwargs): return self
            async def send_message(self, message):
                if self.session.endswith('-plan'): return json.dumps(plan)
                self.calls += 1
                return json.dumps(dialogue_fixture() if self.calls == 1 else {'turns': []})
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test-only', 'SIMULATOR_AI_PROVIDER': 'openai'}), patch('services.visual_simulators.LlmChat', Chat):
            with self.assertRaisesRegex(ValueError, '6 turnos para 7 etapas'):
                asyncio.run(generate_visual_simulator('Simulador de feedback'))

    def test_incomplete_and_invalid_completion_still_rejected(self):
        plan = human_plan()
        plan['learningDesign']['stages'] += copy.deepcopy(plan['learningDesign']['stages'][:2])
        with self.assertRaisesRegex(ValueError, '6 turnos para 8 etapas'):
            validate_dialogue(dialogue_fixture(), plan)
        bad = dialogue_fixture()
        bad['turns'] += copy.deepcopy(bad['turns'][:2])
        bad['turns'][-1]['choices'][0]['requiresFact'] = 'nonexistent'
        with self.assertRaisesRegex(ValueError, 'pré-requisito'):
            validate_dialogue(bad, plan)

    def test_state_data_requires_meaningful_consequences_and_history(self):
        self.assertEqual(len(validate_dialogue(dialogue_fixture(),human_plan())['turns']),6)
        for invalid in ('effects','reactions','requires','condition'):
            bad=dialogue_fixture()
            if invalid=='effects':
                for c in bad['turns'][0]['choices']: c['effects']=[10,10,10]
            if invalid=='reactions': bad['turns'][0]['choices'][0]['guardedResponse']=bad['turns'][0]['choices'][0]['openResponse']
            if invalid=='requires': bad['turns'][0]['choices'][0]['requiresFact']='f0'
            if invalid=='condition':
                for t in bad['turns']:
                    for c in t['choices']: c['requiresFact']=''
            with self.assertRaises(ValueError): validate_dialogue(bad,human_plan())

    def test_offline_player_safely_embeds_text_and_preserves_agent_runtime(self):
        from services.ai_agent import _normalize_interactive_storyboard_slide, _wrap_interactive_fullbleed
        spec=human_plan(); data=validate_dialogue(dialogue_fixture(),spec)
        data['profile']['opening']='</script><img src=x onerror=alert(1)>'
        document=render_dialogue(data,spec)
        self.assertNotIn(data['profile']['opening'],document)
        self.assertNotIn('<img ',document)
        self.assertIn('data-human-simulator-version="1"',document)
        self.assertEqual(_wrap_interactive_fullbleed(document),document)
        self.assertEqual(_normalize_interactive_storyboard_slide({'type':'simulator','elements':[{'type':'html','htmlContent':document}]})['elements'][0]['htmlContent'],document)

    def test_human_generation_uses_verified_runtime_without_html_review_loop(self):
        import asyncio
        from services.visual_simulators import generate_visual_simulator
        calls=[]
        class Chat:
            def __init__(self,**kwargs): self.session=kwargs['session_id']
            def with_model(self,*args): return self
            def with_params(self,**kwargs): return self
            async def send_message(self,message):
                calls.append((self.session,message.text))
                if self.session.endswith('-plan'): return json.dumps(human_plan())
                if self.session.endswith('-dialogue'): return json.dumps(dialogue_fixture())
                raise AssertionError('Human simulation must not regenerate unverified HTML')
        with patch.dict(os.environ,{'OPENAI_API_KEY':'test-only','SIMULATOR_AI_PROVIDER':'openai'}), patch('services.visual_simulators.LlmChat',Chat):
            result=asyncio.run(generate_visual_simulator('Simulador de feedback corretivo','Curso: fatos observáveis e escuta.'))
        self.assertEqual(len(calls),2)
        self.assertIn('Curso: fatos observáveis e escuta.',calls[1][1])
        self.assertIn('data-human-simulator-version="1"',result['html'])


if __name__=='__main__': unittest.main()
