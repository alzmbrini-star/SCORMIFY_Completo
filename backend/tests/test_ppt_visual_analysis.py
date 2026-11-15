import copy
import io
from unittest.mock import AsyncMock, patch
import pytest
from PIL import Image
from services import gamma_course_analysis as g
from test_gamma_course_analysis import database,response,route_helpers


def ppt():
 return {'id':'p','source':'ppt','updatedAt':'revision','course':{'slides':[
  {'id':'s1','title':'Distância segura','order':0,'backgroundImage':'/api/projects/p/assets/slide_001.png','width':1920,'height':1080,
   'extractedText':'Aumentar distância na chuva.','notes':'Preserve notas originais', 'audio':[{'id':'audio'}], 'annotations':[{'id':'mark'}],
   'elements':[{'id':'original-quiz','type':'html','htmlContent':'ORIGINAL HTML','assessmentConfig':{'questions':[{'id':'q','prompt':'Questão já criada'}]}}]},
  {'id':'s2','title':'Revisão','order':1,'extractedText':'Revise os pneus antes de viajar.','elements':[{'id':'t','type':'text','content':'<b>Calibragem</b>'}]}]}}


@pytest.mark.asyncio
async def test_ppt_reads_full_background_and_combines_extracted_text_notes_and_interactions():
 p=ppt();before=copy.deepcopy(p);db=database();send=AsyncMock(return_value=response())
 result=await g.analyze(p,db,'unused',send=send)
 assert p==before
 assert result['visualAnalysis']['provider']=='PPT'
 assert result['visualAnalysis']['visualSlides']==1 and result['visualAnalysis']['textOnlySlides']==1
 assert [x['slideIndex'] for x in result['improvements']]==[0,1]
 visual=next(call for call in send.call_args_list if call.args[1])
 for text in ['Aumentar distância na chuva.','Preserve notas originais','Questão já criada']:
  assert text in visual.args[0]
 assert Image.open(io.BytesIO(visual.args[1])).format=='JPEG'
 db.gamma_generations.find_one.assert_not_called()
 assert db.project_assets.find_one.call_args.args[0]=={'project_id':'p','filename':'slide_001.png'}


@pytest.mark.asyncio
async def test_missing_image_uses_known_text_without_claiming_vision_and_retries_explicitly():
 p=ppt();db=database();send=AsyncMock(return_value=response())
 with patch.object(g,'load_picture',side_effect=ValueError('missing')):
  first=await g.analyze(p,db,'unused',send=send)
 assert first['visualAnalysis']['visualSlides']==0
 assert first['visualAnalysis']['textOnlySlides']==2
 assert all(c.args[1] is None for c in send.call_args_list)
 db.course_visual_analysis.find_one.return_value={'result':first}
 retry=AsyncMock(return_value=response());second=await g.analyze(p,db,'unused',send=retry)
 assert second['visualAnalysis']['visualSlides']==1
 retry.assert_awaited_once()  # Real text-only slide stays cached; only missing image is retried.


@pytest.mark.asyncio
async def test_image_only_ppt_is_read_without_inventing_original_source():
 p=ppt();p['course']['slides']=p['course']['slides'][:1]
 p['course']['slides'][0].update(extractedText=None,notes=None,elements=[])
 result=await g.analyze(p,database(),'unused',send=AsyncMock(return_value=response()))
 assert result['visualAnalysis']['visualSlides']==1
 assert not result['visualAnalysis']['sourceAvailable']
 assert 'não estão disponíveis' in result['missingElements'][0]


@pytest.mark.asyncio
async def test_unreadable_ppt_has_no_invented_suggestions():
 result=await g.analyze(ppt(),database(),'unused',send=AsyncMock(return_value={'readable':False}))
 assert result['improvements']==[] and result['visualAnalysis']['readSlides']==0


def test_ppt_apply_is_additive_and_preserves_every_existing_field():
 p=ppt();before=copy.deepcopy(p['course']['slides'])
 result={'updatedSlides':[{'slideIndex':0,'title':'Do not replace','notes':'Do not replace','elements':[{'type':'text','content':'Complemento'}]}]}
 route_helpers()._apply_ai_result_to_slides(p['course']['slides'],result,lambda:'new',p)
 assert len(p['course']['slides'])==3
 for original in before:
  current=next(s for s in p['course']['slides'] if s['id']==original['id'])
  assert {k:v for k,v in current.items() if k!='order'}=={k:v for k,v in original.items() if k!='order'}


@pytest.mark.parametrize('source',[None,'imported','duplicate'])
def test_legacy_ppt_detected_without_widening_manual_or_agent(source):
 p=ppt();p['source']=source
 assert g.is_visual_project(p)
 p['source']='manual';assert not g.is_visual_project(p)
 p['source']=source;p['createdByAgent']=True;assert not g.is_visual_project(p)


def test_editable_image_objects_are_composed_only_from_this_projects_assets():
 p=ppt();s=p['course']['slides'][1];s['elements'].append({'id':'img','type':'image','src':'/api/projects/p/assets/detail.png','x':100,'y':60,'width':200,'height':100})
 picture=g.load_picture(p,s,database(),'unused')
 assert Image.open(io.BytesIO(picture)).width==1800
 s['elements'][-1]['src']='https://remote.test/secret.png'
 with pytest.raises(ValueError):g.load_picture(p,s,database(),'unused')


def test_tutor_explains_ppt_vision_entry_limits_and_additive_preservation():
 from services.creator_guide import GUIDE
 entry=next(x for x in GUIDE if x['id']=='ppt-visual-analysis')
 text=' '.join(entry['steps'])
 assert entry['target']=='agent'
 for value in ['Editar Curso Existente','créditos','somente texto','preservados','HTML/SCORM']:
  assert value in text
