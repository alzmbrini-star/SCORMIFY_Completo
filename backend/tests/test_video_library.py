import ast
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from fastapi import HTTPException, Query


def library(**values):
    path = Path(__file__).resolve().parents[1]/'routes/video_library.py'
    nodes = [n for n in ast.parse(path.read_text(encoding='utf-8')).body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))]
    for node in nodes: node.decorator_list=[]
    scope = dict(Depends=lambda _:None, require_auth=None, HTTPException=HTTPException, Query=Query,
        has_role=lambda user,role:role in user.get('roles',[]),
        has_any_role=lambda user,*roles:bool(set(user.get('roles',[])) & (set(roles)|{'super_admin'})))
    scope.update(values)
    exec(compile(ast.Module(body=nodes,type_ignores=[]),str(path),'exec'),scope)
    return SimpleNamespace(**scope)


class Cursor:
    def __init__(self, rows): self.rows=rows
    async def to_list(self, limit): return self.rows
    def __aiter__(self):
        async def rows():
            for row in self.rows: yield row
        return rows()


class VideoLibraryTests(unittest.IsolatedAsyncioTestCase):
    def test_company_scope_never_leaks_orphan_projects(self):
        lib=library()
        self.assertEqual(lib.project_scope({'companyId':'a'}),{'companyId':'a'})
        self.assertEqual(lib.project_scope({}),{'id':{'$in':[]}})
        self.assertEqual(lib.project_scope({'roles':['super_admin']}),{})
        item=lib.normalize('runway',{'id':'local-job','taskId':'external-task','status':'failed'})
        self.assertEqual(item['video_id'],'local-job')
        self.assertTrue(item['can_delete'])

    async def test_all_providers_history_pagination_and_safe_listing(self):
        project={'id':'p','title':'Curso','runwayPending':[{'id':'r','title':'Runway narrado','narration':{'text':'Olá'},'music':{'enabled':True},'videoUrl':'/r.mp4','status':'completed'}],
            'klingPending':[{'taskId':'k','title':'Kling','status':'completed','videoUrl':'/k.mp4'}]}
        queries={}
        def coll(name,rows):
            def find(query, *args): queries[name]=query;return Cursor(rows)
            return SimpleNamespace(find=find)
        db=SimpleNamespace(projects=coll('projects',[project]),
            kling_generations=coll('kling',[{'taskId':'old','projectId':'p','status':'completed','videoUrl':'/old.mp4'}]),
            heygen_videos=coll('heygen',[{'video_id':'h','project_id':'p','status':'completed'}]),
            heygem_videos=coll('heygem',[{'video_id':'m','status':'completed'}]),
            video_library_hidden=coll('hidden',[]))
        lib=library(db=db)
        result=await lib.catalog('', '', 0, 100, {'companyId':'a','id':'u'})
        self.assertEqual(len(result['videos']),5)
        self.assertEqual({r['provider'] for r in result['videos']},{'heygen','heygem','runway','kling'})
        self.assertEqual(queries['heygen'],{'project_id':{'$in':['p']}})
        self.assertEqual(queries['heygem'],{'userId':'u'})
        self.assertEqual((await lib.catalog('runway','narrado',0,100,{'companyId':'a'}))['total'],1)
        page=await lib.catalog('','',0,2,{'companyId':'a','id':'u'})
        self.assertTrue(page['hasMore']);self.assertEqual(len(page['videos']),2)
        # Tombstones affect failed rows only, even if a provider later succeeds.
        db.video_library_hidden=coll('hidden',[{'_id':'runway:r'}])
        self.assertEqual((await lib.catalog('runway','',0,100,{'companyId':'a'}))['total'],1)
        project['runwayPending'][0]['status']='failed'
        self.assertEqual((await lib.catalog('runway','',0,100,{'companyId':'a'}))['total'],0)

    async def test_refresh_other_owner_denied_before_provider_call(self):
        db=SimpleNamespace(heygem_videos=SimpleNamespace(find_one=AsyncMock(return_value=None)))
        lib=library(db=db)
        with self.assertRaises(HTTPException) as exc: await lib.authorize_item('heygem','secret',{'id':'other'})
        self.assertEqual(exc.exception.status_code,404)
        db.heygem_videos.find_one.assert_awaited_once_with({'video_id':'secret','userId':'other'})

    async def test_failed_records_recoverable_for_every_provider_without_job_or_asset_deletion(self):
        for provider in ('heygen','heygem','runway','kling'):
            with self.subTest(provider=provider):
                hidden=SimpleNamespace(update_one=AsyncMock(), delete_one=AsyncMock())
                row={'status':'failed'} if provider != 'runway' else {'id':'p','runwayPending':[{'id':'v','status':'failed'}]}
                auth=AsyncMock(return_value=row)
                lib=library(db=SimpleNamespace(video_library_hidden=hidden),authorize_item=auth)
                # Functions share the module namespace; replace authorization
                # after compilation so this unit test isolates mutations.
                lib.delete.__globals__['authorize_item']=auth
                self.assertEqual(await lib.delete(provider,'v',{'roles':['editor'],'id':'u'}),{'deleted':True,'recoverable':True})
                hidden.update_one.assert_awaited_once()
                self.assertEqual(hidden.update_one.call_args.args[0],{'_id':provider+':v'})
                self.assertEqual(await lib.restore(provider,'v',{'roles':['editor']}),{'restored':True})
                hidden.delete_one.assert_awaited_once_with({'_id':provider+':v'})

    async def test_processing_or_successful_runway_cannot_be_deleted_and_viewers_denied(self):
        hidden=SimpleNamespace(update_one=AsyncMock())
        for state in ('completed','processing','unknown','composing','narrating','music'):
            lib=library(db=SimpleNamespace(video_library_hidden=hidden))
            lib.delete.__globals__['authorize_item']=AsyncMock(return_value={'runwayPending':[{'id':'v','status':state}]})
            with self.assertRaises(HTTPException) as exc:
                await lib.delete('runway','v',{'roles':['editor']})
            self.assertEqual(exc.exception.status_code,409)
        with self.assertRaises(HTTPException) as exc:
            await lib.delete('runway','v',{'roles':['viewer']})
        self.assertEqual(exc.exception.status_code,403)
        hidden.update_one.assert_not_awaited()

