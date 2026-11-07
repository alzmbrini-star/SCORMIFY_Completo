import base64
import copy
from types import SimpleNamespace
from unittest.mock import AsyncMock
import asyncio
import pytest
from services.course_recovery_copy import recovered_project
from test_layout_recovery import route

REQUEST='265ec481-4ccb-4139-8387-d62ad1780424'

def fixture():
    html='<p>Texto original</p>'
    return {'metadata':{'title':'FreeStyle'},'questions':[{'id':'q','question':'Pergunta?'}],
        'slides':[{'id':'s','width':1920,'height':820,'duration':10,'elements':[
            {'id':'e','type':'html','x':38,'y':21,'width':1844,'height':778,'startTime':3,
             'htmlContent':'__B64__:'+base64.b64encode(html.encode()).decode(),'gameConfig':{'questionIds':['q']}},
            {'id':'image','type':'image','x':0,'y':790,'width':30,'height':30,'src':'data:image/png;base64,AA=='}]}]}

def test_copy_preserves_geometry_content_configs_media_and_ids_without_touching_original():
    original={'id':'source','name':'FreeStyle','companyId':'tenant','course':{'slides':[]},'status':'exported'}
    reference=fixture();before=copy.deepcopy((original,reference))
    result=recovered_project(original,reference,'owner','now',REQUEST)
    assert (original,reference)==before
    assert result['id']!='source' and result['companyId']=='tenant' and result['userId']=='owner'
    assert result['status']=='draft' and result['name']=='FreeStyle (Recuperado)'
    slide=result['course']['slides'][0]
    assert slide['id']=='s' and slide['width']==1920
    assert slide['elements'][0]['htmlContent']=='<p>Texto original</p>'
    assert slide['elements'][0]['startTime']==3 and slide['elements'][0]['gameConfig']=={'questionIds':['q']}
    assert slide['elements'][1]['width']==30 and slide['elements'][1]['src'].startswith('data:')
    assert result['id']==recovered_project(original,reference,'owner','later',REQUEST)['id']

def test_bad_reference_is_rejected_not_imported_with_default_boxes():
    for key,value in [('width',None),('width',0),('x',float('inf'))]:
        ref=fixture();ref['slides'][0]['elements'][0][key]=value
        with pytest.raises(ValueError):recovered_project({'id':'p'},ref,'u','now',REQUEST)
    with pytest.raises(ValueError):recovered_project({'id':'p'},fixture(),'u','now','bad')

def test_route_authorizes_original_and_only_inserts_a_separate_draft():
    original={'id':'source','name':'FreeStyle','companyId':'tenant'}
    authorize=AsyncMock(return_value=original);write=AsyncMock()
    fn=route('recover_export_copy',load_authorized_project=authorize,db=SimpleNamespace(projects=SimpleNamespace(update_one=write)),now_utc=lambda:SimpleNamespace(isoformat=lambda:'now'))
    result=asyncio.run(fn('source',SimpleNamespace(json=AsyncMock(return_value={'referenceCourse':fixture(),'requestId':REQUEST})),{'user_id':'u'}))
    authorize.assert_awaited_once_with('source',{'user_id':'u'})
    guard,op=write.await_args.args
    assert guard['_id']=='html-recovery:'+result['projectId']
    assert result['projectId']!='source' and set(op)=={'$setOnInsert'} and write.await_args.kwargs=={'upsert':True}
