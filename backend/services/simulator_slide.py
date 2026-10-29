"""Slide-sized presentation upgrade. Never changes simulation rules or state."""
import base64
from pathlib import Path
import re

MARKER = 'scormify-simulator-slide-v3'
ENGINE = re.compile(r'<body\b[^>]*\bdata-sim-engine=["\'](?:finite-rules-v1|entity-planning-v1)["\']', re.I)


def simulator_slide_source():
    for folder in (Path('/app/game_templates'), Path(__file__).resolve().parents[2]/'frontend/src/components/games'):
        path=folder/'simulatorSlideRuntime.js'
        if path.is_file():
            return path.read_text(encoding='utf-8').replace('export function simulatorSlideRuntime','function simulatorSlideRuntime',1)
    raise RuntimeError('Interface de slide para simuladores indisponível')


def upgrade_simulator_slide(document):
    if not isinstance(document,str) or not document:
        return document
    if document.startswith('__B64__:'):
        try:
            source=base64.b64decode(document[8:],validate=True).decode('utf-8')
            updated=upgrade_simulator_slide(source)
            return '__B64__:'+base64.b64encode(updated.encode()).decode() if updated!=source else document
        except (ValueError,UnicodeError):
            return document
    if not ENGINE.search(document) or 'id="scormify-simulator-plan"' not in document:
        return document
    from services.rule_visuals import upgrade_visual_document
    document=upgrade_visual_document(document)
    if f'id="{MARKER}"' in document:return document
    document=re.sub(r'<script id="scormify-simulator-slide-v[12]">[\s\S]*?</script>','',document,count=1)
    script='<script id="'+MARKER+'">('+simulator_slide_source()+')();</script>'
    return re.sub(r'</body>',lambda _:script+'</body>',document,count=1,flags=re.I) if re.search(r'</body>',document,re.I) else document+script


def refresh_simulator_slides(project):
    if project:
        course=project.get('course') or {}
        for slide in course.get('slides',[]):
            for element in slide.get('elements',[]):
                if element.get('type')!='html':continue
                raw=element.get('htmlContent')
                updated=upgrade_simulator_slide(raw)
                if not isinstance(updated,str):continue
                try: source=base64.b64decode(updated[8:]).decode() if updated.startswith('__B64__:') else updated
                except (ValueError,UnicodeError):continue
                if not ENGINE.search(source) or f'id="{MARKER}"' not in source:continue
                element.update(htmlContent=updated,x=0,y=0,width=slide.get('width') or course.get('width') or 960,
                               height=slide.get('height') or course.get('height') or 540,htmlDisplayMode='page',objectFit='cover')
    return project
