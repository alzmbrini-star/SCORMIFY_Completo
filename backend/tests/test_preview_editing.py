import ast
import copy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from datetime import datetime,timezone
import pytest
from fastapi import HTTPException
from services.preview_editing import edit_result,editor_data,revision
from services.assessment_formats import native_quiz
from services.assessment_renderer import assessment_element


def fixture():
 spec={'title':'Processo','questions':[{'id':'original','type':'single_choice','title':'PDI','prompt':'O que é PDI?',
    'options':[{'id':'a','text':'Programa de Desenvolvimento Individual','isCorrect':True},
               {'id':'b','text':'Outro','isCorrect':False}],'explanation':'Programa','points':3,'media':{'url':'keep.png','kind':'image'}}]}
 element,bank=native_quiz(spec)
 return {'updatedSlides':[],'newSlides':[{'afterIndex':4,'type':'quiz','title':'Processo','requestSignature':'keep',
    'elements':[element],'nativeQuizQuestions':bank},
   {'afterIndex':20,'type':'scenario','title':'PDI','scenarioConfig':{'theme':'PDI','objectives':'Aplicar','branches':[{'id':'keep'}]}},
   {'afterIndex':23,'type':'interactive_assessment','title':'Visual','elements':[assessment_element(spec['questions'],'Visual')]}]}


def test_native_text_only_patch_preserves_bank_ids_points_correctness_settings_and_other_resources():
 source=fixture();before=copy.deepcopy(source);slide=source['newSlides'][0];q=slide['nativeQuizQuestions'][0]
 change={'prompt':'O que significa PDI?','options':[{'id':o['id'],'text':'Plano de Desenvolvimento Individual' if o['isCorrect'] else o['text']} for o in q['alternatives']],
         'explanation':'PDI é o Plano de Desenvolvimento Individual, com objetivos, ações e evidências.'}
 result=edit_result(source,4,'quiz',revision(slide),change,q['id'])
 after=result['newSlides'][0]['nativeQuizQuestions'][0]
 assert after['text']==change['prompt'] and after['points']==3 and after['id']==q['id']
 assert [o['isCorrect'] for o in after['alternatives']]==[o['isCorrect'] for o in q['alternatives']]
 assert result['newSlides'][0]['elements']==slide['elements']
 assert result['newSlides'][1:]==source['newSlides'][1:] and source==before
 assert result['newSlides'][0]['requestSignature']=='keep'


def test_interactive_patch_rerenders_snapshot_without_regenerating_or_replacing_media():
 source=fixture();s=source['newSlides'][2]
 result=edit_result(source,23,'interactive_assessment',revision(s),{'prompt':'Defina PDI','explanation':'Plano de Desenvolvimento Individual'},'original')
 e=result['newSlides'][2]['elements'][0];q=e['assessmentConfig']['questions'][0]
 assert q['media']['url']=='keep.png' and q['points']==3 and q['options']==s['elements'][0]['assessmentConfig']['questions'][0]['options']
 assert 'Defina PDI' in e['htmlContent'] and 'Plano de Desenvolvimento Individual' in e['htmlContent']


def test_resource_title_and_scenario_text_preserve_branches_and_ids():
 source=fixture();s=source['newSlides'][1]
 out=edit_result(source,20,'scenario',revision(s),{'title':'Plano de Desenvolvimento Individual','scenario':{'objectives':'Objetivos, ações e evidências'}})
 assert out['newSlides'][1]['scenarioConfig']['branches']==s['scenarioConfig']['branches']
 s=source['newSlides'][0]
 out=edit_result(source,4,'quiz',revision(s),{'title':'Novo título'})
 assert out['newSlides'][0]['elements'][0]['quizConfig']['title']=='Novo título'


@pytest.mark.parametrize('changes',[{'points':0},{'options':[{'id':'x','text':'Injected'}]},
    {'options':[]},{'prompt':'<script>alert(1)</script>'},{'prompt':''},{'prompt':'x'*8001},
    {'options':[{'id':'x','text':'a','isCorrect':True}]}])
def test_invalid_or_structural_edits_are_rejected(changes):
 source=fixture();s=source['newSlides'][0];before=copy.deepcopy(source)
 with pytest.raises(ValueError):edit_result(source,4,'quiz',revision(s),changes,s['nativeQuizQuestions'][0]['id'])
 assert source==before


def test_old_revision_or_unknown_resource_refused_and_metadata_excludes_grading_flags():
 source=fixture();s=source['newSlides'][0];metadata=editor_data(s)
 assert 'isCorrect' not in str(metadata) and 'passingScore' not in str(metadata)
 with pytest.raises(LookupError):edit_result(source,4,'quiz','stale',{'title':'New'})
 with pytest.raises(LookupError):edit_result(source,5,'quiz',revision(s),{'title':'New'})


def route_fixture():
 tree=ast.parse((Path(__file__).parents[1]/'routes/agent.py').read_text(encoding='utf-8'))
 node=next(n for n in tree.body if isinstance(n,ast.AsyncFunctionDef) and n.name=='agent_edit_preview_text')
 node.decorator_list=[];node.returns=None
 for arg in node.args.args:arg.annotation=None
 node.args.defaults=[ast.Constant(None)]
 result=fixture();saved={'id':'preview','projectId':'p','aiResult':result,'coverage':{'complete':True},'imageStatus':'ready'}
 project={'id':'p','source':'gamma','course':{'slides':[{'id':str(i)} for i in range(26)]}}
 store=SimpleNamespace(find_one=AsyncMock(return_value=saved),update_one=AsyncMock(return_value=SimpleNamespace(matched_count=1)))
 scope={'HTTPException':HTTPException,'datetime':datetime,'timezone':timezone,'load_authorized_project':AsyncMock(return_value=project),
        'db':SimpleNamespace(improvement_previews=store),'_preview_new_slides':lambda r:r['newSlides']}
 exec(compile(ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[])),'preview-text-route','exec'),scope)
 data=SimpleNamespace(afterIndex=4,type='quiz',revision=revision(result['newSlides'][0]),questionId=None,changes={'title':'Revisado'})
 return scope,store,data,project,saved


@pytest.mark.asyncio
async def test_route_only_writes_matching_preview_never_course_or_question_bank():
 scope,store,data,project,saved=route_fixture();before=copy.deepcopy(project)
 response=await scope['agent_edit_preview_text']('p','preview',data,{'user_id':'author'})
 assert response['updatedCount']==0 and response['newCount']==3 and project==before
 query,update=store.update_one.await_args.args
 assert query['id']=='preview' and query['projectId']=='p' and query['aiResult']==saved['aiResult']
 assert set(update['$set'])=={'aiResult','textEditedAt'}
 assert not hasattr(scope['db'],'projects') and not hasattr(scope['db'],'questions')


@pytest.mark.asyncio
@pytest.mark.parametrize('condition',['denied','expired','images','stale','race'])
async def test_route_refuses_unauthorized_expired_busy_stale_and_concurrent_updates(condition):
 scope,store,data,project,saved=route_fixture()
 if condition=='denied':scope['load_authorized_project'].side_effect=HTTPException(403,'denied')
 if condition=='expired':store.find_one.return_value=None
 if condition=='images':saved['imageStatus']='processing'
 if condition=='stale':data.revision='stale'
 if condition=='race':store.update_one.return_value=SimpleNamespace(matched_count=0)
 with pytest.raises(HTTPException) as exc:await scope['agent_edit_preview_text']('p','preview',data,{})
 assert exc.value.status_code in (403,409)
 if condition!='race':store.update_one.assert_not_awaited()


def test_tutor_describes_preview_only_editing_limits_and_zero_ai_credit_usage():
 from services.creator_guide import GUIDE
 text=' '.join(next(t for t in GUIDE if t['id']=='course-preview-completion')['steps'])
 for phrase in ['Editar textos da prévia','Salvar somente na prévia','não usa créditos','imagens','respostas corretas','prévia expirad']:
  assert phrase in text
