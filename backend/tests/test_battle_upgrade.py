import ast
import base64
import json
import logging
from pathlib import Path
import unittest
from services.battle_upgrade import upgrade_battle_html,refresh_battles,battle_runtime_source

ROOT=Path(__file__).resolve().parents[2]


class BattleUpgradeTests(unittest.TestCase):
    def test_legacy_unicode_battle_is_upgraded_without_changing_saved_questions(self):
        source='<html><body><script>const QE={};const SETTINGS={"type":"battle"};const Game={enemyHealth:100};const question="Criação e empatia";</script></body></html>'
        upgraded=upgrade_battle_html(source)
        self.assertIn(source.split('<body>')[1].split('</body>')[0],upgraded)
        self.assertIn('scormify-battle-v1',upgraded)
        self.assertEqual(upgrade_battle_html(upgraded),upgraded)
        self.assertEqual(upgrade_battle_html(source.replace('"battle"','"race"')),source.replace('"battle"','"race"'))
        element={'type':'html','htmlContent':'__B64__:'+base64.b64encode(source.encode()).decode()}
        refresh_battles({'course':{'slides':[{'elements':[element]}]}})
        self.assertEqual(base64.b64decode(element['htmlContent'][8:]).decode(),upgraded)

    def test_agent_template_resolves_both_offline_runtimes(self):
        agent=ROOT/'backend/services/ai_agent.py';tree=ast.parse(agent.read_text(encoding='utf-8'))
        nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in {'_editor_game_template_source','_build_editor_game_html'}]
        env={'__file__':str(agent),'Path':Path,'json':json,'logger':logging.getLogger(__name__),'_EDITOR_GAME_TYPE_BY_AGENT_MECHANIC':{'battle':'battle'}}
        exec(compile(ast.Module(body=nodes,type_ignores=[]),str(agent),'exec'),env)
        html=env['_build_editor_game_html']('battle','Batalha',[{'question':'Pergunta','alternatives':['A','B'],'correct':0}])
        self.assertIn('scormify-battle-v1',html)
        self.assertNotIn('${battleRuntime.toString()}',html)
        self.assertNotIn('${crosswordRuntime.toString()}',html)
        self.assertIn('Sua energia',html)
        self.assertIn('battle-attack-right',html)
        self.assertNotIn('export function',battle_runtime_source())


if __name__=='__main__':unittest.main()
