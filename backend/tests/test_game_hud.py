import base64
import ast
import json
import logging
from pathlib import Path
import re
import unittest
from services.game_hud import GAME_HUD_CSS, refresh_game_huds, upgrade_game_hud

ROOT = Path(__file__).resolve().parents[2]


class GameHudTests(unittest.TestCase):
    def fixture(self):
        return '<html><head></head><body><header class="hud">SCORMIFY GAMES<div class="chips">'+''.join(
            f'<span class="chip">⭐ <b id="{key}">{value}</b></span>' for key,value in [('lives',3),('timer',30),('xp',100),('coins',10)])+'</div></header><script>const QuestionEngine={};timer.textContent=29;</script></body></html>'

    def test_upgrades_old_game_without_touching_logic_or_metric_ids(self):
        source=self.fixture(); upgraded=upgrade_game_hud(source)
        self.assertIn('⏱ Tempo',upgraded); self.assertIn('⭐ Pontuação',upgraded)
        self.assertEqual(upgraded.count('hud-metric hud-'),4)
        self.assertEqual(re.findall(r'<script>[\s\S]*?</script>',source),re.findall(r'<script>[\s\S]*?</script>',upgraded))
        self.assertEqual(upgrade_game_hud(upgraded),upgraded)
        for key in ['lives','timer','xp','coins']:
            self.assertEqual(upgraded.count(f'id="{key}"'),1)

    def test_read_time_upgrade_including_unicode_base64(self):
        source=self.fixture(); encoded='__B64__:'+base64.b64encode(source.encode()).decode()
        element={'type':'html','htmlContent':encoded}
        project={'course':{'slides':[{'elements':[element]}]}}
        refresh_game_huds(project)
        decoded=base64.b64decode(element['htmlContent'][8:]).decode()
        self.assertEqual(decoded,upgrade_game_hud(source))
        self.assertEqual(upgrade_game_hud('<p>Normal</p>'),'<p>Normal</p>')

    def test_frontend_backend_css_and_responsive_parity(self):
        source=(ROOT/'frontend/src/utils/gameHud.js').read_text(encoding='utf-8')
        css=source.split('export const GAME_HUD_CSS = `',1)[1].split('`;',1)[0]
        self.assertEqual(css,GAME_HUD_CSS)
        self.assertIn('max-width:420px',css)
        self.assertIn('font-size:clamp(30px',css)

    def test_agent_uses_the_same_hud_in_canonical_editor_templates(self):
        agent = ROOT/'backend/services/ai_agent.py'
        tree = ast.parse(agent.read_text(encoding='utf-8'))
        names = {'_editor_game_template_source','_build_editor_game_html'}
        nodes = [n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names]
        env = {'__file__':str(agent),'Path':Path,'json':json,'logger':logging.getLogger(__name__),
               '_EDITOR_GAME_TYPE_BY_AGENT_MECHANIC':{'quiz_show':'quiz_show','penalty_quest':'penalty','memory_match':'memory','knowledge_climb':'climb','target_challenge':'treasure'}}
        exec(compile(ast.Module(body=nodes,type_ignores=[]),str(agent),'exec'),env)
        for mechanic in env['_EDITOR_GAME_TYPE_BY_AGENT_MECHANIC']:
            html = env['_build_editor_game_html'](mechanic,'Teste',[{'question':'Pergunta','alternatives':['A','B'],'correct':0}])
            self.assertIn('scormify-game-hud-v1',html)
            self.assertIn('⭐ Pontuação',html)


if __name__ == '__main__': unittest.main()
