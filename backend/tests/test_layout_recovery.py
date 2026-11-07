import ast
import asyncio
import copy
import gzip
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock
import logging
import pytest
from fastapi import HTTPException

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from services.layout_recovery import layout_recovery_plan,backup_layout_source
from services.layout_recovery import reference_layout_plan,layout_metadata_regression


def test_reference_recovers_custom_boxes_by_content_without_replacing_content():
    original={'slides':[{'id':'s','width':1920,'height':820,'elements':[
        {'id':'a','type':'html','htmlContent':'<p>Current</p>','x':38,'y':21,'width':1844,'height':778},
        {'id':'b','type':'image','src':'image.png','x':80,'y':700,'width':30,'height':30}]}]}
    broken={'course':copy.deepcopy(original)}
    for s in broken['course']['slides']:
        for k in ('id','width','height'):s.pop(k)
        for e in s['elements']:
            for k in ('id','x','y','width','height'):e.pop(k)
    before=copy.deepcopy(broken)
    changes,slides,skipped=reference_layout_plan(broken,original)
    fixed=apply(broken,changes)
    assert slides==[1] and skipped==[]
    assert fixed['course']['slides'][0]['elements'][1]['width']==30
    assert fixed['course']['slides'][0]['elements'][0]['x']==38
    assert all(k.rsplit('.',1)[1] in {'id','width','height','x','y'} for k in changes)
    assert broken==before
    assert reference_layout_plan(fixed,original)==({},[],[])
    assert layout_metadata_regression(fixed,broken['course'])
    assert not layout_metadata_regression(fixed,fixed['course'])


def test_reference_never_replaces_changed_or_unidentified_content_or_healthy_geometry():
    old={'slides':[{'width':1920,'height':820,'elements':[{'type':'html','htmlContent':'old','x':40,'y':40,'width':800,'height':500}]}]}
    p={'course':{'slides':[{'elements':[{'type':'html','htmlContent':'new'}]}]}}
    assert reference_layout_plan(p,old)==({},[],[1])
    p['course']['slides'][0]['elements'][0].update(htmlContent='old',id='e',x=120,y=140,width=900,height=600)
    changes,_,_=reference_layout_plan(p,old)
    assert not any('.elements.' in k for k in changes)
    with pytest.raises(ValueError):reference_layout_plan(p,{'slides':[]})

HTML='<html><script id="video-quiz-data" type="application/json">{"checkpoints":[{"question":"Preserve?"}]}</script><video></video></html>'
def sample():
    return {'id':'p','updatedAt':'revision-1','course':{'slides':[
        {'duration':10,'elements':[{'type':'html','htmlContent':HTML,'startTime':2,'endTime':None,'style':{'color':'red'}}]},
        {'elements':[{'type':'html','htmlContent':HTML.replace('video-quiz-data','assessment-data')}]},
        {'id':'s3','width':1920,'height':820,'elements':[{'id':'e3','type':'html','htmlContent':HTML,'x':0,'y':0,'width':100,'height':100}]},
    ]}}

def apply(project,changes):
    result=copy.deepcopy(project)
    for path,value in changes.items():
        keys=path.split('.');target=result
        for key in keys[:-1]: target=target[int(key)] if isinstance(target,list) else target[key]
        target[keys[-1]]=value
    return result

def test_three_activities_recover_without_touching_content_or_timing():
    project=sample();before=copy.deepcopy(project)
    changes,slides=layout_recovery_plan(project)
    assert slides == [1,2,3]
    assert all(path.rsplit('.',1)[1] in ('id','width','height','title','order','x','y','htmlDisplayMode') for path in changes)
    fixed=apply(project,changes)
    for old,new in zip(before['course']['slides'],fixed['course']['slides']):
        assert new['id'] and new['width']==1920 and new['height']==820
        element=new['elements'][0]
        assert element['id'] and element['width']==1920 and element['height']==820
        assert element['htmlContent']==old['elements'][0]['htmlContent']
        assert {k:v for k,v in element.items() if k in ('startTime','endTime','style')} == {k:v for k,v in old['elements'][0].items() if k in ('startTime','endTime','style')}
    assert project == before
    assert layout_recovery_plan(fixed)==({},[])

def test_does_not_resize_intentional_custom_or_multi_element_layouts():
    project=sample();project['course']['slides']=[
      {'id':'s','width':1280,'height':720,'elements':[{'id':'e','type':'html','htmlContent':HTML,'width':640,'height':360,'x':70,'y':100}]},
      {'elements':[{'type':'html','htmlContent':HTML},{'type':'text','content':'custom'}]},
      {'elements':[{'type':'html','htmlContent':'<p>Manual HTML</p>'}]},
    ]
    assert layout_recovery_plan(project)==({},[])

def test_original_snapshot_is_losslessly_backed_up_compressed(monkeypatch):
    recorded={}
    class Bucket:
        def __init__(self,db,bucket_name): recorded['bucket']=bucket_name
        async def upload_from_stream(self,name,stream,metadata):
            recorded.update(data=stream.read(),metadata=metadata)
    monkeypatch.setattr('services.layout_recovery.AsyncIOMotorGridFSBucket',Bucket)
    project=sample();changes,_=layout_recovery_plan(project)
    recovery_id=asyncio.run(backup_layout_source(object(),project,'u',changes))
    assert json.loads(gzip.decompress(recorded['data'])) == project
    assert recorded['metadata']['recoveryId']==recovery_id
    assert recorded['bucket']=='layout_recovery_backups'

def route(name,**namespace):
    source=Path(__file__).resolve().parents[1]/'routes/projects_crud.py'
    tree=ast.parse(source.read_text(encoding='utf-8'))
    fn=next(n for n in tree.body if isinstance(n,ast.AsyncFunctionDef) and n.name==name)
    fn.decorator_list=[]
    scope={'HTTPException':HTTPException,'Request':object,'Depends':lambda x:None,'require_auth':lambda:None,'logger':logging.getLogger('test'),**namespace}
    exec(compile(ast.Module(body=[fn],type_ignores=[]),str(source),'exec'),scope)
    return scope[name]

def test_backup_precedes_guarded_metadata_only_write(monkeypatch):
    project=sample();events=[]
    async def backup(*args):events.append('backup');return 'r'
    async def update(guard,operation):
        events.append('update');assert guard=={'id':'p','updatedAt':'revision-1'}
        assert all('htmlContent' not in key for key in operation['$set']);return SimpleNamespace(matched_count=1)
    monkeypatch.setattr('services.layout_recovery.backup_layout_source',backup)
    collection=SimpleNamespace(find_one=AsyncMock(return_value=project),update_one=update)
    fn=route('recover_activity_layout',load_authorized_project=AsyncMock(return_value=project),db=SimpleNamespace(projects=collection),now_utc=lambda:SimpleNamespace(isoformat=lambda:'revision-2'))
    result=asyncio.run(fn('p',SimpleNamespace(json=AsyncMock(return_value={'expectedUpdatedAt':'revision-1'})),{'user_id':'u'}))
    assert events==['backup','update'] and result['recoveredSlides']==[1,2,3]

def test_stale_revision_or_failed_backup_never_modifies_course(monkeypatch):
    project=sample();collection=SimpleNamespace(find_one=AsyncMock(return_value=project),update_one=AsyncMock())
    backup=AsyncMock(side_effect=RuntimeError('backup unavailable'))
    monkeypatch.setattr('services.layout_recovery.backup_layout_source',backup)
    fn=route('recover_activity_layout',load_authorized_project=AsyncMock(return_value=project),db=SimpleNamespace(projects=collection))
    with pytest.raises(HTTPException) as err:
        asyncio.run(fn('p',SimpleNamespace(json=AsyncMock(return_value={'expectedUpdatedAt':'stale'})),{}))
    assert err.value.status_code==409 and not backup.called
    with pytest.raises(RuntimeError):
        asyncio.run(fn('p',SimpleNamespace(json=AsyncMock(return_value={'expectedUpdatedAt':'revision-1'})),{}))
    collection.update_one.assert_not_called()

def test_future_partial_course_save_cannot_strip_recovered_metadata():
    project=sample();fixed=apply(project,layout_recovery_plan(project)[0]);update=AsyncMock()
    fn=route('save_course',load_authorized_project=AsyncMock(return_value=fixed),update_project=update)
    with pytest.raises(HTTPException) as err:asyncio.run(fn('p',project['course'],{}))
    assert err.value.status_code==409;update.assert_not_called()
