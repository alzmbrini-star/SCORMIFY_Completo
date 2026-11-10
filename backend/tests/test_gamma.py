import ast
import asyncio
import io
import unittest
import uuid
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException, Query
from PIL import Image
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from services import gamma_api
from models import Project


def routes(**values):
    path = Path(__file__).resolve().parents[1] / 'routes/gamma.py'
    nodes = [n for n in ast.parse(path.read_text(encoding='utf8')).body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
    for node in nodes:
        if hasattr(node, 'decorator_list'): node.decorator_list = []
    from datetime import datetime, timezone, timedelta
    scope = dict(Depends=lambda _: None, require_auth=None, HTTPException=HTTPException, BaseModel=BaseModel,
        ConfigDict=ConfigDict, Field=Field, model_validator=model_validator, Query=Query, uuid=uuid, gamma_api=gamma_api, Project=Project,
        datetime=datetime, timezone=timezone, timedelta=timedelta, asyncio=asyncio, Path=Path,
        has_any_role=lambda u, *roles: bool(set(u.get('roles', [])) & (set(roles) | {'super_admin'})))
    scope.update(values)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), 'exec'), scope)
    return SimpleNamespace(**scope)


def archive(names):
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w') as z:
        for name, color in names:
            image = io.BytesIO(); Image.new('RGB', (320, 180), color).save(image, 'PNG')
            z.writestr(name, image.getvalue())
    return output.getvalue()


class GammaTests(unittest.IsolatedAsyncioTestCase):
    def test_flexible_count_validated_in_model_and_payload(self):
        model=routes().Generate
        for value in [1, 12, 25, 100]:
            data=model(requestId=uuid.uuid4(), title='Teste', prompt='Conteúdo para apresentação', numCards=value)
            body=gamma_api.generation_payload('Teste','Conteúdo',num_cards=data.numCards)
            self.assertEqual(body['numCards'], value)
            self.assertIn(f'meta de {value} slides', body['additionalInstructions'])
            self.assertNotIn('três slides de desenvolvimento', body['additionalInstructions'])
        for value in [0,-1,101,1.5,True,'12',None]:
            with self.assertRaises(ValidationError): model(requestId=uuid.uuid4(), title='Teste', prompt='Conteúdo para apresentação', numCards=value)
            with self.assertRaises(gamma_api.GammaError): gamma_api.generation_payload('Teste','Conteúdo',num_cards=value)
        self.assertEqual(model(requestId=uuid.uuid4(),title='Teste',prompt='Conteúdo para apresentação').numCards,5)

    def test_archive_accepts_more_than_twenty_cards(self):
        self.assertEqual(len(list(gamma_api.png_slides(archive([(f'card{i}.png','red') for i in range(25)])))),25)

    async def test_import_converts_and_persists_sequentially(self):
        import tempfile
        emitted=[]; saved=[]
        def images(_):
            for index in range(25):
                emitted.append(index)
                yield (b'image',320,180)
        async def store(*_):
            self.assertEqual(len(emitted),len(saved)+1, 'Never convert all slides before persisting the first')
            saved.append(len(saved))
            return True
        with tempfile.TemporaryDirectory() as directory:
            projects=SimpleNamespace(update_one=AsyncMock(return_value=SimpleNamespace(modified_count=1)))
            module=routes(PROJECTS_DIR=directory, db=SimpleNamespace(projects=projects),store_asset_async=store)
            with patch.object(gamma_api,'png_slides',side_effect=images):
                count=await module.import_archive({'id':'j','projectId':'new','archiveId':'stored','title':'Teste'},b'archive')
            self.assertEqual(count,25)

    def test_payload_ptbr_private_no_connectors_or_max_quality(self):
        body = gamma_api.generation_payload('Teste Gamma', 'Conteúdo da apresentação')
        self.assertEqual(body['numCards'], 5)
        self.assertEqual(body['quality'], 'standard')
        self.assertIn('Português do Brasil', body['additionalInstructions'])
        self.assertTrue(body['disableConnectors'])
        self.assertEqual(body['sharingOptions']['externalAccess'], 'noAccess')
        self.assertEqual(body['exportAs'], 'png')

    def test_theme_or_template_payload_not_both(self):
        self.assertEqual(gamma_api.generation_payload('Teste', 'Conteúdo', theme_id='custom_1')['themeId'], 'custom_1')
        body = gamma_api.generation_payload('Teste', 'Conteúdo', template_id='template_1')
        self.assertEqual(body['templateId'], 'template_1')
        self.assertNotIn('themeId', body)
        with self.assertRaises(gamma_api.GammaError): gamma_api.generation_payload('Teste', 'Conteúdo', 't', 'm')
        model = routes().Generate
        with self.assertRaises(ValidationError): model(requestId=uuid.uuid4(), title='Teste', prompt='conteúdo para cinco slides', themeId='t', templateId='m')

    async def test_theme_catalog_read_only_bounded_and_encoded(self):
        response = {'data': [{'id': 'theme1', 'name': 'Ocean', 'type': 'custom', 'colorKeywords': ['blue'], 'secret': 'hidden'}], 'hasMore': True, 'nextCursor': 'next'}
        with patch.object(gamma_api, 'request', new_callable=AsyncMock, return_value=response) as request:
            result = await gamma_api.design_catalog('themes', 'a&b', 'cursor/x', 'custom')
        self.assertEqual(request.call_args.args[0], 'GET')
        self.assertIn('query=a%26b', request.call_args.args[1])
        self.assertIn('after=cursor%2Fx', request.call_args.args[1])
        self.assertEqual(result['nextCursor'], 'next')
        self.assertEqual(result['items'][0]['colors'], ['blue'])
        self.assertNotIn('secret', result['items'][0])

    async def test_template_catalog_includes_both_sources_without_signed_previews(self):
        response = {'workspaceTemplates': [{'id': 'w', 'title': 'Marca', 'url': 'https://gamma.app/docs/w', 'previewUrl': 'https://signed-private'}], 'exploreTemplates': [{'id': 'o', 'title': 'Oficial', 'url': 'javascript:bad'}]}
        with patch.object(gamma_api, 'request', new_callable=AsyncMock, return_value=response) as request:
            result = await gamma_api.design_catalog('templates', 'vendas')
        self.assertEqual(request.call_args.args[0], 'GET')
        self.assertEqual([item['source'] for item in result['items']], ['workspace', 'official'])
        self.assertNotIn('signed-private', str(result))
        self.assertIsNone(result['items'][1]['url'])

    def test_archive_natural_order_and_no_path_extraction(self):
        slides = list(gamma_api.png_slides(archive([('card10.png', 'blue'), ('../../card2.png', 'red')])))
        self.assertEqual(len(slides), 2)
        self.assertEqual(slides[0][1:], (320, 180))
        image = Image.open(io.BytesIO(slides[0][0]))
        self.assertGreater(image.getpixel((10, 10))[0], 200)
        with self.assertRaises(gamma_api.GammaError): list(gamma_api.png_slides(b'not ZIP'))
        with self.assertRaises(gamma_api.GammaError): list(gamma_api.png_slides(archive([])))

    def test_keys_and_urls_not_exposed(self):
        module = routes()
        row = module.public({'id': 'job', 'generationId': 'secret-id', 'exportUrl': 'https://signed', 'archiveId': 'internal'})
        self.assertNotIn('exportUrl', row)
        self.assertNotIn('archiveId', row)
        self.assertIsNone(gamma_api.public_gamma_url('https://gamma.app.evil.test/x'))
        self.assertEqual(gamma_api.public_gamma_url('https://gamma.app/docs/x'), 'https://gamma.app/docs/x')
        with self.assertRaises(gamma_api.GammaError): gamma_api.generation_id('../x')

    def test_request_forbids_existing_project_target_and_reader(self):
        module = routes()
        with self.assertRaises(ValidationError): module.Generate(requestId=uuid.uuid4(), title='Teste', prompt='conteúdo para cinco slides', projectId='existing')
        with self.assertRaises(HTTPException): module.creator({'roles': ['aprovador']})
        module.creator({'roles': ['super_admin']})

    async def test_duplicate_submission_never_calls_gamma(self):
        db = SimpleNamespace(gamma_generations=SimpleNamespace(find_one=AsyncMock(return_value={'id': 'same', 'status': 'pending'})))
        module = routes(db=db)
        with patch.object(gamma_api, 'configured', return_value=True), patch.object(gamma_api, 'request', new_callable=AsyncMock) as request:
            row = await module.generate(module.Generate(requestId=uuid.uuid4(), title='Teste', prompt='conteúdo para cinco slides'), {'roles': ['editor'], 'id': 'user'})
        self.assertEqual(row['id'], 'same'); request.assert_not_called()

    async def test_create_only_new_project_and_owner(self):
        db = SimpleNamespace(gamma_generations=SimpleNamespace(find_one=AsyncMock(return_value=None), insert_one=AsyncMock(), update_one=AsyncMock()),
                             projects=SimpleNamespace(insert_one=AsyncMock()))
        module = routes(db=db, resolve_company_id_for_creation=AsyncMock(return_value='company'))
        with patch.object(gamma_api, 'configured', return_value=True), patch.object(gamma_api, 'request', new_callable=AsyncMock, return_value={'generationId': 'gen_abc123'}):
            row = await module.generate(module.Generate(requestId=uuid.uuid4(), title='Teste Gamma', prompt='conteúdo para apresentação', numCards=12), {'roles': ['editor'], 'id': 'user'})
        project = db.projects.insert_one.call_args.args[0]
        self.assertEqual(project['course']['slides'], [])
        self.assertEqual(project['course']['metadata']['title'], 'Teste Gamma')
        self.assertEqual(project['companyId'], 'company')
        self.assertEqual(row['status'], 'pending')
        self.assertEqual(row['numCards'],12)

    async def test_unknown_paid_submission_is_not_retried(self):
        db = SimpleNamespace(gamma_generations=SimpleNamespace(find_one=AsyncMock(return_value=None), insert_one=AsyncMock(), update_one=AsyncMock()),
                             projects=SimpleNamespace(insert_one=AsyncMock()))
        module = routes(db=db, resolve_company_id_for_creation=AsyncMock(return_value='company'))
        with patch.object(gamma_api, 'configured', return_value=True), patch.object(gamma_api, 'request', new_callable=AsyncMock, side_effect=gamma_api.GammaError('sem confirmação')) as request:
            row = await module.generate(module.Generate(requestId=uuid.uuid4(), title='Teste Gamma', prompt='conteúdo para cinco slides'), {'roles': ['editor'], 'id': 'user'})
        self.assertEqual(row['status'], 'unknown'); self.assertEqual(request.await_count, 1)

    async def test_owner_authorization_before_project(self):
        db = SimpleNamespace(gamma_generations=SimpleNamespace(find_one=AsyncMock(return_value=None)))
        load = AsyncMock()
        module = routes(db=db, load_authorized_project=load)
        with self.assertRaises(HTTPException): await module.authorized('other-job', {'roles': ['editor'], 'id': 'user'})
        load.assert_not_called()
        self.assertEqual(db.gamma_generations.find_one.call_args.args[0]['userId'], 'user')

    async def test_completed_poll_only_reads_then_imports_no_paid_post(self):
        job = {'id': 'j', 'projectId': 'new', 'status': 'pending', 'generationId': 'gen_abc'}
        collection = SimpleNamespace(update_one=AsyncMock(return_value=SimpleNamespace(modified_count=1)), find_one=AsyncMock(return_value={**job, 'status': 'completed'}))
        module = routes(db=SimpleNamespace(gamma_generations=collection))
        module.poll.__globals__['authorized'] = AsyncMock(return_value=job)
        importer = AsyncMock(return_value=5); module.poll.__globals__['import_archive'] = importer
        with patch.object(gamma_api, 'request', new_callable=AsyncMock, return_value={'status': 'completed', 'exportUrl': 'https://signed', 'gamma': {'gammaUrl': 'https://gamma.app/docs/test'}}) as request, patch.object(gamma_api, 'download', new_callable=AsyncMock, return_value=b'zip'):
            await module.poll('j', {'id': 'user'})
        self.assertEqual(request.call_args.args[0], 'GET')
        importer.assert_awaited_once()
        update = collection.update_one.call_args.kwargs if collection.update_one.call_args.kwargs else collection.update_one.call_args.args[1]
        self.assertNotIn('https://signed', str(update))

    async def test_mismatch_warning_uses_requested_quantity_without_regenerating(self):
        job={'id':'j','projectId':'new','status':'pending','generationId':'gen_abc','numCards':12}
        collection=SimpleNamespace(update_one=AsyncMock(return_value=SimpleNamespace(modified_count=1)),find_one=AsyncMock(return_value=job))
        module=routes(db=SimpleNamespace(gamma_generations=collection))
        module.poll.__globals__['authorized']=AsyncMock(return_value=job)
        module.poll.__globals__['import_archive']=AsyncMock(return_value=13)
        with patch.object(gamma_api,'request',new_callable=AsyncMock,return_value={'status':'completed','exportUrl':'https://signed'}) as request, patch.object(gamma_api,'download',new_callable=AsyncMock,return_value=b'zip'):
            await module.poll('j', {'id':'user'})
        warning=collection.update_one.call_args.args[1]['$set']['warning']
        self.assertIn('entregou 13',warning)
        self.assertIn('solicitados 12',warning)
        self.assertEqual(request.await_count,1)
        self.assertEqual(request.call_args.args[0],'GET')

    async def test_import_compare_and_set_never_overwrites_existing_course(self):
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            projects = SimpleNamespace(update_one=AsyncMock(return_value=SimpleNamespace(modified_count=0)))
            store = AsyncMock(return_value=True)
            module = routes(PROJECTS_DIR=directory, db=SimpleNamespace(projects=projects), store_asset_async=store)
            with self.assertRaisesRegex(gamma_api.GammaError, 'já contém slides'):
                await module.import_archive({'id': 'j', 'projectId': 'new', 'archiveId': 'stored', 'title': 'Teste'}, archive([('card1.png', 'red')]))
            query = projects.update_one.call_args.args[0]
            self.assertEqual(query, {'id': 'new', 'gammaJobId': 'j', 'course.slides': {'$size': 0}})
            store.assert_awaited_once()

    def test_private_policy_warning_visible(self):
        module = routes()
        self.assertIn('privacidade', module.sharing_warning({'warnings': [{'code': 'ignored_external_access'}]}))


if __name__ == '__main__': unittest.main()
