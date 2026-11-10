import ast
import copy
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from services import runway_ai, runway_narration


def route(name, **values):
    path = Path(__file__).resolve().parents[1] / 'routes/runway.py'
    nodes = ast.parse(path.read_text(encoding='utf-8')).body
    node = next(n for n in nodes if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name)
    node.decorator_list = []
    from datetime import datetime, timezone, timedelta
    import uuid, math
    from fastapi import HTTPException
    scope = dict(Request=object, Depends=lambda _:None, require_auth=None, HTTPException=HTTPException,
                 runway_ai=runway_ai, runway_narration=runway_narration, uuid=uuid, math=math, datetime=datetime, timezone=timezone, timedelta=timedelta,
                 now=lambda:'2026-11-10T12:00:00+00:00', ACTIVE=['submitting','submitted','processing','saving','unknown'])
    scope.update(values)
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), 'exec'), scope)
    return scope[name]


class RunwayPayloadTests(unittest.IsolatedAsyncioTestCase):
    def test_text_only_and_image_models(self):
        endpoint, payload = runway_ai.build_payload({'prompt':'Uma demonstração de engrenagens'})
        self.assertEqual(endpoint, 'text_to_video')
        self.assertEqual(payload['model'], 'gen4.5')
        self.assertNotIn('promptImage', payload)
        endpoint, payload = runway_ai.build_payload({'prompt':'Movimento lento','model':'gen4_turbo','image':'https://example.com/start.png','duration':10,'aspectRatio':'9:16'})
        self.assertEqual(endpoint, 'image_to_video')
        self.assertEqual(payload['ratio'], '720:1280')
        self.assertNotIn('audio',payload)

    def test_reject_bad_options_before_paid_call(self):
        for opts in ({'model':'unknown'}, {'model':'gen4_turbo'}, {'duration':15}, {'duration':True},
                     {'aspectRatio':'1:1'}, {'image':'http://example.com/a.png'}, {'image':'data:image/svg+xml;base64,AAA'},
                     {'image':'data:image/png;base64,notbase64'}, {'prompt':'x'*1001}, {'prompt':1}, {'image':{}}):
            with self.subTest(opts=opts), self.assertRaises(ValueError):
                runway_ai.build_payload({'prompt':'Cena', **opts})

    async def test_submission_maps_task_id_without_retry(self):
        task_id='17f20503-6c24-4c16-946b-35dbbce2af2f'
        with patch.object(runway_ai, 'request', AsyncMock(return_value={'id':task_id})) as request:
            self.assertEqual(await runway_ai.submit({'prompt':'Cena'}),task_id)
            request.assert_awaited_once()
        with patch.object(runway_ai, 'request', AsyncMock(side_effect=TimeoutError)) as request:
            with self.assertRaises(TimeoutError):await runway_ai.submit({'prompt':'Cena'})
            request.assert_awaited_once()

    async def test_secret_only_in_server_header(self):
        client=AsyncMock()
        response=SimpleNamespace(status_code=200,json=lambda:{'id':'mock'})
        client.request.return_value=response
        context=AsyncMock()
        context.__aenter__.return_value=client
        with patch.dict('os.environ', {'RUNWAYML_API_SECRET':'test-secret'}), patch.object(runway_ai.httpx,'AsyncClient',return_value=context):
            result=await runway_ai.request('POST','text_to_video',{'promptText':'Cena'})
        self.assertEqual(result, {'id':'mock'})
        call=client.request.call_args
        self.assertEqual(call.kwargs['headers']['X-Runway-Version'],'2024-11-06')
        self.assertEqual(call.kwargs['headers']['Authorization'],'Bearer test-secret')
        self.assertNotIn('test-secret',str(call.kwargs['json']))

    def test_placeholder_bounded_and_does_not_embed_prompt(self):
        fn=route('placeholder')
        slot=fn({'width':1920,'height':820},{'duration':10,'aspectRatio':'9:16','prompt':'<script>x</script>'},'job')
        self.assertGreater(slot['width'],0)
        self.assertLessEqual(slot['x']+slot['width'],1920)
        self.assertLessEqual(slot['y']+slot['height'],820)
        self.assertNotIn('<script>',slot['htmlContent'])

    def test_roles_include_multi_role_accounts(self):
        check=route('can_edit',has_any_role=lambda user,*roles:bool(set(user.get('roles',[])) & set(roles)))
        check({'roles':['editor']})
        with self.assertRaises(Exception):check({'roles':['viewer']})


class RunwayRouteTests(unittest.IsolatedAsyncioTestCase):
    async def test_atomic_claim_before_submit_and_duplicate_refused(self):
        collection=SimpleNamespace(update_one=AsyncMock(return_value=SimpleNamespace(modified_count=1)))
        async def load(*_):return {'course':{'slides':[{'id':'s1'}]}}
        submit=AsyncMock(return_value='task')
        provider=SimpleNamespace(configured=lambda:True,build_payload=runway_ai.build_payload,validate_music=runway_ai.validate_music,submit=submit)
        class Request:
            async def json(self):return {'projectId':'p1','slideId':'s1','prompt':'Cena'}
        fn=route('generate',db=SimpleNamespace(projects=collection),can_edit=lambda _:None,
                 load_authorized_project=load,placeholder=route('placeholder'),runway_ai=provider)
        result=await fn(Request(),{})
        self.assertEqual(result['taskId'],'task')
        query, update=collection.update_one.call_args_list[0].args
        self.assertIn('$not',query['runwayPending'])
        self.assertIn('course.slides.$[slide].elements',update['$push'])
        self.assertNotIn('image',update['$push']['runwayPending'])
        collection.update_one.return_value=SimpleNamespace(modified_count=0)
        with self.assertRaises(Exception):await fn(Request(),{})
        submit.assert_awaited_once()

    async def test_uncertain_response_is_not_resubmitted_or_silently_failed(self):
        collection=SimpleNamespace(update_one=AsyncMock(return_value=SimpleNamespace(modified_count=1)))
        class Request:
            async def json(self):return {'projectId':'p1','slideId':'s1','prompt':'Cena'}
        provider=SimpleNamespace(configured=lambda:True,build_payload=runway_ai.build_payload,validate_music=runway_ai.validate_music,submit=AsyncMock(side_effect=TimeoutError))
        fn=route('generate',db=SimpleNamespace(projects=collection),can_edit=lambda _:None,
                 load_authorized_project=AsyncMock(return_value={'course':{'slides':[{'id':'s1'}]}}),
                 placeholder=route('placeholder'),runway_ai=provider)
        result=await fn(Request(),{})
        self.assertEqual(result['status'],'unknown')
        self.assertIn('data-runway-job',result['placeholder']['htmlContent'])
        provider.submit.assert_awaited_once()

    async def test_save_keeps_geometry_id_and_durable_url_even_if_slot_deleted(self):
        from tempfile import TemporaryDirectory
        slot=route('placeholder')({}, {}, 'job')
        slot['x']=123
        calls=[]
        collection=SimpleNamespace(find_one=AsyncMock(return_value={'course':{'slides':[{'id':'s1','elements':[slot]}]}}),
                                   update_one=AsyncMock(side_effect=lambda *a,**kw:calls.append((copy.deepcopy(a),kw))))
        provider=SimpleNamespace(download=AsyncMock())
        store=AsyncMock(return_value=True)
        with TemporaryDirectory() as directory:
            fn=route('save_result',db=SimpleNamespace(projects=collection),PROJECTS_DIR=directory,Path=Path,
                     runway_ai=provider,store_asset_async=store)
            url=await fn('p1',{'id':'job'},'https://example.com/out.mp4')
        self.assertTrue(url.startswith('/api/projects/p1/assets/runway_'))
        video=calls[0][0][1]['$set']['course.slides.$[slide].elements.$[slot]']
        self.assertEqual(video['x'],123)
        self.assertEqual(video['id'],'job')
        self.assertEqual(video['provider'],'runway')
        self.assertEqual(calls[0][1]['array_filters'],[{'slide.id':'s1'},{'slot.id':'job'}])
        self.assertEqual(calls[-1][0][1]['$set']['runwayPending.$.status'],'completed')
        store.assert_awaited_once()

    async def test_cross_project_access_stops_before_provider(self):
        provider=SimpleNamespace(get_task=AsyncMock())
        fn=route('project_status',can_edit=lambda _:None,load_authorized_project=AsyncMock(side_effect=PermissionError),runway_ai=provider)
        with self.assertRaises(PermissionError):await fn('other-project',{})
        provider.get_task.assert_not_awaited()

    async def test_polling_success_persists_once_and_storage_error_can_recover(self):
        job={'id':'job','taskId':'task','status':'submitted'}
        project={'runwayPending':[job]}
        collection=SimpleNamespace(update_one=AsyncMock(return_value=SimpleNamespace(modified_count=1)),
                                   find_one=AsyncMock(return_value=project))
        get=AsyncMock(return_value={'status':'SUCCEEDED','output':['https://example.com/video.mp4']})
        save=AsyncMock()
        fn=route('project_status',can_edit=lambda _:None,load_authorized_project=AsyncMock(return_value=project),
                 db=SimpleNamespace(projects=collection),runway_ai=SimpleNamespace(get_task=get),
                 save_result=save,logger=SimpleNamespace(warning=lambda *args:None))
        await fn('p1',{})
        save.assert_awaited_once_with('p1',job,'https://example.com/video.mp4')
        self.assertIn('$unset',collection.update_one.call_args.args[1])
        save.side_effect=ValueError('Falha de armazenamento')
        await fn('p1',{})
        errors=[call.args[1].get('$set',{}).get('runwayPending.$.error') for call in collection.update_one.call_args_list]
        self.assertIn('Falha de armazenamento',errors)
        self.assertEqual(job['status'],'submitted')

    async def test_poll_lease_prevents_duplicate_provider_calls(self):
        provider=SimpleNamespace(get_task=AsyncMock())
        project={'runwayPending':[{'id':'job','taskId':'task','status':'processing'}]}
        collection=SimpleNamespace(update_one=AsyncMock(return_value=SimpleNamespace(modified_count=0)),find_one=AsyncMock(return_value=project))
        fn=route('project_status',can_edit=lambda _:None,load_authorized_project=AsyncMock(return_value=project),
                 db=SimpleNamespace(projects=collection),runway_ai=provider)
        await fn('p1',{})
        provider.get_task.assert_not_awaited()


def test_tutor_knows_runway_entry_point_and_limits():
    from services.creator_guide import topics_for
    topic=next(t for t in topics_for({'role':'editor'}) if t['id']=='video')
    text=str(topic)
    for expected in ('Criar com Runway','RUNWAYML_API_SECRET','Gen-4 Turbo','sem narração','Biblioteca Runway','créditos'):
        assert expected in text
