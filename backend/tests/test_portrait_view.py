"""Portrait export is a presentation-only enhancement, never a course rewrite."""
import ast
import copy
import re
from pathlib import Path
import pytest
from services.portrait_view import install_portrait_view
from services.single_page_exporter import generate_single_page_html
from services.html_exporter import generate_html_template
from services.scorm_exporter import _build_html

ROOT=Path(__file__).resolve().parents[1]

def fixture():
    return {'id':'portrait-check','name':'Visualização em retrato','enableVlibras':False,'course':{'metadata':{'title':'Teste'},'slides':[
        {'id':'original','title':'Imagem inteira','width':1280,'height':720,'gammaSource':True,
         'backgroundImage':'data:image/svg+xml;base64,PHN2Zy8+', 'notes':'Nota original',
         'elements':[{'id':'link','type':'text','content':'Conteúdo original','x':320,'y':360,'width':640,'height':100}]},
        {'id':'quiz','title':'Quiz tradicional','width':1280,'height':720,'elements':[
            {'id':'q','type':'quiz','quizConfig':{'title':'Quiz preservado','questionIds':['question'],'passingScore':70}}]},
        {'id':'assessment','title':'Avaliação visual','elements':[{'id':'interactive','type':'html',
          'htmlContent':'<html><body><img src="data:image/svg+xml;base64,PHN2Zy8+" alt="Apoio"><button onclick="this.textContent=\'Respondido\'">Responder</button></body></html>'}]}
    ]}}

@pytest.mark.parametrize('scorm',[False,True])
def test_singlepage_preserves_source_questions_images_coordinates(scorm):
    project=fixture();before=copy.deepcopy(project)
    questions=[{'id':'question','text':'Qual a finalidade?','alternatives':[{'text':'Aprender','isCorrect':True},{'text':'Ignorar','isCorrect':False}],'explanation':'Explicação original'}]
    html=generate_single_page_html(project,'/none',questions=questions,scorm_mode=scorm)
    assert project==before
    sections=re.findall(r'<section class="([^"]*)" data-index="\d+"',html)
    assert len([s for s in sections if 'sp-end-card' not in s])==3
    assert 'aspect-ratio:1280/720' in html and 'left:25.00%' in html and 'top:50.00%' in html
    assert 'Qual a finalidade?' in html and 'Explicação original' in html
    assert 'data:text/html;charset=utf-8;base64' in html
    assert 'data:image/svg+xml;base64,PHN2Zy8+' in html
    assert html.count('id="course-portrait-support"')==1
    assert 'min-height:520px' not in html
    assert ('SCORM' in html) if scorm else True

def test_injection_shared_by_traditional_html_and_scorm_and_idempotent():
    document=generate_html_template('Curso',fixture()['course'],1280,720,enable_vlibras=False)
    scorm=_build_html('Curso','pt-BR',1280,720,enable_vlibras=False)
    for html in [document,scorm]:
        assert html.count('id="course-portrait-support"')==1
        assert 'object-fit:contain!important' in html
        assert 'course-image-dialog' in html and 'Ampliar imagem' in html
        assert install_portrait_view(html)==html

def test_viewer_does_not_complete_activities_or_rewrite_data():
    script=(ROOT/'services/export_assets/portrait-view.js').read_text(encoding='utf-8')
    assert 'SP.mark' not in script and 'LMSSetValue' not in script and 'fetch(' not in script
    assert 'showModal()' in script and "viewer.close()" in script and 'lastFocus.focus()' in script
    assert 'stopPropagation' in script and 'data-locked' in script

def test_support_script_is_not_inserted_into_authored_html_json():
    original='<html><head></head><body><script>const course={"htmlContent":"<body>original</body>"};</script></body></html>'
    result=install_portrait_view(original)
    assert '"htmlContent":"<body>original</body>"' in result
    assert result.index('var viewer,pan,picture,lastFocus')>result.index('const course=')

def test_preview_route_is_owned_snapshot_background_job_without_course_writes():
    tree=ast.parse((ROOT/'routes/export.py').read_text(encoding='utf-8'))
    node=next(n for n in ast.walk(tree) if isinstance(n,ast.AsyncFunctionDef) and n.name=='start_singlepage_preview')
    source=ast.unparse(node)
    for required in ['require_auth','load_authorized_project','copy.deepcopy','guidedPath','companyId','userId','asyncio.create_task','_run_html_export_job','create_job']:
        assert required in source
    assert not re.search(r'(update_one|replace_one|delete_one|insert_one)',source)
    legacy=next(n for n in ast.walk(tree) if isinstance(n,ast.AsyncFunctionDef) and n.name=='preview_singlepage')
    assert 'await asyncio.to_thread(generate_single_page_html' in ast.unparse(legacy)

def test_tutor_explains_saved_preview_portrait_and_reexport():
    from services.creator_guide import GUIDE
    text=str(GUIDE)
    for token in ['segundo plano','Ampliar imagem','Reexporte HTML/ZIP','não têm seus textos internos']:
        assert token in text
