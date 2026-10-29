import base64
import unittest
from services.crossword_upgrade import upgrade_crossword_html,refresh_crosswords,crossword_runtime_source


class CrosswordUpgradeTests(unittest.TestCase):
    def test_existing_unicode_game_upgrades_without_replacing_questions_or_score(self):
        source='<html><body><script>const QE={};const SETTINGS={"type":"crossword"};function renderCrossword(){};const title="Empatia e criação";</script></body></html>'
        upgraded=upgrade_crossword_html(source)
        self.assertIn(source.split('<body>')[1].split('</body>')[0],upgraded)
        self.assertIn('crosswordRuntime',upgraded)
        self.assertEqual(upgrade_crossword_html(upgraded),upgraded)
        self.assertEqual(upgrade_crossword_html(source.replace('"crossword"','"climb"')),source.replace('"crossword"','"climb"'))
        element={'type':'html','htmlContent':'__B64__:'+base64.b64encode(source.encode()).decode()}
        refresh_crosswords({'course':{'slides':[{'elements':[element]}]}})
        self.assertEqual(base64.b64decode(element['htmlContent'][8:]).decode(),upgraded)

    def test_runtime_is_self_contained_and_deployed_with_existing_docker_copy(self):
        source=crossword_runtime_source()
        self.assertIn('function crosswordRuntime',source)
        self.assertNotIn('export function',source)
        self.assertIn("input.addEventListener('paste'",source)
        self.assertIn("input.oninput",source)

    def test_v2_runtime_is_replaced_and_reveal_is_available_offline(self):
        source='<body><script>const QE={};const SETTINGS={"type":"crossword"};function renderCrossword(){}</script><script id="scormify-crossword-v2">oldRuntime()</script></body>'
        upgraded=upgrade_crossword_html(source)
        self.assertNotIn('oldRuntime()',upgraded)
        self.assertIn('scormify-crossword-v4',upgraded)
        self.assertIn('REVELAR RESPOSTAS PARA ESTUDAR',upgraded)
        self.assertEqual(upgrade_crossword_html(upgraded),upgraded)

    def test_v3_migrates_to_uncut_runtime(self):
        source='<body><script>const QE={};const SETTINGS={"type":"crossword"};function renderCrossword(){}</script><script id="scormify-crossword-v3">outdated()</script></body>'
        upgraded=upgrade_crossword_html(source)
        self.assertNotIn('outdated()',upgraded)
        self.assertIn('scormify-crossword-v4',upgraded)
        self.assertIn('Complete a resposta:',upgraded)


if __name__=='__main__':unittest.main()
