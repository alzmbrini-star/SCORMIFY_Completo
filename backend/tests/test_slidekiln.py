import io
import base64
import re
import zipfile
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, Mock
import pytest
import httpx
from fastapi import HTTPException, BackgroundTasks
from services import slidekiln as sk
from routes import slidekiln as route


def zipped(entries):
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w') as archive:
        for k,v in entries.items(): archive.writestr(k,v)
    return out.getvalue()


def test_ppt_validation_and_zip_traversal():
    assert sk.pptx_info(zipped({'[Content_Types].xml':'x','ppt/presentation.xml':'x','ppt/slides/slide1.xml':'x'}),'a.pptx')['slides']==1
    for name in ('../secret','/secret','assets/../../secret','C:/secret'):
        with pytest.raises(ValueError):sk.safe_zip(zipped({name:'x'}))
    with pytest.raises(ValueError):sk.safe_zip(zipped({'assets/secret':'x'}).replace(b'assets/secret',b'assets\\secret'))
    with pytest.raises(ValueError):sk.pptx_info(b'bad','a.ppt')
    with pytest.raises(ValueError):sk.safe_zip(b'bad')


def test_document_is_offline_and_keeps_links():
    raw='<!doctype html><html><head><link rel="stylesheet" href="assets/styles.css"></head><body><img src="assets/a.png"><audio src="assets/a.wav"></audio><a href="https://example.com">Link</a><script src="assets/player.js"></script></body></html>'
    result=sk.offline_document(zipped({'index.html':raw,'assets/player.js':'window.SlideKiln={};','assets/styles.css':"@font-face{src:url('fonts/a.ttf')}",'assets/fonts/a.ttf':b'font','assets/a.png':b'png','assets/a.wav':b'audio'}))
    assert 'data:audio/' in result and 'data:image/png;base64,' in result
    assert 'href="https://example.com"' in result
    assert 'id="sk-mobile"' in result and 'Ampliar' in result
    assert "connect-src 'none'" in result and 'src="assets/' not in result
    assert 'allow-same-origin' not in sk.module_html(str(uuid.uuid4()),uuid.uuid4().hex+'.sk.html')


@pytest.mark.parametrize('source',['https://evil.test/a.js','../secret.js','/etc/passwd'])
def test_external_or_missing_resource_rejected(source):
    with pytest.raises(ValueError):sk.offline_document(zipped({'index.html':f'<html><head></head><body><script src="{source}"></script></body></html>','assets/player.js':'x','assets/styles.css':'x'}))


@pytest.mark.asyncio
async def test_billable_post_is_idempotent_and_not_retried(monkeypatch):
    monkeypatch.setenv('SLIDEKILN_API_KEY','not-a-real-key')
    ident=str(uuid.uuid4());calls=[]
    def handler(request):
        calls.append(request)
        assert request.headers['Idempotency-Key']==ident
        assert b'"hosted": false' in request.content
        return httpx.Response(503)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(httpx.HTTPStatusError):await sk.submit(client,b'x','a.pptx',ident)
    assert len(calls)==1


@pytest.mark.asyncio
async def test_download_does_not_forward_key_or_follow_private_redirect():
    def handler(request):
        assert 'authorization' not in request.headers
        return httpx.Response(302,headers={'location':'http://127.0.0.1/secrets'})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ValueError):await sk.download(client,str(uuid.uuid4()))


def user(role='super_admin'):
    return {'user_id':'owner','companyId':'company','role':role}


def job(status='awaiting_approval'):
    return {'id':str(uuid.uuid4()),'ownerId':'owner','companyId':'company','status':status,
            'expiresAt':(datetime.now(timezone.utc)+timedelta(minutes=10)).isoformat()}


def mocked_db(monkeypatch, record):
    collection=Mock(find_one=AsyncMock(return_value=record),update_one=AsyncMock(return_value=Mock(modified_count=1)))
    monkeypatch.setattr(route.deps,'db',Mock(slidekiln_jobs=collection))
    monkeypatch.setattr(sk,'configured',lambda:True)
    return collection


@pytest.mark.asyncio
async def test_approval_requires_both_confirmations_and_superadmin(monkeypatch):
    record=job();collection=mocked_db(monkeypatch,record)
    for payload,who in [(route.Approval(),user()),(route.Approval(approveCost=True),user()),(route.Approval(approveCost=True,confirmRights=True),user('editor'))]:
        with pytest.raises(HTTPException):await route.approve(record['id'],payload,BackgroundTasks(),who)
    collection.update_one.assert_not_awaited()


@pytest.mark.asyncio
async def test_repeated_or_expired_approval_never_submits(monkeypatch):
    record=job('processing');collection=mocked_db(monkeypatch,record);background=BackgroundTasks()
    await route.approve(record['id'],route.Approval(approveCost=True,confirmRights=True),background,user())
    assert not background.tasks
    collection.update_one.assert_not_awaited()
    record.update(status='awaiting_approval',expiresAt='2000-01-01T00:00:00+00:00')
    with pytest.raises(HTTPException):await route.approve(record['id'],route.Approval(approveCost=True,confirmRights=True),background,user())
    assert not background.tasks


@pytest.mark.asyncio
async def test_atomic_approval_schedules_only_winner(monkeypatch):
    record=job();collection=mocked_db(monkeypatch,record);background=BackgroundTasks()
    collection.update_one.return_value=Mock(modified_count=0)
    await route.approve(record['id'],route.Approval(approveCost=True,confirmRights=True),background,user())
    assert not background.tasks
    collection.update_one.return_value=Mock(modified_count=1)
    await route.approve(record['id'],route.Approval(approveCost=True,confirmRights=True),background,user())
    assert len(background.tasks)==1


@pytest.mark.asyncio
async def test_no_cross_tenant_access_and_no_secrets_in_view(monkeypatch):
    record=job();collection=mocked_db(monkeypatch,None)
    with pytest.raises(HTTPException):await route.authorized(record['id'],user())
    assert collection.find_one.call_args.args[0]['ownerId']=='owner'
    assert collection.find_one.call_args.args[0]['companyId']=='company'
    record.update(blob='secret',providerJobId='secret',sha256='secret')
    assert not {'blob','providerJobId','sha256','ownerId','companyId'}&route.public(record).keys()


def test_inline_asset_is_copied_without_modifying_original(tmp_path):
    pid=str(uuid.uuid4());filename=uuid.uuid4().hex+'.sk.html';path=tmp_path/filename
    path.write_text('<html>offline</html>')
    original=path.read_bytes();result=sk.inline_module_assets(sk.module_html(pid,filename),str(tmp_path))
    assert 'data:text/html;base64,' in result and '/api/projects/' not in result
    assert path.read_bytes()==original


def test_media_keyboard_patch_precedes_vendor_and_is_idempotent():
    original='<html><head><script>vendorNavigation()</script></head><body><audio controls></audio></body></html>'
    patched=sk.runtime_document(original)
    assert patched.index('sk-media-keyboard-v1') < patched.index('vendorNavigation')
    assert sk.runtime_document(patched)==patched
    assert 'preventDefault' not in sk.MEDIA_KEYS
    assert 'stopImmediatePropagation' in sk.MEDIA_KEYS
    assert 'AUDIO|VIDEO' in sk.MEDIA_KEYS and 'pointerdown' not in sk.MEDIA_KEYS
    assert ',true)' not in sk.MEDIA_KEYS  # preserve native target/default handlers


def test_existing_deck_exports_receive_patch_without_rewriting_asset(tmp_path):
    pid=str(uuid.uuid4());filename=uuid.uuid4().hex+'.sk.html';path=tmp_path/filename
    original=b'<html><head></head><body><audio controls></audio></body></html>'
    path.write_bytes(original)
    result=sk.inline_module_assets(sk.module_html(pid,filename),str(tmp_path))
    encoded=re.search(r'data-sk-src="data:text/html;base64,([^"]+)"',result)[1]
    exported=base64.b64decode(encoded).decode()
    assert 'sk-media-keyboard-v1' in exported
    assert '<audio controls>' in exported and path.read_bytes()==original


@pytest.mark.asyncio
async def test_existing_deck_response_is_patched_without_writing(tmp_path):
    from routes.export import _astryx_display_response
    path=tmp_path/(uuid.uuid4().hex+'.sk.html')
    original=b'<html><head></head><body><video controls></video></body></html>'
    path.write_bytes(original)
    response=await _astryx_display_response(path,'')
    assert b'sk-media-keyboard-v1' in response.body
    assert b'<video controls>' in response.body
    assert "sandbox allow-scripts allow-popups" in response.headers['content-security-policy']
    assert response.headers['cache-control']=='private, max-age=0, must-revalidate'
    assert path.read_bytes()==original


def test_tutor_explains_approval_module_limit_and_existing_provider():
    from services.creator_guide import topics_for
    topic=next(t for t in topics_for(user()) if t['id']=='import')
    text=' '.join(topic['steps'])
    for word in ('SlideKiln','ConvertAPI','Super Admin','SLIDEKILN_API_KEY','10 MB','um único bloco','Banco Central','Espaço','sem reconversão'):
        assert word in text


class EmptyCursor:
    def limit(self, value):return self
    def __aiter__(self):return self
    async def __anext__(self):raise StopAsyncIteration


@pytest.mark.asyncio
async def test_quote_only_stores_input_and_never_calls_converter(monkeypatch):
    from starlette.datastructures import UploadFile
    collection=Mock(find=Mock(return_value=EmptyCursor()),count_documents=AsyncMock(return_value=0),find_one=AsyncMock(return_value=None),insert_one=AsyncMock())
    monkeypatch.setattr(route.deps,'db',Mock(slidekiln_jobs=collection))
    uploads=Mock(upload_from_stream=AsyncMock(return_value='private-blob'),delete=AsyncMock())
    monkeypatch.setattr(route,'bucket',lambda:uploads)
    monkeypatch.setattr(sk,'configured',lambda:True)
    monkeypatch.setattr(sk,'submit',AsyncMock())
    monkeypatch.setattr(route,'usd_brl_reference',AsyncMock(return_value={'available':True,'rate':5.74,'asOfDate':'2026-11-26'}))
    data=zipped({'[Content_Types].xml':'x','ppt/presentation.xml':'x','ppt/slides/slide1.xml':'x'})
    result=await route.quote(UploadFile(io.BytesIO(data),filename='original.pptx'),'',user())
    assert result['status']=='awaiting_approval' and result['budget']['maxUsd']==1
    assert 'blob' not in result
    sk.submit.assert_not_awaited()
    collection.insert_one.assert_awaited_once()


@pytest.mark.asyncio
async def test_producer_only_inserts_fresh_project(monkeypatch,tmp_path):
    import hashlib
    data=b'approved-source';record=job('processing')
    record.update(blob='input',sha256=hashlib.sha256(data).hexdigest(),filename='a.pptx',slides=8,targetCompanyId='company')
    collection=Mock(find_one=AsyncMock(return_value=record),update_one=AsyncMock())
    projects=Mock(insert_one=AsyncMock(),update_one=AsyncMock())
    monkeypatch.setattr(route.deps,'db',Mock(slidekiln_jobs=collection,projects=projects))
    monkeypatch.setattr(route.deps,'PROJECTS_DIR',tmp_path)
    uploads=Mock(open_download_stream=AsyncMock(return_value=Mock(read=AsyncMock(return_value=data))),delete=AsyncMock())
    monkeypatch.setattr(route,'bucket',lambda:uploads)
    monkeypatch.setattr(sk,'submit',AsyncMock(return_value=str(uuid.uuid4())))
    monkeypatch.setattr(sk,'status',AsyncMock(return_value={'state':'succeeded','stats':{'warnings':[]}}))
    monkeypatch.setattr(sk,'download',AsyncMock(return_value=b'package'))
    monkeypatch.setattr(sk,'offline_document',lambda _: '<html>safe fixture</html>')
    monkeypatch.setattr(route,'store_asset_async',AsyncMock(return_value=True))
    await route.produce(record['id'])
    projects.update_one.assert_not_awaited()
    projects.insert_one.assert_awaited_once()
    saved=projects.insert_one.call_args.args[0]
    uuid.UUID(saved['id'])
    assert len(saved['course']['slides'])==1 and saved['course']['conversionReport']['pptSlideCount']==8
    assert saved['companyId']=='company' and saved['source']=='ppt'
    sk.submit.assert_awaited_once()
