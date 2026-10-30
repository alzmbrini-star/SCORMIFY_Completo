import copy,json,unittest
from services.component_catalog import catalog
from services.component_scenes import compile_project
from services.rule_simulators import validate_rules,trace_rules,single_action_shortcuts,transition
from services.rule_visuals import visual_state,illustration_detail_issues
from component_pilots import pilots,technical_pilot,feedback_pilot


class ContextComponentTests(unittest.TestCase):
    def test_key_text_and_meaningful_shape_contrasts(self):
        def luminance(color):
            channels=[int(color[i:i+2],16)/255 for i in (1,3,5)]
            channels=[x/12.92 if x<=.04045 else ((x+.055)/1.055)**2.4 for x in channels]
            return sum(x*w for x,w in zip(channels,[.2126,.7152,.0722]))
        def ratio(a,b):
            lo,hi=sorted([luminance(a),luminance(b)]);return (hi+.05)/(lo+.05)
        for style in ('studio','blueprint'):
            technical,human,planning=[validate_rules(raw) for raw in pilots(style)]
            nodes={n['id']:n['attrs'] for n in technical['visual']['nodes']}
            self.assertGreaterEqual(ratio(nodes['channel_labela']['fill'],nodes['harbor_bank']['fill']),4.5)
            nodes={n['id']:n['attrs'] for n in planning['visual']['nodes']}
            self.assertGreaterEqual(ratio(nodes['board_tasktxt0']['fill'],nodes['board_card0']['fill']),4.5)
            self.assertGreaterEqual(ratio(nodes['budget_upper']['fill'],nodes['budget_glass']['fill']),3)

    def test_three_pilots_two_styles_preserve_logic_and_have_perceptible_consequences(self):
        self.assertEqual(len(catalog()['components']),12)
        for style in ('studio','blueprint'):
            for raw in pilots(style):
                with self.subTest(style=style,title=raw['title']):
                    before=copy.deepcopy(raw);logic=copy.deepcopy(raw);logic.pop('visualProject');expected=validate_rules(logic)
                    data=validate_rules(raw);self.assertEqual(raw,before)
                    for key in ('actions','variables','goal','failure','maxSteps','checks'):self.assertEqual(data[key],expected[key])
                    self.assertEqual(single_action_shortcuts(data),[])
                    self.assertEqual(illustration_detail_issues(data['visual'],data),[])
                    self.assertLessEqual(len(data['visual']['nodes']),100)
                    self.assertEqual(validate_rules(data)['visual'],data['visual'])
                    initial={v['id']:v['initial'] for v in data['variables']}
                    for check in data['checks']:
                        self.assertEqual(trace_rules(data,check['actions']),trace_rules(expected,check['actions']))
                        self.assertNotEqual(visual_state(data['visual'],initial),visual_state(data['visual'],check['expected']))

    def test_old_projects_remain_compatible_but_cannot_silently_use_new_components(self):
        raw=technical_pilot();raw['visualProject']['catalogVersion']=1
        with self.assertRaisesRegex(ValueError,'catálogo'):validate_rules(raw)
        raw=feedback_pilot();raw['visualProject']['instances'][1]['variant']='unknown'
        with self.assertRaisesRegex(ValueError,'Variante'):validate_rules(raw)
        raw=feedback_pilot();raw['visualProject']['instances'][0]['variant']='short_hair'
        with self.assertRaisesRegex(ValueError,'Variante'):validate_rules(raw)

    def test_new_action_slots_cannot_be_wired_to_unrelated_effects(self):
        from component_pilots import planning_pilot
        raw=technical_pilot();raw['visualProject']['instances'][1]['actions']['entry']='forcar'
        with self.assertRaisesRegex(ValueError,'entrada esperada'):validate_rules(raw)
        raw=planning_pilot();raw['visualProject']['instances'][1]['actions']['plan']='dispersar'
        with self.assertRaisesRegex(ValueError,'entrada esperada'):validate_rules(raw)

    def test_boat_elevation_depends_on_its_location_not_only_chamber_level(self):
        data=validate_rules(technical_pilot())
        def project(position,level):
            state={v['id']:v['initial'] for v in data['variables']};state.update(barco=position,nivel=level)
            return next(n for n in visual_state(data['visual'],state) if n['id']=='channel_boat')['attrs']['y']
        self.assertEqual(project(0,2),155)
        self.assertEqual(project(1,0),155);self.assertEqual(project(1,2),65)
        self.assertEqual(project(2,0),65)

    def test_human_expressions_represent_actual_distinct_states(self):
        data=validate_rules(feedback_pilot());state={v['id']:v['initial'] for v in data['variables']}
        def mouth(s):return next(n for n in visual_state(data['visual'],s) if n['id']=='listener_mouth')['attrs']['d']
        initial=mouth(state)
        bad=transition(data,state,next(a for a in data['actions'] if a['id']=='pressionar'))
        good=dict(state,abertura=3)
        self.assertNotEqual(initial,mouth(bad));self.assertNotEqual(initial,mouth(good));self.assertNotEqual(mouth(bad),mouth(good))


if __name__=='__main__':unittest.main()
