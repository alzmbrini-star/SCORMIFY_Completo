import asyncio,copy,json,unittest
from unittest.mock import patch,AsyncMock
from services.rule_simulators import RuleDependencyError,validate_rules,generate_rule_simulator
from services.simulator_diagnostics import editor_attempts,record_attempt
from test_rule_simulators import fixtures,op,ref


def missing_writer():
    raw=fixtures()[0]
    raw['variables'][1]['initial']=3
    for a in raw['actions']:a['effects'].pop('confianca',None)
    raw['actions'][3]['effects']={'acordo':1}
    raw['goal']['when']=op('all',op('ge',ref('descoberta'),2),op('ge',ref('confianca'),3))
    raw['failure']['when']=op('eq',ref('acordo'),1)
    return raw


class DependencyRepair(unittest.TestCase):
    def test_two_references_do_not_mean_two_variables_have_effects(self):
        raw=missing_writer();before=copy.deepcopy(raw)
        with self.assertRaises(RuleDependencyError) as caught:validate_rules(raw)
        details=caught.exception.details
        self.assertEqual(details['directGoalReferences'],['confianca','descoberta'])
        self.assertEqual(details['assignedGoalDependencies'],['descoberta'])
        self.assertEqual(details['goalDependenciesWithoutEffects'],['confianca'])
        self.assertEqual(details['variablesOutsideGoalChain'],['acordo'])
        self.assertEqual(details['actionDependencies'][0]['writes'],['descoberta'])
        self.assertEqual(raw,before)
        self.assertIn('Referências sem efeito nas ações: confianca',str(caught.exception))

    def test_repair_receives_actual_missing_writer_then_validates_every_rule(self):
        messages=[]
        class Chat:
            def __init__(self,**kwargs):pass
            def with_model(self,*args):return self
            def with_params(self,**kwargs):return self
            async def send_message(self,message):
                messages.append(json.loads(message.text))
                return json.dumps(missing_writer() if len(messages)==1 else fixtures()[0])
        with patch('emergentintegrations.llm.chat.LlmChat',Chat),patch(
                'services.rule_visuals.generate_visual',AsyncMock(return_value=(None,''))):
            result=asyncio.run(generate_rule_simulator('Tema arbitrário',json.dumps({'simulatorOptions':{'complexity':'applied'}}),'qa','openai','fake','model'))
        self.assertEqual(len(messages),2)
        self.assertEqual(messages[1]['repairDetails']['goalDependenciesWithoutEffects'],['confianca'])
        self.assertTrue(result['spec']['verification']['solutionVerified'])
        self.assertNotIn('invalid_causal_dependencies',result['html'])

    def test_editor_collects_attempts_privately_and_isolates_concurrent_requests(self):
        async def collect(label):
            record={}
            with editor_attempts(record):
                await asyncio.sleep(0)
                for n in range(5):record_attempt(label+str(n),{'title':label},[],error='Invalid rule')
            return record
        async def both():return await asyncio.gather(collect('first'),collect('second'))
        a,b=asyncio.run(both())
        self.assertEqual(len(a['attempts']),3)
        self.assertEqual([x['document'] for x in a['attempts']],['first2','first3','first4'])
        self.assertTrue(all(x['document'].startswith('second') for x in b['attempts']))
        record_attempt('outside',{},[])
        self.assertEqual(a['attempts'][-1]['document'],'first4')


if __name__=='__main__':unittest.main()
