"""Discrete guided presentation thresholds are independent of any subject."""
import copy,unittest
from services.rule_visuals import validate_visual,visual_state
from services.rule_simulators import validate_rules
from test_process_demo import process_demo
from test_rule_visuals import lock_fixture


def threshold_scene():
    return {'version':1,'title':'Mudança por etapa','description':'Um objeto aparece a partir da etapa final.',
            'background':'#edf4fa','nodes':[{'id':'piece','type':'rect','label':'Objeto observado',
            'attrs':{'x':40,'y':40,'width':120,'height':80,'fill':'#398bd5','opacity':0},
            'bindings':[{'property':'opacity','var':'etapa','input':[2,2],'output':[0,1]}]}]}


class VisualThresholds(unittest.TestCase):
    def test_threshold_not_interpolation_preserves_input_and_is_idempotent(self):
        raw=threshold_scene();before=copy.deepcopy(raw);spec=validate_rules(process_demo())
        scene=validate_visual(raw,spec)
        self.assertEqual(raw,before);self.assertEqual(validate_visual(scene,spec),scene)
        for step,expected in ((0,0),(1,0),(2,1)):
            self.assertEqual(visual_state(scene,{'etapa':step})[0]['attrs']['opacity'],expected)

    def test_threshold_applies_at_and_above_boundary_and_can_decrease(self):
        raw=threshold_scene();raw['nodes'][0]['bindings'][0].update(input=[1,1],output=[1,0])
        scene=validate_visual(raw,validate_rules(process_demo()))
        self.assertEqual([visual_state(scene,{'etapa':s})[0]['attrs']['opacity'] for s in (0,1,2)],[1,0,0])

    def test_inverted_out_of_range_unknown_and_nonfinite_remain_rejected(self):
        for change in ({'input':[2,1]},{'input':[3,3]},{'var':'invented'},{'output':[0,float('nan')]}):
            raw=threshold_scene();raw['nodes'][0]['bindings'][0].update(change)
            with self.assertRaises(ValueError):validate_visual(raw,validate_rules(process_demo()))

    def test_challenge_contract_is_not_silently_reinterpreted(self):
        spec=lock_fixture();spec['visual']['nodes'][5]['bindings'][0]['input']=[1,1]
        with self.assertRaisesRegex(ValueError,'Intervalo de entrada precisa crescer:'):
            validate_rules(spec)


if __name__=='__main__':unittest.main()
