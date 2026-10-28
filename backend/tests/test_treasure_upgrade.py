import ast
import base64
import json
import logging
from pathlib import Path
import unittest
from services.treasure_upgrade import upgrade_treasure_html,refresh_treasures

ROOT=Path(__file__).resolve().parents[2]


class TreasureUpgradeTests(unittest.TestCase):
    def test_existing_map_is_upgraded_without_changing_questions(self):
        source='<html><body><script>const QE={};const SETTINGS={"type":"treasure"};function renderAdventure(){};const text="Criação";</script></body></html>'
        upgraded=upgrade_treasure_html(source)
        self.assertIn(source.split('<body>')[1].split('</body>')[0],upgraded)
        self.assertIn('scormify-treasure-v1',upgraded)
        self.assertEqual(upgrade_treasure_html(upgraded),upgraded)
        self.assertEqual(upgrade_treasure_html(source.replace('"treasure"','"race"')),source.replace('"treasure"','"race"'))
        element={'type':'html','htmlContent':'__B64__:'+base64.b64encode(source.encode()).decode()}
        refresh_treasures({'course':{'slides':[{'elements':[element]}]}})
        self.assertEqual(base64.b64decode(element['htmlContent'][8:]).decode(),upgraded)

    def test_agent_resolves_canonical_map_runtime(self):
        path=ROOT/'backend/services/ai_agent.py';tree=ast.parse(path.read_text(encoding='utf-8'))
        nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in {'_editor_game_template_source','_build_editor_game_html'}]
        env={'__file__':str(path),'Path':Path,'json':json,'logger':logging.getLogger(__name__),'_EDITOR_GAME_TYPE_BY_AGENT_MECHANIC':{'target_challenge':'treasure'}}
        exec(compile(ast.Module(body=nodes,type_ignores=[]),str(path),'exec'),env)
        html=env['_build_editor_game_html']('target_challenge','Mapa',[{'question':'Pergunta','alternatives':['A','B'],'correct':0}])
        self.assertIn('scormify-treasure-v1',html)
        self.assertNotIn('${treasureRuntime.toString()}',html)
        self.assertIn('treasureResults',html)


if __name__=='__main__':unittest.main()
