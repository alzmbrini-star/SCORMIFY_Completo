import asyncio
import copy
import json
import subprocess
import zipfile
from pathlib import Path
from models import Project, SlideElement
from services.image_shadow import image_shadow_style

ROOT=Path(__file__).resolve().parents[2]
ASSET=ROOT/'backend/services/export_assets/image-shadow.js'


def test_frontend_and_export_runtime_are_identical_and_match_server():
    frontend=(ROOT/'frontend/src/utils/imageShadow.js').read_text(encoding='utf-8')
    frontend_runtime='function imageShadowStyle'+frontend.split('export function imageShadowStyle',1)[1].split('export function imageShadowPreset',1)[0]
    assert ASSET.read_text(encoding='utf-8').strip() == frontend_runtime.strip()
    cases=[None,{'preset':'none'},{'preset':'soft'},{'preset':'medium','mode':'frame'},
           {'preset':'custom','color':'#123456','x':-3,'y':7,'opacity':32,'blur':12},
           {'preset':'custom','color':'red;url(bad)','x':999,'y':-999,'blur':999,'opacity':999}]
    script=ASSET.read_text(encoding='utf-8')+'\nconsole.log(JSON.stringify('+json.dumps(cases)+'.map(imageShadowStyle)));'
    result=subprocess.run(['node','-e',script],capture_output=True,text=True,check=True)
    assert json.loads(result.stdout)==[image_shadow_style(c) for c in cases]


def sample():
    return {'id':'shadow-test','name':'Sombra','enableVlibras':False,'course':{'width':960,'height':540,'slides':[{'id':'s1','elements':[{'id':'im1','type':'image','x':120,'y':100,'width':500,'height':300,'src':'data:image/png;base64,aGVsbG8=','imageShadow':{'preset':'soft','mode':'contour'}}]}]}}


def test_configuration_round_trips_without_modifying_image_or_geometry():
    image=sample()['course']['slides'][0]['elements'][0];before=copy.deepcopy(image)
    saved=SlideElement(**image).model_dump()
    assert saved['imageShadow']==image['imageShadow']
    for key in ('src','x','y','width','height'):assert saved[key]==before[key]
    assert image==before


def test_html_and_scorm_ship_the_shared_runtime_and_saved_configuration(tmp_path):
    from services.html_exporter import generate_standalone_html
    from services.scorm_exporter import export_scorm_package
    original=sample();before=copy.deepcopy(original)
    html=asyncio.run(generate_standalone_html(original,str(tmp_path)))
    assert 'function imageShadowStyle(shadow)' in html
    assert 'imageShadowStyle(elem.imageShadow)' in html
    assert '"imageShadow": {"preset": "soft", "mode": "contour"}' in html
    assert html.index('function imageShadowStyle(shadow)')<html.index('imageShadowStyle(elem.imageShadow)')
    path=export_scorm_package(Project(**sample()),str(tmp_path/'storage'),str(tmp_path/'output'))
    with zipfile.ZipFile(path) as package:
        player=package.read('scripts/player.js').decode()
        course=json.loads(package.read('course.json'))
        assert any(package.read(name)==b'hello' for name in package.namelist() if name.startswith('assets/'))
    assert 'function imageShadowStyle(shadow)' in player and 'imageShadowStyle(element.imageShadow)' in player
    assert "element.imageShadow) el.style.setProperty('overflow', 'visible', 'important')" in player
    exported_image=course['slides'][0]['elements'][0]
    assert exported_image['imageShadow']==before['course']['slides'][0]['elements'][0]['imageShadow']
    for key in ('x','y','width','height'):assert exported_image[key]==before['course']['slides'][0]['elements'][0][key]
    assert original==before


def test_flow_export_obeys_none_and_contour_without_replacing_asset():
    from services.single_page_exporter import _render_image_element_inner
    image={'src':'https://example.org/original.png','imageShadow':{'preset':'soft'}}
    html=_render_image_element_inner(image,'p','','')
    assert 'filter:drop-shadow(0px 6px 16px rgba(0,0,0,0.18)) !important;' in html
    assert image['src'] in html
    html=_render_image_element_inner({**image,'imageShadow':{'preset':'none'}},'p','','')
    assert 'box-shadow:none !important;' in html and 'filter:none !important;' in html


def test_editor_views_and_thumbnails_apply_shadow_to_img_not_selection_frame():
    for name in ('SlideCanvas','CoursePreview','SplitPreview'):
        source=(ROOT/f'frontend/src/components/editor/{name}.jsx').read_text(encoding='utf-8')
        assert 'imageShadowStyle(element.imageShadow)' in source
    canvas=(ROOT/'frontend/src/components/editor/SlideCanvas.jsx').read_text(encoding='utf-8')
    assert "element.type === 'image' ? 'overflow-visible' : 'overflow-hidden'" in canvas
    thumb=(ROOT/'frontend/src/pages/Editor/components/SlideThumbnailContent.jsx').read_text(encoding='utf-8')
    assert 'imageShadowStyle(el.imageShadow)' in thumb
