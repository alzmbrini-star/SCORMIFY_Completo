"""Export existing linked Gamma and explicitly replace selected base images."""
import asyncio
import hashlib
import re
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from routes.auth import require_auth, has_any_role
from routes.deps import db, PROJECTS_DIR
from routes.projects_common import load_authorized_project
from services import gamma_api
from services.asset_store import store_asset_async
from services.gamma_refresh import linked_bases, document_id, image_patches

router = APIRouter(tags=['Gamma'])


def timestamp(): return datetime.now(timezone.utc).isoformat()


def user_id(user): return user.get('user_id') or user.get('id')


async def editable(pid, user):
    if not has_any_role(user, 'editor', 'company_admin'):
        raise HTTPException(403, 'Atualizar slides Gamma requer permissão de edição.')
    project = await load_authorized_project(pid, user)
    try: linked_bases(project)
    except ValueError as exc: raise HTTPException(400, str(exc)) from None
    return project


def revision(project):
    value = project.get('updatedAt')
    return value.isoformat() if hasattr(value, 'isoformat') else value


def safe(job):
    return {key: job.get(key) for key in ['id', 'status', 'error', 'bases', 'images', 'createdAt', 'appliedSlides']}


class Prepare(BaseModel):
    model_config = ConfigDict(extra='forbid')
    requestId: uuid.UUID


class Mapping(BaseModel):
    model_config = ConfigDict(extra='forbid')
    slideId: str = Field(min_length=1, max_length=128)
    sourceIndex: int = Field(ge=0, le=101, strict=True)


class Apply(BaseModel):
    model_config = ConfigDict(extra='forbid')
    mappings: list[Mapping] = Field(min_length=1, max_length=102)


async def owned_job(pid, ident, user):
    project = await editable(pid, user)
    job = await db.gamma_refreshes.find_one({'id': ident, 'projectId': pid, 'userId': user_id(user)})
    if not job: raise HTTPException(404, 'Atualização Gamma não encontrada.')
    return project, job


@router.post('/projects/{pid}/gamma-refresh')
async def prepare(pid: str, data: Prepare, user=Depends(require_auth)):
    project = await editable(pid, user)
    ident = str(uuid.uuid5(uuid.NAMESPACE_URL, f'gamma-refresh:{pid}:{user_id(user)}:{data.requestId}'))
    existing = await db.gamma_refreshes.find_one({'_id': ident})
    if existing: return safe(existing)
    source = await db.gamma_generations.find_one({'id': project['gammaJobId'], 'projectId': pid})
    try: gamma_id = document_id(source or {})
    except ValueError as exc: raise HTTPException(400, str(exc)) from None
    if not gamma_api.configured(): raise HTTPException(503, 'Configure GAMMA_API_KEY no servidor.')
    job = {'_id': ident, 'id': ident, 'projectId': pid, 'userId': user_id(user), 'companyId': project.get('companyId'),
           'status': 'submitting', 'createdAt': timestamp(), 'baseRevision': revision(project), 'bases': linked_bases(project)}
    from pymongo.errors import DuplicateKeyError
    try: await db.gamma_refreshes.insert_one(job)
    except DuplicateKeyError: return safe(await db.gamma_refreshes.find_one({'_id': ident}))
    try:
        response = await gamma_api.request('POST', f'/gammas/{gamma_id}/export', {'exportAs': 'png'})
        export_id = response.get('exportId')
        if not isinstance(export_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', export_id):
            raise gamma_api.GammaError('Gamma não confirmou a exportação. Nenhum slide foi alterado.')
        update = {'status': 'pending', 'exportId': export_id}
    except gamma_api.GammaError as exc: update = {'status': 'failed', 'error': str(exc)}
    await db.gamma_refreshes.update_one({'_id': ident}, {'$set': update})
    job.update(update)
    return safe(job)


@router.get('/projects/{pid}/gamma-refresh/{ident}')
async def poll(pid: str, ident: str, user=Depends(require_auth)):
    _, job = await owned_job(pid, ident, user)
    if job['status'] not in ['pending', 'preparing']: return safe(job)
    now = timestamp()
    lease = await db.gamma_refreshes.update_one({'_id': job['_id'], '$or': [{'leaseUntil': {'$exists': False}}, {'leaseUntil': {'$lt': now}}]},
        {'$set': {'leaseUntil': (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()}})
    if not lease.modified_count: return safe(job)
    update = {}
    try:
        response = await gamma_api.request('GET', '/exports/' + job['exportId'])
        if response.get('status') == 'failed':
            update = {'status': 'failed', 'error': 'O Gamma não concluiu a exportação. O curso está preservado.'}
        elif response.get('status') == 'completed':
            raw = await gamma_api.download(response.get('exportUrl'))
            images, iterator = [], gamma_api.png_slides(raw)
            while True:
                image = await asyncio.to_thread(next, iterator, None)
                if image is None: break
                content, width, height = image
                index = len(images)
                digest = hashlib.sha256(content).hexdigest()
                filename = f'gamma_refresh_{job["id"]}_{index+1}_{digest[:12]}.webp'
                path = Path(PROJECTS_DIR) / pid / 'assets' / filename
                path.parent.mkdir(parents=True, exist_ok=True)
                await asyncio.to_thread(path.write_bytes, content)
                if not await store_asset_async(db, pid, filename, str(path)):
                    raise gamma_api.GammaError('Não foi possível persistir a imagem. Consulte novamente; o curso não foi alterado.')
                images.append({'index': index, 'src': f'/api/projects/{pid}/assets/{filename}', 'width': width, 'height': height})
            update = {'status': 'ready', 'images': images, 'error': None}
    except gamma_api.GammaError as exc: update = {'error': str(exc)}
    finally:
        await db.gamma_refreshes.update_one({'_id': job['_id']}, {'$set': update, '$unset': {'leaseUntil': ''}})
    return safe(await db.gamma_refreshes.find_one({'_id': job['_id']}))


@router.post('/projects/{pid}/gamma-refresh/{ident}/apply')
async def apply(pid: str, ident: str, data: Apply, user=Depends(require_auth)):
    project, job = await owned_job(pid, ident, user)
    if project.get('gammaLastRefreshId') == ident: return {'appliedSlides': job.get('appliedSlides'), 'alreadyApplied': True}
    if job['status'] != 'ready': raise HTTPException(409, 'Aguarde a preparação das imagens antes de aplicar.')
    if revision(project) != job.get('baseRevision'):
        raise HTTPException(409, 'O curso mudou durante a revisão. Salve suas edições e prepare uma nova atualização; nada foi substituído.')
    try: patches, backup = image_patches(project, job, [row.model_dump() for row in data.mappings])
    except ValueError as exc: raise HTTPException(400, str(exc)) from None
    # Retain old URLs and correspondence before modifying the course. Old files
    # remain in persistent asset storage; no deletion or replacement in place.
    await db.gamma_refresh_backups.update_one({'_id': ident}, {'$setOnInsert': {'projectId': pid, 'companyId': project.get('companyId'),
        'userId': user_id(user), 'createdAt': timestamp(), 'images': backup}}, upsert=True)
    guard = {'id': pid, 'course.slides': project['course']['slides']}
    guard['updatedAt'] = project['updatedAt'] if 'updatedAt' in project else {'$exists': False}
    patches.update({'updatedAt': timestamp(), 'gammaLastRefreshId': ident})
    result = await db.projects.update_one(guard, {'$set': patches})
    if not result.modified_count: raise HTTPException(409, 'O curso recebeu outra edição. Nada foi substituído; prepare novamente.')
    await db.gamma_refreshes.update_one({'_id': job['_id']}, {'$set': {'status': 'applied', 'appliedSlides': len(backup)}})
    return {'appliedSlides': len(backup)}
