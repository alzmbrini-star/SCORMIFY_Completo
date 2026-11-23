import copy
from pathlib import Path
from services.assessment_renderer import assessment_element, refresh_assessment_documents
from services.single_page_exporter import generate_single_page_html
from services.html_exporter import generate_html_template

ROOT = Path(__file__).resolve().parents[2]
CONFIG = {'enabled': True, 'badges': [], 'quizFeedbackRanges': []}

def project():
    question = {'id':'q1','title':'Pergunta','prompt':'Texto original','type':'single_choice','points':3,
                'options':[{'id':'a','text':'Sim','isCorrect':True}],
                'media':{'kind':'image','url':'data:image/png;base64,aGVsbG8=','name':'Captura'}}
    return {'id':'p1','name':'Curso','course':{'slides':[{'id':'s1','title':'Avaliação',
        'notes':'Notas intactas','elements':[assessment_element([question])]}]}}

def test_shared_runtime_matches_template():
    source=(ROOT/'frontend/src/components/assessment/assessmentRuntime.js').read_text(encoding='utf-8')
    body=source[source.index('export function '):].replace('export function ', 'function ',1).strip()
    template=(ROOT/'backend/services/export_assets/assessment-player.html').read_text(encoding='utf-8')
    assert body in template

def test_saved_assessment_refresh_preserves_questions_images_and_notes():
    saved=project();before=copy.deepcopy(saved)
    refresh_assessment_documents(saved)
    element=saved['course']['slides'][0]['elements'][0]
    assert element['assessmentConfig']==before['course']['slides'][0]['elements'][0]['assessmentConfig']
    assert saved['course']['slides'][0]['notes']=='Notas intactas'
    assert 'scormify-assessment-gamification' in element['htmlContent']

def test_single_page_export_marks_controlled_frames_and_includes_engine(tmp_path):
    saved=project();before=copy.deepcopy(saved)
    html=generate_single_page_html(saved,str(tmp_path),'',gamification_config=CONFIG)
    assert 'data-assessment="true"' in html
    assert 'scormify-assessment-gamification' in html
    assert saved==before

def test_traditional_html_includes_enabled_engine_and_respects_disabled():
    for enabled in (True,False):
        html=generate_html_template('Curso',{'slides':[],'metadata':{},'_gamification':dict(CONFIG,enabled=enabled)},960,540,False)
        assert ('var Gamification = (function()' in html)==enabled
        assert 'data-assessment="true"' in html

def test_scorm_package_keeps_assessment_and_shared_gamification(tmp_path):
    import json, zipfile
    from models import Project
    from services.scorm_exporter import export_scorm_package
    saved=project();before=copy.deepcopy(saved)
    archive=export_scorm_package(Project(**saved),str(tmp_path),str(tmp_path),gamification_config=CONFIG)
    with zipfile.ZipFile(archive) as z:
        assert 'scormify-assessment-gamification' in z.read('scripts/gamification.js').decode()
        assert "htmlIframe.dataset.assessment = 'true'" in z.read('scripts/player.js').decode()
        course=json.loads(z.read('course.json'))
        exported=course['slides'][0]['elements'][0]['assessmentConfig']['questions']
        assert z.read(exported[0]['media']['url'])==b'hello'
        exported[0]['media']['url']=saved['course']['slides'][0]['elements'][0]['assessmentConfig']['questions'][0]['media']['url']
        assert exported==saved['course']['slides'][0]['elements'][0]['assessmentConfig']['questions']
    assert saved==before
