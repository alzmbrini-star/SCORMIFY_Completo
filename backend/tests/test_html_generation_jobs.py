"""Test job persistence/ownership without a live database or paid AI calls."""
import ast
import asyncio
import hashlib
import json
import logging
import sys
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from types import SimpleNamespace, ModuleType
from unittest.mock import AsyncMock, patch


class HttpError(Exception):
    def __init__(self, status_code, detail):
        self.status_code, self.detail = status_code, detail


class DuplicateKeyError(Exception):
    pass


class Collection:
    def __init__(self): self.docs = {}

    def match(self, query):
        return next((doc for doc in self.docs.values() if all(doc.get(k) == v for k, v in query.items())), None)

    async def find_one(self, query):
        doc = self.match(query)
        return dict(doc) if doc else None

    async def insert_one(self, doc):
        if doc['_id'] in self.docs: raise DuplicateKeyError()
        self.docs[doc['_id']] = dict(doc)

    async def update_one(self, query, update):
        doc = self.match(query)
        if doc: doc.update(update['$set'])
        return SimpleNamespace(modified_count=int(doc is not None))


class Request(SimpleNamespace):
    def model_dump(self): return vars(self).copy()


class Jobs(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.collection = Collection()
        self.auth = AsyncMock()
        self.scope = dict(asyncio=asyncio, hashlib=hashlib, json=json, datetime=datetime,
                          timezone=timezone, timedelta=timedelta, HTTPException=HttpError,
                          DuplicateKeyError=DuplicateKeyError, HtmlJobRequest=object,
                          BackgroundTasks=object, Depends=lambda _: None, require_auth=None,
                          db=SimpleNamespace(html_generation_jobs=self.collection),
                          load_authorized_project=self.auth, logger=logging.getLogger('job-test'))
        source = Path(__file__).resolve().parents[1] / 'routes' / 'html_generation_jobs.py'
        functions = [node for node in ast.parse(source.read_text(encoding='utf-8')).body
                     if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
        for node in functions: node.decorator_list = []
        exec(compile(ast.Module(body=functions, type_ignores=[]), str(source), 'exec'), self.scope)
        self.body = Request(prompt='Crie um simulador', courseContext='Curso de vendas',
                            projectId='project', requestId='unique-request-id-0001')
        self.user = {'user_id': 'alice', 'companyId': 'one'}
        self.tasks = []
        self.background = SimpleNamespace(add_task=lambda *args: self.tasks.append(args))

    async def start(self, user=None):
        return await self.scope['start_html_job'](self.body, self.background, user or self.user)

    async def test_lost_post_response_deduplicates_and_authorizes_project(self):
        first, second = await self.start(), await self.start()
        self.assertEqual(first, second)
        self.assertEqual(len(self.collection.docs), 1)
        self.auth.assert_awaited_with('project', self.user)
        self.body.prompt = 'Outro simulador'
        with self.assertRaises(HttpError) as err: await self.start()
        self.assertEqual(err.exception.status_code, 409)

    async def test_worker_is_claimed_once_and_result_is_recoverable(self):
        self.body.simulatorComplexity='advanced'
        self.body.simulatorVisualStyle='technical'
        job = await self.start()
        fake = ModuleType('routes.agent')
        fake.GenerateHtmlRequest = lambda **kw: SimpleNamespace(**kw)
        fake.generate_html_with_ai = AsyncMock(return_value={'html': '<html>Atividade</html>'})
        with patch.dict(sys.modules, {'routes.agent': fake}):
            for function, *args in self.tasks + self.tasks: await function(*args)
        fake.generate_html_with_ai.assert_awaited_once()
        request=fake.generate_html_with_ai.call_args.args[0]
        self.assertEqual(request.simulatorComplexity,'advanced')
        self.assertEqual(request.simulatorVisualStyle,'technical')
        result = await self.scope['get_html_job'](job['jobId'], self.user)
        self.assertEqual(result['html'], '<html>Atividade</html>')
        self.assertNotIn('ownerId', result)
        self.assertNotIn('requestHash', result)
        self.assertEqual((await self.start())['status'], 'done')

    async def test_another_owner_cannot_read_result(self):
        job = await self.start()
        with self.assertRaises(HttpError) as err:
            await self.scope['get_html_job'](job['jobId'], {'user_id': 'bob'})
        self.assertEqual(err.exception.status_code, 404)
        self.assertNotEqual((await self.start({'user_id': 'bob'}))['jobId'], job['jobId'])

    async def test_validation_failure_is_preserved(self):
        job = await self.start()
        fake = ModuleType('routes.agent')
        fake.GenerateHtmlRequest = lambda **kw: kw
        fake.generate_html_with_ai = AsyncMock(side_effect=HttpError(422, 'O controle não altera o cenário.'))
        with patch.dict(sys.modules, {'routes.agent': fake}):
            function, *args = self.tasks[0]
            await function(*args)
        result = await self.scope['get_html_job'](job['jobId'], self.user)
        self.assertEqual(result['status'], 'error')
        self.assertIn('controle', result['error'])
        self.assertNotIn('html', result)

    async def test_orphaned_job_after_restart_has_actionable_error(self):
        job = await self.start()
        self.collection.docs[job['jobId']].update(status='running', updatedAt=datetime.now(timezone.utc) - timedelta(minutes=21))
        result = await self.scope['get_html_job'](job['jobId'], self.user)
        self.assertEqual(result['status'], 'error')
        self.assertIn('nova tentativa', result['error'])

    async def test_cancellation_marks_job_interrupted(self):
        job = await self.start()
        fake = ModuleType('routes.agent')
        fake.GenerateHtmlRequest = lambda **kw: kw
        fake.generate_html_with_ai = AsyncMock(side_effect=asyncio.CancelledError())
        with patch.dict(sys.modules, {'routes.agent': fake}):
            function, *args = self.tasks[0]
            with self.assertRaises(asyncio.CancelledError): await function(*args)
        result = await self.scope['get_html_job'](job['jobId'], self.user)
        self.assertIn('reinicialização', result['error'])


if __name__ == '__main__': unittest.main()
