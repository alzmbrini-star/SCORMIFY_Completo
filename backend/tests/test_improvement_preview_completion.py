import copy
from unittest.mock import AsyncMock
import pytest
from services.improvement_preview import complete_preview,coverage,signature

def setup():
 kinds=['interactive_assessment','visual_summary','interactive_assessment','reinforcement','narration','reinforcement','scenario']
 indices=[0,3,6,9,13,16,18]
 project={'id':'p','source':'gamma','course':{'slides':[{'id':str(i),'gammaSource':{'elementId':str(i)}} for i in range(19)]}}
 selected=[{'slideIndex':i,'type':t,'description':f'Objetivo {i}','suggestion':'Proposta'} for i,t in zip(indices,kinds)]
 def slide(item):
  row={'afterIndex':item['slideIndex'],'type':item['type'],'title':item['description'],'elements':[{'type':'html','htmlContent':'<h2>Conteúdo válido</h2>'}]}
  if item['type']=='interactive_assessment':
   row['elements'][0]['assessmentConfig']={'questions':[{'id':'q','prompt':'Preservar pergunta','correctAnswer':'A','media':{'url':'/api/projects/p/assets/saved.png'}}]}
   row['elements'][0]['agentAssessment']={'imagesEnabled':True}
  if item['type']=='scenario':row.update(elements=[],scenarioConfig={'theme':'Aplicação','objectives':'Planejar'})
  if item['type'] in ('reinforcement','visual_summary','narration'):
   from services.resource_layouts import prepare_resource_slide
   row['resourceLayout']={'kind':'note' if item['type']=='narration' else 'flow' if item['type']=='visual_summary' else 'cards','title':row['title'],'items':[{'front':'Conceito','back':'Explicação didática completa.'}]}
   row=prepare_resource_slide(row)
  return row
 return project,selected,slide

@pytest.mark.asyncio
async def test_reuses_four_valid_resources_and_generates_exactly_three_missing_without_course_mutation():
 p,selected,slide=setup();old={'newSlides':[slide(i) for i in selected[:4]]};before=copy.deepcopy((p,old))
 generate=AsyncMock(side_effect=lambda i:{'newSlides':[slide(i)]})
 result,info=await complete_preview(p,selected,old,generate)
 assert info['expected']==7 and info['ready']==7 and info['complete'] and info['reusedCount']==4 and info['generatedCount']==3
 assert generate.await_count==3 and {c.args[0]['slideIndex'] for c in generate.call_args_list}=={13,16,18}
 assert result['newSlides'][:4]==old['newSlides'] and (p,old)==before
 assert result['updatedSlides']==[]

@pytest.mark.asyncio
async def test_missing_items_never_report_complete_and_valid_work_is_not_rebilled_on_retry():
 p,s,slide=setup();old={'newSlides':[slide(i) for i in s[:4]]};generate=AsyncMock(return_value={'newSlides':[]})
 result,info=await complete_preview(p,s,old,generate)
 assert not info['complete'] and info['ready']==4 and generate.await_count==6
 retry=AsyncMock(side_effect=lambda i:{'newSlides':[slide(i)]})
 finished,again=await complete_preview(p,s,result,retry)
 assert again['complete'] and again['reusedCount']==4 and retry.await_count==3

@pytest.mark.asyncio
async def test_changed_request_or_wrong_origin_not_reused_and_duplicate_output_not_accepted():
 p,s,slide=setup();oldslide=slide(s[0]);oldslide['requestSignature']=signature({**s[0],'suggestion':'Outra proposta'})
 generate=AsyncMock(return_value={'newSlides':[]})
 result,info=await complete_preview(p,s,{'newSlides':[oldslide]},generate)
 assert info['ready']==0 and not info['complete']
 assert not coverage({'newSlides':[{'afterIndex':0,'type':'quiz','elements':[]}]},s)['complete']

def test_tutor_explains_scripts_isolation_no_grades_and_partial_reuse():
 from services.creator_guide import GUIDE
 text=' '.join(next(x for x in GUIDE if x['id']=='course-preview-completion')['steps'])
 assert 'origem isolada' in text and 'não registra notas' in text and 'ausentes' in text
