"""Display-only upgrade for Agent Astryx lessons. Never writes a course."""
import base64
import re
from functools import lru_cache
from pathlib import Path

@lru_cache(maxsize=1)
def viewport_script():
    source=(Path(__file__).with_name('astryx_assets')/'viewport.js').read_text(encoding='utf-8')
    return source.replace('export const ', 'const ').replace('export function ', 'function ')+'\nastryxViewportRuntime(astryxViewportCss);'

def upgrade_astryx_viewport(document):
    if not isinstance(document,str):return document
    if document.startswith('__B64__:'):
        try:raw=base64.b64decode(document[8:],validate=True).decode('utf-8')
        except (ValueError,UnicodeError):return document
        fixed=upgrade_astryx_viewport(raw)
        return document if fixed==raw else '__B64__:'+base64.b64encode(fixed.encode()).decode()
    if not re.search(r'data-astryx-lesson=["\']',document) or 'id="astryx-viewport-v1"' in document:return document
    snippet='<script id="astryx-viewport-v1">'+viewport_script()+'</script>'
    return re.sub(r'</body\s*>',lambda m:snippet+m[0],document,count=1,flags=re.I) if re.search(r'</body\s*>',document,re.I) else document+snippet
