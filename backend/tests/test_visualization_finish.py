import base64,copy,json,re,unittest
from services.didactic_visualizations import validate,render,upgrade_presentation,FINISH_MARKER
from services.simulator_slide import upgrade_simulator_slide,refresh_simulator_slides
from visual_finish_fixtures import pilots


class Finish(unittest.TestCase):
    def test_three_contexts_and_palettes_use_same_renderer_without_logical_changes(self):
        for plan in pilots():
            before=copy.deepcopy(plan);data=validate(plan);document=render(data)
            embedded=json.loads(re.search(r'id="scormify-visualization-plan" type="application/json">(.*?)</script>',document,re.S)[1])
            self.assertEqual(embedded,data);self.assertEqual(plan,before)
            self.assertIn(FINISH_MARKER,document);self.assertEqual(upgrade_presentation(document),document)
            self.assertNotIn('https://',document);self.assertNotIn('LMSSetValue',document)

    def test_saved_documents_upgrade_only_presentation_including_base64(self):
        document=render(pilots()[0]);legacy=re.sub(r'<script id="'+FINISH_MARKER+r'">.*?</script>','',document,flags=re.S)
        updated=upgrade_simulator_slide(legacy)
        self.assertIn(FINISH_MARKER,updated)
        old_plan=re.search(r'id="scormify-visualization-plan" type="application/json">(.*?)</script>',legacy,re.S)[1]
        self.assertIn(old_plan,updated)
        self.assertEqual(upgrade_simulator_slide(updated),updated)
        encoded='__B64__:'+base64.b64encode(legacy.encode()).decode()
        self.assertIn(FINISH_MARKER,base64.b64decode(upgrade_simulator_slide(encoded)[8:]).decode())
        project={'course':{'slides':[{'elements':[{'type':'html','x':10,'y':20,'width':700,'height':400,'htmlContent':legacy}]}]}}
        el=refresh_simulator_slides(project)['course']['slides'][0]['elements'][0]
        self.assertEqual([el[k] for k in ('x','y','width','height')],[10,20,700,400]);self.assertIn(FINISH_MARKER,el['htmlContent'])

    def test_material_schema_rejects_external_css_and_invalid_appearance(self):
        for mutate in (lambda p:p['presentation'].update(accent='url(https://example.com)'),
                       lambda p:p['nodes'][1]['appearance'].update(material='<script>'),
                       lambda p:p['nodes'][1]['appearance'].update(filter='url(https://example.com)')):
            p=pilots()[0];mutate(p)
            with self.assertRaises(ValueError):validate(p)


if __name__=='__main__':unittest.main()
