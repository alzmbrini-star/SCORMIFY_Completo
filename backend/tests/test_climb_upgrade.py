import ast
import base64
import json
import logging
from pathlib import Path
import unittest
from services.climb_upgrade import upgrade_climb_html,refresh_climbs

ROOT=Path(__file__).resolve().parents[2]


class ClimbUpgradeTests(unittest.TestCase):
    def test_existing_climb_keeps_questions_and_upgrades_unicode_base64(self):
        source='<html><body><script>const QE={};const SETTINGS={"type":"climb"};function renderAdventure(){};const text="Criação";</script></body></html>'
        upgraded=upgrade_climb_html(source)
        self.assertIn(source.split('<body>')[1].split('</body>')[0],upgraded)
        self.assertIn('scormify-climb-v1',upgraded)
        self.assertEqual(upgrade_climb_html(upgraded),upgraded)
        self.assertEqual(upgrade_climb_html(source.replace('"climb"','"race"')),source.replace('"climb"','"race"'))
        element={'type':'html','htmlContent':'__B64__:'+base64.b64encode(source.encode()).decode()}
        refresh_climbs({'course':{'slides':[{'elements':[element]}]}})
        self.assertEqual(base64.b64decode(element['htmlContent'][8:]).decode(),upgraded)

    def test_agent_resolves_canonical_climb_runtime(self):
        path=ROOT/'backend/services/ai_agent.py';tree=ast.parse(path.read_text(encoding='utf-8'))
        nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in {'_editor_game_template_source','_build_editor_game_html'}]
        env={'__file__':str(path),'Path':Path,'json':json,'logger':logging.getLogger(__name__),'_EDITOR_GAME_TYPE_BY_AGENT_MECHANIC':{'knowledge_climb':'climb'}}
        exec(compile(ast.Module(body=nodes,type_ignores=[]),str(path),'exec'),env)
        html=env['_build_editor_game_html']('knowledge_climb','Escalada',[{'question':'Pergunta','alternatives':['A','B'],'correct':0}])
        self.assertIn('scormify-climb-v1',html)
        self.assertNotIn('${climbRuntime.toString()}',html)
        self.assertIn('Subida por acertos',html)


if __name__=='__main__':unittest.main()
