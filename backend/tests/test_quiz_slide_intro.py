import copy
import pytest
from services.ai_agent import DESIGN_TEMPLATES, _build_quiz_slide


@pytest.mark.parametrize('template', DESIGN_TEMPLATES, ids=lambda t: t['id'])
def test_quiz_intro_has_no_redundant_paragraph_or_overlapping_box(template):
    palette={**template['palette'], 'mode':template['mode'],
             'fontHeading':template['fonts']['heading'], 'fontBody':template['fonts']['body']}
    source={'title':'Quiz da unidade','notes':'Orientação ao instrutor'}
    before=copy.deepcopy(source)
    ids=['question-1','question-2','question-3']
    elements=_build_quiz_slide(source,palette,'Trabalho em Equipe',ids)
    intro=next(e for e in elements if 'Teste seus conhecimentos' in e.get('htmlContent',''))
    assert 'Hora de praticar' in intro['htmlContent']
    assert '<p' not in intro['htmlContent']
    assert 'Responda às perguntas' not in ''.join(e.get('htmlContent','') for e in elements)
    quiz=next(e for e in elements if e['type']=='quiz')
    assert intro['y']+intro['height'] < quiz['y']
    assert (quiz['x'],quiz['y'],quiz['width'],quiz['height'])==(260,280,1400,500)
    config=quiz['quizConfig']
    assert config['questionIds']==ids and config['questionCount']==3
    assert config['passingScore']==60.0 and config['maxAttempts']==0
    assert config['showFeedback'] and config['showExplanation']
    assert config['shuffleQuestions'] and config['shuffleAlternatives']
    assert source==before


def test_empty_question_list_does_not_add_placeholder_instructions():
    elements=_build_quiz_slide({}, {'accent':'#2563eb'}, 'Unidade', [])
    assert len(elements)==2
    assert all(e['type']=='html' for e in elements)
    assert 'Responda às perguntas' not in str(elements)
