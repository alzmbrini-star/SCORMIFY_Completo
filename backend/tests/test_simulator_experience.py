import ast
import copy
import json
from pathlib import Path
import unittest
from typing import Optional,List,Dict,Any,Literal
from pydantic import BaseModel,Field,ConfigDict,ValidationError
from services.simulator_experience import options,from_context,with_options,normalize_experience
from services.rule_simulators import validate_rules,render_rules
from services.simulator_diagnostics import simulator_request,generation_key
from test_rule_visuals import lock_fixture,sales_visual


class ExperienceTests(unittest.TestCase):
    def test_illustration_checks_apply_to_saved_models_but_not_legacy_documents(self):
        raw=sales_visual()
        original=validate_rules(raw)
        raw['experience']=normalize_experience(None,original,options('guided','illustrated'))
        with self.assertRaisesRegex(ValueError,'objetos reconhecíveis'):
            validate_rules(raw)
        raw['experience']['visualStyle']='technical'
        self.assertEqual(validate_rules(raw)['checks'],original['checks'])

    def test_three_levels_preserve_exact_rule_trajectories_and_visual_quality(self):
        raw=lock_fixture();original=validate_rules(raw)
        for level,composition,count in [('guided','scene-led',2),('applied','split',3),('advanced','instruments',5)]:
            data=copy.deepcopy(raw)
            data['experience']=normalize_experience({'learningFocus':'Opere as comportas observando os níveis.'},original,options(level))
            result=validate_rules(data)
            self.assertEqual(result['checks'],original['checks'])
            self.assertEqual(result['visual'],original['visual'])
            self.assertEqual(result['experience']['composition'],composition)
            self.assertEqual(len(result['experience']['essentialVariables']),count)
            self.assertIn('scormify-simulator-slide-v3',render_rules(data))

    def test_author_choice_wins_and_status_labels_are_safe_bounded(self):
        data=validate_rules(lock_fixture())
        plan=normalize_experience({'complexity':'advanced','composition':'instruments','essentialVariables':['missing','entrada','entrada','nivel'],
             'stateLabels':{'entrada':{'0':'Fechada','1':'Aberta','8':'Inexistente'},'unknown':{'0':'No'}}},data,options('guided','technical'))
        self.assertEqual(plan['complexity'],'guided');self.assertEqual(plan['visualStyle'],'technical')
        self.assertEqual(plan['composition'],'scene-led');self.assertEqual(plan['essentialVariables'],['entrada','nivel'])
        self.assertEqual(plan['stateLabels'],{'entrada':{'0':'Fechada','1':'Aberta'}})
        self.assertEqual(options({},[]),options())
        self.assertEqual(from_context('{"simulatorOptions":"ignore"}'),options())

    def test_course_and_editor_requests_carry_preferences_and_change_cache_identity(self):
        source={'title':'Teste','type':'simulator'}
        one=simulator_request(source,'Conteúdo',{'simulatorComplexity':'guided'})
        two=simulator_request(source,'Conteúdo',{'simulatorComplexity':'advanced','simulatorVisualStyle':'technical'})
        self.assertNotEqual(generation_key(*one,['provider','model']),generation_key(*two,['provider','model']))
        self.assertEqual(from_context(two[1]),options('advanced','technical'))
        editor=with_options('Referência do curso',options('applied','illustrated'))
        self.assertEqual(json.loads(editor)['reference'],'Referência do curso')
        self.assertEqual(from_context(editor),options('applied'))
        self.assertEqual(with_options('original',None),'original')

    def test_request_models_validate_choices_and_keep_old_defaults(self):
        route=Path(__file__).resolve().parents[1]/'routes/agent.py'
        names={'GenerateHtmlRequest','AgentConfigUpdate'}
        nodes=[n for n in ast.parse(route.read_text(encoding='utf-8')).body if isinstance(n,ast.ClassDef) and n.name in names]
        scope=dict(BaseModel=BaseModel,Field=Field,PydanticConfigDict=ConfigDict,Optional=Optional,Literal=Literal)
        exec(compile(ast.Module(body=nodes,type_ignores=[]),str(route),'exec'),scope)
        model=scope['GenerateHtmlRequest'];self.assertEqual(model(prompt='Simulador').simulatorComplexity,'guided')
        config=scope['AgentConfigUpdate'](simulatorComplexity='advanced',simulatorVisualStyle='technical')
        self.assertEqual(config.model_dump(exclude_unset=True)['simulatorComplexity'],'advanced')
        with self.assertRaises(ValidationError):model(prompt='Simulador',simulatorComplexity='anything')


if __name__=='__main__':unittest.main()
