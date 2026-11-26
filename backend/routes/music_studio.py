"""Music library; no endpoint edits courses. Generation requires explicit BRL approval."""
import uuid
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import Response
from pydantic import BaseModel, Field
from routes import deps
from routes.auth import require_auth, has_role
from routes.runway import can_edit, narration_allowed
from routes.projects_common import load_authorized_project
from services import music_studio as music
from services.film_exchange import usd_brl_reference

router=APIRouter(tags=['Music studio'])


def now():return datetime.now(timezone.utc)


def permission(user):
    can_edit(user)
    if not narration_allowed(user):raise HTTPException(403,'Sua empresa precisa da permissão ElevenLabs para gerar músicas.')


def view(job):return {k:v for k,v in job.items() if k not in ('_id','ownerId','companyId')}


async def authorized(ident,user):
    permission(user)
    try:uuid.UUID(ident)
    except (ValueError,TypeError):raise HTTPException(404,'Música não encontrada.') from None
    job=await deps.db.music_jobs.find_one({'id':ident},{'_id':0})
    if not job or (not has_role(user,'super_admin') and (job['ownerId']!=str(user.get('user_id') or user.get('id')) or job.get('companyId')!=user.get('companyId'))):
        raise HTTPException(404,'Música não encontrada.')
    # A restarted worker never resubmits an uncertain paid request.
    if job['status']=='generating' and now()-datetime.fromisoformat(job['startedAt'])>timedelta(minutes=15):
        await deps.db.music_jobs.update_one({'id':ident,'status':'generating'},{'$set':{'status':'unknown','notice':'Geração não confirmada após interrupção. Confira o histórico ElevenLabs antes de criar outro orçamento; não será repetida automaticamente.'}})
        job=await deps.db.music_jobs.find_one({'id':ident},{'_id':0})
    return job


class Estimate(BaseModel):
    spec:music.MusicSpec
    requestId:uuid.UUID
    sourceProjectId:str|None=None


class Approve(BaseModel):
    quoteId:str
    ceilingBrl:float=Field(ge=0,le=10000,allow_inf_nan=False)
    consent:bool=False


class Generate(BaseModel):
    quoteId:str


@router.get('/music/config')
async def config(user=Depends(require_auth)):
    permission(user)
    return {'configured':bool(music.api_key()),'maxDuration':300,'provider':'ElevenLabs · Eleven Music'}


@router.get('/music')
async def history(user=Depends(require_auth)):
    permission(user)
    # Always own library; superadmins can open an explicit authorized job separately.
    rows=await deps.db.music_jobs.find({'ownerId':str(user.get('user_id') or user.get('id')),'companyId':user.get('companyId')},{'_id':0}).sort('createdAt',-1).limit(30).to_list(30)
    return {'music':[view(row) for row in rows]}


@router.post('/music/quotes')
async def estimate(body:Estimate,user=Depends(require_auth)):
    permission(user)
    if not music.api_key():raise HTTPException(503,'Configure ELEVENLABS_API_KEY no servidor; nenhuma geração foi solicitada.')
    if body.sourceProjectId:await load_authorized_project(body.sourceProjectId,user)
    owner=str(user.get('user_id') or user.get('id'))
    # Deterministic identity makes transport retries idempotent without paid calls or duplicate drafts.
    ident=str(uuid.uuid5(uuid.NAMESPACE_URL,'scormify-music:'+owner+':'+str(body.requestId)))
    existing=await deps.db.music_jobs.find_one({'id':ident},{'_id':0})
    if existing:
        if existing['spec']!=body.spec.model_dump():raise HTTPException(409,'Solicitação já usada para outro conteúdo. Calcule novo orçamento.')
        return view(await authorized(ident,user))
    try:q=music.quote(body.spec.model_dump(),await usd_brl_reference())
    except ValueError as exc:raise HTTPException(503,str(exc)) from None
    job={'id':ident,'ownerId':owner,'companyId':user.get('companyId'),'spec':body.spec.model_dump(),
         'sourceProjectId':body.sourceProjectId,'quote':q,'status':'quoted','createdAt':now().isoformat()}
    await deps.db.music_jobs.update_one({'_id':ident},{'$setOnInsert':job},upsert=True)
    return view(await authorized(ident,user))


@router.get('/music/{ident}')
async def get(ident:str,user=Depends(require_auth)):return view(await authorized(ident,user))


@router.post('/music/{ident}/approve')
async def approve(ident:str,body:Approve,user=Depends(require_auth)):
    job=await authorized(ident,user)
    if job['status'] not in ('quoted','approved'):raise HTTPException(409,'Esta geração já foi iniciada ou encerrada; não será repetida.')
    try:approval=music.validate_approval(job,body.quoteId,body.ceilingBrl,body.consent)
    except ValueError as exc:raise HTTPException(409,str(exc)) from None
    await deps.db.music_jobs.update_one({'id':ident,'status':{'$in':['quoted','approved']}},{'$set':{'status':'approved','approval':approval}})
    return view(await authorized(ident,user))


async def produce(ident,spec):
    try:
        raw=await music.compose(spec)
        # Separate protected collection: no generic/public project asset URL is created.
        # The bounded MP3 fits safely inside MongoDB's document limit (no base64 overhead).
        await deps.db.music_assets.update_one({'_id':ident},
              {'$setOnInsert':{'data':raw,'contentType':'audio/mpeg'}},upsert=True)
        await deps.db.music_jobs.update_one({'id':ident,'status':'generating'},{'$set':{'status':'ready','completedAt':now().isoformat(),'audioUrl':f'/api/music/{ident}/audio'}})
    except Exception:
        # Never expose raw provider errors, credentials or lyrics; never repeat the POST.
        await deps.db.music_jobs.update_one({'id':ident,'status':'generating'},{'$set':{'status':'unknown','notice':'A geração ou o armazenamento não foi confirmado. Pode ter consumido créditos. Confira o histórico e o saldo ElevenLabs antes de criar outro orçamento; não há nova tentativa automática.'}})


@router.post('/music/{ident}/generate')
async def generate(ident:str,body:Generate,background:BackgroundTasks,user=Depends(require_auth)):
    job=await authorized(ident,user)
    if job['status'] in ('generating','ready','unknown'):return view(job)
    approval=job.get('approval',{})
    try:music.validate_approval(job,body.quoteId,approval.get('ceilingBrl',0),bool(approval))
    except ValueError as exc:raise HTTPException(409,str(exc)) from None
    if approval.get('quoteId')!=body.quoteId or job['status']!='approved':raise HTTPException(409,'Aprove o orçamento atual antes de gerar.')
    if not music.api_key():raise HTTPException(503,'Chave ElevenLabs indisponível; nenhuma chamada foi enviada.')
    result=await deps.db.music_jobs.update_one({'id':ident,'status':'approved','approval.quoteId':body.quoteId},
          {'$set':{'status':'generating','startedAt':now().isoformat()}})
    if result.modified_count:background.add_task(produce,ident,job['spec'])
    return view(await authorized(ident,user))


@router.get('/music/{ident}/audio')
async def audio(ident:str,user=Depends(require_auth)):
    job=await authorized(ident,user)
    if job['status']!='ready':raise HTTPException(409,'Áudio ainda não disponível.')
    asset=await deps.db.music_assets.find_one({'_id':ident})
    raw=(asset or {}).get('data')
    if not raw:raise HTTPException(404,'Áudio não localizado no armazenamento; nenhuma nova geração foi solicitada.')
    return Response(content=raw,media_type='audio/mpeg',headers={'Cache-Control':'private, no-store','Content-Disposition':'attachment; filename="scormify-musica.mp3"'})
