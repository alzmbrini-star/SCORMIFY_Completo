import ast
import asyncio
import copy
import hashlib
import io
import json
import logging
import os
from pathlib import Path
import re
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch
import uuid
from datetime import datetime, timezone, timedelta

from services.assessment_images import image_prompt, create_support_image
from services.assessment_assets import inline_assessment_assets

ROOT = Path(__file__).resolve().parents[1]


class HttpError(Exception):
    def __init__(self, status, detail):
        self.status_code, self.detail = status, detail


class Collection:
    def __init__(self): self.rows = []
    async def insert_one(self, row): self.rows.append(copy.deepcopy(row))
    async def insert_many(self, rows): self.rows.extend(copy.deepcopy(rows))
    async def find_one(self, query):
        return next((copy.deepcopy(r) for r in self.rows if all(r.get(k) == v for k,v in query.items())), None)
    async def update_one(self, query, update):
        row = next((r for r in self.rows if all(r.get(k) == v for k,v in query.items())), None)
        if row is None: return SimpleNamespace(modified_count=0)
        row.update(copy.deepcopy(update.get('$set', {})))
        return SimpleNamespace(modified_count=1)


def fixture():
    return [
        {'type':'single_choice','title':'Escuta','prompt':'Como ouvir em uma conversa?', 'options':[{'id':'a','text':'Ouvir','isCorrect':True},{'id':'b','text':'Interromper'}]},
        {'type':'multiple_choice','title':'Ambiente','prompt':'Quais condições favorecem o diálogo?', 'options':[{'id':'a','text':'Privacidade','isCorrect':True},{'id':'b','text':'Calma','isCorrect':True}]},
        {'type':'ordering','title':'Preparação','prompt':'Ordene as etapas de preparação.', 'items':[{'id':'a','text':'Observar'},{'id':'b','text':'Conversar'}]},
        {'type':'categorization','title':'Comportamentos','prompt':'Classifique os comportamentos.', 'targets':[{'id':'a','label':'Adequado'},{'id':'b','label':'Inadequado'}], 'items':[{'id':'a','text':'Ouvir','correctTarget':'a'},{'id':'b','text':'Gritar','correctTarget':'b'}]},
    ]


class AssessmentImageTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.db = SimpleNamespace(assessment_questions=Collection(), assessment_generation_jobs=Collection())
        self.project = {'id':'project-1','name':'Feedback','companyId':'company-1'}
        self.auth = AsyncMock(return_value=self.project)
        env = dict(asyncio=asyncio, hashlib=hashlib, json=json, logging=logging, os=os, re=re, uuid=uuid,
            datetime=datetime, timezone=timezone, timedelta=timedelta, Any=object,
            HTTPException=HttpError, Depends=lambda _:None, require_auth=None, BackgroundTasks=object,
            DuplicateKeyError=RuntimeError, db=self.db, PROJECTS_DIR='/tmp/project-assets',
            QUESTION_TYPES={'single_choice','multiple_choice','ordering','categorization'},
            load_authorized_project=self.auth, logger=logging.getLogger('assessment-test'))
        tree=ast.parse((ROOT/'routes/assessments.py').read_text(encoding='utf-8'))
        funcs=[n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))]
        for n in funcs:n.decorator_list=[]
        exec(compile(ast.Module(body=funcs,type_ignores=[]),'assessment-functions','exec'),env)
        self.env=env
        llm=ModuleType('emergentintegrations.llm.chat')
        rows=fixture()
        class Chat:
            def __init__(self,**kwargs):pass
            def with_model(self,*args):return self
            def with_params(self,**kwargs):return self
            async def send_message(self,*args):return json.dumps({'questions':rows})
        llm.LlmChat=Chat;llm.UserMessage=lambda **kwargs:kwargs
        self.modules=patch.dict(sys.modules,{'emergentintegrations.llm.chat':llm})
        self.modules.start()
        self.credentials=patch.dict(os.environ,{'OPENAI_API_KEY':'test-no-live-call'})
        self.credentials.start()
        self.addCleanup(self.modules.stop);self.addCleanup(self.credentials.stop)

    async def test_every_type_gets_own_persisted_support_and_roundtrips(self):
        active=maximum=0
        async def picture(question,project,database,folder):
            nonlocal active,maximum
            active+=1;maximum=max(maximum,active)
            await asyncio.sleep(0)
            active-=1
            return {'url':f'/api/projects/project-1/assets/{question["id"]}.png','kind':'image','name':question['title']}
        with patch('services.assessment_images.create_support_image',picture):
            result=await self.env['_create_questions']({'prompt':'Feedback','count':4},self.project,'author')
        self.assertEqual(result['imagesGenerated'],4)
        self.assertLessEqual(maximum,2)
        self.assertEqual(len({q['media']['url'] for q in result['items']}),4)
        for q in result['items']:
            stored=await self.db.assessment_questions.find_one({'id':q['id']})
            self.assertEqual(stored['media'],q['media'])
            self.assertEqual(stored['projectId'],'project-1')
            self.assertEqual(self.env['normalise'](stored,self.project,'author')['media'],q['media'])

    async def test_image_failure_preserves_questions_and_is_not_reported_as_success(self):
        async def picture(q,*args):
            if q['type']=='ordering':raise TimeoutError('image unavailable')
            return {'url':'/api/projects/project-1/assets/image.png','kind':'image','name':'Apoio'}
        with patch('services.assessment_images.create_support_image',picture):
            result=await self.env['_create_questions']({'prompt':'Feedback','count':4},self.project,'author')
        self.assertEqual(result['generated'],4);self.assertEqual(result['imagesGenerated'],3)
        self.assertEqual(len(self.db.assessment_questions.rows),4)
        failed=next(q for q in result['items'] if q['type']=='ordering')
        self.assertIsNone(failed['media']);self.assertEqual(failed['imageGenerationStatus'],'failed')
        self.assertIn('Preparação',result['warnings'][0])

    async def test_duplicate_start_and_worker_do_not_repeat_paid_requests(self):
        tasks=SimpleNamespace(add_task=lambda *args:None)
        payload={'projectId':'project-1','prompt':'Feedback','requestId':'request-1234567890','count':4}
        first=await self.env['start_generation'](payload,tasks,{'user_id':'author'})
        second=await self.env['start_generation'](payload,tasks,{'user_id':'author'})
        self.assertEqual(first['jobId'],second['jobId']);self.assertEqual(len(self.db.assessment_generation_jobs.rows),1)
        generate=AsyncMock(return_value={'items':[],'generated':4,'imagesGenerated':4})
        with patch.dict(self.env,{'_create_questions':generate}):
            await self.env['_run_generation'](first['jobId'],self.project,payload,'author')
            await self.env['_run_generation'](first['jobId'],self.project,payload,'author')
        generate.assert_awaited_once()

    async def test_conflicting_request_and_cross_owner_poll_are_rejected(self):
        tasks=SimpleNamespace(add_task=lambda *args:None)
        payload={'projectId':'project-1','prompt':'Feedback','requestId':'request-1234567890'}
        job=await self.env['start_generation'](payload,tasks,{'user_id':'author'})
        with self.assertRaises(HttpError) as error:
            await self.env['start_generation']({**payload,'prompt':'Other'},tasks,{'user_id':'author'})
        self.assertEqual(error.exception.status_code,409)
        with self.assertRaises(HttpError) as error:
            await self.env['generation_status'](job['jobId'],{'user_id':'other'})
        self.assertEqual(error.exception.status_code,404)

    def test_prompt_is_specific_and_does_not_include_answer_key(self):
        q={**fixture()[0],'options':[{'text':'SECRET_ANSWER','isCorrect':True}], 'explanation':'SECRET_FEEDBACK'}
        prompt=image_prompt(q,self.project)
        self.assertIn(q['prompt'],prompt);self.assertIn('Feedback',prompt)
        self.assertNotIn('SECRET_',prompt)

    async def test_asset_is_only_returned_after_persistence(self):
        from PIL import Image
        data=io.BytesIO();Image.new('RGB',(4,4),'blue').save(data,format='PNG')
        agent=ModuleType('services.ai_agent');agent._openai_image_bytes=AsyncMock(return_value=data.getvalue())
        assets=ModuleType('services.asset_store');assets.store_asset_async=AsyncMock(return_value=True)
        with tempfile.TemporaryDirectory() as folder, \
             patch.dict(sys.modules,{'services.ai_agent':agent,'services.asset_store':assets}):
            media=await create_support_image(fixture()[0],self.project,self.db,folder)
            self.assertEqual(media['kind'],'image')
            self.assertTrue((Path(folder)/'project-1/assets'/media['url'].split('/')[-1]).is_file())
            assets.store_asset_async.assert_awaited_once()
        assets.store_asset_async=AsyncMock(return_value=False)
        with tempfile.TemporaryDirectory() as folder, \
             patch.dict(sys.modules,{'services.ai_agent':agent,'services.asset_store':assets}):
            with self.assertRaises(ValueError):await create_support_image(fixture()[0],self.project,self.db,folder)

    def test_export_embeds_the_image_in_the_question_snapshot(self):
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder)/'support.png').write_bytes(b'png-fixture')
            data={'questions':[{'id':'same-id','media':{'url':'/api/projects/project-1/assets/support.png','kind':'image'}}]}
            html='<head></head><script id="assessment-data" type="application/json">'+json.dumps(data)+'</script>'
            exported=inline_assessment_assets(html,folder)
            self.assertIn('data:image/png;base64,',exported)
            self.assertIn('same-id',exported)


if __name__=='__main__':unittest.main()
