"""Offline contracts: no provider calls, GPU jobs or paid TTS in these tests."""
import asyncio
import base64
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock,MagicMock,patch
from fastapi import FastAPI,HTTPException
from fastapi.testclient import TestClient
from services import heygem
from routes import heygem as routes

CODE='12345678-1234-4321-9234-123456789abc'
USER={'user_id':'author','companyId':'company','role':'editor',
      'company':{'permissions':{'heygen':True,'elevenlabs':True}}}

class Service(unittest.IsolatedAsyncioTestCase):
    def test_configuration_and_native_video(self):
        for url in ('','http://gpu.test','https://user:pass@gpu.test','https://gpu.test?secret=1'):
            with patch.dict(os.environ,{'HEYGEM_BRIDGE_URL':url,'HEYGEM_BRIDGE_KEY':'x'*24}):
                self.assertFalse(heygem.configuration()[2])
        with patch.dict(os.environ,{'HEYGEM_BRIDGE_URL':'https://gpu.test','HEYGEM_BRIDGE_KEY':'x'*24}):
            self.assertTrue(heygem.configuration()[2])
        item=heygem.video_element('https://api.test/api/heygem/assets/'+CODE+'.mp4')
        self.assertEqual(item['type'],'video');self.assertFalse(item['autoplay'])
        self.assertTrue(item['src'].startswith('/api/heygem/assets/'))
        for value in ('https://evil.test/movie.mp4','/api/heygem/assets/../../secret.mp4'):
            with self.assertRaises(heygem.HeygemError):heygem.asset_path(value)

    async def test_no_unconfigured_network_and_catalog_allowlist(self):
        with patch.dict(os.environ,{'HEYGEM_BRIDGE_URL':'','HEYGEM_BRIDGE_KEY':''}):
            with self.assertRaises(heygem.HeygemError):await heygem.bridge('GET','/avatars')
        with patch.object(heygem,'bridge',AsyncMock(return_value={'avatars':[
            {'id':'teacher','name':'Professor','path':'/private/base.mp4'}, {'id':'../bad'}]})):
            self.assertEqual(await heygem.catalog(),[{'id':'teacher','name':'Professor'}])

    async def test_permissions_and_idempotency(self):
        self.assertIs(await routes.require_creator(USER),USER)
        with self.assertRaises(HTTPException):await routes.require_creator(dict(USER,role='aprovador'))
        with self.assertRaises(HTTPException):await routes.require_creator(dict(USER,company={'permissions':{}}))
        row={'video_id':CODE,'status':'processing','userId':'author','requestId':CODE}
        database=SimpleNamespace(heygem_videos=SimpleNamespace(find_one=AsyncMock(return_value=row)))
        request=SimpleNamespace(json=AsyncMock(return_value={'script':'Olá','consent':True,
            'avatar_id':'teacher','voice_id':'voice','request_id':CODE}))
        with patch.object(routes,'db',database),patch.object(heygem,'speech',AsyncMock()) as speech:
            self.assertEqual((await routes.generate(request,USER))['video_id'],CODE)
            speech.assert_not_awaited()
        database.heygem_videos.find_one.assert_awaited_once_with({'userId':'author','requestId':CODE})

    async def test_ambiguous_submit_preserves_id_without_repeating_tts(self):
        collection=SimpleNamespace(update_one=AsyncMock(),find_one=AsyncMock(return_value={'status':'submitting'}))
        with patch.object(routes,'db',SimpleNamespace(heygem_videos=collection)),\
             patch.object(heygem,'speech',AsyncMock(return_value=b'audio')) as speech,\
             patch.object(heygem,'submit',AsyncMock(side_effect=TimeoutError('private-key'))):
            await routes.start_job(CODE,'author','teacher','voice','Olá')
            speech.assert_awaited_once()
            change=collection.update_one.call_args.args[1]['$set']
            self.assertEqual(change['status'],'unknown');self.assertNotIn('private-key',change['error'])

    async def test_completed_poll_persists_before_exposing_url(self):
        stream=SimpleNamespace(_id='file',closed=False,write=AsyncMock(),close=AsyncMock(),abort=AsyncMock())
        collection=SimpleNamespace(find_one_and_update=AsyncMock(return_value={'video_id':CODE}),update_one=AsyncMock())
        async def download(code):yield b'\x00\x00\x00\x18ftypisomdata'
        with patch.object(routes,'db',SimpleNamespace(heygem_videos=collection)),\
             patch.object(routes,'bucket',return_value=SimpleNamespace(open_upload_stream=AsyncMock(return_value=stream))),\
             patch.object(heygem,'status',AsyncMock(return_value={'status':'completed'})),patch.object(heygem,'download',download):
            result=await routes.reconcile({'video_id':CODE,'userId':'author','status':'processing'})
        stream.close.assert_awaited_once();self.assertEqual(result['status'],'completed')
        self.assertEqual(result['video_url'],'/api/heygem/assets/'+CODE+'.mp4')

    async def test_export_materializes_and_rewrites_nested_sources(self):
        source='/api/heygem/assets/'+CODE+'.mp4'
        project={'id':'project','companyId':'company','course':{'slides':[{'elements':[
            {'src':'https://api.test'+source},{'htmlContent':'<video src="'+source+'"></video>'}]}]}}
        stream=SimpleNamespace(read=AsyncMock(side_effect=[b'video',b'']),close=MagicMock())
        database=SimpleNamespace(heygem_videos=SimpleNamespace(find_one=AsyncMock(return_value={'fileId':'file'})))
        with tempfile.TemporaryDirectory() as directory,patch('motor.motor_asyncio.AsyncIOMotorGridFSBucket',return_value=SimpleNamespace(open_download_stream=AsyncMock(return_value=stream))):
            self.assertEqual(await heygem.prepare_for_export(project,database,directory),1)
            self.assertEqual((Path(directory)/('heygem_'+CODE+'.mp4')).read_bytes(),b'video')
        self.assertNotIn('/api/heygem/',json.dumps(project))
        self.assertIn('/api/projects/project/assets/heygem_',json.dumps(project))
        database.heygem_videos.find_one.assert_awaited_once_with({'video_id':CODE,'status':'completed','companyId':'company'})

class HttpContracts(unittest.TestCase):
    def setUp(self):
        app=FastAPI();app.include_router(routes.router,prefix='/api')
        self.app=app;self.client=TestClient(app)

    def test_configuration_requires_authentication(self):
        self.assertIn(self.client.get('/api/heygem/config').status_code,(401,403))

    def test_configuration_never_exposes_secret(self):
        self.app.dependency_overrides[routes.require_auth]=lambda:USER
        with patch.dict(os.environ,{'HEYGEM_BRIDGE_KEY':'private-key-'*4,'HEYGEM_BRIDGE_URL':'https://private.test'}):
            response=self.client.get('/api/heygem/config')
        self.assertEqual(response.status_code,200)
        self.assertNotIn('private',response.text)

    def test_other_authors_job_is_not_visible(self):
        self.app.dependency_overrides[routes.require_auth]=lambda:USER
        find=AsyncMock(return_value=None)
        with patch.object(routes,'db',SimpleNamespace(heygem_videos=SimpleNamespace(find_one=find))):
            self.assertEqual(self.client.get('/api/heygem/jobs/'+CODE).status_code,404)
        self.assertEqual(find.call_args.args[0]['userId'],'author')

    def test_range_video_delivery(self):
        stream=SimpleNamespace(length=12,seek=MagicMock(),read=AsyncMock(return_value=b'345'),close=MagicMock())
        with patch.object(routes,'db',SimpleNamespace(heygem_videos=SimpleNamespace(find_one=AsyncMock(return_value={'fileId':'file'})))),\
             patch.object(routes,'bucket',return_value=SimpleNamespace(open_download_stream=AsyncMock(return_value=stream))):
            response=self.client.get('/api/heygem/assets/'+CODE+'.mp4',headers={'Range':'bytes=3-5'})
        self.assertEqual(response.status_code,206);self.assertEqual(response.content,b'345')
        self.assertEqual(response.headers['content-range'],'bytes 3-5/12');stream.seek.assert_called_once_with(3)

class GpuBridge(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec=importlib.util.spec_from_file_location('heygem_bridge',Path(__file__).parents[2]/'deploy/heygem-bridge/app.py')
        cls.bridge=importlib.util.module_from_spec(spec);spec.loader.exec_module(cls.bridge)

    def test_auth_catalog_and_path_confinement(self):
        bridge=self.bridge
        with tempfile.TemporaryDirectory() as directory,patch.object(bridge,'root',Path(directory).resolve()),\
             patch.dict(os.environ,{'HEYGEM_BRIDGE_KEY':'x'*24,'HEYGEM_AVATARS_JSON':'[]'}):
            client=TestClient(bridge.app)
            self.assertEqual(client.get('/avatars').status_code,401)
            self.assertEqual(client.get('/avatars',headers={'Authorization':'Bearer '+'x'*24}).json(),{'avatars':[]})
            with self.assertRaises(HTTPException):bridge.path_inside('../outside.mp4')
            with self.assertRaises(HTTPException):bridge.code_path('../../secret')

    def test_existing_uuid_does_not_resubmit_to_gpu(self):
        bridge=self.bridge;audio=b'audio'
        with tempfile.TemporaryDirectory() as directory,patch.object(bridge,'root',Path(directory).resolve()),\
             patch.dict(os.environ,{'HEYGEM_BRIDGE_KEY':'x'*24}),patch.object(bridge,'catalog',return_value=[{'id':'teacher'}]):
            target=bridge.code_path(CODE);target.parent.mkdir()
            import hashlib
            target.write_text(json.dumps({'avatar_id':'teacher','audio_hash':hashlib.sha256(audio).hexdigest(),'status':'submitting'}))
            with patch.object(bridge.httpx,'AsyncClient') as network:
                response=TestClient(bridge.app).post('/jobs',headers={'Authorization':'Bearer '+'x'*24},
                    json={'code':CODE,'avatar_id':'teacher','audio_base64':base64.b64encode(audio).decode()})
            self.assertEqual(response.status_code,200);network.assert_not_called()

    def test_tutor_documents_limits_and_both_entrypoints(self):
        from services.creator_guide import GUIDE
        guide=str(next(item for item in GUIDE if item['id']=='heygem'))
        for word in ('Editor','Agente','GPU','ElevenLabs','1000','autorização','HeyGen','PT-BR'):
            self.assertIn(word,guide)

if __name__=='__main__':unittest.main()
