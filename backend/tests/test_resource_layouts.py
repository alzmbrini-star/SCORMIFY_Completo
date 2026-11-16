import copy
import json
from unittest.mock import AsyncMock
import pytest
from bs4 import BeautifulSoup
from services.resource_layouts import prepare_resource_slide, render_layout, validate_layout, layout_ready, VERSION


@pytest.mark.parametrize('theme',['Qualificação e auditoria','Panificação artesanal','Manutenção de automóveis','Comunicação em equipe'])
def test_theme_independent_compilation_preserves_every_item_and_sizes(theme):
 raw={'kind':'cards','title':theme,'items':[{'front':f'{theme} — conceito {i}','back':f'Explicação completa {i}: '+('Texto importante. '*60).rstrip()} for i in range(17)]}
 slide={'type':'flashcard','resourceLayout':raw,'notes':'Não alterar','elements':[]};before=copy.deepcopy(slide)
 compiled=prepare_resource_slide(slide)
 assert compiled['resourceLayout']==raw|{'intro':''} and compiled['notes']=='Não alterar' and slide==before
 assert len(compiled['resourceLayout']['items'])==17 and layout_ready(compiled)
 element=compiled['elements'][0]
 assert (element['width'],element['height'],element['htmlDisplayMode'])==(1920,820,'page')
 doc=BeautifulSoup(element['htmlContent'],'html.parser')
 assert json.loads(doc.select_one('#resource-layout-data').string)['items']==raw['items']
 assert '#flashcards div' not in element['htmlContent'] and 'rotateY' not in element['htmlContent']


def test_known_nested_face_bug_is_rebuilt_without_losing_the_weights():
 source={'type':'reinforcement','title':'Critérios','elements':[{'type':'html','htmlContent':"<style>#flashcards div{width:200px;height:150px;display:flex}</style><div id='flashcards'><div onclick='flipCard(this)'><div class='front'>Coerência do plano</div><div class='back'>25%</div></div><div><div class='front'>Rastreabilidade</div><div class='back'>75%</div></div></div>"}]}
 out=prepare_resource_slide(source)
 assert out['resourceLayout']['items']==[{'front':'Coerência do plano','back':'25%'},{'front':'Rastreabilidade','back':'75%'}]
 assert layout_ready(out) and source['elements'][0]['htmlContent'].startswith('<style>')


@pytest.mark.parametrize('kind',['quiz','interactive_assessment','simulator','scenario','game'])
def test_other_engines_and_questions_are_never_converted(kind):
 slide={'type':kind,'elements':[{'type':'quiz' if kind=='quiz' else 'html','quizConfig':{'questionIds':['old']},'assessmentConfig':{'questions':[{'id':'q','media':{'url':'saved.png'}}]},'htmlContent':'Original'}]}
 before=copy.deepcopy(slide);assert prepare_resource_slide(slide)==before and slide==before


def test_empty_fragment_is_not_visual_validation_and_tampering_blocks_readiness():
 assert not layout_ready({'type':'reinforcement','elements':[{'htmlContent':'<p>Algum texto</p>'}]})
 with pytest.raises(ValueError):prepare_resource_slide({'type':'reinforcement','elements':[]})
 out=prepare_resource_slide({'type':'narration','title':'Explicação','elements':[{'htmlContent':'<h2>Explicação</h2><p>Texto original completo.</p>'}]})
 assert layout_ready(out)
 out['elements'][0]['htmlContent']='<p>Pequeno e vazio</p>'
 assert not layout_ready(out)


def test_code_examples_are_preserved_as_text_and_cannot_close_json_script():
 raw={'kind':'cards','title':'Programação','items':[{'front':'Comentários e scripts','back':'/* exemplo didático */ </script><script>alert(1)</script>'}]}
 document=render_layout(raw);soup=BeautifulSoup(document,'html.parser')
 assert len(soup.find_all('script'))==2
 assert json.loads(soup.select_one('#resource-layout-data').string)['items']==raw['items']


def test_apply_uses_same_full_slide_document_and_preserves_page_mode():
 from test_gamma_course_analysis import route_helpers
 slide=prepare_resource_slide({'type':'visual_summary','resourceLayout':{'kind':'flow','title':'Processo','items':[{'front':'Etapa A','back':'Detalhe completo.'}]}})
 element=route_helpers()._build_improved_elements(slide['elements'],lambda:'new')[0]
 assert element['htmlContent']==slide['elements'][0]['htmlContent']
 assert (element['x'],element['y'],element['width'],element['height'],element['htmlDisplayMode'])==(0,0,1920,820,'page')


@pytest.mark.asyncio
async def test_compatible_previous_resource_reuses_text_without_ai_or_course_writes():
 from services.improvement_preview import complete_preview
 project={'id':'p','source':'gamma','course':{'slides':[{'id':'s','gammaSource':{'elementId':'bg'}}]}}
 previous={'newSlides':[{'type':'narration','afterIndex':0,'title':'Explicação','elements':[{'type':'html','htmlContent':'<h2>Explicação</h2><p>Texto integral a preservar.</p>'}]}]}
 before=copy.deepcopy((project,previous));generate=AsyncMock()
 result,info=await complete_preview(project,[{'slideIndex':0,'type':'narration'}],previous,generate)
 generate.assert_not_awaited();assert info['complete'] and info['layout']['ready']==1
 assert (project,previous)==before and 'Texto integral a preservar.' in result['newSlides'][0]['elements'][0]['htmlContent']


def test_storyboard_and_final_generation_skip_old_shrink_wrapper():
 from services.ai_agent import _normalize_interactive_storyboard_slide,_wrap_interactive_fullbleed,_interactive_html_is_functional
 slide={'type':'flashcard','resourceLayout':{'kind':'cards','title':'Tema','items':[{'front':'Pergunta','back':'Explicação'}]}}
 normalized=_normalize_interactive_storyboard_slide(slide)
 doc=normalized['elements'][0]['htmlContent'];assert _interactive_html_is_functional(doc,'flashcard')
 assert _wrap_interactive_fullbleed(doc)==doc and '__scormify_fit' not in doc
 assert "className='resource-'+data.kind" in doc
 assert prepare_resource_slide(normalized)==normalized


def test_incomplete_layout_is_counted_as_pending_and_never_complete():
 from services.improvement_preview import coverage
 selection=[{'slideIndex':0,'type':'reinforcement'}]
 status=coverage({'newSlides':[]},selection)
 assert status['layout']=={'total':1,'ready':0,'method':'controlled-template'} and not status['complete']


def test_tutor_explains_scope_validation_limits_no_credits_or_retroactive_edits():
 from services.creator_guide import GUIDE
 text=' '.join(next(x for x in GUIDE if x['id']=='agent-resource-layout')['steps'])
 for phrase in ['qualquer','Quiz tradicional','Avaliação interativa com imagens','não reescreve cursos','HTML/SCORM','não gera imagens','Não é uma auditoria']:
  if phrase=='qualquer':assert 'independentemente do assunto' in text
  else:assert phrase in text
