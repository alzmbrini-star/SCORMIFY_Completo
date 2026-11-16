import copy
import pytest
from services.course_resource_balance import budget,balanced_result,validate_selection,validate_additions
from services.gamma_course_analysis import additive_result

def course(n=19):
 return {'source':'gamma','course':{'slides':[{'id':str(i),'title':f'Slide {i+1}','gammaSource':{'elementId':str(i)},'elements':[]} for i in range(n)]}}

def ideas(n=19):
 return {'visualAnalysis':{'assessmentFormatsVersion':2,'readSlides':n,'totalSlides':n,'slides':[]},'improvements':[
  {'slideIndex':i,'sourceSlideId':str(i),'type':kind,'description':f'{kind} {i}','suggestion':'Aplicação contextual','priority':'media'}
  for i in range(n) for kind in ['quiz','scenario','reinforcement']]}

def test_51_candidates_for_19_teaching_slides_become_at_most_seven_distributed_diverse_items():
 p=course();raw=ideas();raw['improvements']=raw['improvements'][:51];before=copy.deepcopy(p)
 result=balanced_result(raw,p)
 assert len(result['improvements'])==7
 assert len({i['slideIndex'] for i in result['improvements']})==7
 assert {i['type'] for i in result['improvements']}=={'quiz','scenario','reinforcement'}
 assert max(i['slideIndex'] for i in result['improvements'])>=15
 assert result['resourceBalance']['hardMaximumTotal']==19
 assert p==before and len(raw['improvements'])==51
 assert balanced_result(result,p)==result

def test_existing_resources_are_deducted_and_never_counted_as_more_teaching():
 p=course();p['course']['slides'] += [{'id':f'r{i}','learningResource':{'type':'quiz'},'elements':[]} for i in range(6)]
 assert budget(p)['recommendedAdditions']==1
 assert len(balanced_result(ideas(),p)['improvements'])==1
 p['course']['slides'].append({'id':'last','learningResource':{'type':'scenario'}})
 assert budget(p)['recommendedAdditions']==0
 assert balanced_result(ideas(),p)['improvements']==[]

def test_legacy_unmarked_gamma_additions_do_not_inflate_the_budget():
 p=course();p['course']['slides'] += [{'id':f'old{i}','elements':[]} for i in range(51)]
 assert budget(p)['explanatorySlides']==19 and budget(p)['existingResourceSlides']==51
 assert balanced_result(ideas(),p)['improvements']==[]

def test_orientation_and_admin_hour_quizzes_are_not_prioritized():
 p=course();raw=ideas();raw['improvements'][0]['description']='Quantas horas de projeto integrador?'
 raw['visualAnalysis']['slides']=[{'slideIndex':1,'pedagogicalRole':'orientation'}]
 out=balanced_result(raw,p)
 assert all(i['slideIndex']!=1 for i in out['improvements'])
 assert not any('Quantas horas' in i['description'] for i in out['improvements'])

@pytest.mark.parametrize('n', [0,1,2,3,19,100])
def test_total_never_exceeds_content_and_new_resources_have_at_most_one_origin(n):
 p=course(n);out=balanced_result(ideas(n),p)
 assert len(out['improvements'])<=n
 assert len(out['improvements'])==len({i['slideIndex'] for i in out['improvements']})

def test_old_51_selection_and_ai_overgeneration_refused_before_any_course_write():
 p=course();before=copy.deepcopy(p)
 with pytest.raises(ValueError):validate_selection(p,ideas()['improvements'][:51])
 with pytest.raises(ValueError):validate_selection(p,[ideas()['improvements'][0],ideas()['improvements'][1]])
 with pytest.raises(ValueError):additive_result({'newSlides':[{'afterIndex':i,'elements':[]} for i in range(8)]},p)
 assert p==before

def test_duplicates_from_model_are_refused_and_tutor_documents_budget():
 with pytest.raises(ValueError):validate_additions(course(),[{'afterIndex':0},{'afterIndex':0}])
 from services.creator_guide import GUIDE
 text=' '.join(next(e for e in GUIDE if e['id']=='course-resource-balance')['steps'])
 assert '19' in text and '7' in text and 'não são slides salvos' in text


def cached_route():
 import ast
 from pathlib import Path
 from types import SimpleNamespace
 from unittest.mock import AsyncMock
 from fastapi import HTTPException
 tree=ast.parse((Path(__file__).parents[1]/'routes/agent.py').read_text(encoding='utf-8'))
 node=next(n for n in tree.body if isinstance(n,ast.AsyncFunctionDef) and n.name=='agent_analyze_course')
 node.decorator_list=[];node.returns=None
 for arg in node.args.args:arg.annotation=None
 node.args.defaults=[ast.Constant(None) for _ in node.args.defaults]
 scope={'HTTPException':HTTPException}
 exec(compile(ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[])),'cached-route','exec'),scope)
 p=course();p['id']='p'
 scope['load_authorized_project']=AsyncMock(return_value=p)
 scope['db']=SimpleNamespace(analysis_cache=SimpleNamespace(find_one=AsyncMock(return_value=None)),course_visual_analysis=SimpleNamespace(find_one=AsyncMock(return_value={'result':ideas()})))
 return scope,SimpleNamespace(query_params={'cached_only':'true'})


@pytest.mark.asyncio
async def test_cached_only_endpoint_rebalances_without_ai_or_course_writes():
 from unittest.mock import patch,AsyncMock
 scope,request=cached_route()
 with patch('services.gamma_course_analysis.analyze',new_callable=AsyncMock) as paid:
  result=await scope['agent_analyze_course']('p',request,{'user_id':'author'})
  paid.assert_not_awaited()
 assert len(result['improvements'])==7
 scope['load_authorized_project'].assert_awaited_once()


@pytest.mark.asyncio
async def test_cached_only_endpoint_never_starts_paid_work_when_cache_absent():
 from fastapi import HTTPException
 scope,request=cached_route();scope['db'].course_visual_analysis.find_one.return_value=None
 with pytest.raises(HTTPException) as error:
  await scope['agent_analyze_course']('p',request,{})
 assert error.value.status_code==409


@pytest.mark.asyncio
async def test_cached_only_endpoint_preserves_project_authorization_boundary():
 from fastapi import HTTPException
 scope,request=cached_route();scope['load_authorized_project'].side_effect=HTTPException(404,'not found')
 with pytest.raises(HTTPException):await scope['agent_analyze_course']('p',request,{})
 scope['db'].course_visual_analysis.find_one.assert_not_awaited()
