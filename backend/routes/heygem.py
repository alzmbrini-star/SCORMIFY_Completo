"""Optional HeyGem provider, isolated from HeyGen credentials, jobs and credits."""
import asyncio
import hashlib
import re
import uuid
from datetime import datetime,timezone
from fastapi import APIRouter,Depends,HTTPException,Request
from fastapi.responses import StreamingResponse
from motor.motor_asyncio import AsyncIOMotorGridFSBucket
from routes.auth import require_auth,has_any_role,has_role
from routes.deps import db
from services import heygem

router=APIRouter(tags=['HeyGem'])
tasks=set()
async def require_creator(user:dict=Depends(require_auth)):
    if not has_any_role(user,'editor','company_admin'):raise HTTPException(403,'Acesso de criador necessário.')
    permissions=(user.get('company') or {}).get('permissions',{})
    if not has_role(user,'super_admin') and not (permissions.get('heygen') and permissions.get('elevenlabs')):
        raise HTTPException(403,'A empresa precisa das permissões de avatar e ElevenLabs para usar HeyGem.')
    if not owner(user):raise HTTPException(401)
    return user
def now():return datetime.now(timezone.utc).isoformat()
def owner(user):return str(user.get('user_id') or user.get('id') or '')
def bucket():return AsyncIOMotorGridFSBucket(db,bucket_name='heygem_media')
def public(row):
    return {k:row.get(k) for k in ('video_id','title','status','video_url','error','created_at','provider')}


@router.get('/heygem/config')
async def config(user:dict=Depends(require_auth)):
    ready=heygem.configuration()[2]
    return {'configured':ready,'ttsReady':bool(heygem.tts_key()),'provider':'heygem',
            'mode':'gpu-bridge-v1','transparent':False,
            'message':'Ponte GPU HeyGem configurada.' if ready else 'HeyGem indisponível: configure a ponte GPU no servidor. HeyGen continua independente.'}


@router.get('/heygem/avatars')
async def avatars(user:dict=Depends(require_auth)):
    try:return {'avatars':await heygem.catalog()}
    except heygem.HeygemError as exc:raise HTTPException(503,str(exc))


async def start_job(code,user_id,avatar,voice,script):
    try:
        audio=await heygem.speech(script,voice)
        await db.heygem_videos.update_one({'video_id':code,'userId':user_id},{'$set':{'status':'submitting'}})
        await heygem.submit(code,avatar,audio)
        await db.heygem_videos.update_one({'video_id':code,'userId':user_id},{'$set':{'status':'processing'}})
    except Exception as exc:
        # A timeout after submit is ambiguous. Preserve its UUID and reconcile;
        # polling never resubmits paid work or generates another audio.
        row=await db.heygem_videos.find_one({'video_id':code})
        ambiguous=row and row.get('status')=='submitting'
        await db.heygem_videos.update_one({'video_id':code},{'$set':{
            'status':'unknown' if ambiguous else 'failed',
            'error':str(exc)[:300] if isinstance(exc,heygem.HeygemError) else 'Falha ao preparar o avatar. O curso não foi alterado.'}})


@router.post('/heygem/jobs')
async def generate(request:Request,user:dict=Depends(require_creator)):
    body=await request.json()
    if not isinstance(body,dict):raise HTTPException(422,'Configuração inválida.')
    script=body.get('script');avatar=body.get('avatar_id');voice=body.get('voice_id');key=body.get('request_id')
    if not isinstance(script,str) or not 1<=len(script.strip())<=1000:raise HTTPException(422,'Informe até 1000 caracteres de fala para a prova de conceito.')
    if body.get('consent') is not True:raise HTTPException(422,'Confirme a autorização de uso da imagem e da voz.')
    if not isinstance(avatar,str) or not isinstance(voice,str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,100}',voice):raise HTTPException(422,'Selecione avatar e ID de voz ElevenLabs.')
    try:key=str(uuid.UUID(str(key)))
    except ValueError:raise HTTPException(422,'Identificador da solicitação inválido.')
    query={'userId':owner(user),'requestId':key}
    existing=await db.heygem_videos.find_one(query)
    fingerprint=hashlib.sha256((avatar+'\0'+voice+'\0'+script.strip()).encode()).hexdigest()
    if existing:
        if existing.get('fingerprint') and existing['fingerprint']!=fingerprint:
            raise HTTPException(409,'Esta solicitação já pertence a outro roteiro. Atualize a tarefa existente.')
        return public(existing)
    try:
        if avatar not in {a['id'] for a in await heygem.catalog()}:raise HTTPException(422,'Avatar não cadastrado na ponte HeyGem.')
        if not heygem.tts_key():raise heygem.HeygemError('Configure ElevenLabs antes de iniciar a geração.')
    except heygem.HeygemError as exc:raise HTTPException(503,str(exc))
    code=str(uuid.uuid4())
    row={'_id':owner(user)+':'+key,'video_id':code,'requestId':key,'userId':owner(user),
         'companyId':user.get('companyId'),'provider':'heygem','status':'preparing','fingerprint':fingerprint,
         'title':str(body.get('title') or 'Avatar HeyGem')[:120],'created_at':now()}
    from pymongo.errors import DuplicateKeyError
    try:await db.heygem_videos.insert_one(row)
    except DuplicateKeyError:return public(await db.heygem_videos.find_one(query))
    task=asyncio.create_task(start_job(code,owner(user),avatar,voice,script.strip()))
    tasks.add(task);task.add_done_callback(tasks.discard)
    return public(row)


async def reconcile(row):
    code=row['video_id']
    if row['status'] in ('completed','failed','preparing'):return row
    try:
        result=await heygem.status(code)
        if result.get('status')=='failed':
            row.update(status='failed',error='O serviço GPU informou falha na renderização. Confira o servidor antes de gerar novamente.')
        elif result.get('status')=='completed':
            # Atomic lease avoids two pollers downloading the same output.
            from datetime import timedelta
            lease=(datetime.now(timezone.utc)-timedelta(minutes=5)).isoformat()
            claimed=await db.heygem_videos.find_one_and_update({'video_id':code,
                '$or':[{'persistingAt':{'$exists':False}},{'persistingAt':{'$lt':lease}}]},
                {'$set':{'persistingAt':now()}})
            if not claimed:return row
            stream=None
            try:
                stream=await bucket().open_upload_stream(code+'.mp4',metadata={'owner':row['userId'],'content_type':'video/mp4'})
                first=True
                async for chunk in heygem.download(code):
                    if first and (len(chunk)<12 or chunk[4:8]!=b'ftyp'):raise heygem.HeygemError('O resultado não é um MP4 válido.')
                    first=False;await stream.write(chunk)
                if first:raise heygem.HeygemError('O HeyGem retornou um vídeo vazio.')
                await stream.close()
                row.update(status='completed',video_url='/api/heygem/assets/'+code+'.mp4',fileId=stream._id,error=None)
            except Exception:
                if stream is not None and not stream.closed:await stream.abort()
                await db.heygem_videos.update_one({'video_id':code},{'$unset':{'persistingAt':''}})
                raise
        else:row['status']='processing'
        await db.heygem_videos.update_one({'video_id':code},{'$set':{k:row[k] for k in ('status','video_url','fileId','error') if k in row}})
    except Exception:
        row['error']='Não foi possível atualizar ou armazenar o vídeo. Atualizar tenta recuperar a mesma tarefa, sem nova geração.'
    return row


@router.get('/heygem/videos')
async def videos(user:dict=Depends(require_auth)):
    rows=await db.heygem_videos.find({'userId':owner(user)}).sort('created_at',-1).limit(50).to_list(50)
    return {'videos':[public(r) for r in rows]}


@router.get('/heygem/jobs/{code}')
async def status(code:str,user:dict=Depends(require_auth)):
    row=await db.heygem_videos.find_one({'video_id':code,'userId':owner(user)})
    if not row:raise HTTPException(404,'Vídeo não encontrado.')
    return public(await reconcile(row))


@router.get('/heygem/assets/{filename}')
async def asset(filename:str,request:Request):
    # Random UUID is a capability URL, like public course assets. No provider key
    # or private gateway URL is embedded in exports. Do not list files publicly.
    if not re.fullmatch(r'[a-f0-9-]{36}\.mp4',filename):raise HTTPException(404)
    row=await db.heygem_videos.find_one({'video_id':filename[:-4],'status':'completed'})
    if not row or not row.get('fileId'):raise HTTPException(404)
    stream=await bucket().open_download_stream(row['fileId']);size=stream.length
    start,end=0,size-1;partial=False
    header=request.headers.get('range','')
    if header:
        match=re.fullmatch(r'bytes=(\d*)-(\d*)',header)
        if not match or not any(match.groups()):
            stream.close();raise HTTPException(416,headers={'Content-Range':f'bytes */{size}'})
        a,b=match.groups()
        if a:start=int(a);end=min(int(b),end) if b else end
        else:start=max(0,size-int(b))
        if start>end or start>=size:
            stream.close();raise HTTPException(416,headers={'Content-Range':f'bytes */{size}'})
        partial=True
    async def chunks():
        stream.seek(start);left=end-start+1
        try:
            while left:
                chunk=await stream.read(min(1024*1024,left))
                if not chunk:break
                left-=len(chunk);yield chunk
        finally:stream.close()
    headers={'Accept-Ranges':'bytes','Content-Length':str(end-start+1),'Cache-Control':'public,max-age=86400',
             'X-Content-Type-Options':'nosniff'}
    if partial:headers['Content-Range']=f'bytes {start}-{end}/{size}'
    return StreamingResponse(chunks(),status_code=206 if partial else 200,media_type='video/mp4',headers=headers)
