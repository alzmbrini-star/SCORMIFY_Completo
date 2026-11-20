import copy
import json
import re
from unittest.mock import AsyncMock, MagicMock
import pytest
from pydantic import ValidationError
from services.astryx_appearance import Appearance, STYLES, PALETTES, appearance_css, appearance_plan, style_document, normalize, luminance
from services.astryx_prototype import AstryxContent, render_documents
from services.astryx_agent import build_elements, TEMPLATE


@pytest.mark.parametrize('style',[s['id'] for s in STYLES])
@pytest.mark.parametrize('palette',[p['id'] for p in PALETTES])
def test_all_styles_palettes_preserve_accessible_images_and_activities(style,palette):
    opt={'style':style,'palette':palette}
    docs=render_documents(AstryxContent(appearance=Appearance(**opt)))
    for doc in docs:
        assert 'id="astryx-appearance-v1"' in doc and '.ax-page figcaption{display:none!important}' in doc
        assert f'"style": "{style}"' in doc and f'"palette": "{palette}"' in doc
        assert style_document(doc,opt)==doc
    assert 'alt="Ilustração de pessoas conectadas por um objetivo comum"' in docs[0]
    assert 'ax-confirm' in docs[2] and 'addEventListener' in docs[2]


@pytest.mark.parametrize('bad',[{'style':'unknown'},{'palette':'x'},{'customAccent':'red;}</style><script>x()</script>'},{'customAccent':'#fff'},{'captions':'invalid'},{'injected':'x'}])
def test_invalid_options_cannot_inject_css(bad):
    with pytest.raises(ValidationError):normalize(bad)


def test_custom_accent_gets_safe_contrast_and_caption_toggle_does_not_change_alt():
    css=appearance_css({'customAccent':'#ffff00'})
    effective=re.search('--ax-accent:(#[a-f0-9]{6})',css)[1]
    assert (luminance('#f4f7fc')+.05)/(luminance(effective)+.05)>=4.5
    raw=render_documents(AstryxContent())[0]
    enabled=style_document(raw,{'captions':True})
    assert 'figcaption{display:block!important}' in enabled and 'alt="Ilustração de pessoas' in enabled
    assert re.findall(r'<figcaption>.*?</figcaption>',raw)==re.findall(r'<figcaption>.*?</figcaption>',enabled)


def fixture():
    docs=render_documents(AstryxContent())
    return {'id':'only-target','updatedAt':'old','companyId':'company-a','course':{'metadata':{'title':'Original'},'slides':[
        {'id':str(i),'notes':'Preserve notes','interactions':[{'id':'interaction','score':5}],
         'elements':[{'id':'element-'+str(i),'type':'html' if i<3 else 'quiz',
          'htmlContent':docs[i] if i<3 else '<p>Protected</p>','quizConfig':{'questionIds':['q1','q2','q3']}}]} for i in range(19)]},
        'questions':[{'id':'q'+str(i),'points':3} for i in range(6)]}


def test_existing_course_only_updates_appearance_not_content_ids_or_scripts():
    project=fixture();before=copy.deepcopy(project)
    changes,previews=appearance_plan(project,{'style':'editorial','palette':'rose'})
    assert project==before and len(previews)==3 and len(project['course']['slides'])==19
    assert set(changes)=={*[f'course.slides.{i}.elements.0.htmlContent' for i in range(3)],'course.metadata.astryxAppearance'}
    for row in previews:
        old=project['course']['slides'][row['slide']-1]['elements'][0]['htmlContent']
        def scripts(doc):return re.findall(r'<script(?! id="astryx-appearance-data")[\s\S]*?</script>',doc)
        assert scripts(old)==scripts(row['html'])
        def visible_source(doc):return re.sub(r'<(?:style|script)[\s\S]*?</(?:style|script)>','',doc)
        assert visible_source(old)==visible_source(row['html'])


def test_new_agent_lessons_receive_settings_without_changing_source_or_alt():
    slide={'title':'Teste','imageAlt':'Descrição acessível original','elements':[{'type':'text','content':'<p>Conteúdo integral</p>'}]}
    before=copy.deepcopy(slide)
    el=build_elements(slide,{**TEMPLATE['palette'],'astryxAppearance':{'style':'soft','palette':'amber'}},image_url='/api/projects/p/assets/a.png')[0]
    assert slide==before and el['astryxAppearance']['captions'] is False
    assert 'alt="Descrição acessível original"' in el['htmlContent']
    assert 'border-radius:32px' in el['htmlContent']


@pytest.mark.asyncio
async def test_explicit_appearance_flows_through_agent_config_and_real_exports(tmp_path,monkeypatch):
    from services import ai_agent
    from test_astryx_agent import storyboard
    from services.astryx_prototype import illustration
    from services.html_exporter import generate_standalone_html
    from services.scorm_exporter import export_scorm_package
    from models import Project
    from test_astryx_prototype import expand_embedded
    from PIL import Image
    import zipfile
    options=normalize({'style':'editorial','palette':'rose','captions':True})
    monkeypatch.setattr(ai_agent,'_new_chat',lambda *a,**kw:pytest.fail('No paid calls for design'))
    sb=storyboard('Testes de aparência');before=copy.deepcopy(sb)
    course=await ai_agent.generate_course_from_storyboard('test',sb,{'title':'Testes de aparência','astryxAppearance':options},
        design_template_id='astryx',project_id='local-appearance',media_config={str(i):{'type':'gallery_image','galleryImageUrl':illustration()} if i==1 else {'type':'none'} for i in range(len(sb['slides']))})
    assert course['metadata']['astryxAppearance']==options and sb==before
    project={'id':'local-appearance','name':'Aparência','enableVlibras':False,'course':course}
    asset_dir=tmp_path/'local-appearance'/'assets'
    asset_dir.mkdir(parents=True)
    Image.new('RGB',(80,50),(80,120,200)).save(asset_dir/'docx_001_0123456789abcdef.png')
    question_bank=copy.deepcopy(course['quizQuestions'])
    standalone=await generate_standalone_html(project,str(asset_dir),questions=question_bank)
    assert 'astryx-appearance-v1' in expand_embedded(standalone)
    archive=export_scorm_package(Project(**project),str(tmp_path),str(tmp_path),questions=question_bank)
    with zipfile.ZipFile(archive) as z:
        saved=json.loads(z.read('course.json'))
        documents=[e['htmlContent'] for s in saved['slides'] for e in s['elements'] if e.get('astryxDesign')]
        assert documents and all('figcaption{display:block!important}' in d and '--ax-accent:#aa2853' in d for d in documents)
    assert question_bank==course['quizQuestions']


@pytest.mark.asyncio
async def test_routes_are_authorized_read_only_for_preview_and_cas_backed_up_for_apply(monkeypatch):
    from routes import projects_crud as r
    from services.agent_quality import fingerprint
    import services.layout_recovery as recovery
    project=fixture();before=copy.deepcopy(project)
    db=MagicMock();db.projects.find_one=AsyncMock(return_value=project)
    db.projects.update_one=AsyncMock(return_value=MagicMock(matched_count=1))
    auth=AsyncMock(return_value=project);backup=AsyncMock(return_value='backup')
    monkeypatch.setattr(r,'db',db);monkeypatch.setattr(r,'load_authorized_project',auth)
    monkeypatch.setattr(recovery,'backup_layout_source',backup)
    user={'role':'editor','user_id':'author','companyId':'company-a'}
    data=r.AstryxAppearanceRequest(appearance=Appearance(style='corporate',captions=True))
    preview=await r.astryx_project_preview('only-target',data,user)
    assert preview['totalSlides']==19 and len(preview['slides'])==3
    db.projects.update_one.assert_not_awaited();backup.assert_not_awaited()
    data.fingerprint=preview['fingerprint']
    out=await r.astryx_project_apply('only-target',data,user)
    assert out['backupId']=='backup'
    guard,operation=db.projects.update_one.await_args.args
    assert guard=={'id':'only-target','course':project['course'],'updatedAt':'old'}
    assert set(operation['$set'])=={*[f'course.slides.{i}.elements.0.htmlContent' for i in range(3)],'course.metadata.astryxAppearance','updatedAt'}
    assert project==before and data.fingerprint==fingerprint(project)
    auth.assert_awaited_with('only-target',user)


@pytest.mark.asyncio
async def test_apply_rejects_stale_preview_and_read_only_role(monkeypatch):
    from routes import projects_crud as r
    from fastapi import HTTPException
    project=fixture();db=MagicMock();db.projects.find_one=AsyncMock(return_value=project);db.projects.update_one=AsyncMock()
    monkeypatch.setattr(r,'db',db);monkeypatch.setattr(r,'load_authorized_project',AsyncMock(return_value=project))
    data=r.AstryxAppearanceRequest(appearance=Appearance(),fingerprint='stale')
    with pytest.raises(HTTPException) as stale:await r.astryx_project_apply('only-target',data,{'role':'editor'})
    assert stale.value.status_code==409
    with pytest.raises(HTTPException) as role:await r.astryx_project_preview('only-target',data,{'role':'approver'})
    assert role.value.status_code==403
    db.projects.update_one.assert_not_awaited()
