import base64
import copy
import json
from pathlib import Path
from services.singlepage_preview_assets import prepare_preview_assets
from services.single_page_exporter import generate_single_page_html,_resolve_asset_url
from services.assessment_assets import inline_assessment_assets

def test_lossless_preview_images_are_deduplicated_without_course_mutation(tmp_path):
    raw=b'original image bytes'*10000
    uri='data:image/png;base64,'+base64.b64encode(raw).decode()
    source={'id':'p','name':'Preview','enableVlibras':False,'course':{'slides':[{'id':'s','title':'Imagem','elements':[{'type':'image','src':uri}]}]},'other':uri,
            'html':'<script id="assessment-data">'+json.dumps({'image':{'url':uri}})+'</script><img src="'+uri+'">'}
    before=copy.deepcopy(source);snapshot=prepare_preview_assets(copy.deepcopy(source),tmp_path,'https://app.invalid')
    assert source==before and snapshot['other'].startswith('https://app.invalid/api/projects/p/assets/preview-image-')
    files=list(tmp_path.iterdir());assert len(files)==1 and files[0].read_bytes()==raw
    assert 'data:image/png' not in str(snapshot)
    html=generate_single_page_html(snapshot,str(tmp_path),'https://app.invalid',preview_mode=True)
    assert 'preview-image-' in html and uri not in html
    # Context is reset: a normal exporter invocation still embeds exact bytes.
    url='/api/projects/p/assets/'+files[0].name
    assert _resolve_asset_url(url,'p',str(tmp_path),'https://app.invalid')==uri

def test_preview_does_not_restore_or_embed_assessment_images(tmp_path):
    document='<head></head><script id="assessment-data">'+json.dumps({'image':{'url':'/api/projects/p/assets/not-local.png'}})+'</script>'
    result=inline_assessment_assets(document,str(tmp_path),inline_media=False)
    assert '/api/projects/p/assets/not-local.png' in result and 'assessment-viewport' in result
    assert not list(tmp_path.iterdir())

def test_large_preview_payload_becomes_small_before_rendering(tmp_path):
    uri='data:image/webp;base64,'+base64.b64encode(b'original'*700000).decode()
    snapshot={'id':'p','name':'Large','course':{'slides':[{'id':'s','title':'Original','elements':[{'type':'image','src':uri}]}]}}
    prepare_preview_assets(snapshot,tmp_path,'https://app.invalid')
    assert len(json.dumps(snapshot))<1500
    output=generate_single_page_html(snapshot,str(tmp_path),'https://app.invalid',preview_mode=True)
    assert len(output)<500000
