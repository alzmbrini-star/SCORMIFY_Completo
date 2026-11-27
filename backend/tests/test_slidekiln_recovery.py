import base64
import hashlib
import io
import uuid
import zipfile
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, Mock, MagicMock
import pytest
from fastapi import BackgroundTasks, HTTPException
from routes import slidekiln as route
from services import slidekiln as sk, asset_store as store


def user():return {'user_id':'owner','companyId':'company','role':'super_admin'}
def record():return {'id':str(uuid.uuid4()),'status':'unknown','ownerId':'owner','companyId':'company',
    'targetCompanyId':'company','filename':'meu.pptx','slides':30,'providerJobId':str(uuid.uuid4())}


def setup_job(monkeypatch,job):
    async def update(query,change):
        job.update(change['$set'])
        return Mock(modified_count=1)
    collection=Mock(find_one=AsyncMock(return_value=job),update_one=AsyncMock(side_effect=update))
    projects=Mock(find_one=AsyncMock(return_value=None),insert_one=AsyncMock(),update_one=AsyncMock())
    monkeypatch.setattr(route.deps,'db',Mock(slidekiln_jobs=collection,projects=projects))
    monkeypatch.setattr(route,'resolve_company_id_for_creation',AsyncMock(return_value='company'))
    monkeypatch.setattr(sk,'configured',lambda:True)
    return collection,projects


@pytest.mark.asyncio
async def test_recovery_claim_once_and_never_submits(monkeypatch):
    job=record();collection,_=setup_job(monkeypatch,job)
    background=BackgroundTasks()
    response=await route.recover(job['id'],background,user())
    assert response['status']=='recovering' and not response['canRecover']
    assert len(background.tasks)==1 and background.tasks[0].args==(job['id'],True)
    with pytest.raises(HTTPException):await route.recover(job['id'],BackgroundTasks(),user())
    collection.update_one.assert_awaited_once()


@pytest.mark.asyncio
async def test_recovery_race_loser_does_not_start_worker(monkeypatch):
    job=record();collection,_=setup_job(monkeypatch,job)
    collection.update_one.side_effect=None
    collection.update_one.return_value=Mock(modified_count=0)
    background=BackgroundTasks()
    await route.recover(job['id'],background,user())
    assert not background.tasks


@pytest.mark.asyncio
async def test_completed_recovery_returns_same_project(monkeypatch):
    job=record();job.update(status='completed',projectId=str(uuid.uuid4()))
    collection,_=setup_job(monkeypatch,job);background=BackgroundTasks()
    result=await route.recover(job['id'],background,user())
    assert result['projectId']==job['projectId'] and not background.tasks
    collection.update_one.assert_not_awaited()


@pytest.mark.asyncio
async def test_recovery_requires_ownership_and_a_previous_result(monkeypatch):
    job=record();collection,_=setup_job(monkeypatch,job)
    collection.find_one.return_value=None
    with pytest.raises(HTTPException) as exc:await route.recover(job['id'],BackgroundTasks(),user())
    assert exc.value.status_code==404
    query=collection.find_one.call_args.args[0]
    assert query['ownerId']=='owner' and query['companyId']=='company'
    collection.find_one.return_value=job;job.pop('providerJobId')
    with pytest.raises(HTTPException) as exc:await route.recover(job['id'],BackgroundTasks(),user())
    assert exc.value.status_code==409
    collection.update_one.assert_not_awaited()


def test_stale_active_attempt_is_visible_and_recoverable_without_mutation():
    job=record();job.update(status='processing',approvedAt=(datetime.now(timezone.utc)-timedelta(minutes=25)).isoformat())
    result=route.public(job)
    assert result['status']=='interrupted' and result['canRecover']
    assert job['status']=='processing'
    assert not {'providerJobId','packageBlob','blob','ownerId','companyId'}&result.keys()


@pytest.mark.asyncio
async def test_history_is_bounded_scoped_and_redacted(monkeypatch):
    job=record()
    class Cursor:
        def sort(self,*args):return self
        def limit(self,n):assert n==20;return self
        def __aiter__(self):self.done=False;return self
        async def __anext__(self):
            if self.done:raise StopAsyncIteration
            self.done=True;return job
    collection=Mock(find=Mock(return_value=Cursor()))
    monkeypatch.setattr(route.deps,'db',Mock(slidekiln_jobs=collection))
    result=await route.history(user())
    collection.find.assert_called_once_with({'ownerId':'owner','companyId':'company'})
    assert result[0]['filename']=='meu.pptx' and result[0]['canRecover']
    assert 'providerJobId' not in result[0]


@pytest.mark.asyncio
@pytest.mark.parametrize('cached',[False,True])
async def test_worker_recovers_without_original_input_or_billable_submit(monkeypatch,tmp_path,cached):
    job=record();job['status']='recovering'
    if cached:job['packageBlob']='saved-zip'
    collection,projects=setup_job(monkeypatch,job)
    monkeypatch.setattr(route.deps,'PROJECTS_DIR',tmp_path)
    source=Mock(open_download_stream=AsyncMock(side_effect=AssertionError('must not reopen/reupload PPT')),delete=AsyncMock())
    monkeypatch.setattr(route,'bucket',lambda:source)
    saved=Mock(open_download_stream=AsyncMock(return_value=Mock(read=AsyncMock(return_value=b'previous-zip'))),
               upload_from_stream=AsyncMock(return_value='saved-zip'))
    monkeypatch.setattr(route,'packages',lambda:saved)
    monkeypatch.setattr(sk,'submit',AsyncMock(side_effect=AssertionError('no paid conversion')))
    monkeypatch.setattr(sk,'status',AsyncMock(return_value={'state':'succeeded','stats':{'warnings':[]}}))
    monkeypatch.setattr(sk,'download',AsyncMock(return_value=b'previous-zip'))
    monkeypatch.setattr(sk,'offline_document',lambda package:'<html><head></head><body>original</body></html>')
    monkeypatch.setattr(route,'store_asset_async',AsyncMock(return_value=True))
    await route.produce(job['id'],True)
    assert job['status']=='completed' and job['packageBlob']=='saved-zip'
    assert job['projectId']==job['pendingProjectId']
    sk.submit.assert_not_awaited();source.open_download_stream.assert_not_awaited();source.delete.assert_not_awaited()
    if cached:sk.download.assert_not_awaited();saved.upload_from_stream.assert_not_awaited()
    else:sk.download.assert_awaited_once();saved.upload_from_stream.assert_awaited_once()
    projects.update_one.assert_not_awaited();projects.insert_one.assert_awaited_once()
    project=projects.insert_one.call_args.args[0]
    assert project['id']==job['projectId'] and project['importJobId']==job['id']


@pytest.mark.asyncio
async def test_interrupted_finalization_reuses_own_project_without_edit(monkeypatch,tmp_path):
    job=record();job.update(status='recovering',packageBlob='zip',pendingProjectId=str(uuid.uuid4()))
    _,projects=setup_job(monkeypatch,job)
    projects.find_one.return_value={'id':job['pendingProjectId'],'importJobId':job['id'],'userId':job['ownerId']}
    monkeypatch.setattr(route,'packages',lambda:Mock(open_download_stream=AsyncMock(return_value=Mock(read=AsyncMock(return_value=b'zip')))))
    monkeypatch.setattr(sk,'offline_document',lambda _: '<html>safe</html>')
    await route.produce(job['id'],True)
    assert job['status']=='completed' and job['projectId']==job['pendingProjectId']
    projects.insert_one.assert_not_awaited();projects.update_one.assert_not_awaited()


def test_document_larger_than_old_limit_preserves_original_image_bytes():
    image=b'original-image-byte'*500000
    raw='<html><head><link href="assets/styles.css"></head><body><img src="assets/a.png"><script src="assets/player.js"></script></body></html>'
    package=io.BytesIO()
    with zipfile.ZipFile(package,'w',zipfile.ZIP_DEFLATED) as z:
        for name,data in {'index.html':raw,'assets/styles.css':'','assets/player.js':'window.SlideKiln={};','assets/a.png':image}.items():z.writestr(name,data)
    document=sk.offline_document(package.getvalue())
    assert 10*1024*1024<len(document.encode())<sk.MAX_DOCUMENT
    assert base64.b64encode(image).decode() in document
    assert sk.MAX_DOCUMENT==32*1024*1024


@pytest.mark.asyncio
async def test_large_slidekiln_asset_uses_gridfs_and_restores_exact_bytes(monkeypatch,tmp_path):
    raw=b'unchanged-source'*600000
    path=tmp_path/'large.sk.html';path.write_bytes(raw)
    collection=Mock(find_one=AsyncMock(return_value=None),update_one=AsyncMock())
    db=Mock(project_assets=collection)
    bucket=Mock(upload_from_stream=AsyncMock(return_value='chunk-id'),delete=AsyncMock(),
                open_download_stream=AsyncMock(return_value=Mock(read=AsyncMock(return_value=raw))))
    monkeypatch.setattr(store,'AsyncIOMotorGridFSBucket',lambda *_a,**_kw:bucket)
    assert await store.store_asset_async(db,'new-project',path.name,str(path))
    update=collection.update_one.call_args.args[1]
    assert update['$set']['gridfs_id']=='chunk-id' and 'data' not in update['$set']
    assert update['$set']['sha256']==hashlib.sha256(raw).hexdigest()
    bucket.upload_from_stream.assert_awaited_once()
    collection.find_one.return_value={'gridfs_id':'chunk-id','content_type':'text/html'}
    restored,mime=await store.retrieve_asset_async(db,'new-project',path.name)
    assert restored==raw and mime=='text/html'
    assert not store._chunked_slidekiln('original.png',len(raw))


@pytest.mark.asyncio
async def test_repeated_large_asset_persistence_does_not_duplicate_chunks(monkeypatch,tmp_path):
    raw=b'source-original'*600000;path=tmp_path/'large.sk.html';path.write_bytes(raw)
    collection=Mock(find_one=AsyncMock(return_value={'gridfs_id':'existing','sha256':hashlib.sha256(raw).hexdigest()}),update_one=AsyncMock())
    create=Mock(side_effect=AssertionError('must not duplicate chunks'))
    monkeypatch.setattr(store,'AsyncIOMotorGridFSBucket',create)
    assert await store.store_asset_async(Mock(project_assets=collection),'new-project',path.name,str(path))
    create.assert_not_called();collection.update_one.assert_not_awaited()


def test_large_asset_sync_restore_for_offline_exports(monkeypatch,tmp_path):
    raw=b'export-original-media'*100
    db=Mock(project_assets=Mock(find_one=Mock(return_value={'gridfs_id':'chunks','content_type':'text/html'})))
    client=MagicMock();client.__getitem__.return_value=db
    monkeypatch.setattr(store,'MongoClient',lambda *_a,**_kw:client)
    bucket=Mock(download_to_stream=Mock(side_effect=lambda _id,stream:stream.write(raw)))
    monkeypatch.setattr(store,'GridFSBucket',lambda *_a,**_kw:bucket)
    dest=tmp_path/'restored.sk.html'
    assert store.retrieve_asset_sync('mongodb://test.invalid','test','new-project',dest.name,str(dest))
    assert dest.read_bytes()==raw
    bucket.download_to_stream.assert_called_once()
    client.close.assert_called_once()
