"""Create Gamma presentations only in NEW projects. Existing courses are never targets."""
import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from motor.motor_asyncio import AsyncIOMotorGridFSBucket
from pydantic import BaseModel, ConfigDict, Field

from models import Project
from routes.auth import require_auth, has_any_role
from routes.deps import db, PROJECTS_DIR
from routes.projects_common import resolve_company_id_for_creation, load_authorized_project
from services.asset_store import store_asset_async
from services import gamma_api

router = APIRouter(tags=['Gamma'])


def now():
    return datetime.now(timezone.utc).isoformat()


def creator(user):
    if not has_any_role(user, 'editor', 'company_admin'):
        raise HTTPException(403, 'Criar com Gamma requer permissão de edição.')


def owner(user):
    return user.get('user_id') or user.get('id')


def public(job):
    # Explicit allowlist: no API keys, signed export URLs or raw provider responses.
    return {key: job.get(key) for key in ['id', 'projectId', 'title', 'status', 'createdAt', 'error',
            'progress', 'actualSlides', 'gammaUrl', 'credits', 'warning', 'requestId']}


def sharing_warning(response):
    codes = {item.get('code') for item in response.get('warnings', []) if isinstance(item, dict)}
    if codes & {'ignored_external_access', 'ignored_workspace_access', 'external_access_failed', 'workspace_access_failed'}:
        return 'O Gamma não confirmou a privacidade solicitada. Confira as permissões da apresentação no Gamma antes de incluir conteúdo confidencial.'
    return None


class Generate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    requestId: uuid.UUID
    title: str = Field(min_length=3, max_length=160)
    prompt: str = Field(min_length=20, max_length=10000)
    companyId: str | None = None


@router.get('/gamma/status')
async def configuration(user=Depends(require_auth)):
    creator(user)
    return {'configured': gamma_api.configured(), 'slides': 5, 'language': 'pt-BR'}


@router.get('/gamma/jobs')
async def jobs(user=Depends(require_auth)):
    creator(user)
    rows = await db.gamma_generations.find({'userId': owner(user)}, {'_id': 0}).sort('createdAt', -1).limit(30).to_list(30)
    return [public(row) for row in rows]


@router.post('/gamma/generate')
async def generate(data: Generate, user=Depends(require_auth)):
    creator(user)
    if not gamma_api.configured():
        raise HTTPException(503, 'Configure GAMMA_API_KEY no servidor.')
    # Deterministic ID provides atomic local idempotency across workers and reconnects.
    ident = str(uuid.uuid5(uuid.NAMESPACE_URL, 'scormify-gamma:' + str(owner(user)) + ':' + str(data.requestId)))
    existing = await db.gamma_generations.find_one({'_id': ident})
    if existing:
        return public(existing)
    company = await resolve_company_id_for_creation(user, data.companyId)
    project = Project(name=data.title).model_dump(mode='json')
    project.update({'status': 'processing', 'source': 'gamma', 'gammaJobId': ident,
                    'userId': owner(user), 'companyId': company})
    project['course']['metadata'].update({'title': data.title, 'language': 'pt-BR'})
    project['course']['slides'] = []
    job = {'_id': ident, 'id': ident, 'projectId': project['id'], 'userId': owner(user),
           'companyId': company, 'title': data.title, 'requestId': str(data.requestId),
           'status': 'submitting', 'createdAt': now()}
    from pymongo.errors import DuplicateKeyError
    try:
        await db.gamma_generations.insert_one(job)
    except DuplicateKeyError:
        return public(await db.gamma_generations.find_one({'_id': ident}))
    try:
        await db.projects.insert_one(project)
    except Exception:
        await db.gamma_generations.update_one({'_id': ident}, {'$set': {'status': 'failed', 'error': 'Não foi possível criar o projeto. Nenhuma geração foi solicitada.'}})
        raise HTTPException(503, 'Não foi possível criar o projeto; nenhuma geração foi solicitada.') from None
    try:
        response = await gamma_api.request('POST', '/agent/generations', gamma_api.generation_payload(data.title, data.prompt))
        update = {'generationId': gamma_api.generation_id(response.get('generationId')), 'status': 'pending', 'warning': sharing_warning(response)}
    except gamma_api.GammaError as exc:
        update = {'status': 'unknown', 'error': str(exc)}
    await db.gamma_generations.update_one({'_id': ident}, {'$set': update})
    job.update(update)
    return public(job)


async def authorized(ident, user):
    creator(user)
    job = await db.gamma_generations.find_one({'id': ident, 'userId': owner(user)})
    if not job:
        raise HTTPException(404, 'Geração Gamma não encontrada.')
    await load_authorized_project(job['projectId'], user)
    return job


async def import_archive(job, raw):
    pid = job['projectId']
    if not job.get('archiveId'):
        bucket = AsyncIOMotorGridFSBucket(db, bucket_name='gamma_exports')
        file_id = await bucket.upload_from_stream('gamma-slides.zip', raw, metadata={'projectId': pid})
        await db.gamma_generations.update_one({'id': job['id']}, {'$set': {'archiveId': file_id}})
    # Conversion happens outside the event loop. No original file path is ever extracted.
    images = await asyncio.to_thread(lambda: list(gamma_api.png_slides(raw)))
    slides = []
    for index, (content, width, height) in enumerate(images):
        filename = f'gamma_{job["id"]}_{index+1}.webp'
        path = Path(PROJECTS_DIR) / pid / 'assets' / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(path.write_bytes, content)
        if not await store_asset_async(db, pid, filename, str(path)):
            raise gamma_api.GammaError('Não foi possível persistir um slide. Consulte novamente; não gere outra apresentação.')
        stage_w, stage_h = 1920, round(1920 * height / width)
        slides.append({'id': str(uuid.uuid5(uuid.NAMESPACE_URL, filename)), 'title': job['title'] if index == 0 else f'Slide {index+1}',
                       'order': index, 'width': stage_w, 'height': stage_h, 'background': '#FFFFFF', 'duration': 10,
                       'elements': [{'id': str(uuid.uuid5(uuid.NAMESPACE_DNS, filename)), 'type': 'image',
                         'src': f'/api/projects/{pid}/assets/{filename}', 'x': 0, 'y': 0,
                         'width': stage_w, 'height': stage_h, 'objectFit': 'contain', 'startTime': 0, 'duration': 10}],
                       'notes': 'Criado com Gamma. Imagem-base: textos originais não são objetos editáveis separados.', 'audio': [], 'annotations': []})
    # Compare-and-set: never replace a course edited while the generation was pending.
    result = await db.projects.update_one({'id': pid, 'gammaJobId': job['id'], 'course.slides': {'$size': 0}},
        {'$set': {'course.slides': slides, 'status': 'ready', 'updatedAt': now()}})
    if not result.modified_count:
        raise gamma_api.GammaError('O projeto já contém slides. Eles foram preservados; baixe o ZIP original para revisar a geração.')
    return len(slides)


@router.get('/gamma/jobs/{ident}')
async def poll(ident: str, user=Depends(require_auth)):
    job = await authorized(ident, user)
    if not job.get('generationId') or job['status'] in ['completed', 'failed', 'preserved']:
        return public(job)
    timestamp = now()
    lease = await db.gamma_generations.update_one({'id': ident, '$or': [{'leaseUntil': {'$exists': False}}, {'leaseUntil': {'$lt': timestamp}}]},
        {'$set': {'leaseUntil': (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()}})
    if not lease.modified_count:
        return public(job)
    update = {}
    try:
        response = await gamma_api.request('GET', '/agent/generations/' + job['generationId'])
        update = {'status': 'pending', 'error': None, 'progress': response.get('progress'), 'credits': response.get('credits')}
        warning = sharing_warning(response) or job.get('warning')
        update['warning'] = warning
        gamma = response.get('gamma') or {}
        update['gammaUrl'] = gamma_api.public_gamma_url(gamma.get('gammaUrl'))
        if response.get('status') == 'failed':
            update.update(status='failed', error='Gamma não concluiu a geração (' + str((response.get('error') or {}).get('reason', 'indisponível'))[:80] + '). Confira os créditos no Gamma antes de gerar outra.')
        elif response.get('status') == 'completed':
            export_url = response.get('exportUrl')
            if not export_url:
                update.update(status='failed', error='Gamma concluiu a apresentação, mas não forneceu o ZIP. Abra no Gamma para exportar; não é necessário gerar novamente.')
            else:
                raw = await gamma_api.download(export_url)
                count = await import_archive(job, raw)
                update.update(status='completed', actualSlides=count, progress={'percent': 100},
                              warning=warning if count == 5 else ((warning or '') + f' Gamma entregou {count} slides; 5 é uma meta flexível do provedor. Não houve nova geração automática.').strip())
    except gamma_api.GammaError as exc:
        update.update(error=str(exc))
        if 'já contém slides' in str(exc):
            update['status'] = 'preserved'
    finally:
        await db.gamma_generations.update_one({'id': ident}, {'$set': update, '$unset': {'leaseUntil': ''}})
    return public(await db.gamma_generations.find_one({'id': ident}))


@router.get('/gamma/jobs/{ident}/download')
async def original(ident: str, user=Depends(require_auth)):
    job = await authorized(ident, user)
    if not job.get('archiveId'):
        raise HTTPException(404, 'ZIP ainda não está disponível.')
    stream = await AsyncIOMotorGridFSBucket(db, bucket_name='gamma_exports').open_download_stream(job['archiveId'])
    async def chunks():
        while True:
            chunk = await stream.read(256 * 1024)
            if not chunk:
                break
            yield chunk
    return StreamingResponse(chunks(), media_type='application/zip', headers={'Content-Disposition': 'attachment; filename="Gamma-slides.zip"'})
