"""No live provider/database calls: orphan recovery and thread-loop ownership."""
import ast
import asyncio
import copy
import logging
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from services.heygen_recovery import reconcile_project


def project():
    return dict(id='p1',heygenPending=[dict(slideId='s1',title='Osseointegração',status='failed',videoQuizEnabled=True)],
        course={'slides':[{'id':'s1','elements':[{'id':'e1','htmlContent':'<div data-heygen-slide="s1">Aguarde</div>',
            'videoQuizPending':dict(title='Aula',checkpoints=[dict(at=4,question='Qual?',options=['A','B'],correctIndex=1,explanation='B.')])}]}]})


class Cursor:
    def __init__(self, rows): self.rows=rows
    def limit(self,n): self.rows=self.rows[:n];return self
    async def to_list(self,n): return copy.deepcopy(self.rows[:n])


class Store:
    def __init__(self,p,rows):
        self.project=p;self.rows=rows;self.queries=[]
        self.heygen_videos=SimpleNamespace(find=self.find,update_one=AsyncMock())
        self.projects=SimpleNamespace(update_one=self.update)
    def find(self,query):
        self.queries.append(query)
        return Cursor([r for r in self.rows if all(r.get(k)==v for k,v in query.items())])
    async def update(self,query,update):
        assert query['id']==self.project['id']
        for item in self.project['heygenPending']:
            if item['slideId']==query['heygenPending.slideId']:
                for key,value in update.get('$set',{}).items():item[key.split('.')[-1]]=value
                for key in update.get('$unset',{}):item.pop(key.split('.')[-1],None)
        return SimpleNamespace(matched_count=1)


def test_recover_exact_completed_library_job_without_provider_generation():
    p=project();snapshot=copy.deepcopy(p['course'])
    store=Store(p,[dict(project_id='p1',slide_id='s1',video_id='v1',status='completed',video_url='https://example.org/alpha.webm')])
    fetch=AsyncMock(side_effect=AssertionError('Completed library job needs no provider request'))
    apply=AsyncMock(return_value=True)
    first=asyncio.run(reconcile_project(store,p,fetch,apply))
    second=asyncio.run(reconcile_project(store,p,fetch,apply))
    assert first['status']==second['status']=='all_done'
    assert first['videos'][0]['videoId']=='v1' and first['completedCount']==1
    assert apply.await_count==1 and fetch.await_count==0
    assert p['course']==snapshot  # Only the guarded callback may change the block.
    assert all(q['project_id']=='p1' and q['slide_id']=='s1' for q in store.queries)


def test_ambiguous_cross_project_and_author_edits_are_not_replaced():
    p=project();fetch=AsyncMock();apply=AsyncMock(return_value=False)
    foreign=dict(project_id='other',slide_id='s1',video_id='v1',status='completed',video_url='https://example.org/a.webm')
    result=asyncio.run(reconcile_project(Store(p,[foreign]),p,fetch,apply))
    assert result['status']=='partial_failed' and apply.await_count==fetch.await_count==0
    row=dict(foreign,project_id='p1')
    result=asyncio.run(reconcile_project(Store(p,[row,dict(row,video_id='v2')]),p,fetch,apply))
    assert 'mais de um' in result['videos'][0]['error'] and apply.await_count==0
    result=asyncio.run(reconcile_project(Store(p,[row]),p,fetch,apply))
    assert result['status']=='partial_failed' and 'identificar' in result['videos'][0]['error']
    assert p['heygenPending'][0]['status']=='failed'


def test_provider_processing_and_failure_never_report_all_success():
    for provider_status in ('processing','failed'):
        p=project();row=dict(project_id='p1',slide_id='s1',video_id='v1',status='processing')
        fetch=AsyncMock(return_value={'status':provider_status});apply=AsyncMock()
        result=asyncio.run(reconcile_project(Store(p,[row]),p,fetch,apply))
        assert result['status']==('processing' if provider_status=='processing' else 'partial_failed')
        assert not result['completedCount'] and apply.await_count==0
        assert result['videos'][0]['videoId']=='v1'


def load_function(name, namespace):
    source=(Path(__file__).resolve().parents[1]/'routes/agent.py').read_text(encoding='utf-8')
    function=next(n for n in ast.parse(source).body if isinstance(n,ast.AsyncFunctionDef) and n.name==name)
    function.decorator_list=[]
    exec(compile(ast.Module(body=[function],type_ignores=[]),'agent-function','exec'),namespace)
    return namespace[name]


def test_callback_restores_questions_and_never_overwrites_changed_block():
    p=project();writes=[]
    async def update(query,patch): writes.append((query,patch));return SimpleNamespace(matched_count=1)
    db=SimpleNamespace(projects=SimpleNamespace(find_one=AsyncMock(return_value=p),update_one=update))
    fn=load_function('_update_slide_with_heygen_video',{'db':db})
    assert asyncio.run(fn('p1','s1','https://example.org/alpha.webm')) is True
    query,patch=writes[0]
    config=patch['$set']['course.slides.0.elements.0.videoQuizConfig']
    assert config['checkpoints'][0]['question']=='Qual?'
    assert config['src'].endswith('alpha.webm') and config['preserveTransparency']
    assert query['course.slides.0.elements.0.htmlContent']==p['course']['slides'][0]['elements'][0]['htmlContent']
    p['course']['slides'][0]['elements'][0]={'htmlContent':'<p>Author changed this block</p>'}
    assert asyncio.run(fn('p1','s1','https://example.org/alpha.webm')) is False
    assert len(writes)==1


def test_legacy_placeholder_id_mismatch_is_recovered_only_with_exact_question_element_identity():
    from services.heygen_recovery import original_placeholder, bind_slide_id
    old_id='11111111-2222-3333-4444-555555555555'
    element={'id':'e1','htmlContent':f'<div data-heygen-slide="{old_id}">Gerando vídeo com Avatar IA...</div>',
             'videoQuizPending':{'instanceId':'e1','checkpoints':[]}}
    assert original_placeholder(element,'actual-slide')
    wrong=copy.deepcopy(element);wrong['videoQuizPending']['instanceId']='other-element'
    assert not original_placeholder(wrong,'actual-slide')
    wrong=copy.deepcopy(element);wrong['htmlContent']='<p>My edited block</p>'
    assert not original_placeholder(wrong,'actual-slide')
    wrong=copy.deepcopy(element);wrong['htmlContent']+='<video src="custom.webm"></video>'
    assert not original_placeholder(wrong,'actual-slide')
    pending=[{'slideIndex':2,'slideId':old_id}]
    bind_slide_id(pending,2,'actual-slide',[element])
    assert pending[0]['slideId']=='actual-slide'
    assert 'data-heygen-slide="actual-slide"' in element['htmlContent']
    assert old_id not in element['htmlContent']


def test_worker_creates_and_closes_own_client_on_each_event_loop_and_reuses_jobs(monkeypatch):
    import motor.motor_asyncio
    rows=[];clients=[];posts=[]
    class Client:
        def __init__(self,*args,**kwargs):
            self.loop=asyncio.get_running_loop();self.closed=False;clients.append(self)
            async def find(query):
                assert asyncio.get_running_loop() is self.loop
                return next((r for r in rows if all(r.get(k)==v for k,v in query.items())),None)
            async def insert(row):
                assert asyncio.get_running_loop() is self.loop
                rows.append(row)
            self.db=SimpleNamespace(heygen_videos=SimpleNamespace(find_one=find,insert_one=insert),
                projects=SimpleNamespace(update_one=AsyncMock(),find_one_and_update=AsyncMock(return_value={'id':'claimed'})))
        def __getitem__(self,key):return self.db
        def close(self):self.closed=True
    class HTTP:
        def __init__(self,**kwargs):pass
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        async def post(self,url,**kwargs):
            posts.append((url,kwargs));return SimpleNamespace(status_code=200,json=lambda:{'data':{'video_id':'v'+str(len(posts))}})
    monkeypatch.setattr(motor.motor_asyncio,'AsyncIOMotorClient',Client)
    fn=load_function('_trigger_heygen_videos',dict(os=os,httpx=SimpleNamespace(AsyncClient=HTTP),
        HEYGEN_BASE_URL='https://api.heygen.com',HEYGEN_HEADERS={},now_utc=lambda:'now',logger=logging.getLogger('test')))
    item=dict(slideId='s1',avatar_id='avatar',voice_id='voice',script='Texto completo.',title='Aula')
    asyncio.run(fn('p1',[item]));asyncio.run(fn('p2',[item]));asyncio.run(fn('p1',[item]))
    assert len(posts)==2 and len(clients)==3 and all(c.closed for c in clients)
    assert len({id(c.loop) for c in clients})==3
    assert posts[0][1]['json']['input_text']=='Texto completo.'


def test_status_authorizes_project_before_reconciling():
    source=(Path(__file__).resolve().parents[1]/'routes/agent.py').read_text(encoding='utf-8')
    fn=next(n for n in ast.parse(source).body if isinstance(n,ast.AsyncFunctionDef) and n.name=='agent_heygen_status')
    segment=ast.get_source_segment(source,fn)
    assert segment.index('await load_authorized_project') < segment.index('await reconcile_project')
    assert '.post(' not in segment and 'generate-course' not in segment
