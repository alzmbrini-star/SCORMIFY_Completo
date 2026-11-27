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
from routes.projects_common import load_authorized_project
from services import slidekiln as sk
from services.film_exchange import usd_brl_reference
from services.asset_store import store_asset_async
from models import Project, Slide, SlideElement

router = APIRouter(tags=['SlideKiln PPT'])
_cover_lock = asyncio.Semaphore(1)


@router.get('/projects/{project_id}/slidekiln-cover')
async def course_cover(project_id: str, user=Depends(require_auth)):
    """Authorized passive derivative; never writes a course or calls SlideKiln."""
    import json
    import re
    from services.slidekiln_cover import VERSION, build_cover
    from services.asset_store import retrieve_asset_async
    project=await load_authorized_project(project_id,user)
    first=(project.get('course',{}).get('slides') or [{}])[0]
    element=next((el for el in first.get('elements',[]) if el.get('type')=='html' and el.get('source')=='slidekiln'),None)
    if not element:raise HTTPException(404,'Capa SlideKiln não disponível.')
    match=re.search(r'/api/projects/'+re.escape(project_id)+r'/assets/([a-f0-9]{32}\.sk\.html)',element.get('htmlContent') or '')
    if not match:raise HTTPException(404,'Pacote da capa não disponível.')
    folder=deps.PROJECTS_DIR/project_id/'assets'
    path=folder/match[1]
    async with _cover_lock:
        if not path.is_file():
            data,_=await retrieve_asset_async(deps.db,project_id,match[1])
            if not data:raise HTTPException(404,'Pacote convertido indisponível. Nenhuma conversão foi solicitada.')
            folder.mkdir(parents=True,exist_ok=True)
            await asyncio.to_thread(path.write_bytes,data)
            del data
        if path.stat().st_size>sk.MAX_DOCUMENT:raise HTTPException(413,'Pacote excede o limite seguro.')
        def prepare():
            digest=hashlib.sha256()
            with path.open('rb') as source:
                while block:=source.read(128*1024):digest.update(block)
            cache=folder/('_sk-cover-'+VERSION+'-'+digest.hexdigest()[:24]+'.json')
            if cache.is_file():return json.loads(cache.read_text(encoding='utf-8'))
            result=build_cover(path)
            temporary=cache.with_suffix('.'+uuid.uuid4().hex+'.tmp')
            try:
                temporary.write_text(json.dumps(result,ensure_ascii=False),encoding='utf-8')
                temporary.replace(cache)
            finally:temporary.unlink(missing_ok=True)
            return result
        try:return await asyncio.to_thread(prepare)
        except ValueError as exc:raise HTTPException(422,str(exc)) from None


def permission(user):
    if not has_any_role(user, 'editor', 'company_admin'):
        raise HTTPException(403, 'A importação requer permissão de edição.')


def owner(user):
    return str(user.get('user_id') or user.get('id'))


def bucket():
    return AsyncIOMotorGridFSBucket(deps.db, bucket_name='slidekiln_inputs')


def packages():
    return AsyncIOMotorGridFSBucket(deps.db, bucket_name='slidekiln_packages')


def public(job):
    result = {k: job.get(k) for k in ('id','status','filename','slides','budget','expiresAt','message','projectId','warnings','phase','updatedAt')}
    stale = is_stale(job)
    if stale:
        result.update(status='interrupted', message='O processamento foi interrompido. Recupere o pacote existente, sem reconverter.')
    result['canRecover'] = bool((job.get('providerJobId') or job.get('packageBlob')) and
        (stale or job.get('status') in ('unknown','failed','recoverable','interrupted')))
    return result


def is_stale(job):
    if job.get('status') not in ('processing','recovering'):
        return False
    when = job.get('updatedAt') or job.get('approvedAt')
    return bool(when and datetime.now(timezone.utc) - datetime.fromisoformat(when) > timedelta(minutes=20))


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
            'maxDocumentBytes': sk.MAX_DOCUMENT, 'approvalRequired': True, 'moduleMode': True,
            'canApprove': has_role(user, 'super_admin')}


@router.get('/ppt/slidekiln/jobs')
async def history(user=Depends(require_auth)):
    permission(user)
    cursor = deps.db.slidekiln_jobs.find({'ownerId':owner(user),'companyId':user.get('companyId')}).sort('expiresAt',-1).limit(20)
    return [public(job) async for job in cursor]


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
        'status':{'$in':['awaiting_approval','processing','recovering','unknown','recoverable']}})
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
            'message': 'Conversão autorizada. Não envie novamente.', 'phase':'starting',
            'updatedAt':datetime.now(timezone.utc).isoformat()}})
    if claim.modified_count:
        background.add_task(produce, ident)
    return public(await authorized(ident, user))


@router.get('/ppt/slidekiln/{ident}')
async def get_job(ident: str, user=Depends(require_auth)):
    job = await authorized(ident, user)
    return public(job)


@router.post('/ppt/slidekiln/{ident}/recover')
async def recover(ident: str, background: BackgroundTasks, user=Depends(require_auth)):
    job = await authorized(ident, user)
    if job.get('status') == 'completed':
        return public(job)
    if not public(job)['canRecover']:
        raise HTTPException(409, 'Não há pacote recuperável ou a importação ainda está em andamento. Nenhuma conversão foi solicitada.')
    await resolve_company_id_for_creation(user, job.get('targetCompanyId'))
    if not job.get('packageBlob') and not sk.configured():
        raise HTTPException(503, 'Chave indisponível para consultar o resultado existente; não houve nova conversão.')
    claim = await deps.db.slidekiln_jobs.update_one({'id':ident,'status':job['status'],
        'updatedAt':job.get('updatedAt')}, {'$set':{'status':'recovering','phase':'recovering',
        'updatedAt':datetime.now(timezone.utc).isoformat(),
        'message':'Recuperando o pacote já convertido. Sem nova conversão ou cobrança de conversão.'}})
    if claim.modified_count:
        background.add_task(produce,ident,True)
    return public(await authorized(ident,user))


async def progress(ident, phase, message, **extra):
    await deps.db.slidekiln_jobs.update_one({'id':ident},{'$set':{'phase':phase,'message':message,
        'updatedAt':datetime.now(timezone.utc).isoformat(),**extra}})


async def produce(ident, recovery=False):
    job = await deps.db.slidekiln_jobs.find_one({'id': ident})
    submitted = False
    try:
        if not job:
            return
        if job.get('status') == 'completed':
            return
        result = {'stats':{'warnings':job.get('warnings') or []}}
        if job.get('packageBlob'):
            stream = await packages().open_download_stream(job['packageBlob'])
            package = await stream.read()
        else:
            async with httpx.AsyncClient(timeout=120, follow_redirects=False) as client:
                provider_id = job.get('providerJobId')
                if recovery:
                    if not provider_id:
                        raise ValueError('Não há identificador do resultado anterior. Nenhuma nova conversão foi solicitada.')
                else:
                    if provider_id:
                        raise ValueError('Já existe uma chamada ao provedor; use Recuperar pacote existente.')
                    stream = await bucket().open_download_stream(job['blob'])
                    data = await stream.read()
                    if hashlib.sha256(data).hexdigest() != job['sha256']:
                        raise ValueError('Arquivo diferente do orçamento aprovado.')
                    submitted = True
                    provider_id = await sk.submit(client, data, job['filename'], ident)
                    job['providerJobId'] = provider_id
                    await progress(ident,'converting','Conversão em andamento no SlideKiln. Não envie novamente.',providerJobId=provider_id)
                for _ in range(180):
                    result = await sk.status(client, provider_id)
                    if result.get('state') == 'succeeded':
                        break
                    if result.get('state') in ('failed','expired'):
                        raise ValueError('O resultado anterior falhou ou expirou no provedor. Nenhuma nova conversão foi solicitada.')
                    await asyncio.sleep(3)
                else:
                    raise TimeoutError('O resultado não foi confirmado no prazo; consulte o acompanhamento. Não haverá reconversão automática.')
                await progress(ident,'downloading','Conversão concluída. Baixando o pacote existente para o SCORMIFY.')
                package = await sk.download(client, provider_id)
            blob = await packages().upload_from_stream(ident+'.zip',package,
                metadata={'jobId':ident,'ownerId':job['ownerId'],'companyId':job.get('companyId')})
            job['packageBlob'] = blob
            await progress(ident,'validating','Pacote salvo. Validando conteúdo e mídias.',packageBlob=blob,
                warnings=(result.get('stats') or {}).get('warnings',[]))
        await progress(ident,'importing','Preparando o novo projeto. Os cursos existentes não são alterados.')
        document = await asyncio.to_thread(sk.offline_document, package)
        # A fresh project and asset namespace; never update an existing course.
        pending_id = job.get('pendingProjectId') or str(uuid.uuid4())
        await progress(ident,'saving','Salvando o novo projeto e suas mídias.',pendingProjectId=pending_id)
        existing = await deps.db.projects.find_one({'id':pending_id})
        if existing:
            if existing.get('importJobId') != ident or existing.get('userId') != job['ownerId']:
                raise ValueError('Não foi possível confirmar o destino da recuperação. Nenhum curso existente foi modificado.')
            await progress(ident,'completed','Projeto recuperado. Abra no Editor.',status='completed',projectId=pending_id)
            return
        project = Project(id=pending_id,name=Path(job['filename']).stem)
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
        record.update({'source':'ppt','importProvider':'slidekiln','importJobId':ident,'userId':job['ownerId'],
                       'companyId':job.get('targetCompanyId'),'status':'ready'})
        await deps.db.projects.insert_one(record)
        await progress(ident,'completed','Apresentação importada como bloco interativo. Revise no Editor.',
            status='completed',projectId=project.id,warnings=project.course.conversionReport['warnings'])
    except Exception as exc:
        # Do not expose signed URLs, job capability identifiers, keys, or provider response bodies.
        message = str(exc) if isinstance(exc, (ValueError, TimeoutError)) else 'Não foi possível confirmar a importação. Confira o histórico SlideKiln antes de autorizar outra chamada.'
        await progress(ident,'attention',message[:500],
            status='recoverable' if job.get('providerJobId') or job.get('packageBlob') else ('unknown' if submitted else 'failed'))
    finally:
        if job and not recovery:
            try:
                await bucket().delete(job['blob'])
            except Exception:
                pass
