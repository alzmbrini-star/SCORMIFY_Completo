import copy,unittest
from services.rule_simulators import validate_rules,PROCESS_PROMPT
from services.simulator_experience import normalize_experience,options
from test_process_demo import process_demo


class IllustrativePolicy(unittest.TestCase):
    def test_guided_presentation_metadata_is_not_an_arbitrary_generation_barrier(self):
        raw=process_demo()
        for key in ('subtitle','briefing','courseConnection','debrief'):raw.pop(key)
        for key in ('description','unit'):raw['variables'][0].pop(key)
        for key in ('description','unavailable'):raw['actions'][0].pop(key)
        raw['scenes'][0].pop('facts')
        original=copy.deepcopy(raw);result=validate_rules(raw)
        self.assertEqual(raw,original)
        self.assertEqual(result['scenes'][0]['facts'],[])
        self.assertEqual(result['checks'][0]['actions'],['avancar','avancar'])
        self.assertEqual(validate_rules(result),result)
        self.assertIn('Qualquer'.lower(),PROCESS_PROMPT.lower())

    def test_no_automatic_metrics_or_thematic_routing(self):
        for title in ('Mecanismo mecânico','Ciclo natural','Comunicação entre pessoas','Conceito abstrato novo'):
            raw=process_demo();raw['title']=title;data=validate_rules(raw)
            plan=normalize_experience({},data,options())
            self.assertEqual(plan['composition'],'immersive')
            self.assertEqual(plan['essentialVariables'],[])
            self.assertEqual(plan['environment'],data['briefing'])

    def test_explicitly_helpful_indicator_and_lateral_controls_remain_possible(self):
        data=validate_rules(process_demo())
        plan=normalize_experience({'essentialVariables':['etapa'],'composition':'scene-led'},data,options())
        self.assertEqual(plan['essentialVariables'],['etapa'])
        self.assertEqual(plan['composition'],'scene-led')
        strict=copy.deepcopy(data);strict.pop('didacticMode')
        self.assertEqual(normalize_experience({},strict,options())['composition'],'scene-led')

    def test_relaxed_prose_does_not_accept_wrong_types_or_broken_logic(self):
        for modify in (lambda raw:raw.update(briefing=42),lambda raw:raw['actions'][0]['effects'].update(missing=1),
                       lambda raw:raw['actions'][0].update(requires=False)):
            raw=process_demo();modify(raw)
            with self.assertRaises((ValueError,TypeError)):validate_rules(raw)
        raw=process_demo();raw['mission']='x'*400;raw.pop('subtitle')
        self.assertEqual(len(validate_rules(raw)['subtitle']),240)


if __name__=='__main__':unittest.main()
