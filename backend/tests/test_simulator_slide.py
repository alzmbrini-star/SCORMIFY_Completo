import base64
import copy
import json
from pathlib import Path
import re
import unittest

from services.simulator_slide import upgrade_simulator_slide,refresh_simulator_slides,MARKER
from services.rule_simulators import render_rules
from test_rule_simulators import fixtures
from services.planning_simulators import render_planning
from test_planning_simulators import fixture


class SlidePresentationTests(unittest.TestCase):
    def test_both_engines_use_one_idempotent_presentation_without_changing_data(self):
        for document in (render_rules(fixtures()[0]),render_planning(fixture())):
            self.assertEqual(document.count('id="'+MARKER+'"'),1)
            self.assertEqual(upgrade_simulator_slide(document),document)
            before=re.search(r'<script id="scormify-simulator-plan"[^>]*>(.*?)</script>',document,re.S)[1]
            legacy=re.sub(r'<script id="'+MARKER+r'">[\s\S]*?</script>','',document)
            upgraded=upgrade_simulator_slide(legacy)
            after=re.search(r'<script id="scormify-simulator-plan"[^>]*>(.*?)</script>',upgraded,re.S)[1]
            self.assertEqual(json.loads(before),json.loads(after))
            self.assertIn('grid-template-rows:auto 86px minmax(0,1fr) 52px',upgraded)
            self.assertNotIn('scale(',upgraded)

    def test_encoded_and_authored_styles_are_preserved_and_geometry_uses_course_canvas(self):
        original=render_planning(fixture()).replace('</head>','<style id="author-colors">h1{color:#ffe000}</style></head>')
        encoded='__B64__:'+base64.b64encode(original.encode()).decode()
        project={'course':{'width':1920,'height':820,'slides':[{'elements':[{'type':'html','htmlContent':encoded,'x':400,'y':100,'width':300,'height':100}]}]}}
        updated=refresh_simulator_slides(copy.deepcopy(project))['course']['slides'][0]['elements'][0]
        self.assertEqual((updated['x'],updated['y'],updated['width'],updated['height']),(0,0,1920,820))
        self.assertEqual(updated['htmlDisplayMode'],'page')
        self.assertIn('author-colors',base64.b64decode(updated['htmlContent'][8:]).decode())
        self.assertEqual(project['course']['slides'][0]['elements'][0]['width'],300)

    def test_unrelated_documents_and_malformed_base64_remain_untouched(self):
        for document in ('<html><body>Uma página comum</body></html>','__B64__:not base64',None,''):
            self.assertEqual(upgrade_simulator_slide(document),document)

    def test_exporters_bypass_page_scaling_for_planning_and_rule_simulators(self):
        folder=Path(__file__).resolve().parents[1]/'services'
        for file in ('export_assets/player.js','html_exporter.py'):
            source=(folder/file).read_text(encoding='utf-8')
            for engine in ('finite-rules-v1','entity-planning-v1'):
                self.assertIn("wrappedHtml.indexOf('data-sim-engine=\""+engine+"\"') === -1",source)


if __name__=='__main__':unittest.main()
