import asyncio
import base64
import hashlib
from pathlib import Path
from PIL import Image, ImageChops, ImageStat
from services.astryx_images import display_image, prepare_astryx_images
from services.astryx_viewport import upgrade_astryx_viewport
from services.html_exporter import process_html_content_images
from services.single_page_exporter import _inline_assets_in_html

def asset(tmp_path):
    folder=tmp_path/'project1'/'assets';folder.mkdir(parents=True)
    source=folder/'ai_img_abcdef123456.png'
    Image.effect_noise((1800,1000),32).convert('RGB').save(source)
    return source

def document(filename):
    return '<html><body><main data-astryx-lesson="1"><p>Conteúdo integral</p><img src="/api/projects/project1/assets/'+filename+'" alt="Descrição original"><script>const questions=[1,2,3];</script></main></body></html>'

def test_derivative_smaller_cached_proportional_original_untouched(tmp_path):
    source=asset(tmp_path);before=source.read_bytes()
    result=display_image(source)
    assert result!=source and result.suffix=='.webp'
    assert result.stat().st_size < len(before)*.9
    with Image.open(result) as image:
        assert image.size==(1600,889)
        with Image.open(source) as original:
            original.thumbnail((1600,1600),Image.Resampling.LANCZOS)
            assert max(ImageStat.Stat(ImageChops.difference(original,image.convert('RGB'))).rms)<15
    assert display_image(source)==result
    assert source.read_bytes()==before
    assert not list(source.parent.glob('*.webp'))

def test_only_generated_images_in_astryx_are_changed(tmp_path):
    source=asset(tmp_path)
    raw=document(source.name)
    preview=prepare_astryx_images(raw)
    assert '?astryx_image=v1' in preview and 'decoding="async"' in preview
    assert prepare_astryx_images(preview)==preview
    assert prepare_astryx_images(raw.replace('data-astryx-lesson','data-other'))==raw.replace('data-astryx-lesson','data-other')
    for name in ('capture.png','docx_image11.png','logo.png','ai_img_abcdef123456.gif'):
        assert prepare_astryx_images(document(name))==document(name)
    offline=prepare_astryx_images(preview,source.parent)
    assert 'data:image/webp;base64,' in offline and 'astryx_image=' not in offline
    assert 'alt="Descrição original"' in offline and 'const questions=[1,2,3]' in offline

def test_corrupt_small_and_animated_images_fall_back(tmp_path):
    bad=tmp_path/'ai_img_abcdef12.png';bad.write_bytes(b'not an image'*15000)
    assert display_image(bad)==bad
    small=tmp_path/'ai_img_abcdef13.png';Image.new('RGB',(10,10)).save(small)
    assert display_image(small)==small
    assert display_image(tmp_path/'ai_img_abcdef14.png')==tmp_path/'ai_img_abcdef14.png'

def test_html_and_single_page_embed_optimized_data(tmp_path):
    source=asset(tmp_path);raw=document(source.name)
    for output in (asyncio.run(process_html_content_images(raw,str(source.parent),'')),
                   _inline_assets_in_html(raw,'project1',str(source.parent),'')):
        assert 'data:image/webp;base64,' in output
        assert 'astryx_image=' not in output
        assert 'Conteúdo integral' in output and 'const questions=[1,2,3]' in output
        assert len(output)<len(base64.b64encode(source.read_bytes()))*.9

def test_legacy_viewport_and_encoded_documents_get_display_upgrade():
    raw=document('ai_img_abcdef123456.png')
    upgraded=upgrade_astryx_viewport(raw)
    assert '?astryx_image=v1' in upgraded
    assert upgrade_astryx_viewport(upgraded)==upgraded
    encoded='__B64__:'+base64.b64encode(raw.encode()).decode()
    assert base64.b64decode(upgrade_astryx_viewport(encoded)[8:]).decode()==upgraded

def test_export_stream_uses_file_token_not_large_base64(tmp_path):
    from services.export_media_stream import MediaStream,CURRENT
    source=asset(tmp_path)
    spool=MediaStream();token=CURRENT.set(spool)
    try:
        output=prepare_astryx_images(document(source.name),source.parent)
        assert 'data:image/webp;base64,' in output
        assert len(output)<1000
        assert len(b''.join(spool.chunks(output)))>1000
    finally:
        CURRENT.reset(token)
        spool.close()

def test_server_variant_keeps_original_route_and_cache_headers(tmp_path):
    from routes.export import _astryx_display_response
    source=asset(tmp_path)
    normal=asyncio.run(_astryx_display_response(source,''))
    optimized=asyncio.run(_astryx_display_response(source,'v1'))
    assert Path(normal.path)==source
    assert Path(optimized.path)!=source and optimized.media_type=='image/webp'
    assert 'must-revalidate' in optimized.headers['cache-control']
    from starlette.requests import Request
    request=Request({'type':'http','headers':[(b'if-none-match',optimized.headers['etag'].encode())]})
    assert asyncio.run(_astryx_display_response(source,'v1',request)).status_code==304

def test_scorm_uses_smaller_payload_without_editing_snapshot(tmp_path):
    import copy,json,zipfile
    from models import Project
    from services.scorm_exporter import export_scorm_package
    source=asset(tmp_path)
    saved={'id':'project1','name':'Astryx','enableVlibras':False,'course':{'slides':[
        {'id':'s1','title':'Original','notes':'Notas','elements':[{'id':'e1','type':'html','astryxDesign':True,
          'x':0,'y':0,'width':960,'height':540,'htmlContent':document(source.name)}]}]}}
    before=copy.deepcopy(saved)
    result=export_scorm_package(Project(**saved),str(tmp_path),str(tmp_path/'exports'))
    with zipfile.ZipFile(result) as archive:
        course=json.loads(archive.read('course.json'))
        content=course['slides'][0]['elements'][0]['htmlContent']
        if content.startswith('__B64__:'):content=base64.b64decode(content[8:]).decode()
        assert 'data:image/webp;base64,' in content and 'astryx_image=' not in content
        assert 'const questions=[1,2,3]' in content
    assert saved==before
