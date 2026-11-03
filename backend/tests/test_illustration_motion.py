import copy,unittest
from services.illustration_motion import validate_motions
from services.rule_visuals import validate_visual
from services.rule_simulators import validate_rules
from test_process_demo import process_demo
from test_visual_fidelity import scene

def motion():return dict(node='part_0',kind='orbit',cx=400,cy=225,dx=100,dy=60,cycles=1,phase=0)

class IllustrationMotion(unittest.TestCase):
    def test_motions_are_generic_detached_and_do_not_require_fake_variable_effects(self):
        raw=scene(True)
        for node in raw['nodes']:node.pop('bindings',None)
        raw['motions']=[motion()];before=copy.deepcopy(raw)
        result=validate_visual(raw,validate_rules(process_demo()))
        self.assertEqual(result['motions'],raw['motions']);self.assertEqual(raw,before)

    def test_bad_references_types_ranges_and_duplicates_are_rejected(self):
        nodes=scene(True)['nodes']
        for change in (dict(node='missing'),dict(kind='eval'),dict(cycles=0),dict(cx=float('nan')),dict(dx=10000),dict(phase='x')):
            value=motion();value.update(change)
            with self.assertRaises(ValueError):validate_motions([value],nodes)
        with self.assertRaises(ValueError):validate_motions([motion(),motion()],nodes)

    def test_challenge_engine_does_not_silently_become_a_movie(self):
        raw=scene(True);raw['motions']=[motion()]
        data=validate_rules(process_demo());data.pop('didacticMode')
        with self.assertRaisesRegex(ValueError,'modo demonstração'):validate_visual(raw,data)

if __name__=='__main__':unittest.main()
