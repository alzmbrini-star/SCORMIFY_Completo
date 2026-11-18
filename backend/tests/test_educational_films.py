import ast
import asyncio
import copy
import io
from pathlib import Path
from datetime import datetime,timezone,timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock,MagicMock
from typing import Optional
import uuid
import pytest
from PIL import Image
from pydantic import BaseModel,Field
from fastapi import APIRouter,Depends,HTTPException
from services.educational_film import Board,normalized_board,revision,quote,require_ready,project_shell,media_keys
from services.film_worker import operation_signature


def board():
 return normalized_board({'title':'História educativa','topic':'Aprender colaboração e comunicação através de uma história concreta.',
  'characters':[{'name':'Ana','description':'Mulher adulta, cabelo castanho e camisa azul.'}],
  'narratorVoice':'brVoice','scenes':[{'title':f'Cena {i+1}','visual':'Ana conversa com a equipe e organiza os cartões sobre a mesa.',
   'narration':'Ana escuta a equipe.','duration':5} for i in range(3)]})


def film(approved=False):
 b=board();f={'id':str(uuid.uuid4()),'projectId':str(uuid.uuid4()),'sourceProjectId':'original',
  'slideId':'new-slide','ownerId':'u','companyId':'c','board':b,'revision':revision(b),'operations':{},'status':'draft'}
 if approved:
  f['storyboardApproval']=f['revision'];q=quote(f)
  f.update(status='budget_approved',budgetApproval={'revision':f['revision'],'quoteId':q['id'],'ceilingUsd':q['suggestedCeilingUsd'],
       'token':'approval','at':datetime.now(timezone.utc).isoformat()})
 return f


def test_media_is_blocked_until_both_approvals_and_same_revision():
 f=film()
 with pytest.raises(ValueError):require_ready(f,f['revision'])
 f['storyboardApproval']=f['revision']
 with pytest.raises(ValueError):require_ready(f,f['revision'])
 f=film(True);assert require_ready(f,f['revision'])==f['board']
 f['board']['scenes'][0]['narration']='Texto alterado'
 with pytest.raises(ValueError):require_ready(f,f['revision'])


def test_quote_is_itemized_reuses_completed_media_and_does_not_hide_unknown_charges():
 f=film(True);before=copy.deepcopy(f);q=quote(f)
 assert [i['usd'] for i in q['items']]==[.20,.75,.03,.05]
 assert q['estimatedUsd']==1.03 and q['duration']==15 and f==before
 f['operations']={'character_0':{'status':'ready'},'video_0':{'status':'submitted'}}
 q=quote(f);assert q['items'][0]['quantity']==3 and q['items'][1]['quantity']==10
 f['operations']['frame_0']={'status':'sending'}
 with pytest.raises(ValueError,match='não confirmado'):quote(f)


def test_edit_signatures_reuse_only_compatible_assets():
 b=board();new=copy.deepcopy(b);new['scenes'][0]['narration']='Vamos ouvir todos.'
 assert operation_signature(b,'voice_0')!=operation_signature(new,'voice_0')
 assert operation_signature(b,'frame_0')==operation_signature(new,'frame_0')
 assert operation_signature(b,'video_0')==operation_signature(new,'video_0')
 new['characters'][0]['description']='Mulher adulta, cabelos pretos e roupa vermelha.'
 assert operation_signature(b,'frame_0')!=operation_signature(new,'frame_0')


def test_new_workspace_never_uses_original_project_or_authored_course_data():
 f=film();before=copy.deepcopy(f);p=project_shell(f,'u','c','now')
 assert p['id']==f['projectId'] and p['id']!=f['sourceProjectId']
 assert len(p['course']['slides'])==1 and not p['course']['questions'] and f==before


@pytest.mark.parametrize('change',[{'visual':''},{'narration':'x'*56},{'speaker':'character2'}])
def test_incomplete_or_overlong_storyboards_cannot_be_approved(change):
 b=board();b['scenes'][0].update(change)
 with pytest.raises(ValueError):normalized_board(b,True)


def scope(f):
 path=Path(__file__).resolve().parents[1]/'routes/educational_films.py'
 tree=ast.parse(path.read_text(encoding='utf-8'))
 nodes=[n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef))]
 db=SimpleNamespace(educational_films=SimpleNamespace(find_one=AsyncMock(side_effect=lambda *a,**k:copy.deepcopy(f)),
     update_one=AsyncMock(return_value=SimpleNamespace(modified_count=1,matched_count=1))),projects=SimpleNamespace(update_one=AsyncMock()))
 env=dict(router=APIRouter(),BaseModel=BaseModel,Field=Field,Optional=Optional,uuid=uuid,Board=Board,
  Depends=Depends,require_auth=lambda:None,HTTPException=HTTPException,db=db,TASKS=set(),PROJECTS_DIR='unused',
  can_edit=MagicMock(),has_role=lambda u,r:r in u.get('roles',[]),load_authorized_project=AsyncMock(return_value={'id':'workspace'}),
  normalized_board=normalized_board,revision=revision,quote=quote,require_ready=require_ready,project_shell=project_shell,media_keys=media_keys,
  operation_signature=operation_signature,runway_ai=SimpleNamespace(configured=lambda:True),
  runway_narration=SimpleNamespace(available=lambda:True,media_tools=lambda:('ffmpeg','ffprobe')),
  narration_allowed=lambda u:True,run=AsyncMock(),asyncio=asyncio,datetime=datetime,timezone=timezone,timedelta=timedelta)
 exec(compile(ast.Module(body=nodes,type_ignores=[]),str(path),'exec'),env)
 return SimpleNamespace(**env)


@pytest.mark.asyncio
async def test_api_blocks_unapproved_media_and_foreign_owner_before_provider_calls():
 s=scope(film());body=s.Approval(revision='bad')
 with pytest.raises(HTTPException):await s.generate('id',body,{'id':'u','companyId':'c'})
 s.run.assert_not_awaited()
 s=scope(film(True))
 with pytest.raises(HTTPException) as error:await s.get('id',{'id':'another','companyId':'c'})
 assert error.value.status_code==404;s.load_authorized_project.assert_not_awaited()


@pytest.mark.asyncio
async def test_api_approval_does_not_generate_and_budget_requires_consent():
 f=film();s=scope(f);user={'id':'u','companyId':'c'}
 approved=await s.approve_storyboard(f['id'],s.Approval(revision=f['revision']),user)
 assert approved['storyboardApproval']==f['revision'];s.run.assert_not_awaited();s.db.projects.update_one.assert_not_awaited()
 s=scope(approved)
 with pytest.raises(HTTPException):await s.approve_budget(f['id'],s.BudgetApproval(revision=f['revision'],quoteId=approved['quote']['id'],ceilingUsd=10,consent=False),user)
 s.run.assert_not_awaited()


@pytest.mark.asyncio
async def test_api_generation_claim_is_atomic_expiring_and_cannot_submit_twice():
 f=film(True);s=scope(f);user={'id':'u','companyId':'c'}
 s.db.educational_films.update_one.return_value=SimpleNamespace(modified_count=0,matched_count=0)
 with pytest.raises(HTTPException):await s.generate(f['id'],s.Approval(revision=f['revision']),user)
 s.run.assert_not_awaited()
 f['budgetApproval']['at']=(datetime.now(timezone.utc)-timedelta(days=2)).isoformat();s=scope(f)
 with pytest.raises(HTTPException,match='expirou'):await s.generate(f['id'],s.Approval(revision=f['revision']),user)
 s.run.assert_not_awaited()


@pytest.mark.asyncio
async def test_api_edit_revokes_both_approvals_without_project_writes():
 f=film(True);s=scope(f);changed=copy.deepcopy(f['board']);changed['style']='3d'
 result=await s.edit(f['id'],s.Edit(revision=f['revision'],board=Board(**changed)),{'id':'u','companyId':'c'})
 assert result['status']=='draft' and result['storyboardApproval'] is None and result['budgetApproval'] is None
 assert result['revision']!=f['revision'];s.db.projects.update_one.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize('real_media',[False,True])
async def test_full_worker_with_stubbed_providers_is_serial_persistent_and_source_safe(tmp_path,monkeypatch,real_media):
 from services import film_worker as w
 f=film(True);f.update(status='generating',runId='run');updates=[];paid=[]
 async def update(query,change,**kw):
  updates.append((query,change))
  for path,value in change['$set'].items():
   if path.startswith('operations.'):f['operations'][path.split('.')[1]]=copy.deepcopy(value)
   else:f[path]=copy.deepcopy(value)
  return SimpleNamespace(matched_count=1)
 db=SimpleNamespace(educational_films=SimpleNamespace(find_one=AsyncMock(return_value=f),update_one=update),
  projects=SimpleNamespace(update_one=AsyncMock()),image_gallery=SimpleNamespace(update_one=AsyncMock()))
 async def submit(method,path,payload):
  paid.append(path);return {'id':str(uuid.uuid4())}
 audio_bytes=b'audio';ffmpeg='ffmpeg';original_media=w.runway_narration.run_media
 if real_media:
  import imageio_ffmpeg,subprocess,wave
  ffmpeg=imageio_ffmpeg.get_ffmpeg_exe();video_source=tmp_path/'fixture.mp4'
  subprocess.run([ffmpeg,'-y','-v','error','-f','lavfi','-i','color=c=blue:s=320x180:r=24','-t','5','-c:v','libx264','-threads','1',str(video_source)],check=True,timeout=30)
  data=io.BytesIO()
  with wave.open(data,'wb') as wav:wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(22050);wav.writeframes(b'\0\0'*22050*2)
  audio_bytes=data.getvalue()
 async def download(url,path,media_type):
  if media_type=='image':Image.new('RGB',(128,72),'blue').save(path,'PNG')
  elif real_media and media_type=='video':__import__('shutil').copyfile(video_source,path)
  elif real_media:path.write_bytes(audio_bytes)
  else:path.write_bytes(b'media')
 async def media(args,**kw):Path(args[-1]).write_bytes(b'muxed');return b''
 monkeypatch.setattr(w.runway_ai,'request',submit);monkeypatch.setattr(w.runway_ai,'get_task',AsyncMock(return_value={'status':'SUCCEEDED','output':['https://example.test/output']}))
 monkeypatch.setattr(w.runway_ai,'download',download);monkeypatch.setattr(w.runway_narration,'speech',AsyncMock(return_value=audio_bytes))
 monkeypatch.setattr(w.runway_narration,'duration',AsyncMock(return_value=2));monkeypatch.setattr(w.runway_narration,'media_tools',lambda:(ffmpeg,'ffprobe'))
 monkeypatch.setattr(w.runway_narration,'run_media',original_media if real_media else media);monkeypatch.setattr(w,'store_asset_async',AsyncMock(return_value=True))
 await w.run(f['id'],'run',db,tmp_path)
 assert f['status']=='completed' and f['duration']==15
 assert paid.count('text_to_image')==4 and paid.count('image_to_video')==3 and paid.count('text_to_music')==1
 assert len(f['operations'])==11 and all(o['status']=='ready' for o in f['operations'].values())
 assert f['videoUrl'].startswith('/api/projects/'+f['projectId']) and f['subtitlesUrl'].endswith('.srt')
 query=db.projects.update_one.call_args.args[0]
 assert query['id']==f['projectId'] and query['id']!='original' and query['course.slides.0.elements']==[]
 if real_media:
  output=tmp_path/f['projectId']/'assets'/f'educational_film_{f["id"]}.mp4'
  assert output.stat().st_size>10000
  subprocess.run([ffmpeg,'-v','error','-i',str(output),'-f','null','-'],check=True,timeout=30)


@pytest.mark.asyncio
async def test_ambiguous_paid_submission_is_not_repeated(tmp_path,monkeypatch):
 from services import film_worker as w
 f=film(True);f.update(status='generating',runId='run')
 async def update(query,change):
  for path,value in change['$set'].items():
   if path.startswith('operations.'):f['operations'][path.split('.')[1]]=copy.deepcopy(value)
   else:f[path]=value
  return SimpleNamespace(matched_count=1)
 db=SimpleNamespace(educational_films=SimpleNamespace(find_one=AsyncMock(return_value=f),update_one=update))
 submit=AsyncMock(side_effect=TimeoutError('lost POST response'));monkeypatch.setattr(w.runway_ai,'request',submit)
 await w.run(f['id'],'run',db,tmp_path)
 assert f['status']=='unknown' and submit.await_count==1
 with pytest.raises(ValueError):quote(f)


def test_tutor_documents_actual_approval_credit_and_export_limits():
 from services.creator_guide import GUIDE
 text=' '.join(next(t for t in GUIDE if t['id']=='educational-film')['steps'])
 for term in ('Aprovar storyboard','Aprovar orçamento','24 horas','não garante','projeto independente','SRT','HTML/SCORM','não há sincronização labial automática'):
  assert term.casefold() in text.casefold()
