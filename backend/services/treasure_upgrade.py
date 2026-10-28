"""Upgrade map feedback without changing questions, scoring or progression."""
import base64
from pathlib import Path
import re


def treasure_runtime_source():
    for folder in (Path('/app/game_templates'),Path(__file__).resolve().parents[2]/'frontend/src/components/games'):
        path=folder/'treasureRuntime.js'
        if path.is_file():
            return path.read_text(encoding='utf-8').replace('export function treasureRuntime','function treasureRuntime',1)
    raise RuntimeError('Runtime do mapa indisponível')


def upgrade_treasure_html(html):
    if not isinstance(html,str) or not html or 'scormify-treasure-v1' in html:
        return html
    if html.startswith('__B64__:'):
        try:
            source=base64.b64decode(html[8:],validate=True).decode('utf-8')
            upgraded=upgrade_treasure_html(source)
            return '__B64__:'+base64.b64encode(upgraded.encode()).decode() if upgraded != source else html
        except (ValueError,UnicodeError):
            return html
    if not re.search(r'["\']type["\']\s*:\s*["\']treasure["\']',html) or 'renderAdventure' not in html or 'const QE=' not in html:
        return html
    script='<script id="scormify-treasure-v1">('+treasure_runtime_source()+")(Game,BANK,QE,document.getElementById('stage'));</script>"
    return re.sub(r'</body>',lambda _:script+'</body>',html,count=1,flags=re.I) if re.search(r'</body>',html,re.I) else html+script


def refresh_treasures(project):
    if project:
        for slide in (project.get('course') or {}).get('slides',[]):
            for element in slide.get('elements',[]):
                if element.get('type')=='html' and isinstance(element.get('htmlContent'),str):
                    element['htmlContent']=upgrade_treasure_html(element['htmlContent'])
    return project
