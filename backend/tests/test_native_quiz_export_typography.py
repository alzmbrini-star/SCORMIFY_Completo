import copy
from pathlib import Path
import pytest
from services.html_exporter import generate_html_template
from services.single_page_exporter import _render_quiz_element_inner

ASSETS=Path(__file__).resolve().parents[1]/'services/export_assets'

def test_html_embeds_shared_typography_and_binds_it_on_question_and_result():
    course={'slides':[{'id':'s','elements':[{'id':'q','type':'quiz','quizConfig':{'fontSize':20,'questionIds':['q1']}}]}],
            'questions':[{'id':'q1','text':'Conteúdo original','alternatives':[{'id':'a','text':'Resposta','isCorrect':True}]}]}
    original=copy.deepcopy(course)
    html=generate_html_template('Quiz',course,1920,1080,enable_vlibras=False)
    assert 'window.ScormifyQuizTypography = ' in html
    assert html.count('window.ScormifyQuizTypography.bind(container, quiz.config)')==2
    assert 'class="quiz-native-option-text"' in html and 'class="quiz-native-options"' in html
    assert course==original


def test_scorm_packages_same_typography_before_quiz_controller():
    exporter=(ASSETS.parent/'scorm_exporter.py').read_text(encoding='utf-8')
    assert '_read_asset("quiz-typography.js")' in exporter
    js=(ASSETS/'quiz-controller.js').read_text(encoding='utf-8')
    assert js.count('ScormifyQuizTypography.bind(container, quiz.config)')==2
    assert 'var altFontSize = baseFontSize;' in js
    assert 'var questionFontSize = baseFontSize * 1.125;' in js


@pytest.mark.parametrize('size,expected',[(20,'20'),(28,'28'),('20px','20'),(None,'16'),('bad','16'),(0,'16'),(500,'16')])
def test_single_page_honors_numeric_size_and_rejects_bad_values(size,expected):
    element={'quizConfig':{'fontSize':size,'questionIds':[]}}
    original=copy.deepcopy(element)
    output=_render_quiz_element_inner(element,0,0,{})
    assert f'--sp-quiz-font-size:{expected}px' in output
    assert element==original


def test_scoped_styles_preserve_question_hierarchy_and_mobile_wrapping():
    js=(ASSETS/'quiz-typography.js').read_text(encoding='utf-8')
    assert 'base * 1.125' in js and 'base + \'px\'' in js
    assert '@media(max-width:640px)' in js
    assert 'repeat(2,minmax(0,1fr))' in js
    assert '.quiz-player-container[data-quiz-typography="v1"]' in js


def test_tutor_describes_font_entry_export_preservation_and_reexport():
    from services.creator_guide import GUIDE
    text=' '.join(next(row for row in GUIDE if row['id']=='assessment-formats')['steps'])
    for value in ['Tamanho da fonte','1,125','Página Única','exportados novamente','Não há alteração de perguntas']:
        assert value in text
