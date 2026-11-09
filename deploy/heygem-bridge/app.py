"""Authenticated file bridge for the official self-hosted HeyGem/Duix GPU API.

Mount the SAME persistent volume at /code/data in this container and Duix.
No browser-facing URLs, arbitrary downloads or caller-supplied filesystem paths.
"""
import asyncio
import base64
import hashlib
import hmac
import json
import os
import re
import subprocess
from pathlib import Path
import httpx
from fastapi import FastAPI,Depends,Header,HTTPException,Request
from fastapi.responses import FileResponse

app=FastAPI(title='SCORMIFY HeyGem bridge',docs_url=None,redoc_url=None,openapi_url=None)
root=Path(os.environ.get('HEYGEM_DATA_DIR','/code/data')).resolve()
native=os.environ.get('HEYGEM_NATIVE_URL','http://duix-avatar-gen-video:8383/easy').rstrip('/')
locks={}


def authorize(authorization:str=Header(default='')):
    secret=os.environ.get('HEYGEM_BRIDGE_KEY','')
    if len(secret)<24:raise HTTPException(503,'Bridge not configured')
    if not hmac.compare_digest(authorization,'Bearer '+secret):raise HTTPException(401)


def path_inside(value):
    path=(root/value).resolve()
    if not path.is_relative_to(root):raise HTTPException(422,'Path outside data volume')
    return path


def code_path(code):
    if not re.fullmatch(r'[a-f0-9]{8}-[a-f0-9-]{27}',code):raise HTTPException(404)
    return path_inside('scormify-jobs/'+code+'.json')


def catalog():
    rows=json.loads(os.environ.get('HEYGEM_AVATARS_JSON','[]'))
    result=[]
    for row in rows:
        if not re.fullmatch(r'[a-zA-Z0-9_-]{1,80}',str(row.get('id',''))):continue
        path=path_inside(row['path'])
        if path.suffix.lower()=='.mp4' and path.is_file():result.append(row)
    return result


@app.get('/avatars',dependencies=[Depends(authorize)])
def avatars():return {'avatars':[{'id':r['id'],'name':r.get('name',r['id'])} for r in catalog()]}


@app.post('/jobs',dependencies=[Depends(authorize)])
async def submit(request:Request):
    if int(request.headers.get('content-length','0'))>12_000_000:raise HTTPException(413)
    raw=await request.body()
    if len(raw)>12_000_000:raise HTTPException(413)
    body=json.loads(raw);code=body.get('code','');target=code_path(code)
    avatar=next((a for a in catalog() if a['id']==body.get('avatar_id')),None)
    if not avatar:raise HTTPException(422,'Avatar not configured')
    try:audio=base64.b64decode(body.get('audio_base64',''),validate=True)
    except ValueError:raise HTTPException(422,'Invalid audio')
    if not 1<=len(audio)<=8_000_000:raise HTTPException(422,'Audio limit')
    digest=hashlib.sha256(audio).hexdigest()
    async with locks.setdefault(code,asyncio.Lock()):
        if target.exists():
            old=json.loads(target.read_text())
            if old['avatar_id']!=avatar['id'] or old['audio_hash']!=digest:raise HTTPException(409,'Request ID reused')
            return {'code':code,'status':'processing'}
        target.parent.mkdir(parents=True,exist_ok=True)
        source=path_inside('scormify-jobs/'+code+'.mp3');wav=source.with_suffix('.wav')
        source.write_bytes(audio)
        try:
            await asyncio.to_thread(subprocess.run,['ffmpeg','-nostdin','-y','-i',str(source),'-ar','16000','-ac','1',str(wav)],
                                    check=True,timeout=90,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        except (subprocess.SubprocessError,OSError):raise HTTPException(422,'Audio conversion failed')
        # Reserve before submit. Never resubmit an uncertain job after timeouts.
        target.write_text(json.dumps({'avatar_id':avatar['id'],'audio_hash':digest,'status':'submitting'}))
        async with httpx.AsyncClient(timeout=60,follow_redirects=False,trust_env=False) as client:
            response=await client.post(native+'/submit',json={'audio_url':str(wav),
                'video_url':str(path_inside(avatar['path'])),'code':code,'chaofen':0,'watermark_switch':0,'pn':1})
            response.raise_for_status();result=response.json()
        if result.get('code')!=10000:
            target.write_text(json.dumps({'avatar_id':avatar['id'],'audio_hash':digest,'status':'failed'}))
            raise HTTPException(502,'GPU rejected job')
    return {'code':code,'status':'processing'}


async def query(code):
    target=code_path(code)
    if not target.exists():raise HTTPException(404)
    saved=json.loads(target.read_text())
    if saved['status']=='failed':return {'status':'failed'}
    async with httpx.AsyncClient(timeout=30,follow_redirects=False,trust_env=False) as client:
        response=await client.get(native+'/query',params={'code':code});response.raise_for_status();raw=response.json()
    if raw.get('code') in (9999,10002,10003):return {'status':'failed'}
    data=raw.get('data') or {}
    if raw.get('code')==10000 and data.get('status')==2:
        output=path_inside(data.get('result',''))
        if output.suffix.lower()!='.mp4' or not output.is_file():raise HTTPException(502,'Output not available')
        return {'status':'completed','file':output}
    return {'status':'failed' if data.get('status')==3 else 'processing'}


@app.get('/jobs/{code}',dependencies=[Depends(authorize)])
async def status(code:str):return {'status':(await query(code))['status']}


@app.get('/jobs/{code}/video',dependencies=[Depends(authorize)])
async def video(code:str):
    result=await query(code)
    if result['status']!='completed':raise HTTPException(409,'Not completed')
    return FileResponse(result['file'],media_type='video/mp4')
