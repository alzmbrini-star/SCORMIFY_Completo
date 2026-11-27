"""Frameless activity wrappers must keep content and progress semantics."""
import copy
import re
import pytest
from services.single_page_exporter import generate_single_page_html


@pytest.mark.parametrize('scorm_mode,preview_mode',[(False,False),(True,False),(False,True)])
def test_no_decorative_frame_but_content_and_tracking_remain(tmp_path,scorm_mode,preview_mode):
    project={'id':'frame-qa','name':'Sem moldura','enableVlibras':False,
             'course':{'metadata':{'title':'Sem moldura'},'slides':[
                 {'id':'slide-1','title':'Conteúdo preservado','elements':[
                     {'id':'html-1','type':'html','htmlContent':'<script>window.example=true</script><button>Praticar</button>',
                      'width':900,'height':600},
                     {'id':'audio-1','type':'audio','src':'data:audio/wav;base64,UklGRg=='},
                     {'id':'quiz-1','type':'quiz','quizConfig':{'title':'Quiz preservado','questionIds':['q1']}}
                 ]}]}}
    before=copy.deepcopy(project)
    output=generate_single_page_html(project,str(tmp_path),scorm_mode=scorm_mode,preview_mode=preview_mode)
    assert project==before
    base=re.search(r'\.sp-interactive\{([^}]+)\}',output)[1]
    assert 'background:transparent' in base and 'border:0' in base
    assert 'box-shadow:none' in base and 'padding:0' in base
    assert '#fef9c3' not in base and '#facc15' not in base
    assert '.sp-interactive{padding:16px}' not in output
    assert 'data-required="true"' in output and 'data-interactive="html"' in output
    assert 'data-interactive="audio"' in output and 'data-interactive="quiz"' in output
    assert 'Concluí' in output and 'Quiz preservado' in output
    assert 'data-completed="true"]::after' in output


def test_tutor_explains_frame_removal_without_course_mutation():
    from services.creator_guide import topics_for
    entry=next(t for t in topics_for({'role':'super_admin'}) if t['id']=='export')
    text=' '.join(entry['steps'])
    assert 'moldura amarela' in text and 'indicadores de conclusão' in text
