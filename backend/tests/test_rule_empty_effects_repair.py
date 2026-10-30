"""Regression topology from the supplied diagnostic; no private course data."""
import asyncio,copy,itertools,json,unittest
from unittest.mock import patch,AsyncMock
from services.rule_simulators import (validate_rules,solve_rules,outcome,predicate_bounds,evaluate,
    RuleDependencyError,RuleEffectsError,generate_rule_simulator)
from test_rule_simulators import fixtures,base,var,action,op,ref
from test_rule_short_solution_repair import three_levels


def diagnosed_plan():
    variables=[var('nivel_agua_1','Nível 1',50,100),var('nivel_agua_2','Nível 2',50,100),
        var('nivel_agua_3','Nível 3',50,100),var('pressao','Pressão',50,100),var('barco_posicao','Posição',1,3)]
    return base('Regressão de operação em três níveis',variables,[
        action('abrir_comporta_1','Abrir passagem 1',op('eq',ref('barco_posicao'),1),{
            'nivel_agua_1':op('sub',ref('nivel_agua_1'),10),'nivel_agua_2':op('add',ref('nivel_agua_2'),10),
            'pressao':op('add',ref('pressao'),5),'barco_posicao':2}),
        action('abrir_comporta_2','Abrir passagem 2',op('eq',ref('barco_posicao'),2),{
            'nivel_agua_2':op('sub',ref('nivel_agua_2'),10),'nivel_agua_3':op('add',ref('nivel_agua_3'),10),
            'pressao':op('add',ref('pressao'),5),'barco_posicao':3}),
        action('equilibrar_pressao','Reduzir pressão',op('gt',ref('pressao'),50),{'pressao':op('sub',ref('pressao'),20)}),
        action('verificar_niveis','Consultar níveis',True,{})],
        op('eq',ref('barco_posicao'),3),op('gt',ref('pressao'),100),['abrir_comporta_1','abrir_comporta_2'],[])


class EmptyEffectsRepair(unittest.TestCase):
    def test_diagnostic_reports_empty_effects_not_nonexistent_ids_and_all_masked_faults(self):
        raw=diagnosed_plan();before=copy.deepcopy(raw)
        with self.assertRaises(RuleDependencyError) as caught:validate_rules(raw)
        error=caught.exception;details=error.details
        self.assertIn('effects vazio',str(error));self.assertNotIn('variáveis não declaradas',str(error))
        self.assertEqual(details['emptyEffectActions'],['verificar_niveis'])
        self.assertEqual(details['impossibleConditions'],['failure'])
        self.assertEqual(details['boundedProof']['success'],['abrir_comporta_1','abrir_comporta_2'])
        self.assertIsNone(details['boundedProof']['failure'])
        self.assertEqual(details['shortSuccess']['observedDecisions'],2)
        self.assertEqual(details['assignedGoalDependencies'],['barco_posicao'])
        self.assertEqual(raw,before)

    def test_unknown_variable_and_wrong_effect_type_are_precise_and_never_dropped(self):
        for effects in ({'inventada':1},[],None):
            raw=fixtures()[0];raw['actions'][0]['effects']=effects
            with self.assertRaises(RuleEffectsError) as caught:validate_rules(raw)
            self.assertEqual(caught.exception.details['field'],'actions.investigar.effects')
            self.assertIn('confianca',caught.exception.details['allowedVariableIds'])
            if isinstance(effects,dict):self.assertEqual(caught.exception.details['unknownVariables'],['inventada'])

    def test_time_limit_and_deadlock_do_not_prove_declared_failure(self):
        raw=fixtures()[0];raw['failure']['when']=False
        self.assertIsNone(solve_rules(raw)['failure'])
        state={v['id']:v['initial'] for v in raw['variables']}
        self.assertEqual(outcome(raw,state,raw['maxSteps']),'failure')  # Recovery behavior unchanged.
        raw['actions'].append(action('consult','Consulta',True,{}))
        self.assertIsNone(solve_rules(raw)['failure'])
        for a in raw['actions']:a['requires']=False
        self.assertEqual(outcome(raw,state,0),'failure');self.assertIsNone(solve_rules(raw)['failure'])

    def test_interval_analysis_is_conservative_for_arithmetic_comparison_and_predicates(self):
        variables=[dict(var('x','X',0,2),min=-2),dict(var('y','Y',0,2),min=-2)]
        numbers=[ref('x'),ref('y'),-3,0,3,op('sub',ref('x'),ref('y')),
            op('mul',ref('x'),ref('y')),op('min',ref('x'),ref('y'),1),op('max',ref('x'),ref('y'),-1)]
        for name,a,b in itertools.product(['eq','ne','lt','le','gt','ge'],numbers,numbers):
            node=op(name,a,b);result=predicate_bounds(node,variables)
            if result is not None:
                for x,y in itertools.product(range(-2,3),repeat=2):self.assertIs(evaluate(node,{'x':x,'y':y}),result)
        self.assertIsNone(predicate_bounds(op('any',op('gt',ref('x'),2),op('eq',ref('y'),1)),variables))
        self.assertFalse(predicate_bounds(op('all',op('gt',ref('x'),2),True),variables))
        self.assertTrue(predicate_bounds(op('not',op('gt',ref('x'),2)),variables))

    def test_one_repair_receives_all_failures_before_visual_generation(self):
        messages=[]
        class Chat:
            def __init__(self,**kwargs):pass
            def with_model(self,*args):return self
            def with_params(self,**kwargs):return self
            async def send_message(self,message):
                messages.append(json.loads(message.text));return json.dumps(diagnosed_plan() if len(messages)==1 else three_levels())
        with patch('emergentintegrations.llm.chat.LlmChat',Chat),patch('services.rule_visuals.generate_visual',AsyncMock(return_value=(None,''))) as draw:
            result=asyncio.run(generate_rule_simulator('Processo em três níveis',json.dumps({'simulatorOptions':{'complexity':'applied'}}),'qa','openai','fake','model'))
        self.assertEqual(len(messages),2);draw.assert_awaited_once()
        details=messages[1]['repairDetails']
        self.assertEqual(details['emptyEffectActions'],['verificar_niveis'])
        self.assertEqual(details['impossibleConditions'],['failure'])
        self.assertEqual(details['shortSuccess']['observedDecisions'],2)
        self.assertTrue(result['spec']['verification']['solutionVerified'])
        self.assertNotIn('boundedProof',result['html'])

    def test_previous_acceptance_cannot_bypass_the_stronger_failure_proof(self):
        from services.simulator_diagnostics import diagnostic_scope,capture_generation,generation_key,VERSION
        raw=fixtures()[0];raw['failure']['when']=False;raw['mechanic']='finite-rules-v1'
        previous={'version':VERSION-1,'generationKey':generation_key('p','c',['provider'],VERSION-1),
            'status':'accepted','plan':{'mechanic':'finite-rules-v1'},'result':{'html':'old','spec':raw}}
        fresh=AsyncMock(return_value={'html':'fresh','spec':{}})
        async def run():
            with diagnostic_scope(lambda record:None,[previous]):return await capture_generation(fresh,'p','c','qa',['provider'])
        result=asyncio.run(run());fresh.assert_awaited_once();self.assertEqual(result['html'],'fresh')


if __name__=='__main__':unittest.main()
