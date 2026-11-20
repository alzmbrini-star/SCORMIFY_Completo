import base64
import copy
import json
import re
import zipfile
from unittest.mock import AsyncMock

import pytest
from services.astryx_agent import TEMPLATE, build_elements, compatible, safe_url, lesson_styles
from services.astryx_prototype import assets, illustration
from services import ai_agent


THEMES = ['Astronomia: explorando o céu', 'Atendimento e escuta do cliente', 'Manutenção de bicicletas']


def storyboard(title):
    return {'sourceCoverage': {'status':'complete','units':3}, 'slides': [
        {'type':'title','title':'Capa','moduleName':'Fundamentos','notes':'Nota original da capa',
         'elements':[{'type':'text','content':f'<p>Apresentação completa de {title}.</p>'}]},
        {'type':'content','title':f'Fundamentos de {title}','moduleName':'Fundamentos','sourceRefs':['u1:t1'],
         'notes':'Notas preservadas','librasScript':'Roteiro original',
         'elements':[{'type':'text','content': '<p>Primeiro parágrafo completo com informações para compreender o assunto e suas relações.</p><ul><li>Etapa original A</li><li>Etapa original B</li></ul>'},
                     {'type':'html','htmlContent':'<table><tr><th>Critério</th><th>Procedimento</th></tr><tr><td>Verificação</td><td>Seguir as etapas ensinadas</td></tr></table><p>Último parágrafo obrigatório, não pode ser ignorado.</p>'}]},
        {'type':'quiz','title':'Quiz tradicional','moduleName':'Fundamentos','quizQuestions':[
            {'text':'Qual procedimento foi apresentado?','alternatives':[{'text':'Seguir as etapas ensinadas','isCorrect':True},{'text':'Ignorar as etapas','isCorrect':False}],'explanation':'Use os critérios da explicação.'}]},
        {'type':'interactive_assessment','title':'Avaliação ilustrada','moduleName':'Prática','assessmentRequest':{'questionCount':1,'images':True},'assessmentActivity':{
            'title':'Avaliação ilustrada','instructions':'Responda com base na explicação.','imagesEnabled':True,'questions':[{
                'id':'illustrated-question','type':'single_choice','title':'Observe o exemplo','prompt':'Qual ação está alinhada ao conteúdo?',
                'options':['Seguir os critérios','Ignorar os critérios'],'correct':0,'explanation':'Os critérios orientam a execução.',
                'media':{'type':'image','url':illustration(),'alt':'Ilustração original da avaliação'}}]}},
        {'type':'content','title':'Captura original','moduleName':'Prática','sourceImageOnly':True,
         'sourceImage':'docx_001_0123456789abcdef.png','purpose':'Observe a captura sem redesenhá-la.'},
        {'type':'summary','title':'Síntese do aprendizado','moduleName':'Conclusão','elements':[
            {'type':'text','content':'<p>Resumo completo da explicação.</p><ol><li>Revise os conceitos</li><li>Aplique o procedimento</li></ol>'}]},
    ]}


async def compile_course(title, mode='standard', font='100'):
    sb = storyboard(title)
    return await ai_agent.generate_course_from_storyboard('local-test', sb,
        {'title':title,'visualCourseMode':mode}, project_id='astryx-local-only',
        design_template_id='astryx', global_font_size=font,
        media_config={str(i):{'type':'gallery_image','galleryImageUrl':illustration()} if i==1 else {'type':'none'} for i in range(len(sb['slides']))})


def test_astryx_is_explicit_creation_only_not_random_or_existing_theme():
    old = ai_agent.get_design_templates()
    assert len(old) == 6 and all(t['id'] != 'astryx' for t in old)
    assert len(ai_agent._COURSE_PALETTES) == 6
    assert ai_agent.get_design_template_by_id('astryx') == TEMPLATE
    new = ai_agent.get_design_templates(True)
    assert len(new) == 7 and new[-1]['creationOnly'] is True
    assert old == new[:-1]


@pytest.mark.parametrize('title', THEMES)
@pytest.mark.parametrize('mode', ['standard','illustrated_journey','guided_practice_project'])
@pytest.mark.asyncio
async def test_generic_compilation_keeps_lessons_and_both_assessment_engines(title, mode, monkeypatch):
    monkeypatch.setattr(ai_agent, '_new_chat', lambda *a,**k: pytest.fail('Layout composition must not call paid AI'))
    sb = storyboard(title)
    before = copy.deepcopy(sb)
    result = await ai_agent.generate_course_from_storyboard('test',sb,{'title':title,'visualCourseMode':mode},
        design_template_id='astryx',project_id='local-course',
        media_config={str(i):{'type':'gallery_image','galleryImageUrl':illustration()} if i==1 else {'type':'none'} for i in range(len(sb['slides']))})
    assert len(result['slides']) == 7  # six source slides, plus existing automatic module map
    assert sb == before
    assert result['metadata']['sourceCoverage'] == sb['sourceCoverage']
    assert result['metadata']['visualCourseMode'] == mode
    assert result['metadata']['designTemplateId'] == 'astryx'
    assert result['slides'][0]['title'] == title
    assert title in result['slides'][0]['elements'][0]['astryxTeachingText']
    lesson = next(s for s in result['slides'] if s['title'].startswith('Fundamentos de'))
    assert lesson['notes'] == 'Notas preservadas' and lesson['sourceRefs'] == ['u1:t1']
    assert lesson['librasScript'] == 'Roteiro original'
    document = lesson['elements'][0]['htmlContent']
    for text in ['Etapa original A','Etapa original B','Critério','Seguir as etapas ensinadas','Último parágrafo obrigatório']:
        assert text in document
    assert lesson_styles() in document and '<table>' in document and illustration() in document
    assert 'Trabalho em equipe: juntos fazemos melhor' not in document
    quiz = next(s for s in result['slides'] if s['contentType'] == 'quiz')
    native = next(e for e in quiz['elements'] if e['type'] == 'quiz')
    assert native['quizConfig']['questionIds'] == [result['quizQuestions'][0]['id']]
    assert result['quizQuestions'][0]['text'] == 'Qual procedimento foi apresentado?'
    assessment = next(e for s in result['slides'] for e in s['elements'] if e.get('assessmentConfig'))
    assert assessment['assessmentConfig']['questions'] == sb['slides'][3]['assessmentActivity']['questions']
    assert not assessment.get('astryxDesign')
    capture = next(s for s in result['slides'] if s.get('sourceImageOnly'))
    assert any(e.get('sourceDocumentImage') for e in capture['elements'])
    assert not any(e.get('astryxDesign') for e in capture['elements'])


def test_semantic_copy_retains_text_code_tables_images_and_escapes_attributes():
    slide={'title':'Especial <teste>','elements':[{'content':'<p style="font-size:90px">Texto &amp; <strong>ênfase</strong></p><pre><code>x &lt; 3</code></pre><img onerror="bad()" src="/api/projects/p/assets/source.png" alt="Captura &quot;original&quot;">'}]}
    result=build_elements(slide,TEMPLATE['palette'])[0]
    document=result['htmlContent']
    assert '<pre><code>x &lt; 3</code></pre>' in document
    assert 'Captura &quot;original&quot;' in document
    assert 'Especial &lt;teste&gt;' in document
    assert 'onerror=' not in document and 'font-size:90px' not in document
    assert 'Texto & ênfase' in result['astryxTeachingText']


@pytest.mark.parametrize('raw',['<button>Atividade</button><script>run()</script>','<iframe src="/app"></iframe>','<svg><text>Diagrama</text></svg>'])
def test_authored_apps_are_not_flattened_by_astryx(raw):
    slide={'type':'content','elements':[{'type':'html','htmlContent':raw}]}
    assert not compatible(slide)
    assert build_elements(slide,TEMPLATE['palette']) is None


@pytest.mark.parametrize('url',['javascript:alert(1)','file:///secret','https://[invalid','data:text/html;base64,PGgxPg=='])
def test_unsafe_urls_rejected(url):
    assert safe_url(url) == ''


@pytest.mark.asyncio
async def test_small_font_request_does_not_rewrite_vendor_css_or_mobile_minimum():
    result=await compile_course('Tipos e medidas',font='60')
    for s in result['slides']:
        for e in s['elements']:
            if e.get('astryxDesign'):
                assert lesson_styles() in e['htmlContent']
                assert 'font-size:17px' in e['htmlContent']


@pytest.mark.asyncio
async def test_existing_course_conversion_rejected_without_writes(monkeypatch):
    from routes import projects_crud as routes
    from fastapi import HTTPException
    monkeypatch.setattr(routes,'load_authorized_project',AsyncMock(return_value={'id':'original','course':{'slides':[]}}))
    with pytest.raises(HTTPException) as error:
        await routes.apply_design_template_to_project('original',{'designTemplateId':'astryx'}, {'role':'super_admin'})
    assert error.value.status_code == 422
    from routes.agent import _apply_design_token_to_slide
    slide={'id':'original','elements':[{'type':'quiz','quizConfig':{'questionIds':['q1']}}]}
    before=copy.deepcopy(slide)
    _apply_design_token_to_slide(slide,TEMPLATE)
    assert slide == before


@pytest.mark.asyncio
async def test_real_exports_keep_mixed_players_original_images_and_css(tmp_path):
    from models import Project
    from services.html_exporter import generate_standalone_html
    from services.scorm_exporter import export_scorm_package
    from services.single_page_exporter import generate_single_page_html
    course=await compile_course('Astronomia')
    p={'id':'astryx-local-only','name':'Astryx','enableVlibras':False,'course':course}
    asset_dir=tmp_path/'astryx-local-only'/'assets'
    asset_dir.mkdir(parents=True)
    from PIL import Image
    Image.new('RGB',(80,50),(80,120,200)).save(asset_dir/'docx_001_0123456789abcdef.png')
    before=copy.deepcopy(p)
    output=await generate_standalone_html(p,str(asset_dir),questions=course['quizQuestions'])
    assert 'astryx-agent-host' in output and 'astryx-mobile-stage' in output
    decoded=[base64.b64decode(x).decode() for x in re.findall(r'__B64__:([A-Za-z0-9+/=]+)',output)]
    assert sum('data-astryx-lesson=' in s for s in decoded) == 4
    assert all(lesson_styles() in s for s in decoded if 'data-astryx-lesson=' in s)
    archive=export_scorm_package(Project(**p),str(tmp_path),str(tmp_path),questions=course['quizQuestions'])
    with zipfile.ZipFile(archive) as z:
        data=json.loads(z.read('course.json'))
        assert len(data['slides']) == 7
        assert 'astryx-agent-host' in z.read('index.html').decode()
        assert any(e.get('assessmentConfig') for s in data['slides'] for e in s['elements'])
        assert any(e.get('type') == 'quiz' for s in data['slides'] for e in s['elements'])
    single=generate_single_page_html(p,str(asset_dir),questions=course['quizQuestions'])
    docs=[base64.b64decode(x).decode() for x in re.findall(r'data:text/html;(?:charset=utf-8;)?base64,([A-Za-z0-9+/=]+)',single)]
    assert any('data-astryx-lesson=' in d and lesson_styles() in d for d in docs)
    assert p == before


def test_tutor_explains_new_generation_costs_and_preservation():
    from services.creator_guide import GUIDE
    entry=next(t for t in GUIDE if t['id']=='astryx-agent-design')
    text=' '.join(entry['steps'])
    for word in ['Tema Visual','Mídia','qualquer tema','Quiz tradicional','Avaliação interativa','créditos','Nenhum curso salvo','HTML/SCORM']:
        assert word in text


def test_long_courses_do_not_repeat_the_entire_component_library():
    assert len(lesson_styles().encode()) < 45000
    element=build_elements({'title':'Conceito','elements':[{'content':'<p>Explicação completa do assunto.</p>'}]},TEMPLATE['palette'])[0]
    # MongoDB documents have a 16 MiB ceiling. The design itself must leave
    # ample room for source text, resources and references in long courses.
    course={'slides':[{'id':str(i),'elements':[element]} for i in range(200)]}
    assert len(json.dumps(course,ensure_ascii=False).encode()) < 8*1024*1024


def test_pdf_images_stay_in_flow_without_covering_or_shrinking_teaching_copy():
    from services.pdf_extractor import replace_img_markers_in_slides, _insert_image_on_slide
    sb={'title':'Material original','type':'content','elements':[{'content':'<p>Explicação completa.</p>[IMG:pdf_p1_img1.png]'}]}
    slide={'title':'Material original','elements':build_elements(sb,TEMPLATE['palette'])}
    count=replace_img_markers_in_slides([slide],'p',{'pdf_p1_img1.png'}, {'pdf_p1_img1.png':{'included':True,'caption':'Captura <original>'}})
    assert count == 1
    assert len(slide['elements']) == 1 and slide['elements'][0]['width'] == 1920
    doc=slide['elements'][0]['htmlContent']
    assert 'Explicação completa.' in doc
    assert 'src="/api/projects/p/assets/pdf_p1_img1.png"' in doc
    assert 'Captura &lt;original&gt;' in doc
    assert '[IMG:pdf_p1_img1.png]' not in doc
    _insert_image_on_slide(slide,'p','pdf_p1_img1.png','Captura <original>')
    assert slide['elements'][0]['htmlContent'].count('src="/api/projects/p/assets/pdf_p1_img1.png"') == 1
    # The pre-existing path remains native and retains its original geometry.
    native={'elements':[{'type':'html','width':1280,'x':120,'htmlContent':'Texto original'}]}
    _insert_image_on_slide(native,'p','pdf_p1_img1.png','Captura')
    assert native['elements'][0]['width'] == 1050
    assert any(e['type']=='image' and e['src'].endswith('pdf_p1_img1.png') for e in native['elements'])


def test_reading_and_narration_use_current_copy_after_manual_edits_not_css_or_stale_metadata():
    from services.astryx_agent import teaching_text
    element=build_elements({'title':'Título','elements':[{'content':'<p>Explicação original</p><pre><code>x &lt; 3</code></pre>'}]},TEMPLATE['palette'])[0]
    element['htmlContent']=element['htmlContent'].replace('Explicação original','Explicação revisada')
    text=teaching_text(element)
    assert 'Explicação revisada' in text and 'Explicação original' not in text
    assert 'x < 3' in text and '--color' not in text and 'MIT License' not in text
