import asyncio,copy,json,unittest
from unittest.mock import patch,AsyncMock
from services.rule_simulators import (ShortSolutionError,validate_rules,generate_rule_simulator,
    solve_rules,trace_rules)
from test_rule_simulators import fixtures,op,ref,action
from test_rule_visuals import lock_fixture


def three_levels():
    raw=lock_fixture()
    # Three discrete water levels, each requiring a real filling intervention.
    raw['actions'][3]['requires']=op('all',raw['actions'][3]['requires'],op('lt',ref('nivel'),2))
    raw['actions'][3]['effects']['nivel']=op('add',ref('nivel'),1)
    raw.pop('visual',None)
    return raw


def shortcut(raw):
    raw=copy.deepcopy(raw)
    target=raw['checks'][0]['expected']
    raw['actions'].append(action('skip_dependencies','Concluir ignorando dependências',True,dict(target)))
    return raw


class ShortSolutionRepair(unittest.TestCase):
    def test_shortcut_returns_executed_evidence_for_different_topics_not_a_theme_template(self):
        for raw in (fixtures()[0],fixtures()[1],three_levels()):
            before=copy.deepcopy(raw)
            with self.assertRaises(ShortSolutionError) as caught:validate_rules(shortcut(raw))
            details=caught.exception.details
            self.assertEqual(details['code'],'shortest_success_too_short')
            self.assertEqual(details['observedDecisions'],1)
            self.assertEqual(details['steps'][0]['action'],'skip_dependencies')
            self.assertTrue(details['goalSatisfied'])
            self.assertEqual(details['steps'][0]['before'],details['initialState'])
            self.assertEqual(raw,before)
            self.assertNotIn('visual',details)

    def test_three_water_levels_and_safe_gate_dependencies_are_representable(self):
        spec=validate_rules(three_levels());proof=solve_rules(spec)
        self.assertEqual(proof['success'].count('elevar'),2)
        self.assertGreaterEqual(len(proof['success']),7)
        self.assertEqual(trace_rules(spec,proof['success'])['outcome'],'success')
        state={v['id']:v['initial'] for v in spec['variables']}
        from services.rule_simulators import transition
        self.assertIsNone(transition(spec,state,next(a for a in spec['actions'] if a['id']=='abrir_saida')))

    def test_two_step_shortcut_is_also_rejected_with_both_transitions(self):
        raw=fixtures()[0]
        raw['actions'][2]['requires']=op('all',op('eq',ref('descoberta'),1),op('ge',ref('confianca'),2))
        raw['actions'][2]['effects']['confianca']=3
        with self.assertRaises(ShortSolutionError) as caught:validate_rules(raw)
        self.assertEqual(caught.exception.details['observedDecisions'],2)
        self.assertEqual([s['action'] for s in caught.exception.details['steps']],['investigar','negociar'])

    def test_generator_repairs_measured_shortcut_and_keeps_history_before_drawing(self):
        good=three_levels();messages=[]
        class Chat:
            def __init__(self,**kwargs):pass
            def with_model(self,*args):return self
            def with_params(self,**kwargs):return self
            async def send_message(self,message):
                messages.append(json.loads(message.text))
                return json.dumps(shortcut(good) if len(messages)<3 else good)
        with patch('emergentintegrations.llm.chat.LlmChat',Chat),patch(
                'services.rule_visuals.generate_visual',AsyncMock(return_value=(None,''))) as draw:
            result=asyncio.run(generate_rule_simulator('Eclusa com 3 níveis',json.dumps({'simulatorOptions':{'complexity':'applied'}}),'qa','openai','fake','model'))
        self.assertEqual(len(messages),3);draw.assert_awaited_once()
        self.assertEqual(messages[1]['repairDetails']['steps'][0]['action'],'skip_dependencies')
        self.assertEqual(len(messages[2]['repairHistory']),2)
        self.assertEqual(messages[2]['request'],'Eclusa com 3 níveis')
        self.assertTrue(result['spec']['verification']['solutionVerified'])
        self.assertTrue(result['spec']['verification']['noSingleActionShortcut'])
        self.assertNotIn('shortest_success_too_short',result['html'])

    def test_exhausted_repairs_do_not_claim_the_feature_is_unsupported_or_accept_bad_plan(self):
        class Chat:
            def __init__(self,**kwargs):pass
            def with_model(self,*args):return self
            def with_params(self,**kwargs):return self
            async def send_message(self,message):return json.dumps(shortcut(three_levels()))
        with patch('emergentintegrations.llm.chat.LlmChat',Chat),patch(
                'services.rule_visuals.generate_visual',AsyncMock()) as draw:
            with self.assertRaisesRegex(ValueError,'plano gerado ainda contém inconsistências') as caught:
                asyncio.run(generate_rule_simulator('Eclusa',json.dumps({'simulatorOptions':{'complexity':'applied'}}),'qa','openai','fake','model'))
        draw.assert_not_awaited();self.assertNotIn('recursos suportados',str(caught.exception))


if __name__=='__main__':unittest.main()
