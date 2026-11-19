import base64,copy,uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
from fastapi import HTTPException
from services.educational_film import Board,media_keys,revision,quote,require_ready
from services.film_worker import operation_signature
from services.film_revisions import revision_copy,copy_compatible_media
from services.asset_store import retrieve_asset_async
from services.creator_guide import GUIDE
from tests.test_educational_films import film,scope

class Collection:
    def __init__(self,docs=()):self.docs=copy.deepcopy(list(docs));self.writes=[]
    async def find_one(self,query,projection=None):
        return next((copy.deepcopy(d) for d in self.docs if all(d.get(k)==v for k,v in query.items())),None)
    async def update_one(self,query,change,upsert=False):
        self.writes.append((copy.deepcopy(query),copy.deepcopy(change)))
        d=next((d for d in self.docs if all(d.get(k)==v for k,v in query.items())),None)
        if d is None:
            if not upsert:return SimpleNamespace(matched_count=0,modified_count=0)
            d={**query,**copy.deepcopy(change.get('$setOnInsert',{}))};self.docs.append(d)
        d.update(copy.deepcopy(change.get('$set',{})))
        return SimpleNamespace(matched_count=1,modified_count=1)

def completed():
    f=film(True);f.update(status='completed',videoUrl='/old/final.mp4',subtitlesUrl='/old/captions.srt',runId='old-run',error=None,
        sourceText='Material original completo.',sourceName='ementa.docx')
    assets=[]
    for key in media_keys(f['board']):
        ext='png' if key.startswith(('character_','frame_')) else 'mp4' if key.startswith('video_') else 'mp3'
        name=f'{key}.{ext}'
        f['operations'][key]={'status':'ready','signature':operation_signature(f['board'],key),'filename':name,
            'kind':'video' if ext=='mp4' else 'image' if ext=='png' else 'voice','url':f'/api/projects/{f["projectId"]}/assets/{name}',
            'taskId':'old-task','approval':'old-token'}
        assets.append({'project_id':f['projectId'],'filename':name,'data':base64.b64encode(key.encode()).decode(),'content_type':'application/octet-stream'})
    return f,assets

def setup():
    f,assets=completed();s=scope(f)
    s.db.educational_films=Collection([f]);s.db.projects=Collection([{'id':'original','course':{'questions':['preserve'],'slides':['preserve']}}]);s.db.project_assets=Collection(assets)
    return s,f

@pytest.mark.asyncio
async def test_copy_is_independent_idempotent_and_keeps_original_bytes_approvals_and_courses():
    s,f=setup();original=copy.deepcopy(f);courses=copy.deepcopy(s.db.projects.docs);source_assets=copy.deepcopy(s.db.project_assets.docs)
    body=s.RevisionCopy(revision=f['revision'],requestId=uuid.uuid4());user={'id':'u','companyId':'c'}
    copied=await s.create_revision_copy(f['id'],body,user)
    again=await s.create_revision_copy(f['id'],body,user)
    assert copied==again and copied['id']!=f['id'] and copied['projectId']!=f['projectId']
    assert copied['revisionOfFilmId']==f['id'] and copied['sourceRevision']==f['revision']
    assert copied['status']=='draft' and copied['storyboardApproval'] is None and copied['budgetApproval'] is None
    assert not any(k in copied for k in ('videoUrl','subtitlesUrl','runId','progress'))
    assert copied['board']['scenes']==f['board']['scenes'] and copied['sourceText']==f['sourceText']
    assert copied['reusedMediaCount']==len(media_keys(f['board']))
    assert len(s.db.projects.docs)==2 and s.db.projects.docs[0]==courses[0]
    assert s.db.educational_films.docs[0]==original
    assert s.db.project_assets.docs[:len(source_assets)]==source_assets
    for op in copied['operations'].values():
        assert copied['projectId'] in op['url'] and 'taskId' not in op and 'approval' not in op
    assert len(s.db.project_assets.docs)==2*len(source_assets)
    # Own binaries survive absence of the original project's files.
    s.db.project_assets.docs=[d for d in s.db.project_assets.docs if d['project_id']==copied['projectId']]
    raw,_=await retrieve_asset_async(s.db,copied['projectId'],'video_0.mp4')
    assert raw==b'video_0'
    s.run.assert_not_awaited()
    with pytest.raises(ValueError):require_ready(copied,copied['revision'])
    approved=await s.approve_storyboard(copied['id'],s.Approval(revision=copied['revision']),user)
    assert approved['quote']['estimatedUsd']==0
    with pytest.raises(ValueError):require_ready(approved,approved['revision'])
    with pytest.raises(HTTPException):await s.generate(copied['id'],s.Approval(revision=copied['revision']),user)
    s.run.assert_not_awaited()

@pytest.mark.parametrize('change,dropped',[
    ('narration',{'voice_0'}),('voice',{'voice_0','voice_1','voice_2'}),
    ('visual',{'frame_0','video_0'}),('duration',{'video_0','music'}),
    ('character',{'character_0','frame_0','video_0','frame_1','video_1','frame_2','video_2'}),
    ('music',{'music'}),('volume',set()),('title',set())])
@pytest.mark.asyncio
async def test_editing_revision_reuses_only_compatible_media_and_never_inherits_budget(change,dropped):
    s,f=setup();user={'id':'u','companyId':'c'}
    copied=await s.create_revision_copy(f['id'],s.RevisionCopy(revision=f['revision'],requestId=uuid.uuid4()),user)
    b=copy.deepcopy(copied['board'])
    if change=='narration':b['scenes'][0]['narration']='Vamos colaborar melhor.'
    if change=='voice':b['narratorVoice']='differentVoice'
    if change=='visual':b['scenes'][0]['visual']='Ana explica uma ideia em um novo cenário de escritório.'
    if change=='duration':b['scenes'][0]['duration']=10
    if change=='character':b['characters'][0]['description']='Mulher adulta com casaco vermelho e cabelo preto.'
    if change=='music':b['musicPrompt']='Trilha instrumental original animada com piano.'
    if change=='volume':b['musicVolume']=20
    if change=='title':b['title']='Título revisado para o cliente'
    edited=await s.edit(copied['id'],s.Edit(revision=copied['revision'],board=Board(**b)),user)
    assert set(copied['operations'])-set(edited['operations'])==dropped
    assert edited['storyboardApproval'] is None and edited['budgetApproval'] is None and edited['quote'] is None
    assert edited['reusedMediaCount']==len(copied['operations'])-len(dropped)
    assert s.db.educational_films.docs[0]==f
    s.run.assert_not_awaited()

@pytest.mark.asyncio
async def test_missing_or_incompatible_assets_are_not_falsely_quoted_as_reusable():
    s,f=setup();s.db.project_assets.docs=[d for d in s.db.project_assets.docs if d['filename']!='video_0.mp4']
    s.db.educational_films.docs[0]['operations']['frame_0']['signature']='stale'
    copied=await s.create_revision_copy(f['id'],s.RevisionCopy(revision=f['revision'],requestId=uuid.uuid4()),{'id':'u','companyId':'c'})
    assert 'video_0' not in copied['operations'] and 'frame_0' not in copied['operations']
    assert 'não estavam disponíveis' in copied['reuseNotice']
    copied['storyboardApproval']=copied['revision'];q=quote(copied)
    assert q['items'][0]['quantity']==1 and q['items'][1]['quantity']==5
    s.run.assert_not_awaited()

@pytest.mark.parametrize('status',['generating','planning','unknown'])
@pytest.mark.asyncio
async def test_live_or_uncertain_production_is_not_copied(status):
    s,f=setup();s.db.educational_films.docs[0]['status']=status
    with pytest.raises(HTTPException):await s.create_revision_copy(f['id'],s.RevisionCopy(revision=f['revision'],requestId=uuid.uuid4()),{'id':'u','companyId':'c'})
    assert not s.db.projects.writes and not s.db.project_assets.writes
    s.run.assert_not_awaited()

@pytest.mark.parametrize('state',['sending','unknown','submitted'])
@pytest.mark.asyncio
async def test_pending_paid_tasks_are_never_copied_or_repeated(state):
    s,f=setup();s.db.educational_films.docs[0]['operations']['video_0']['status']=state
    with pytest.raises(HTTPException):await s.create_revision_copy(f['id'],s.RevisionCopy(revision=f['revision'],requestId=uuid.uuid4()),{'id':'u','companyId':'c'})
    assert not s.db.project_assets.writes and not s.db.projects.writes

@pytest.mark.asyncio
async def test_permissions_stale_revision_and_failed_storage_do_not_write_source():
    s,f=setup();body=s.RevisionCopy(revision='stale',requestId=uuid.uuid4())
    for user in ({'id':'other','companyId':'c'},{'id':'u','companyId':'other'},{'id':'u','companyId':'c'}):
        with pytest.raises(HTTPException):await s.create_revision_copy(f['id'],body,user)
    assert not s.db.project_assets.writes and not s.db.projects.writes
    s.db.project_assets.update_one=AsyncMock(side_effect=RuntimeError('private storage error'))
    with pytest.raises(HTTPException) as error:await s.create_revision_copy(f['id'],s.RevisionCopy(revision=f['revision'],requestId=uuid.uuid4()),{'id':'u','companyId':'c'})
    assert error.value.status_code==503 and 'private' not in str(error.value)
    assert not s.db.projects.writes and s.db.educational_films.docs[0]==f
    s.run.assert_not_awaited()

def test_tutor_explains_copy_permissions_storage_reuse_and_new_approvals():
    topic=str(next(t for t in GUIDE if t['id']=='film-revision-copy'))
    for term in ('Criar cópia de revisão','projeto independente','armazenamento','novamente storyboard e orçamento','HTML/SCORM','não chama provedores'):
        assert term in topic
