"""Short HTTP requests around long-running, owner-scoped Editor generation."""
import asyncio
import hashlib
import json
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from pymongo.errors import DuplicateKeyError
from typing import Literal
from routes.auth import require_auth
from routes.deps import db, logger
from routes.projects_common import load_authorized_project

router = APIRouter(prefix='/generate-html/jobs', tags=['Editor generation'])


class HtmlJobRequest(BaseModel):
    prompt: str = Field(min_length=3, max_length=5000)
    courseContext: str = Field(default='', max_length=8000)
    simulatorComplexity: Literal['guided','applied','advanced'] = 'guided'
    simulatorVisualStyle: Literal['illustrated','technical'] = 'illustrated'
    sourceSimulator: str = Field(default='', max_length=120000)
    projectId: str = Field(default='', max_length=100)
    requestId: str = Field(min_length=16, max_length=100, pattern=r'^[A-Za-z0-9_-]+$')


def _owner(user):
    owner = user.get('user_id') or user.get('id')
    if not owner: raise HTTPException(401, 'Sua sessão expirou. Entre novamente.')
    return str(owner)


def _public(job):
    result = {'jobId': job['id'], 'status': job['status']}
    if job['status'] == 'done': result['html'] = job.get('html', '')
    if job['status'] == 'error': result['error'] = job.get('error', 'Não foi possível gerar a atividade.')
    return result


async def _run(job_id, owner, request, user):
    # Claim atomically: a repeated POST must never generate/charge twice.
    claimed = await db.html_generation_jobs.update_one(
        {'_id': job_id, 'ownerId': owner, 'status': 'queued'},
        {'$set': {'status': 'running', 'updatedAt': datetime.now(timezone.utc)}})
    if not claimed.modified_count: return
    try:
        if request.get('sourceSimulator'):
            from services.simulator_visual_refinement import refine_visual
            result=await asyncio.wait_for(refine_visual(request['sourceSimulator'],request['prompt'],request['courseContext'],
                request.get('simulatorComplexity','advanced'),request.get('simulatorVisualStyle','illustrated')),timeout=18*60)
        else:
            from routes.agent import GenerateHtmlRequest, generate_html_with_ai
            result = await asyncio.wait_for(generate_html_with_ai(
            GenerateHtmlRequest(prompt=request['prompt'], courseContext=request['courseContext'],
                                simulatorComplexity=request.get('simulatorComplexity','guided'),
                                simulatorVisualStyle=request.get('simulatorVisualStyle','illustrated')),
            _user=user), timeout=18 * 60)
        if not result.get('html'): raise ValueError('A IA retornou uma atividade vazia.')
        update = {'status': 'done', 'html': result['html']}
    except HTTPException as exc:
        update = {'status': 'error', 'error': str(exc.detail)}
    except TimeoutError:
        update = {'status': 'error', 'error': 'A geração excedeu o tempo de resposta. Tente novamente. Seu curso não foi alterado.'}
    except asyncio.CancelledError:
        await db.html_generation_jobs.update_one({'_id': job_id, 'ownerId': owner},
            {'$set': {'status': 'error', 'error': 'A geração foi interrompida por uma reinicialização do serviço. Tente novamente.'}})
        raise
    except Exception as exc:
        from services.generation_errors import storyboard_error_message
        logger.exception('Editor HTML job failed: %s', job_id)
        message = storyboard_error_message(exc).replace('O storyboard', 'O simulador').replace(
            'Sua estrutura foi preservada.', 'Seu curso não foi alterado.')
        update = {'status': 'error', 'error': message}
    update['updatedAt'] = datetime.now(timezone.utc)
    await db.html_generation_jobs.update_one({'_id': job_id, 'ownerId': owner}, {'$set': update})


@router.post('', status_code=202)
async def start_html_job(body: HtmlJobRequest, tasks: BackgroundTasks, user: dict = Depends(require_auth)):
    owner = _owner(user)
    if body.projectId:
        await load_authorized_project(body.projectId, user)
    request = body.model_dump()
    job_id = 'html_' + hashlib.sha256((owner + ':' + body.requestId).encode()).hexdigest()
    signature = hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()
    job = await db.html_generation_jobs.find_one({'_id': job_id, 'ownerId': owner})
    if not job:
        now = datetime.now(timezone.utc)
        job = {'_id': job_id, 'id': job_id, 'ownerId': owner, 'companyId': user.get('companyId'),
               'projectId': body.projectId, 'requestHash': signature, 'status': 'queued',
               'createdAtDate': now, 'updatedAt': now}
        try:
            await db.html_generation_jobs.insert_one(job)
        except DuplicateKeyError:
            job = await db.html_generation_jobs.find_one({'_id': job_id, 'ownerId': owner})
    if not job or job['requestHash'] != signature:
        raise HTTPException(409, 'Este pedido já foi usado para outra geração. Inicie uma nova tentativa.')
    if job['status'] == 'queued':
        tasks.add_task(_run, job_id, owner, request, {'user_id': owner, 'companyId': user.get('companyId')})
    return _public(job)


@router.get('/{job_id}')
async def get_html_job(job_id: str, user: dict = Depends(require_auth)):
    owner = _owner(user)
    job = await db.html_generation_jobs.find_one({'_id': job_id, 'ownerId': owner})
    if not job: raise HTTPException(404, 'Geração não encontrada para este usuário.')
    updated = job.get('updatedAt') or job['createdAtDate']
    if updated.tzinfo is None: updated = updated.replace(tzinfo=timezone.utc)
    if job['status'] in ('queued', 'running') and datetime.now(timezone.utc) - updated > timedelta(minutes=20):
        update = {'status': 'error', 'error': 'O serviço interrompeu ou excedeu o tempo da geração. Inicie uma nova tentativa.'}
        await db.html_generation_jobs.update_one({'_id': job_id, 'ownerId': owner, 'status': job['status']}, {'$set': update})
        # Re-read in case the worker finished concurrently with this check.
        job = await db.html_generation_jobs.find_one({'_id': job_id, 'ownerId': owner})
    return _public(job)
