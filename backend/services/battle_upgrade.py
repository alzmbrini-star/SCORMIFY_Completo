"""Reuse the canonical battle runtime without regenerating course questions."""
import base64
from pathlib import Path
import re


def battle_runtime_source():
    for folder in (Path('/app/game_templates'),Path(__file__).resolve().parents[2]/'frontend/src/components/games'):
        path=folder/'battleRuntime.js'
        if path.is_file():
            return path.read_text(encoding='utf-8').replace('export function battleRuntime','function battleRuntime',1)
    raise RuntimeError('Runtime da batalha indisponível')


def upgrade_battle_html(html):
    if not isinstance(html,str) or not html or 'scormify-battle-v1' in html:
        return html
    if html.startswith('__B64__:'):
        try:
            source=base64.b64decode(html[8:],validate=True).decode('utf-8')
            upgraded=upgrade_battle_html(source)
            return '__B64__:'+base64.b64encode(upgraded.encode()).decode() if upgraded != source else html
        except (ValueError,UnicodeError):
            return html
    if not re.search(r'["\']type["\']\s*:\s*["\']battle["\']',html) or 'enemyHealth' not in html or 'const QE=' not in html:
        return html
    script='<script id="scormify-battle-v1">('+battle_runtime_source()+")(Game,BANK,QE,document.getElementById('stage'),SETTINGS);</script>"
    return re.sub(r'</body>',lambda _:script+'</body>',html,count=1,flags=re.I) if re.search(r'</body>',html,re.I) else html+script


def refresh_battles(project):
    if project:
        for slide in (project.get('course') or {}).get('slides',[]):
            for element in slide.get('elements',[]):
                if element.get('type')=='html' and isinstance(element.get('htmlContent'),str):
                    element['htmlContent']=upgrade_battle_html(element['htmlContent'])
    return project
