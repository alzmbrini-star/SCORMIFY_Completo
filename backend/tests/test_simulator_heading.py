import copy
import unittest
from services.simulator_heading import reconcile_heading
from services.visual_simulators import validate_custom_html,validate_custom_plan
from test_visual_simulators import LOCK_PLAN,custom_document


class HeadingTests(unittest.TestCase):
    def test_epi_heading_variation_does_not_block_bespoke_scene(self):
        raw=copy.deepcopy(LOCK_PLAN)
        raw['title']='Simulador: Uso de EPIs'
        spec=validate_custom_plan(raw)
        source=custom_document('Uso de EPIs')
        result=validate_custom_html(source,spec)
        self.assertIn('<h1>Simulador: Uso de EPIs</h1>',result)
        self.assertIn('data-simulator-version="3"',result)
        self.assertIn(source[source.index('<script>'):source.index('</script>')+9],result)

    def test_attributes_geometry_and_scripts_retained(self):
        source='<html><head><script>const sample="<h1>Fake</h1>";</script></head><body><h1 id="title" class="heading" style="font-size:24px">Uso <strong>de EPIs</strong></h1><div id="scene">Cena original</div><script>const state={progress:0};</script></body></html>'
        result=reconcile_heading(source,'Simulador: Uso de EPIs')
        self.assertIn('id="title" class="heading" style="font-size:24px">Simulador: Uso de EPIs</h1>',result)
        self.assertIn('const sample="<h1>Fake</h1>";',result)
        self.assertIn('<div id="scene">Cena original</div>',result)
        self.assertIn('const state={progress:0};',result)

    def test_title_is_escaped_and_reconciliation_idempotent(self):
        source='<h1>Antes</h1>'
        title='Uso & proteção <img src=x onerror=bad()>'
        result=reconcile_heading(source,title)
        self.assertIn('&amp;',result)
        self.assertIn('&lt;img',result)
        self.assertNotIn('<img',result)
        self.assertEqual(reconcile_heading(result,title),result)

    def test_interactive_children_or_missing_heading_not_destroyed(self):
        for source in ('<h1><span id="live">Estado dinâmico</span></h1>',
                       '<h1><button onclick="advance()">Avançar</button></h1>',
                       '<h1>Título<script>advance()</script></h1>',
                       '<script>const heading="<h1>Fake</h1>";</script>',
                       '<h1 hidden>Oculto</h1>',
                       '<div>Cena sem cabeçalho</div>'):
            with self.subTest(source=source):self.assertEqual(reconcile_heading(source,'Título'),source)

    def test_other_safety_and_domain_controls_still_validated(self):
        spec=validate_custom_plan(dict(LOCK_PLAN,title='Simulador: Uso de EPIs'))
        source=custom_document('Uso de EPIs').replace('</body>','<script>fetch("https://outside.test")</script></body>')
        with self.assertRaisesRegex(ValueError,'recursos locais'):validate_custom_html(source,spec)


if __name__=='__main__':unittest.main()
