import asyncio
import copy
import uuid
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
import httpx
import pytest
from fastapi import BackgroundTasks, HTTPException
from pydantic import ValidationError
from services import music_studio as service
from routes import music_studio as routes

SPEC={'title':'Aprender em equipe','mode':'educational','theme':'Colaboração, respeito e comunicação em equipe.',
      'style':'Pop leve, acolhedor, dicção clara','lyrics':'Vamos juntos aprender, ouvir e colaborar.','duration':60}
USER={'id':'u','roles':['editor'],'companyId':'c','company':{'permissions':{'elevenlabs':True}}}
def fx():return {'available':True,'rate':5.5,'asOfDate':datetime.now(timezone.utc).date().isoformat(),'source':'Banco Central','stale':False}
def draft():return {'id':str(uuid.uuid4()),'ownerId':'u','companyId':'c','spec':copy.deepcopy(SPEC),'quote':service.quote(SPEC,fx()),'status':'quoted'}


def test_quote_is_brl_dated_revision_bound_and_not_a_generation():
    spec=copy.deepcopy(SPEC);result=service.quote(spec,fx())
    assert result['estimatedUsd']==.15 and result['estimatedBrl']==.83
    assert result['exchange']['asOfDate']==fx()['asOfDate'] and result['revision']==service.signature(spec)
    assert SPEC==spec and result['rateSource']=='https://elevenlabs.io/pricing/api'


@pytest.mark.parametrize('change',[{'duration':0},{'duration':301},{'duration':60.5},{'duration':True},{'mode':'unknown'},{'theme':'x'},{'mode':'instrumental'}])
def test_invalid_specs_are_rejected(change):
    with pytest.raises(ValidationError):service.MusicSpec(**{**SPEC,**change})


def test_payload_ptbr_lyrics_and_instrumental_are_distinct_and_bounded():
    song=service.payload(SPEC)
    assert song['force_instrumental'] is False and SPEC['lyrics'] in song['prompt'] and 'português do Brasil' in song['prompt']
    instrumental=service.payload({**SPEC,'mode':'instrumental','lyrics':''})
    assert instrumental['force_instrumental'] is True and 'sem voz' in instrumental['prompt']
    assert len(song['prompt'])<4100 and song['music_length_ms']==60000


@pytest.mark.parametrize('rate',[{'available':False},{'available':True,'rate':float('nan')},{'available':True,'rate':0}])
def test_no_quote_without_valid_currency(rate):
    with pytest.raises(ValueError):service.quote(SPEC,rate)


def test_approval_requires_consent_current_revision_expiry_and_brl_ceiling():
    job=draft();q=job['quote']
    for ident,limit,consent in [(q['id'],.1,True),(q['id'],1,False),('wrong',1,True),(q['id'],float('nan'),True)]:
        with pytest.raises(ValueError):service.validate_approval(job,ident,limit,consent)
    approved=service.validate_approval(job,q['id'],1,True)
    assert approved['ceilingBrl']==1 and approved['ceilingUsd']<=1/5.5
    with pytest.raises(ValueError):service.validate_approval(job,q['id'],1,True,datetime.now(timezone.utc)+timedelta(days=2))
    job['spec']['lyrics']='Texto modificado'
    with pytest.raises(ValueError):service.validate_approval(job,q['id'],1,True)


class Collection:
    def __init__(self,job=None):self.rows={} if job is None else {job['id']:copy.deepcopy(job)}
    def matches(self,row,query):
        for key,wanted in query.items():
            actual=row
            for part in key.split('.'):actual=actual.get(part) if isinstance(actual,dict) else None
            if isinstance(wanted,dict) and '$in' in wanted:
                if actual not in wanted['$in']:return False
            elif actual!=wanted:return False
        return True
    async def find_one(self,query,*args):
        return next((copy.deepcopy(row) for row in self.rows.values() if self.matches(row,query)),None)
    async def update_one(self,query,update,upsert=False):
        for row in self.rows.values():
            if self.matches(row,query):
                row.update(copy.deepcopy(update.get('$set',{})))
                return SimpleNamespace(modified_count=1)
        if upsert:
            row={**query,**copy.deepcopy(update.get('$setOnInsert',{}))};self.rows[row['id']]=row
            return SimpleNamespace(modified_count=1)
        return SimpleNamespace(modified_count=0)


@pytest.fixture
def setup(monkeypatch):
    job=draft();collection=Collection(job)
    # No projects collection exists: all operations must remain independent of courses.
    monkeypatch.setattr(routes.deps,'db',SimpleNamespace(music_jobs=collection))
    monkeypatch.setattr(service,'api_key',lambda:'test-key')
    monkeypatch.setattr(routes,'usd_brl_reference',AsyncMock(return_value=fx()))
    return job,collection


@pytest.mark.asyncio
async def test_estimate_transport_retry_reuses_quote_and_never_synthesizes(setup,monkeypatch):
    job,db=setup;call=AsyncMock();monkeypatch.setattr(service,'compose',call)
    body=routes.Estimate(spec=SPEC,requestId=uuid.uuid4())
    first=await routes.estimate(body,USER);second=await routes.estimate(body,USER)
    assert first==second and first['status']=='quoted' and 'approval' not in first
    call.assert_not_awaited();routes.usd_brl_reference.assert_awaited_once()


@pytest.mark.asyncio
async def test_generation_requires_approval_and_is_atomic_under_duplicate_clicks(setup):
    job,db=setup;tasks=BackgroundTasks();body=routes.Generate(quoteId=job['quote']['id'])
    with pytest.raises(HTTPException):await routes.generate(job['id'],body,tasks,USER)
    assert len(tasks.tasks)==0
    approved=await routes.approve(job['id'],routes.Approve(quoteId=body.quoteId,ceilingBrl=1,consent=True),USER)
    assert approved['status']=='approved' and len(tasks.tasks)==0
    await asyncio.gather(*(routes.generate(job['id'],body,tasks,USER) for _ in range(4)))
    assert len(tasks.tasks)==1 and db.rows[job['id']]['status']=='generating'


@pytest.mark.asyncio
async def test_owner_company_role_and_eleven_permission_are_enforced(setup):
    job,_=setup
    for user in [{**USER,'id':'other'},{**USER,'companyId':'other'},{**USER,'roles':['viewer']},{**USER,'company':{}}]:
        with pytest.raises(HTTPException):await routes.authorized(job['id'],user)


@pytest.mark.asyncio
async def test_worker_persists_independent_audio_and_retrieves_authenticated_copy(setup,monkeypatch,tmp_path):
    job,db=setup;db.rows[job['id']]['status']='generating'
    raw=b'ID3'+b'\x00'*200
    compose=AsyncMock(return_value=raw);store=AsyncMock()
    monkeypatch.setattr(service,'compose',compose)
    routes.deps.db.music_assets=SimpleNamespace(update_one=store,find_one=AsyncMock(return_value={'data':raw}))
    await routes.produce(job['id'],SPEC)
    assert db.rows[job['id']]['status']=='ready' and store.call_args.args[0]=={'_id':job['id']}
    assert store.call_args.args[1]['$setOnInsert']['data']==raw
    response=await routes.audio(job['id'],USER)
    assert response.body==raw and response.headers['cache-control']=='private, no-store'
    compose.assert_awaited_once()


@pytest.mark.asyncio
async def test_ambiguous_worker_failure_and_restart_never_repeat_paid_post(setup,monkeypatch):
    job,db=setup;db.rows[job['id']]['status']='generating'
    call=AsyncMock(side_effect=httpx.ReadTimeout('secret provider diagnostic'))
    monkeypatch.setattr(service,'compose',call)
    await routes.produce(job['id'],SPEC)
    assert db.rows[job['id']]['status']=='unknown' and 'secret' not in str(db.rows[job['id']])
    tasks=BackgroundTasks();await routes.generate(job['id'],routes.Generate(quoteId=job['quote']['id']),tasks,USER)
    assert not tasks.tasks;call.assert_awaited_once()
    db.rows[job['id']].update(status='generating',startedAt=(datetime.now(timezone.utc)-timedelta(minutes=16)).isoformat())
    assert (await routes.get(job['id'],USER))['status']=='unknown'


@pytest.mark.asyncio
async def test_real_http_adapter_one_post_validates_audio_and_sanitizes_provider_errors(monkeypatch):
    original=httpx.AsyncClient;requests=[]
    async def handle(request):
        requests.append(request);return httpx.Response(200,content=b'ID3'+b'\x00'*200,headers={'Content-Type':'audio/mpeg'})
    monkeypatch.setattr(service,'api_key',lambda:'private-test-key')
    monkeypatch.setattr(service.httpx,'AsyncClient',lambda **kwargs:original(transport=httpx.MockTransport(handle),**kwargs))
    assert (await service.compose(SPEC)).startswith(b'ID3')
    assert len(requests)==1 and requests[0].method=='POST' and requests[0].url.path=='/v1/music'
    assert requests[0].headers['xi-api-key']=='private-test-key'


def test_tutor_has_real_entrypoints_cost_gate_preservation_and_export_limitations():
    from services.creator_guide import GUIDE
    text=str(next(row for row in GUIDE if row['id']=='music-studio'))
    for term in ['Músicas IA','Eleven Music','reais','Banco Central','24 horas','sem repetição','MP3','HTML/SCORM','Play inicial','não altera cursos']:
        assert term.casefold() in text.casefold()
