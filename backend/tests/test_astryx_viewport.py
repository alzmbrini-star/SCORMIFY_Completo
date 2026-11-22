import base64
from pathlib import Path
from services.astryx_viewport import upgrade_astryx_viewport
from services.astryx_agent import build_elements,TEMPLATE

def test_only_agent_astryx_is_upgraded_without_changing_authored_source():
    raw='<html><head></head><body><main data-astryx-lesson="1"><h1>Original</h1><img alt="Captura" src="/api/a.png"><script>function original(){return 4}</script></main></body></html>'
    fixed=upgrade_astryx_viewport(raw)
    assert fixed.replace(fixed[fixed.index('<script id="astryx-viewport-v2">'):fixed.rindex('</script>')+9],'')==raw
    assert upgrade_astryx_viewport(fixed)==fixed
    for marker in ('data-astryx-slide="1"','data-sim-engine="finite-rules-v1"','id="assessment-data"'):
        other=raw.replace('data-astryx-lesson="1"',marker)
        assert upgrade_astryx_viewport(other)==other
    encoded='__B64__:'+base64.b64encode(raw.encode()).decode()
    assert base64.b64decode(upgrade_astryx_viewport(encoded)[8:]).decode()==fixed

def test_runtime_shared_with_frontend_and_new_generation_contains_it():
    root=Path(__file__).resolve().parents[2]
    assert (root/'backend/services/astryx_assets/viewport.js').read_bytes()==(root/'frontend/src/utils/astryxViewportRuntime.js').read_bytes()
    slide={'title':'Título muito longo','notes':'Preservar','elements':[{'type':'text','content':'<p>Texto integral</p>'}]}
    document=build_elements(slide,TEMPLATE['palette'])[0]['htmlContent']
    assert 'id="astryx-viewport-v2"' in document and '<p>Texto integral</p>' in document

def test_previous_viewport_is_replaced_without_touching_authored_scripts():
    raw='<html><body><main data-astryx-lesson="1">Texto integral</main><script id="author">keepQuestions()</script><script id="astryx-viewport-v1">oldViewport()</script></body></html>'
    fixed=upgrade_astryx_viewport(raw)
    assert 'oldViewport()' not in fixed and 'id="astryx-viewport-v1"' not in fixed
    assert '<script id="author">keepQuestions()</script>' in fixed
    assert 'picture.style.width' in fixed and 'image.naturalWidth' in fixed
