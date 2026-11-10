import ast
import asyncio
import copy
import tempfile
import unittest
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field
from services import gamma_api
from services.gamma_refresh import linked_bases, document_id, image_patches
from services.creator_guide import topics_for


def project():
    filename='gamma_job1_1.webp'
    return {'id':'p','source':'gamma','gammaJobId':'job1','updatedAt':'revision1','companyId':'c',
            'course':{'slides':[{'id':'s1','title':'Original','duration':30,'notes':'User notes','audio':[{'src':'audio'}],
            'elements':[{'id':str(uuid.uuid5(uuid.NAMESPACE_DNS,filename)), 'type':'image','src':'/api/projects/p/assets/'+filename,'x':12,'width':1920,'height':1080,'duration':20},
                        {'id':'q','type':'quiz','quizConfig':{'questionIds':['bank1']},'startTime':3},
                        {'id':'user-image','type':'image','src':'/my-image.png'}], 'annotations':[{'id':'a'}]}]}}


def module(**overrides):
    import re, hashlib
    path=Path(__file__).resolve().parents[1]/'routes/gamma_refresh.py'
    nodes=[n for n in ast.parse(path.read_text(encoding='utf-8')).body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef))]
    for node in nodes: node.decorator_list=[]
    scope=dict(Depends=lambda _:None, require_auth=None, HTTPException=HTTPException, BaseModel=BaseModel,ConfigDict=ConfigDict,Field=Field,
               uuid=uuid,datetime=datetime,timezone=timezone,timedelta=timedelta,Path=Path,asyncio=asyncio,re=re,hashlib=hashlib,
               gamma_api=gamma_api,linked_bases=linked_bases,document_id=document_id,image_patches=image_patches,
               has_any_role=lambda u,*roles: bool(set(u.get('roles',[])) & set([*roles,'super_admin'])))
    scope.update(overrides)
    exec(compile(ast.Module(body=nodes,type_ignores=[]),str(path),'exec'),scope)
    return SimpleNamespace(**scope)


class RefreshTests(unittest.IsolatedAsyncioTestCase):
    def test_only_linked_base_changes_never_user_layers_or_slide_metadata(self):
        original=project(); before=copy.deepcopy(original)
        patches,backup=image_patches(original,{'images':[{'index':2,'src':'/new.png'}]},[{'slideId':'s1','sourceIndex':2}])
        self.assertEqual(original,before)
        self.assertEqual(set(patches),{'course.slides.0.elements.0.src','course.slides.0.gammaSource'})
        self.assertEqual(backup[0]['src'], original['course']['slides'][0]['elements'][0]['src'])
        self.assertEqual(patches['course.slides.0.gammaSource']['index'],2)

    def test_reordered_editor_slides_use_ids_not_position(self):
        doc=project(); doc['course']['slides'].insert(0,{'id':'manual','elements':[]})
        patches,_=image_patches(doc,{'images':[{'index':0,'src':'new'}]},[{'slideId':'s1','sourceIndex':0}])
        self.assertIn('course.slides.1.elements.0.src',patches)

    def test_provenance_survives_next_refresh_and_legacy_import(self):
        doc=project(); base=linked_bases(doc)[0]
        doc['course']['slides'][0]['gammaSource']={'jobId':'job1','index':4,'elementId':base['elementId']}
        doc['course']['slides'][0]['elements'][0]['src']='/new-version.webp'
        self.assertEqual(linked_bases(doc)[0]['index'],4)
        doc['course']['slides'][0]['gammaSource']['elementId']='unknown'
        with self.assertRaises(ValueError): linked_bases(doc)

    def test_invalid_mappings_and_external_urls_rejected(self):
        for mappings in [[],[{'slideId':'manual','sourceIndex':0}],[{'slideId':'s1','sourceIndex':99}],[{'slideId':'s1','sourceIndex':0}]*2]:
            with self.assertRaises(ValueError): image_patches(project(),{'images':[{'index':0,'src':'new'}]},mappings)
        self.assertEqual(document_id({'gammaUrl':'https://gamma.app/docs/My-deck-abc123'}),'My-deck-abc123')
        for url in ['https://gamma.app.evil/docs/id','https://127.0.0.1/docs/id','javascript:bad']:
            with self.assertRaises(ValueError): document_id({'gammaUrl':url})

    async def test_permissions_and_tenant_fence_before_provider(self):
        load=AsyncMock(side_effect=HTTPException(404,'not found'))
        m=module(load_authorized_project=load)
        for user,expected in [({'roles':['viewer']},403),({'roles':['editor']},404)]:
            with self.assertRaises(HTTPException) as caught: await m.editable('other',user)
            self.assertEqual(caught.exception.status_code,expected)

    async def test_prepare_is_idempotent_and_calls_export_not_generation(self):
        p=project(); collection=SimpleNamespace(find_one=AsyncMock(return_value=None),insert_one=AsyncMock(),update_one=AsyncMock())
        m=module(load_authorized_project=AsyncMock(return_value=p),db=SimpleNamespace(gamma_refreshes=collection,
            gamma_generations=SimpleNamespace(find_one=AsyncMock(return_value={'gammaUrl':'https://gamma.app/docs/original'}))))
        data=m.Prepare(requestId=uuid.uuid4()); user={'roles':['editor'],'id':'u'}
        with patch.object(gamma_api,'configured',return_value=True),patch.object(gamma_api,'request',new_callable=AsyncMock,return_value={'exportId':'exp_abc'}) as request:
            result=await m.prepare('p',data,user)
            self.assertEqual(request.call_args.args,('POST','/gammas/original/export',{'exportAs':'png'}))
            collection.find_one.return_value={'id':result['id'],'status':'pending'}
            await m.prepare('p',data,user)
            self.assertEqual(request.await_count,1)

    async def test_apply_creates_backup_then_atomic_image_only_patch(self):
        p=project(); job={'_id':'j','id':'j','status':'ready','baseRevision':'revision1','images':[{'index':0,'src':'new'}]}
        projects=SimpleNamespace(update_one=AsyncMock(return_value=SimpleNamespace(modified_count=1)))
        backups=SimpleNamespace(update_one=AsyncMock())
        m=module(db=SimpleNamespace(projects=projects,gamma_refresh_backups=backups,gamma_refreshes=SimpleNamespace(update_one=AsyncMock())))
        m.apply.__globals__['owned_job']=AsyncMock(return_value=(p,job))
        result=await m.apply('p','j',m.Apply(mappings=[{'slideId':'s1','sourceIndex':0}]),{})
        self.assertEqual(result['appliedSlides'],1);backups.update_one.assert_awaited_once()
        guard,update=projects.update_one.call_args.args
        self.assertEqual(guard['updatedAt'],'revision1'); self.assertEqual(guard['course.slides'],p['course']['slides'])
        self.assertNotIn('course.slides',update['$set'])
        self.assertNotIn('course',update['$set'])
        self.assertEqual(len(update['$set']),4)

    async def test_stale_preview_or_failed_cas_never_overwrites(self):
        p=project(); job={'_id':'j','status':'ready','baseRevision':'old'}
        projects=SimpleNamespace(update_one=AsyncMock(return_value=SimpleNamespace(modified_count=0)))
        m=module(db=SimpleNamespace(projects=projects,gamma_refresh_backups=SimpleNamespace(update_one=AsyncMock())))
        m.apply.__globals__['owned_job']=AsyncMock(return_value=(p,job))
        data=m.Apply(mappings=[{'slideId':'s1','sourceIndex':0}])
        with self.assertRaises(HTTPException) as caught: await m.apply('p','j',data,{})
        self.assertEqual(caught.exception.status_code,409);projects.update_one.assert_not_awaited()
        job.update(baseRevision='revision1',images=[{'index':0,'src':'new'}])
        with self.assertRaises(HTTPException) as caught: await m.apply('p','j',data,{})
        self.assertEqual(caught.exception.status_code,409)

    async def test_poll_persists_images_without_changing_project_or_leaking_signed_url(self):
        job={'_id':'j','id':'j','status':'pending','exportId':'exp_abc'}
        collection=SimpleNamespace(update_one=AsyncMock(return_value=SimpleNamespace(modified_count=1)),find_one=AsyncMock(return_value=job))
        store=AsyncMock(return_value=True)
        with tempfile.TemporaryDirectory() as directory:
            m=module(db=SimpleNamespace(gamma_refreshes=collection),PROJECTS_DIR=directory,store_asset_async=store)
            m.poll.__globals__['owned_job']=AsyncMock(return_value=(project(),job))
            with patch.object(gamma_api,'request',new_callable=AsyncMock,return_value={'status':'completed','exportUrl':'https://signed-secret'}) as request,patch.object(gamma_api,'download',new_callable=AsyncMock,return_value=b'zip'),patch.object(gamma_api,'png_slides',return_value=iter([(b'image',320,180)])):
                await m.poll('p','j',{})
            self.assertEqual(request.call_args.args,('GET','/exports/exp_abc'));store.assert_awaited_once()
            update=collection.update_one.call_args.args[1]['$set']
            self.assertEqual(update['status'],'ready');self.assertEqual(len(update['images']),1)
            self.assertNotIn('signed-secret',str(update));self.assertNotIn('exportId',m.safe(job))

    def test_tutor_explains_refresh_and_preservation_limits(self):
        topic=next(t for t in topics_for({'roles':['editor']}) if t['id']=='gamma-refresh')
        text=' '.join(topic['steps'])
        for term in ['Atualizar do Gamma','correspondências','Perguntas','reexporte','reordenação automática']:
            self.assertIn(term,text)
