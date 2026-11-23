import asyncio,base64,copy,io,json,re
from PIL import Image
from services.interactive_images import prepare_interactive_images,compact_piece
from services.assessment_assets import inline_assessment_assets
from services.assessment_renderer import assessment_element,refresh_assessment_documents

def png():
    image=Image.new('RGBA',(200,200),(30,130,200,210));image.putpixel((0,0),(0,0,0,0))
    output=io.BytesIO();image.save(output,'PNG',compress_level=0)
    return 'data:image/png;base64,'+base64.b64encode(output.getvalue()).decode()

def data(document,ident):
    return json.loads(re.search(r'<script[^>]*id="'+ident+r'"[^>]*>([\s\S]*?)</script>',document)[1])

def test_piece_compression_is_lossless_and_keeps_png_schema():
    original=png();result=compact_piece(original)
    assert len(result)<len(original)*.1
    with Image.open(io.BytesIO(base64.b64decode(original.split(',')[1]))) as a,Image.open(io.BytesIO(base64.b64decode(result.split(',')[1]))) as b:
        assert a.size==b.size and a.mode==b.mode and a.tobytes()==b.tobytes()
    assert compact_piece(result)==result
    assert compact_piece('data:image/png;base64,invalid')=='data:image/png;base64,invalid'

def test_simulator_rules_motion_labels_and_editability_unchanged():
    from test_didactic_visualizations import fixture
    from services.didactic_visualizations import render,validate
    spec=fixture();spec['illustrations']=[{'node':'electron','src':png()}];before=copy.deepcopy(spec)
    html=render(spec);result=data(html,'scormify-visualization-plan')
    validate(result)
    assert result['motions']==before['motions'] and result['nodes']==before['nodes']
    assert len(result['illustrations'][0]['src'])<len(spec['illustrations'][0]['src'])
    assert spec==before
    assert prepare_interactive_images(html)==html

def test_assessment_images_support_choices_and_source_snapshot_preservation(tmp_path):
    from services.single_page_exporter import _inline_assets_in_html
    from services.html_exporter import process_html_content_images
    filename='assessment_'+'a'*32+'.png'
    Image.effect_noise((1536,1024),32).convert('RGB').save(tmp_path/filename)
    url='/api/projects/p1/assets/'+filename
    image={'kind':'image','url':url,'name':'Apoio'}
    q={'id':'q1','title':'Pergunta','prompt':'Enunciado original','type':'single_choice','points':3,
       'media':image,'options':[{'id':'a','text':'Sim','isCorrect':True,'media':dict(image)}]}
    el=assessment_element([q]);before=copy.deepcopy(el['assessmentConfig'])
    preview=data(el['htmlContent'],'assessment-data')
    assert 'astryx_image=v1' in preview['questions'][0]['media']['url']
    assert 'astryx_image=v1' in preview['questions'][0]['options'][0]['media']['url']
    for output in (inline_assessment_assets(el['htmlContent'],str(tmp_path)),
                   asyncio.run(process_html_content_images(el['htmlContent'],str(tmp_path),'')),
                   _inline_assets_in_html(el['htmlContent'],'p1',str(tmp_path),'')):
        result=data(output,'assessment-data')
        assert result['questions'][0]['media']['url'].startswith('data:image/webp;base64,')
        assert result['questions'][0]['options'][0]['isCorrect'] is True
        assert result['questions'][0]['points']==3
    refresh_assessment_documents({'course':{'slides':[{'elements':[el]}]}})
    assert el['assessmentConfig']==before

def test_captures_other_media_and_uncontrolled_json_are_untouched():
    raw={'questions':[{'media':{'kind':'image','url':'/api/projects/p1/assets/docx_capture.png'},
                      'options':[{'media':{'kind':'video','url':'/api/projects/p1/assets/assessment_'+'a'*32+'.png'}}]}]}
    document='<script id="assessment-data" type="application/json">'+json.dumps(raw)+'</script>'
    assert prepare_interactive_images(document)==document
    other='<script id="other">'+json.dumps({'illustrations':[{'node':'x','src':png()}]})+'</script>'
    assert prepare_interactive_images(other)==other

def test_encoded_simulator_and_exports_remain_offline(tmp_path):
    spec={'title':'Simulação','motions':[{'node':'person','kind':'translate'}],
          'illustrations':[{'node':'person','src':png()}]}
    raw='<body data-sim-engine="finite-rules-v1"><script id="scormify-simulator-plan" type="application/json">'+json.dumps(spec)+'</script><script>function keepRules(){return 4}</script></body>'
    encoded='__B64__:'+base64.b64encode(raw.encode()).decode()
    fixed=base64.b64decode(prepare_interactive_images(encoded)[8:]).decode()
    assert 'function keepRules(){return 4}' in fixed
    assert data(fixed,'scormify-simulator-plan')['motions']==spec['motions']
    output=inline_assessment_assets(raw,str(tmp_path))
    assert 'data:image/png;base64,' in output and '/api/' not in output

def test_real_scorm_keeps_assessment_snapshot_and_smaller_display(tmp_path):
    import zipfile
    from models import Project
    from services.scorm_exporter import export_scorm_package
    folder=tmp_path/'p1'/'assets';folder.mkdir(parents=True)
    filename='assessment_'+'b'*32+'.png'
    Image.effect_noise((1536,1024),32).convert('RGB').save(folder/filename)
    question={'id':'q1','title':'Pergunta','prompt':'Original','type':'single_choice','points':2,
              'media':{'kind':'image','url':'/api/projects/p1/assets/'+filename},
              'options':[{'id':'a','text':'Sim','isCorrect':True}]}
    element=assessment_element([question]);saved={'id':'p1','name':'Curso','enableVlibras':False,
      'course':{'slides':[{'id':'s1','notes':'Preservadas','elements':[element]}]}}
    before=copy.deepcopy(saved)
    archive=export_scorm_package(Project(**saved),str(tmp_path),str(tmp_path/'exports'))
    with zipfile.ZipFile(archive) as z:
        course=json.loads(z.read('course.json'));el=course['slides'][0]['elements'][0]
        document=el['htmlContent']
        if document.startswith('__B64__:'):document=base64.b64decode(document[8:]).decode()
        assert data(document,'assessment-data')['questions'][0]['media']['url'].startswith('data:image/webp;base64,')
        assert el['assessmentConfig']['questions'][0]['options']==question['options']
    assert saved==before
