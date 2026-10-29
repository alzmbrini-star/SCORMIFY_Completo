import copy
import unittest
import asyncio
import json
import os
from unittest.mock import patch
from services.simulator_model import calculate,validate_model,inject_model


def fixture():
    return {'inputs':[{'id':key,'label':label,'unit':'pontos didáticos','min':0,'max':100,'initial':20} for key,label in [('tech','Tecnologia'),('team','Equipe')]],
            'outputs':[{'id':'quality','label':'Qualidade','unit':'índice didático','expression':{'op':'add','args':[10,{'op':'mul','args':[.6,{'input':'tech'}]},{'op':'mul','args':[.4,{'input':'team'}]}]},'explanation':'Tecnologia e equipe afetam a qualidade.'},
                       {'id':'cost','label':'Custo','unit':'créditos fictícios','expression':{'op':'add','args':[100,{'op':'mul','args':[2,{'input':'tech'}]},{'input':'team'}]},'explanation':'Investimentos consomem créditos.'}]}


class ModelTests(unittest.TestCase):
    def test_generated_names_are_compiled_and_formula_references_preserved(self):
        raw=fixture()
        raw['inputs'][0]['id']='Alocação Tecnologia (%)'
        raw['inputs'][1]['id']='1-Equipe'
        def replace(expression):
            if not isinstance(expression,dict):return
            if expression.get('input')=='tech':expression['input']='Alocação Tecnologia (%)'
            elif expression.get('input')=='team':expression['input']='1-Equipe'
            for child in expression.get('args',[]):replace(child)
        for output in raw['outputs']:replace(output['expression'])
        raw['outputs'][0]['id']='Qualidade Final'
        model=validate_model(raw)
        state={i['id']:i['initial'] for i in model['inputs']}
        self.assertEqual(calculate(model['outputs'][0]['expression'],state),30)
        self.assertEqual(validate_model(model),model)
        self.assertEqual(model['inputs'][0]['label'],'Tecnologia')

    def test_identity_compilation_avoids_collision_and_rejects_ambiguity(self):
        raw=fixture()
        raw['inputs'][0]['id']='TECH'
        raw['inputs'][1]['id']='input_auto_1'
        for output in raw['outputs']:
            def rename(expression):
                if not isinstance(expression,dict):return
                if expression.get('input')=='tech':expression['input']='TECH'
                elif expression.get('input')=='team':expression['input']='input_auto_1'
                for child in expression.get('args',[]):rename(child)
            rename(output['expression'])
        model=validate_model(raw)
        self.assertNotEqual(model['inputs'][0]['id'],model['inputs'][1]['id'])
        raw=fixture();raw['inputs'][1]['id']='tech'
        with self.assertRaisesRegex(ValueError,r'inputs\[1\].id.*repetido'):validate_model(raw)
        raw=fixture();raw['outputs'][0]['expression']={'input':'missing'}
        with self.assertRaisesRegex(ValueError,r'outputs\[0\].expression.*inexistente'):validate_model(raw)

    def test_inputs_change_quality_and_cost(self):
        model=validate_model(fixture())
        before={i['id']:i['initial'] for i in model['inputs']}
        after=dict(before,tech=80)
        self.assertEqual(calculate(model['outputs'][0]['expression'],before),30)
        self.assertEqual(calculate(model['outputs'][0]['expression'],after),66)
        self.assertGreater(calculate(model['outputs'][1]['expression'],after),calculate(model['outputs'][1]['expression'],before))

    def test_dead_metric_or_control_rejected(self):
        raw=fixture();raw['outputs'][0]['expression']=50
        with self.assertRaisesRegex(ValueError,'Indicador sem impacto'):validate_model(raw)
        raw=fixture()
        for output in raw['outputs']:output['expression']={'input':'tech'}
        with self.assertRaisesRegex(ValueError,'Controle sem consequência'):validate_model(raw)

    def test_invalid_formulas_and_nonfinite_values_rejected(self):
        for expression in ('eval("x")',{'input':'unknown'},{'op':'div','args':[1,0]},{'op':'fetch','args':[1,2]},float('nan')):
            raw=fixture();raw['outputs'][0]['expression']=expression
            with self.subTest(expression=expression),self.assertRaises(ValueError):validate_model(raw)

    def test_injected_kernel_precedes_generated_script_and_cannot_close_script(self):
        raw=fixture();raw['outputs'][0]['explanation']='Não executar </script><script>alert(1)</script>'
        html=inject_model('<html><head></head><body><script>scene()</script></body></html>',raw)
        self.assertLess(html.index('window.ScormifyModel'),html.index('scene()'))
        self.assertNotIn('</script><script>alert(1)',html)
        self.assertIn('data-sim-reset',html)

    def test_resource_generation_uses_validated_model_with_free_scene(self):
        from test_visual_simulators import LOCK_PLAN,custom_document
        from services.visual_simulators import generate_visual_simulator
        plan=copy.deepcopy(LOCK_PLAN)
        plan['learningDesign']['kind']='resources'
        plan['causalModel']=fixture()
        plan['stateDesign']={'representation':'scalars','initialState':'Recursos no ponto inicial do modelo.',
            'derivedIndicators':[{'label':item['label'],'source':'outputs do modelo','calculation':'Expressões do causalModel.'} for item in plan['indicators']],
            'checks':[{'actions':[action],'expected':'Indicadores derivados do modelo.'} for action in ['Ajustar tecnologia','Ajustar equipe','Reiniciar']]}
        document=custom_document(plan['title']).replace('<button id="reset">','<button data-sim-reset id="reset">')
        document=document.replace('</body>','<script>ScormifyModel.subscribe(function(state){document.getElementById("feedback").textContent=String(state.outputs.quality);});document.getElementById("level").oninput=function(e){ScormifyModel.setInput("tech",e.target.value);ScormifyModel.setInput("team",e.target.value);};document.getElementById("reset").onclick=function(){ScormifyModel.reset();};</script></body>')
        class Chat:
            def __init__(self,**kwargs):self.session=kwargs['session_id']
            def with_model(self,*args):return self
            def with_params(self,**kwargs):return self
            async def send_message(self,message):
                if self.session.endswith('-plan'):return json.dumps(plan)
                if self.session.endswith('-scene'):return document
                return json.dumps({'pass':True,'issues':[]})
        with patch.dict(os.environ,{'OPENAI_API_KEY':'test-only','SIMULATOR_AI_PROVIDER':'openai'}),patch('services.visual_simulators.LlmChat',Chat):
            result=asyncio.run(generate_visual_simulator('Gerenciar recursos de um projeto'))
        self.assertIn('data-causal-runtime="1"',result['html'])
        self.assertTrue(result['spec']['causalModel']['verification']['outputSensitivity'])

    def test_resource_planner_cannot_omit_causal_model(self):
        from test_visual_simulators import LOCK_PLAN
        from services.visual_simulators import generate_visual_simulator
        plan=copy.deepcopy(LOCK_PLAN);plan['learningDesign']['kind']='resources'
        class Chat:
            def __init__(self,**kwargs):self.session=kwargs['session_id']
            def with_model(self,*args):return self
            def with_params(self,**kwargs):return self
            async def send_message(self,message):
                if not self.session.endswith('-plan'):raise AssertionError('Invalid plan must not be rendered')
                return json.dumps(plan)
        with patch.dict(os.environ,{'OPENAI_API_KEY':'test-only','SIMULATOR_AI_PROVIDER':'openai'}),patch('services.visual_simulators.LlmChat',Chat):
            with self.assertRaisesRegex(ValueError,'causalModel'):
                asyncio.run(generate_visual_simulator('Gerenciar recursos'))


if __name__=='__main__':unittest.main()
