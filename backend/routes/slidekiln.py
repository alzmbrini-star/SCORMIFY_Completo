"""Explicit per-file budget approval before any provider conversion.
Only new projects are created. Uncertain paid calls are never retried.
"""
import asyncio
import hashlib
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
import httpx
from motor.motor_asyncio import AsyncIOMotorGridFSBucket
from fastapi import APIRouter, Depends, File, UploadFile, Form, HTTPException, BackgroundTasks
from pydantic import BaseModel
from routes import deps
from routes.auth import require_auth, has_any_role, has_role
from routes.projects_common import resolve_company_id_for_creation
from services import slidekiln as sk
from services.film_exchange import usd_brl_reference
from services.asset_store import store_asset_async
from models import Project, Slide, SlideElement

router = APIRouter(tags=['SlideKiln PPT'])


def permission(user):
    if not has_any_role(user, 'editor', 'company_admin'):
        raise HTTPException(403, 'A importação requer permissão de edição.')


def owner(user):
    return str(user.get('user_id') or user.get('id'))


def bucket():
    return AsyncIOMotorGridFSBucket(deps.db, bucket_name='slidekiln_inputs')


def public(job):
    return {k: job.get(k) for k in ('id','status','filename','slides','budget','expiresAt','message','projectId','warnings')}


async def authorized(ident, user):
    permission(user)
    job = await deps.db.slidekiln_jobs.find_one({'id': ident, 'ownerId': owner(user), 'companyId': user.get('companyId')})
    if not job:
        raise HTTPException(404, 'Importação não encontrada.')
    return job


@router.get('/ppt/slidekiln/config')
async def config(user=Depends(require_auth)):
    permission(user)
    return {'configured': sk.configured(), 'maxBytes': sk.MAX_INPUT, 'version': sk.VERSION,
            'approvalRequired': True, 'moduleMode': True, 'canApprove': has_role(user, 'super_admin')}


@router.post('/ppt/slidekiln/quote')
async def quote(file: UploadFile=File(...), company_id: str=Form(''), user=Depends(require_auth)):
    permission(user)
    if not sk.configured():
        raise HTTPException(503, 'Configure SLIDEKILN_API_KEY no servidor. O ConvertAPI continua disponível.')
    # Clean only this author's abandoned, unapproved uploads; never courses.
    scope = {'ownerId': owner(user), 'companyId': user.get('companyId')}
    now_iso = datetime.now(timezone.utc).isoformat()
    async for old in deps.db.slidekiln_jobs.find({**scope, 'status':'awaiting_approval', 'expiresAt':{'$lte':now_iso}}).limit(20):
        claimed = await deps.db.slidekiln_jobs.update_one({'id':old['id'],'status':'awaiting_approval'}, {'$set':{'status':'expired'}})
        if claimed.modified_count:
            await bucket().delete(old['blob'])
    if await deps.db.slidekiln_jobs.count_documents({**scope, 'status':'awaiting_approval'}) >= 5:
        raise HTTPException(429, 'Há cinco orçamentos aguardando aprovação. Aguarde a expiração antes de preparar outros.')
    data = await file.read(sk.MAX_INPUT + 1)
    try:
        info = await asyncio.to_thread(sk.pptx_info, data, file.filename or '')
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None
    fx = await usd_brl_reference()
    if not fx.get('available'):
        raise HTTPException(503, 'Cotação indisponível. Nenhuma conversão foi solicitada; tente preparar o orçamento mais tarde.')
    company = await resolve_company_id_for_creation(user, company_id or None)
    digest = hashlib.sha256(data).hexdigest()
    existing = await deps.db.slidekiln_jobs.find_one({**scope,'targetCompanyId':company,'sha256':digest,
        'status':{'$in':['awaiting_approval','processing','unknown']}})
    if existing:
        return public(existing)  # reconnect without duplicating paid work
    ident = str(uuid.uuid4())
    blob = await bucket().upload_from_stream(ident + '.pptx', data)
    job = {'id': ident, 'ownerId': owner(user), 'companyId': user.get('companyId'), 'targetCompanyId': company,
           'filename': Path(file.filename).name[:180], 'sha256': digest, 'blob': blob,
           'slides': info['slides'], 'status': 'awaiting_approval',
           'expiresAt': (datetime.now(timezone.utc) + timedelta(minutes=20)).isoformat(),
           'budget': {'maxUsd': 1.0, 'maxBrl': round(float(fx['rate']) + .005, 2), 'exchange': fx,
                      'notice': 'Até US$ 1,00 por conversão, antes de impostos/tarifas. Pode estar incluída na franquia Pro. O saldo da franquia não é consultado automaticamente. Uma aprovação vale apenas para este arquivo e uma chamada, sem novas tentativas pagas automáticas.'}}
    try:
        await deps.db.slidekiln_jobs.insert_one(job)
    except Exception:
        await bucket().delete(blob)
        raise
    return public(job)


class Approval(BaseModel):
    approveCost: bool = False
    confirmRights: bool = False


@router.post('/ppt/slidekiln/{ident}/approve')
async def approve(ident: str, payload: Approval, background: BackgroundTasks, user=Depends(require_auth)):
    job = await authorized(ident, user)
    if not has_role(user, 'super_admin'):
        raise HTTPException(403, 'A aprovação de uso da conta SlideKiln requer Super Admin.')
    if not payload.approveCost or not payload.confirmRights:
        raise HTTPException(400, 'Confirme o orçamento e os direitos do conteúdo antes de converter.')
    if job['status'] != 'awaiting_approval':
        return public(job)  # idempotent, including running/unknown/failed jobs
    if datetime.now(timezone.utc) >= datetime.fromisoformat(job['expiresAt']):
        raise HTTPException(409, 'Orçamento expirado. Prepare outro antes de converter.')
    if not sk.configured():
        raise HTTPException(503, 'Chave SlideKiln indisponível; nenhuma chamada foi enviada.')
    claim = await deps.db.slidekiln_jobs.update_one({'id': ident, 'status': 'awaiting_approval'},
        {'$set': {'status': 'processing', 'approvedAt': datetime.now(timezone.utc).isoformat(),
                  'message': 'Conversão autorizada. Não envie novamente.'}})
    if claim.modified_count:
        background.add_task(produce, ident)
    return public(await authorized(ident, user))


@router.get('/ppt/slidekiln/{ident}')
async def get_job(ident: str, user=Depends(require_auth)):
    job = await authorized(ident, user)
    if job['status'] == 'processing' and datetime.now(timezone.utc) - datetime.fromisoformat(job['approvedAt']) > timedelta(minutes=20):
        await deps.db.slidekiln_jobs.update_one({'id': ident, 'status': 'processing'}, {'$set': {
            'status': 'unknown', 'message': 'Processamento interrompido ou sem confirmação. Confira o histórico SlideKiln antes de autorizar outra conversão; não houve repetição automática.'}})
        job = await authorized(ident, user)
    return public(job)


async def produce(ident):
    job = await deps.db.slidekiln_jobs.find_one({'id': ident})
    submitted = False
    try:
        stream = await bucket().open_download_stream(job['blob'])
        data = await stream.read()
        if hashlib.sha256(data).hexdigest() != job['sha256']:
            raise ValueError('Arquivo diferente do orçamento aprovado.')
        async with httpx.AsyncClient(timeout=120, follow_redirects=False) as client:
            # Mark uncertainty BEFORE POST: interruption cannot trigger another paid call.
            submitted = True
            provider_id = await sk.submit(client, data, job['filename'], ident)
            await deps.db.slidekiln_jobs.update_one({'id': ident}, {'$set': {'providerJobId': provider_id}})
            for _ in range(180):
                result = await sk.status(client, provider_id)
                if result.get('state') == 'succeeded':
                    break
                if result.get('state') in ('failed','expired'):
                    raise ValueError('O provedor não concluiu a conversão. Confira o histórico antes de autorizar outra chamada.')
                await asyncio.sleep(3)
            else:
                raise TimeoutError('A conversão não foi confirmada no prazo. Confira o histórico SlideKiln; não haverá nova tentativa automática.')
            package = await sk.download(client, provider_id)
        document = await asyncio.to_thread(sk.offline_document, package)
        # A fresh project and asset namespace; never update an existing course.
        project = Project(name=Path(job['filename']).stem)
        project.course.metadata.title = project.name
        filename = uuid.uuid4().hex + '.sk.html'
        folder = deps.PROJECTS_DIR / project.id / 'assets'
        folder.mkdir(parents=True, exist_ok=True)
        asset = folder / filename
        await asyncio.to_thread(asset.write_text, document, encoding='utf-8')
        if not await store_asset_async(deps.db, project.id, filename, str(asset)):
            raise ValueError('Não foi possível persistir o pacote. Não houve nova chamada ao provedor.')
        project.course.slides = [Slide(title=project.name, width=1280, height=800, elements=[SlideElement(
            type='html', width=1280, height=800, htmlContent=sk.module_html(project.id, filename),
            htmlDisplayMode='page', source='slidekiln', pptSlideCount=job['slides'])])]
        project.course.originalFilename = job['filename']
        project.course.conversionReport = {'provider':'slidekiln','moduleMode':True,'pptSlideCount':job['slides'],
            'warnings': (result.get('stats') or {}).get('warnings', [])}
        record = project.model_dump(mode='json')
        record.update({'source':'ppt','importProvider':'slidekiln','userId':job['ownerId'],
                       'companyId':job.get('targetCompanyId'),'status':'ready'})
        await deps.db.projects.insert_one(record)
        await deps.db.slidekiln_jobs.update_one({'id': ident}, {'$set': {'status':'completed',
            'projectId':project.id,'message':'Apresentação importada como bloco interativo. Revise no Editor.',
            'warnings':project.course.conversionReport['warnings']}})
    except Exception as exc:
        # Do not expose signed URLs, job capability identifiers, keys, or provider response bodies.
        message = str(exc) if isinstance(exc, (ValueError, TimeoutError)) else 'Não foi possível confirmar a importação. Confira o histórico SlideKiln antes de autorizar outra chamada.'
        await deps.db.slidekiln_jobs.update_one({'id':ident}, {'$set': {
            'status':'unknown' if submitted else 'failed', 'message':message[:500]}})
    finally:
        if job:
            try:
                await bucket().delete(job['blob'])
            except Exception:
                pass
