import copy
from types import SimpleNamespace
from unittest.mock import AsyncMock,patch
import pytest
from services.assessment_formats import native_quiz,migrate_preview,migrate_analysis,image_counts
from services.improvement_preview import coverage,complete_preview
from services.preview_assessment_images import run_images
from test_gamma_course_analysis import route_helpers

def canonical():
 return {'afterIndex':0,'type':'interactive_assessment','elements':[{'type':'html','htmlContent':'<html><head></head><body>Player</body></html>',
  'assessmentConfig':{'title':'Avaliação','questions':[{'id':'same-question','type':'single_choice','title':'Situação','prompt':'O que fazer?',
    'options':[{'id':'a','text':'Verificar','isCorrect':True},{'id':'b','text':'Ignorar','isCorrect':False}],'explanation':'Verifique o critério.','points':1,'media':None}]}}]}

def test_traditional_quiz_has_native_element_and_distinct_bank_configuration():
 source=canonical()['elements'][0]['assessmentConfig'];before=copy.deepcopy(source)
 element,questions=native_quiz(source)
 assert element['type']=='quiz' and 'assessmentConfig' not in element
 cfg=element['quizConfig'];assert cfg['shuffleQuestions'] and cfg['shuffleAlternatives'] and cfg['showFeedback'] and cfg['passingScore']==70
 assert cfg['questionIds']==[questions[0]['id']] and questions[0]['text']=='O que fazer?'
 assert sum(o['isCorrect'] for o in questions[0]['alternatives'])==1 and source==before
 built=route_helpers()._build_improved_elements([element],lambda:'element')
 assert built[0]['type']=='quiz' and built[0]['quizConfig']==cfg

def test_old_mislabeled_assessment_is_renamed_not_converted_or_resampled():
 old={'newSlides':[canonical()]};old['newSlides'][0]['type']='quiz';before=copy.deepcopy(old)
 migrated=migrate_preview(old)
 assert migrated['newSlides'][0]['type']=='interactive_assessment'
 assert migrated['newSlides'][0]['elements'][0]['assessmentConfig']==old['newSlides'][0]['elements'][0]['assessmentConfig']
 assert old==before
 analysis={'visualAnalysis':{'slides':[]},'improvements':[{'type':'quiz'}]}
 assert migrate_analysis(analysis)['improvements'][0]['type']=='interactive_assessment'
 analysis['visualAnalysis']['assessmentFormatsVersion']=2
 assert migrate_analysis(analysis)['improvements'][0]['type']=='quiz'

@pytest.mark.asyncio
async def test_missing_images_preserve_question_snapshot_but_block_ready_state():
 slide=canonical();selection=[{'slideIndex':0,'type':'interactive_assessment'}]
 info=coverage({'newSlides':[slide]},selection)
 assert info['contentReady']==1 and not info['complete'] and info['images']['pending']==1
 project={'id':'p','source':'ppt','course':{'slides':[{'id':'s','extractedText':'Fonte'}]}}
 generate=AsyncMock();result,info=await complete_preview(project,selection,{'newSlides':[slide]},generate)
 generate.assert_not_awaited();assert not info['complete'] and info['reusedCount']==1
 assert result['newSlides'][0]['elements'][0]['assessmentConfig']['questions'][0]['id']=='same-question'

@pytest.mark.asyncio
async def test_image_job_writes_only_preview_and_uses_situation_not_answers(monkeypatch):
 from services.assessment_images import image_prompt
 slide=canonical();question=slide['elements'][0]['assessmentConfig']['questions'][0]
 assert 'Ignorar' not in image_prompt(question,{'id':'p','name':'Curso'})
 db=SimpleNamespace(improvement_previews=SimpleNamespace(update_one=AsyncMock()))
 source={'id':'preview','aiResult':{'newSlides':[slide]},'requestedImprovements':[{'slideIndex':0,'type':'interactive_assessment'}],'coverage':{'reusedCount':1}}
 before=copy.deepcopy(source)
 image=AsyncMock(return_value={'url':'/api/projects/p/assets/generated.png','kind':'image'})
 monkeypatch.setattr('services.assessment_images.create_support_image',image)
 await run_images(db,'.',{'id':'p'},source)
 updates=[c.args[1]['$set'] for c in db.improvement_previews.update_one.call_args_list]
 result=next(u for u in updates if 'aiResult' in u)
 assert result['coverage']['complete'] and result['coverage']['images']['ready']==1
 q=result['aiResult']['newSlides'][0]['elements'][0]['assessmentConfig']['questions'][0]
 assert q['id']==question['id'] and q['options']==question['options'] and q['media']['url'].endswith('generated.png')
 assert source==before and not hasattr(db,'projects')

@pytest.mark.asyncio
async def test_failed_art_never_declares_illustrated_assessment_ready(monkeypatch):
 db=SimpleNamespace(improvement_previews=SimpleNamespace(update_one=AsyncMock()))
 monkeypatch.setattr('services.assessment_images.create_support_image',AsyncMock(side_effect=ValueError('private provider detail')))
 await run_images(db,'.',{'id':'p'},{'id':'preview','aiResult':{'newSlides':[canonical()]},'requestedImprovements':[{'slideIndex':0,'type':'interactive_assessment'}]})
 values=[c.args[1]['$set'] for c in db.improvement_previews.update_one.call_args_list]
 assert values[-1]['imageStatus']=='failed'
 assert next(v['coverage'] for v in values if 'coverage' in v)['complete'] is False
 assert 'private provider' not in str(values)

def test_tutor_preserves_two_formats_and_mentions_credits_and_export():
 from services.creator_guide import GUIDE
 text=' '.join(next(t for t in GUIDE if t['id']=='assessment-formats')['steps'])
 for phrase in ['Quiz tradicional','Avaliação interativa com imagens','créditos','HTML/SCORM','não são convertidas']:
  assert phrase in text

@pytest.mark.asyncio
async def test_image_lease_prevents_duplicate_paid_worker(monkeypatch):
 import asyncio
 from services import preview_assessment_images as jobs
 worker=AsyncMock();monkeypatch.setattr(jobs,'run_images',worker)
 db=SimpleNamespace(improvement_previews=SimpleNamespace(update_one=AsyncMock(side_effect=[SimpleNamespace(matched_count=1),SimpleNamespace(matched_count=0)])))
 saved={'id':'p1','aiResult':{'newSlides':[canonical()]},'requestedImprovements':[]}
 await jobs.start_images(db,'.',{'id':'p'},saved);await jobs.start_images(db,'.',{'id':'p'},saved)
 await asyncio.sleep(0)
 worker.assert_awaited_once()
