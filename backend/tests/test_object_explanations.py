import copy,unittest
from services.rule_visuals import validate_visual
from services.rule_simulators import validate_rules
from test_process_demo import process_demo
from test_visual_fidelity import scene

class ObjectExplanations(unittest.TestCase):
    def test_explanation_is_optional_bounded_and_never_changes_rules(self):
        raw=scene(True);raw['nodes'][0]['explanation']='Uma peça que recebe movimento.'
        before=copy.deepcopy(raw);result=validate_visual(raw,validate_rules(process_demo()))
        self.assertEqual(result['nodes'][0]['explanation'],raw['nodes'][0]['explanation']);self.assertEqual(raw,before)
        raw['nodes'][0]['explanation']='';self.assertNotIn('explanation',validate_visual(raw,validate_rules(process_demo()))['nodes'][0])
        raw['nodes'][0]['explanation']='x'*400;self.assertEqual(len(validate_visual(raw,validate_rules(process_demo()))['nodes'][0]['explanation']),350)

if __name__=='__main__':unittest.main()
