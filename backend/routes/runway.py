"""Editor-only Runway jobs, project-scoped access and permanent asset storage."""
import logging
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from routes.auth import require_auth, has_any_role
from routes.deps import db, PROJECTS_DIR
from routes.projects_common import load_authorized_project
from services.asset_store import store_asset_async
from services import runway_ai

router = APIRouter(tags=['Runway'])
logger = logging.getLogger(__name__)
ACTIVE = ['submitting', 'submitted', 'processing', 'saving', 'unknown']


def now():
    return datetime.now(timezone.utc).isoformat()


def can_edit(user):
    if not has_any_role(user, 'editor', 'company_admin'):
        raise HTTPException(403, 'A geração Runway requer permissão de edição.')


def placeholder(slide, options, job_id):
    width, height = float(slide.get('width') or 960), float(slide.get('height') or 540)
    ratio = 16 / 9 if options.get('aspectRatio', '16:9') == '16:9' else 9 / 16
    w = min(width * .9, height * .85 * ratio)
    return {'id': job_id, 'type': 'html', 'x': (width-w)/2, 'y': (height-w/ratio)/2,
            'width': w, 'height': w/ratio, 'duration': options.get('duration', 5), 'startTime': 0,
            'htmlContent': f'<div data-runway-job="{job_id}" style="height:100%;display:grid;place-items:center;background:#10223b;color:white;font:18px Arial;text-align:center">Vídeo Runway em processamento. Acompanhe a geração em Adicionar Vídeo → Criar com Runway.</div>'}


@router.get('/runway/status')
async def configuration(user=Depends(require_auth)):
    can_edit(user)
    return {'configured': runway_ai.configured(), 'models': list(runway_ai.MODELS)}


@router.post('/runway/generate')
async def generate(request: Request, user=Depends(require_auth)):
    can_edit(user)
    if not runway_ai.configured():
        raise HTTPException(503, 'Configure RUNWAYML_API_SECRET no servidor.')
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(400, 'Solicitação Runway inválida.')
    try:
        runway_ai.build_payload(body)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None
    project_id, slide_id = body.get('projectId'), body.get('slideId')
    project = await load_authorized_project(project_id, user)
    slides = project.get('course', {}).get('slides', [])
    index = next((i for i, slide in enumerate(slides) if slide.get('id') == slide_id), None)
    if index is None:
        raise HTTPException(404, 'Slide não encontrado.')
    job_id = str(uuid.uuid4())
    slot = placeholder(slides[index], body, job_id)
    job = {'id': job_id, 'slideId': slide_id, 'title': str(body.get('title') or 'Vídeo Runway')[:160],
           'model': body.get('model', 'gen4.5'), 'duration': body.get('duration', 5),
           'status': 'submitting', 'createdAt': now()}
    # One atomic claim per slide prevents concurrent tabs from submitting twice.
    claim = await db.projects.update_one(
        {'id': project_id, 'course.slides.id': slide_id,
         'runwayPending': {'$not': {'$elemMatch': {'slideId': slide_id, 'status': {'$in': ACTIVE}}}}},
        {'$push': {'runwayPending': job, 'course.slides.$[slide].elements': slot},
         '$max': {'course.slides.$[slide].duration': job['duration']}, '$set': {'updatedAt': now()}},
        array_filters=[{'slide.id': slide_id}])
    if not claim.modified_count:
        raise HTTPException(409, 'Já existe uma geração Runway neste slide. Consulte o status antes de gerar novamente.')
    try:
        task_id = await runway_ai.submit(body)
    except Exception as exc:
        # A lost POST response is ambiguous: do not automatically resubmit/pay again.
        uncertain = not isinstance(exc, ValueError)
        message = (str(exc) if isinstance(exc, ValueError) else
                   'Não foi possível confirmar o envio. Verifique as tarefas no painel Runway antes de tentar outra geração.')
        await db.projects.update_one({'id': project_id, 'runwayPending.id': job_id},
            {'$set': {'runwayPending.$.status': 'unknown' if uncertain else 'failed', 'runwayPending.$.error': message}})
        return {'placeholder': slot, 'status': 'unknown' if uncertain else 'failed', 'error': message}
    await db.projects.update_one({'id': project_id, 'runwayPending.id': job_id},
        {'$set': {'runwayPending.$.taskId': task_id, 'runwayPending.$.status': 'submitted'}})
    return {'placeholder': slot, 'taskId': task_id, 'status': 'submitted'}


async def save_result(project_id, job, output):
    filename = f'runway_{job["id"]}.mp4'
    destination = Path(PROJECTS_DIR) / project_id / 'assets' / filename
    await runway_ai.download(output, destination)
    if not await store_asset_async(db, project_id, filename, str(destination)):
        raise ValueError('Não foi possível armazenar o vídeo permanentemente. Atualize para tentar salvar novamente, sem gerar outro vídeo.')
    url = f'/api/projects/{project_id}/assets/{filename}'
    # Re-read after download: the author may have moved/deleted the slot.
    project = await db.projects.find_one({'id': project_id}, {'course.slides': 1})
    for slide in (project or {}).get('course', {}).get('slides', []):
        for element in slide.get('elements', []):
            if element.get('id') == job['id'] and f'data-runway-job="{job["id"]}"' in element.get('htmlContent', ''):
                video = {k: element[k] for k in ('id', 'x', 'y', 'width', 'height', 'duration', 'startTime') if k in element}
                video.update(type='video', src=url, provider='runway', controls=True, autoplay=False, loop=False, muted=False, objectFit='contain')
                # Match by ID at write time, not a stale element index.
                await db.projects.update_one({'id': project_id},
                    {'$set': {'course.slides.$[slide].elements.$[slot]': video}},
                    array_filters=[{'slide.id': slide['id']}, {'slot.id': job['id']}])
    await db.projects.update_one({'id': project_id, 'runwayPending.id': job['id']},
        {'$set': {'runwayPending.$.status': 'completed', 'runwayPending.$.videoUrl': url,
                  'runwayPending.$.error': '', 'updatedAt': now()}})
    return url


@router.get('/runway/projects/{project_id}/status')
async def project_status(project_id: str, user=Depends(require_auth)):
    can_edit(user)
    project = await load_authorized_project(project_id, user)
    for job in project.get('runwayPending', []):
        if not job.get('taskId') or job.get('status') in ('completed', 'failed'):
            continue
        # A lease survives restarts and prevents duplicate persistence/polling.
        cutoff = (datetime.now(timezone.utc)-timedelta(minutes=7)).isoformat()
        poll_cutoff = (datetime.now(timezone.utc)-timedelta(seconds=5)).isoformat()
        claim = await db.projects.update_one({'id': project_id, 'runwayPending': {'$elemMatch': {
            'id': job['id'], '$and': [
                {'$or': [{'leaseAt': {'$exists': False}}, {'leaseAt': {'$lt': cutoff}}]},
                {'$or': [{'checkedAt': {'$exists': False}}, {'checkedAt': {'$lt': poll_cutoff}}]},
            ]}}}, {'$set': {'runwayPending.$.leaseAt': now(), 'runwayPending.$.checkedAt': now()}})
        if not claim.modified_count:
            continue
        try:
            task = await runway_ai.get_task(job['taskId'])
            status = task.get('status', '').upper()
            if status == 'SUCCEEDED':
                outputs = task.get('output') or []
                if not outputs or not isinstance(outputs[0], str):
                    raise ValueError('Tarefa Runway concluída sem vídeo. Consulte o painel do provedor.')
                await save_result(project_id, job, outputs[0])
            else:
                state = 'failed' if status in ('FAILED', 'CANCELLED') else 'processing'
                await db.projects.update_one({'id': project_id, 'runwayPending.id': job['id']},
                    {'$set': {'runwayPending.$.status': state,
                              'runwayPending.$.error': 'A geração Runway falhou ou foi cancelada. Confira o painel do provedor.' if state == 'failed' else ''}})
        except Exception as exc:
            logger.warning('Runway polling/persistence failed: %s', type(exc).__name__)
            await db.projects.update_one({'id': project_id, 'runwayPending.id': job['id']},
                {'$set': {'runwayPending.$.error': str(exc) if isinstance(exc, ValueError) else 'Falha temporária ao consultar/salvar. Atualize para recuperar a mesma tarefa, sem nova cobrança de geração.'}})
        finally:
            await db.projects.update_one({'id': project_id, 'runwayPending.id': job['id']}, {'$unset': {'runwayPending.$.leaseAt': ''}})
    latest = await db.projects.find_one({'id': project_id}, {'runwayPending': 1})
    return {'videos': (latest or {}).get('runwayPending', [])}
