import copy
import threading
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
from pymongo.errors import DuplicateKeyError
from services import storyboard_jobs as jobs


def matches(doc, query):
    for key,value in query.items():
        if key=='$or':
            if not any(matches(doc,q) for q in value):return False
        elif isinstance(value,dict):
            for op,operand in value.items():
                actual=doc.get(key)
                if op=='$ne' and actual==operand:return False
                if op=='$exists' and (key in doc)!=operand:return False
                if op=='$gt' and (actual is None or not actual>operand):return False
                if op=='$lte' and (actual is None or not actual<=operand):return False
        elif doc.get(key)!=value:return False
    return True


class Collection:
    def __init__(self):self.docs={};self.lock=threading.RLock()
    def find_one(self,query,*args):
        with self.lock:return copy.deepcopy(next((d for d in self.docs.values() if matches(d,query)),None))
    def update_one(self,query,update,upsert=False):
        with self.lock:
            doc=next((d for d in self.docs.values() if matches(d,query)),None)
            existed=doc is not None
            if doc is None:
                if not upsert:return SimpleNamespace(matched_count=0)
                if query['_id'] in self.docs:raise DuplicateKeyError('unique _id')
                doc={'_id':query['_id']};self.docs[query['_id']]=doc
            doc.update(copy.deepcopy(update.get('$set',{})))
            if not existed:doc.update(copy.deepcopy(update.get('$setOnInsert',{})))
            for key,value in update.get('$addToSet',{}).items():
                values=doc.setdefault(key,[])
                if value not in values:values.append(value)
            return SimpleNamespace(matched_count=int(existed))
    def find_one_and_update(self,query,update,**kwargs):
        with self.lock:
            self.update_one(query,update,upsert=kwargs.get('upsert',False))
            return copy.deepcopy(self.docs[query['_id']])


class Database:
    def __init__(self):
        self.agent_storyboard_runs=Collection();self.agent_storyboard_batches=Collection()
        self.agent_sessions=Collection()


@pytest.mark.asyncio
async def test_restart_reuses_completed_batches_and_fences_old_worker(monkeypatch):
    db=Database();clock=[jobs.utcnow()];monkeypatch.setattr(jobs,'utcnow',lambda:clock[0])
    first=jobs.acquire_run(db,'s','fingerprint');old=jobs.BatchStore(db,'s',first)
    source=[{'id':'slide1'}];slides=[{'id':'slide1','title':'Conteúdo salvo'}]
    await old.save(1,source,slides)
    assert jobs.acquire_run(db,'s','fingerprint') is None
    clock[0]+=timedelta(seconds=jobs.LEASE_SECONDS+1)
    second=jobs.acquire_run(db,'s','fingerprint');new=jobs.BatchStore(db,'s',second)
    assert second['runId']!=first['runId']
    assert await new.load(1,source)==slides
    with pytest.raises(jobs.StoryboardLeaseLost):await old.save(1,source,[{'id':'slide1','title':'Atrasado'}])
    assert await new.load(1,source)==slides
    assert await new.load(1,[{'id':'another'}]) is None
    new.finish('completed');assert not jobs.run_is_live(db.agent_storyboard_runs.find_one({'_id':'s'}))


@pytest.mark.asyncio
async def test_cache_scope_force_and_immutable_checkpoint():
    db=Database();source=[{'id':'a'}]
    run=jobs.acquire_run(db,'s','one');store=jobs.BatchStore(db,'s',run)
    await store.save(1,source,[{'id':'a','notes':'original'}]);await store.save(1,source,[{'id':'a','notes':'replacement'}])
    assert (await store.load(1,source))[0]['notes']=='original'
    store.finish('failed')
    same=jobs.acquire_run(db,'s','one');assert same['cacheKey']==run['cacheKey']
    jobs.BatchStore(db,'s',same).finish('failed')
    forced=jobs.acquire_run(db,'s','one',force=True);assert forced['cacheKey']!=run['cacheKey']
    forced_store=jobs.BatchStore(db,'s',forced);assert await forced_store.load(1,source) is None
    forced_store.finish('failed')
    resumed=jobs.acquire_run(db,'s','one');assert resumed['cacheKey']==forced['cacheKey']
    jobs.BatchStore(db,'s',resumed).finish('failed')
    changed=jobs.acquire_run(db,'s','two');assert changed['cacheKey']!=resumed['cacheKey']


def test_two_concurrent_clicks_claim_only_one_run():
    db=Database();barrier=threading.Barrier(2);results=[]
    def claim():barrier.wait();results.append(jobs.acquire_run(db,'s','same'))
    threads=[threading.Thread(target=claim) for _ in range(2)]
    for t in threads:t.start()
    for t in threads:t.join()
    assert sum(r is not None for r in results)==1


def test_recovery_is_read_only_and_handles_legacy_sessions():
    session={'id':'s','step':'storyboarding','structure':{'modules':[]},'storyboardProgress':{'batch':2,'total':8}}
    before=copy.deepcopy(session)
    for run in (None,{'status':'failed'},{'status':'running','leaseUntil':jobs.utcnow()-timedelta(seconds=1)}):
        view=jobs.recover_session_view(session,run)
        assert view['step']=='structured' and view['storyboardProgress'] is None
        assert 'Execuções antigas' in view['error']
    assert session==before
    live={'status':'running','leaseUntil':jobs.utcnow()+timedelta(minutes=1)}
    assert jobs.recover_session_view(session,live)==session


def test_inputs_are_fingerprinted_without_modifying_source():
    content='Base do curso';structure={'modules':[{'slides':[{'title':'Simulación','id':'s','type':'game'}]}]};config={'title':'Curso'}
    first=jobs.input_fingerprint(content,structure,config)
    assert first==jobs.input_fingerprint(content,copy.deepcopy(structure),dict(config))
    assert first!=jobs.input_fingerprint(content+' novo',structure,config)
    assert first!=jobs.input_fingerprint(content,structure,dict(config,title='Outro'))
    assert structure['modules'][0]['slides'][0]['title']=='Simulación'


def test_heartbeat_renewal_prevents_a_duplicate_live_run(monkeypatch):
    db=Database();clock=[jobs.utcnow()];monkeypatch.setattr(jobs,'utcnow',lambda:clock[0])
    run=jobs.acquire_run(db,'s','f');store=jobs.BatchStore(db,'s',run)
    clock[0]+=timedelta(seconds=100);store.renew()
    clock[0]+=timedelta(seconds=50)
    assert jobs.acquire_run(db,'s','f') is None


def test_recovery_guidance_is_available_without_spending_ai_credits():
    from services.creator_guide import GUIDE
    topic=next(t for t in GUIDE if t['id']=='storyboard')
    text=' '.join(topic['steps'])
    assert 'não há reinício automático' in text and '15 minutos' in text
    assert 'execuções antigas' in text.lower() and 'jogo final' in text.lower()


@pytest.mark.asyncio
async def test_generator_restarts_from_last_complete_batch_without_rebilling(monkeypatch):
    from services import ai_agent
    source={'modules':[{'title':'M','slides':[{'id':'a','type':'content','title':'A'},{'id':'b','type':'game','title':'B'}]}]}
    async def once(attempt,prompt):return {'mission':'Aplicar o conteúdo','learningPoints':['Um conceito da referência'],'narrationScript':'Explicação do conceito.'}
    from services import storyboard_game_plan
    original=storyboard_game_plan.plan_game
    calls=[]
    async def game(*args):calls.append('game');raise RuntimeError('reinício simulado')
    monkeypatch.setattr(storyboard_game_plan,'plan_game',game)
    class Chat:
        async def send_message(self,message):calls.append('content');return '{"slides":[{"id":"a","type":"content","title":"A","elements":[{"type":"html","htmlContent":"<h1>Conceito</h1><p>Texto explicativo do curso para estudo e aplicação.</p>"}]}]}'
    monkeypatch.setattr(ai_agent,'_new_chat',lambda *a,**k:Chat())
    db=Database();run=jobs.acquire_run(db,'s','f');store=jobs.BatchStore(db,'s',run)
    with pytest.raises(RuntimeError,match='reinício'):await ai_agent.generate_storyboard('s','Referência',source,{},checkpoint_store=store)
    assert len(db.agent_storyboard_batches.docs)==1
    store.finish('failed')
    async def restored_game(slide,content,config,ask):calls.append('game');return await original(slide,content,config,once)
    monkeypatch.setattr(storyboard_game_plan,'plan_game',restored_game)
    resumed=jobs.BatchStore(db,'s',jobs.acquire_run(db,'s','f'))
    result=await ai_agent.generate_storyboard('s','Referência',source,{},checkpoint_store=resumed)
    assert [s['id'] for s in result['slides']]==['a','b']
    assert calls.count('content')==1
    assert len(db.agent_storyboard_batches.docs)==2
    assert 'data-game-plan' in result['slides'][1]['elements'][0]['htmlContent']
    assert 'gamePlan' in result['slides'][1]


@pytest.mark.asyncio
async def test_game_plan_does_not_require_or_regenerate_html():
    from services.storyboard_game_plan import plan_game
    ask=AsyncMock(return_value={'mission':'Escolher com base nas evidências','learningPoints':['Conceito estudado'],'narrationScript':'Explicação.'})
    result=await plan_game({'id':'g','title':'Jogo','type':'game'},'Texto-base',{},ask)
    assert ask.await_count==1 and result['gamePlan']['version']==1
    assert 'não gere HTML' in ask.await_args.args[1]
    assert not result.get('quizQuestions')
    bad=AsyncMock(side_effect=RuntimeError('indisponível'))
    fallback=await plan_game({'title':'Jogo'},'Texto-base',{},bad)
    assert bad.await_count==2 and fallback['gamePlan']['needsReview']


@pytest.mark.asyncio
async def test_session_get_exposes_legacy_interruption_without_writing(monkeypatch):
    from routes import agent
    session={'id':'s','userId':'u','step':'storyboarding','structure':{'modules':[]},'storyboardProgress':{'batch':3,'total':9}}
    sessions=SimpleNamespace(find_one=AsyncMock(return_value=copy.deepcopy(session)),update_one=AsyncMock())
    monkeypatch.setattr(agent,'db',SimpleNamespace(agent_sessions=sessions,
        agent_storyboard_runs=SimpleNamespace(find_one=AsyncMock(return_value=None))))
    result=await agent.get_agent_session('s',SimpleNamespace(query_params={}),{'user_id':'u'})
    assert result['step']=='structured' and result['storyboardRecovery']['savedBatches']==0
    sessions.update_one.assert_not_called()


@pytest.mark.asyncio
async def test_draft_url_only_reads_the_authenticated_owners_saved_session(monkeypatch):
    from routes import agent
    from fastapi import HTTPException
    saved={'id':'s','userId':'u','contentText':'Referência salva','step':'storyboarding',
           'structure':{'modules':[{'title':'Simulación','slides':[]}]}}
    queries=[]
    async def find(query,projection):
        queries.append((query,projection))
        return copy.deepcopy(saved) if query=={'id':'s','userId':'u'} else None
    sessions=SimpleNamespace(find_one=find,update_one=AsyncMock())
    monkeypatch.setattr(agent,'db',SimpleNamespace(agent_sessions=sessions,
        agent_storyboard_runs=SimpleNamespace(find_one=AsyncMock(return_value=None))))
    result=await agent.get_owned_agent_draft('s',{'user_id':'u'})
    assert result['step']=='structured' and result['contentText']=='Referência salva'
    assert result['structure']['modules'][0]['title']=='Simulação'
    assert queries[0][1]['pdfPageImages']==0
    with pytest.raises(HTTPException) as captured:await agent.get_owned_agent_draft('s',{'user_id':'other'})
    assert captured.value.status_code==404
    assert saved['step']=='storyboarding';sessions.update_one.assert_not_called()


@pytest.mark.asyncio
async def test_endpoint_deduplicates_clicks_before_starting_any_ai(monkeypatch):
    from routes import agent
    db=Database();initial={'_id':'s','id':'s','userId':'u','step':'structured','updatedAt':'before',
        'contentText':'Material de referência','structure':{'modules':[{'slides':[{'id':'a','type':'content'}]}]},'config':{}}
    db.agent_sessions.docs['s']=copy.deepcopy(initial)
    async def owned(*args):return db.agent_sessions.find_one({'id':'s'})
    async def update(query,change):return db.agent_sessions.update_one(query,change)
    monkeypatch.setattr(agent,'_owned_diagnostic_session',owned)
    monkeypatch.setattr(agent,'_get_bg_db',lambda:db)
    monkeypatch.setattr(agent,'db',SimpleNamespace(
        simulator_diagnostic_runs=SimpleNamespace(find_one=AsyncMock(return_value=None)),
        agent_sessions=SimpleNamespace(update_one=update)))
    starts=[]
    original_thread=threading.Thread
    class HeldWorker:
        def __init__(self,**kwargs):pass
        def start(self):starts.append(1)
    def thread_factory(*args,**kwargs):
        if getattr(kwargs.get('target'),'__name__','')=='_sync_generate':return HeldWorker(**kwargs)
        return original_thread(*args,**kwargs)
    monkeypatch.setattr(threading,'Thread',thread_factory)
    first=await agent.agent_generate_storyboard('s',None,user={'user_id':'u','role':'superadmin'})
    second=await agent.agent_generate_storyboard('s',None,user={'user_id':'u','role':'superadmin'})
    assert first['status']==second['status']=='processing' and len(starts)==1
