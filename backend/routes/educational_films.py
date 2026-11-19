"""Independent educational films, protected by storyboard AND budget approval."""
import asyncio
import uuid
from datetime import datetime,timezone,timedelta
from fastapi import APIRouter,Depends,HTTPException,UploadFile,File
from pydantic import BaseModel,Field
from typing import Optional
from routes.auth import require_auth,has_role
from routes.runway import can_edit,narration_allowed
from routes.deps import db,PROJECTS_DIR
from routes.projects_common import load_authorized_project,resolve_company_id_for_creation
from services.educational_film import Board,normalized_board,revision,quote,require_ready,project_shell,media_keys
from services.film_worker import run,operation_signature
from services import runway_ai,runway_narration

router=APIRouter(tags=['Educational films'])
TASKS=set()
def now():return datetime.now(timezone.utc).isoformat()

class Create(BaseModel):
    title:str=Field(min_length=3,max_length=160)
    topic:str=Field(min_length=20,max_length=12000)
    scenes:int=Field(default=6,ge=3,le=30)
    characterCount:int=Field(default=2,ge=1,le=6)
    sourceProjectId:Optional[str]=None
    companyId:Optional[str]=None
    requestId:uuid.UUID
    style:str=Field(default='2d',pattern='^(2d|3d)$')
    sourceText:str=Field(default='',max_length=100000)
    sourceName:str=Field(default='',max_length=180)
    sourceWarning:str=Field(default='',max_length=2000)

class Edit(BaseModel):
    revision:str
    board:Board

class Approval(BaseModel):
    revision:str

class BudgetApproval(Approval):
    quoteId:str
    ceilingUsd:float=Field(ge=0,le=1000,allow_inf_nan=False)
    consent:bool=False

async def authorized(film_id,user):
    can_edit(user)
    film=await db.educational_films.find_one({'id':film_id},{'_id':0})
    if not film:raise HTTPException(404,'Filme não encontrado.')
    if not has_role(user,'super_admin') and (film.get('ownerId')!=str(user.get('user_id') or user.get('id')) or film.get('companyId')!=user.get('companyId')):
        raise HTTPException(404,'Filme não encontrado.')
    await load_authorized_project(film['projectId'],user)
    return film

def view(film):
    result={k:v for k,v in film.items() if k not in ('_id','ownerId','runId')}
    try:result['quote']=quote(film)
    except ValueError:result['quote']=None
    return result

def editable(film,rev):
    if film['revision']!=rev:raise HTTPException(409,'O filme mudou em outra aba. Atualize antes de continuar.')
    if film['status'] in ('generating','planning','unknown','completed'):
        raise HTTPException(409,'Este filme está em processamento, concluído ou tem envio não confirmado. Não será modificado nem repetido automaticamente.')

@router.get('/films/config')
async def config(user=Depends(require_auth)):
    can_edit(user)
    return {'runway':runway_ai.configured(),'narration':runway_narration.available() and narration_allowed(user),
            'mediaTools':bool(all(runway_narration.media_tools())),'ratesVersion':'2026-11-18-v1'}

@router.post('/films/extract-document')
async def extract_document(file:UploadFile=File(...),user=Depends(require_auth)):
    can_edit(user)
    from services.gamma_documents import MAX_FILE,DocumentError,extract_document as extract
    try:
        raw=await file.read(MAX_FILE+1)
        result=await asyncio.to_thread(extract,file.filename or '',raw)
        result['warning']=result['warning'].replace('Gamma','IA')
        if (file.filename or '').lower().endswith('.pptx'):
            result['warning']+=' Notas do apresentador não são extraídas nesta opção; acrescente-as manualmente no texto revisado se forem importantes.'
        return result
    except DocumentError as exc:
        raise HTTPException(422,str(exc).replace('Gamma','IA')) from None
    finally:await file.close()

@router.get('/films')
async def history(sourceProjectId:Optional[str]=None,user=Depends(require_auth)):
    can_edit(user)
    query={} if has_role(user,'super_admin') else {'ownerId':str(user.get('user_id') or user.get('id')),'companyId':user.get('companyId')}
    if sourceProjectId:
        await load_authorized_project(sourceProjectId,user);query['sourceProjectId']=sourceProjectId
    films=await db.educational_films.find(query,{'_id':0,'id':1,'board.title':1,'status':1,'updatedAt':1,'projectId':1}).sort('updatedAt',-1).limit(50).to_list(50)
    return {'films':films}

@router.post('/films')
async def create(body:Create,user=Depends(require_auth)):
    can_edit(user);owner=str(user.get('user_id') or user.get('id'))
    source=await load_authorized_project(body.sourceProjectId,user) if body.sourceProjectId else None
    company=source.get('companyId') if source else await resolve_company_id_for_creation(user,body.companyId)
    ident=str(uuid.uuid5(uuid.NAMESPACE_URL,f'film:{owner}:{body.requestId}'))
    existing=await db.educational_films.find_one({'id':ident},{'_id':0})
    if existing:return view(await authorized(ident,user))
    board=normalized_board({'title':body.title,'topic':body.topic,'style':body.style,'characters':[
        {'name':f'Personagem {i+1}','description':'Defina aparência, roupa e personalidade deste personagem.'} for i in range(body.characterCount)],
        'scenes':[{'title':f'Cena {i+1}','visual':'','narration':''} for i in range(body.scenes)]})
    created=now();film={'id':ident,'projectId':str(uuid.uuid5(uuid.NAMESPACE_URL,'workspace:'+ident)),
        'slideId':str(uuid.uuid5(uuid.NAMESPACE_URL,'slide:'+ident)),'sourceProjectId':body.sourceProjectId,
        'ownerId':owner,'companyId':company,'board':board,'revision':revision(board),'status':'draft',
        'operations':{},'createdAt':created,'updatedAt':created,
        'sourceText':body.sourceText,'sourceName':body.sourceName,'sourceWarning':body.sourceWarning}
    # Deterministic insert-only IDs make a network retry safe; never upsert the source course.
    await db.projects.update_one({'_id':'film-workspace:'+ident},{'$setOnInsert':project_shell(film,owner,company,created)},upsert=True)
    await db.educational_films.update_one({'_id':'film:'+ident},{'$setOnInsert':film},upsert=True)
    return view(film)

@router.get('/films/{film_id}')
async def get(film_id:str,user=Depends(require_auth)):
    return view(await authorized(film_id,user))

@router.put('/films/{film_id}')
async def edit(film_id:str,body:Edit,user=Depends(require_auth)):
    film=await authorized(film_id,user);editable(film,body.revision)
    try:board=normalized_board(body.board.model_dump())
    except ValueError as exc:raise HTTPException(400,str(exc)) from None
    kept={}
    for key in media_keys(board):
        old=film.get('operations',{}).get(key)
        if old and old.get('signature')==operation_signature(board,key):kept[key]=old
    values={'board':board,'revision':revision(board),'status':'draft','storyboardApproval':None,'budgetApproval':None,
            'operations':kept,'error':None,'updatedAt':now()}
    done=await db.educational_films.update_one({'id':film_id,'revision':body.revision,'status':film['status']},{'$set':values})
    if not done.matched_count:raise HTTPException(409,'O filme mudou. Atualize a tela.')
    return view({**film,**values})

@router.post('/films/{film_id}/suggest-storyboard')
async def suggest(film_id:str,body:Approval,user=Depends(require_auth)):
    film=await authorized(film_id,user);editable(film,body.revision)
    if film.get('operations'):raise HTTPException(409,'Edite as cenas manualmente para preservar as mídias já produzidas.')
    claim=await db.educational_films.update_one({'id':film_id,'revision':body.revision,'status':film['status']},{'$set':{'status':'planning','updatedAt':now()}})
    if not claim.modified_count:raise HTTPException(409,'Já existe uma preparação em andamento.')
    raw=None
    try:
        from openai import AsyncOpenAI
        from services.llm_config import require_openai_api_key,openai_text_model
        import json
        from services.film_guided import STORYBOARD_SYSTEM,coverage_review,storyboard_format
        board=film['board']
        async with AsyncOpenAI(api_key=require_openai_api_key(),timeout=120,max_retries=0) as client:
            response=await client.chat.completions.create(model=openai_text_model('OPENAI_FILM_STORYBOARD_MODEL'),
                messages=[{'role':'system','content':STORYBOARD_SYSTEM},
                          {'role':'user','content':json.dumps({'topic':board['topic'],'title':board['title'],'style':board['style'],'durations':[s['duration'] for s in board['scenes']],
                            'characterCount':len(board['characters']),'document':film.get('sourceText',''),'documentName':film.get('sourceName',''),'extractionWarning':film.get('sourceWarning','')},ensure_ascii=False)}],response_format=storyboard_format(board),max_tokens=15000)
        raw=json.loads(response.choices[0].message.content)
        if len(raw.get('scenes',[]))!=len(board['scenes']):raise ValueError('A IA não devolveu todas as cenas. Revise manualmente ou solicite outra sugestão.')
        if len(raw.get('characters',[]))!=len(board['characters']):raise ValueError('A IA não devolveu o elenco solicitado. O rascunho foi preservado.')
        for old,new in zip(board['scenes'],raw['scenes']):
            new['duration']=old['duration']
            if isinstance(new.get('visibleCharacters'),list):new['visibleCharacters']=list(dict.fromkeys(new['visibleCharacters']))
        characters=[{**c,'voiceId':board['characters'][i].get('voiceId','') if i<len(board['characters']) else ''} for i,c in enumerate(raw['characters'])]
        board=normalized_board({**board,'characters':characters,'scenes':raw['scenes'],'musicPrompt':raw.get('musicPrompt',board['musicPrompt'])},True)
        values={'board':board,'revision':revision(board),'status':'draft','storyboardApproval':None,'budgetApproval':None,'error':None,'planningCandidate':None,'planningDiagnostic':None,'updatedAt':now(),
                'planningReview':coverage_review(raw,board,revision)}
        await db.educational_films.update_one({'id':film_id,'status':'planning'},{'$set':values})
        return view({**film,**values})
    except Exception as exc:
        from services.film_guided import planning_diagnostic
        diagnostic=planning_diagnostic(exc)
        import logging
        logging.getLogger(__name__).warning('Film storyboard validation: %s',diagnostic)
        candidate=raw if isinstance(raw,dict) and len(json.dumps(raw,ensure_ascii=False))<=100000 else None
        await db.educational_films.update_one({'id':film_id,'status':'planning'},{'$set':{'status':'draft','storyboardApproval':None,'budgetApproval':None,'error':'Não foi possível preparar um storyboard completo. '+diagnostic+' O rascunho foi preservado; não houve geração de mídias.',
            'planningCandidate':candidate,'planningDiagnostic':diagnostic,'updatedAt':now()}})
        raise HTTPException(502,'Não foi possível preparar o storyboard. '+diagnostic+' O rascunho foi preservado; a chamada de texto pode ter sido cobrada. Nenhuma mídia foi gerada.') from None

@router.post('/films/{film_id}/approve-storyboard')
async def approve_storyboard(film_id:str,body:Approval,user=Depends(require_auth)):
    film=await authorized(film_id,user);editable(film,body.revision)
    try:normalized_board(film['board'],True)
    except ValueError as exc:raise HTTPException(400,str(exc)) from None
    values={'storyboardApproval':body.revision,'budgetApproval':None,'status':'storyboard_approved','updatedAt':now()}
    done=await db.educational_films.update_one({'id':film_id,'revision':body.revision,'status':film['status']},{'$set':values})
    if not done.matched_count:raise HTTPException(409,'O filme mudou. Atualize a tela.')
    return view({**film,**values})

@router.post('/films/{film_id}/approve-budget')
async def approve_budget(film_id:str,body:BudgetApproval,user=Depends(require_auth)):
    film=await authorized(film_id,user);editable(film,body.revision)
    try:
        priced=quote(film)
        if not body.consent or body.quoteId!=priced['id'] or body.ceilingUsd<priced['estimatedUsd']:
            raise ValueError('Confirme o orçamento atual e um limite suficiente para as chamadas planejadas.')
    except ValueError as exc:raise HTTPException(400,str(exc)) from None
    values={'status':'budget_approved','updatedAt':now(),'budgetApproval':{'revision':body.revision,'quoteId':priced['id'],
        'ceilingUsd':body.ceilingUsd,'token':str(uuid.uuid4()),'userId':str(user.get('user_id') or user.get('id')),'at':now()}}
    done=await db.educational_films.update_one({'id':film_id,'revision':body.revision,'status':film['status']},{'$set':values})
    if not done.matched_count:raise HTTPException(409,'O filme mudou. Atualize a tela.')
    return view({**film,**values})

@router.post('/films/{film_id}/generate')
async def generate(film_id:str,body:Approval,user=Depends(require_auth)):
    film=await authorized(film_id,user)
    if film['status']!='budget_approved':raise HTTPException(409,'Aprove o storyboard e o orçamento antes de gerar mídias.')
    try:require_ready(film,body.revision)
    except ValueError as exc:raise HTTPException(400,str(exc)) from None
    approved=datetime.fromisoformat(film['budgetApproval']['at'])
    if datetime.now(timezone.utc)-approved>timedelta(hours=24):raise HTTPException(409,'A aprovação expirou. Confira e aprove o orçamento novamente.')
    if not runway_ai.configured() or not runway_narration.available() or not narration_allowed(user):
        raise HTTPException(503,'Confira Runway, ElevenLabs, vozes PT-BR, FFmpeg/FFprobe e as permissões da empresa. Nenhuma mídia foi solicitada.')
    run_id=str(uuid.uuid4());values={'status':'generating','runId':run_id,'heartbeat':now(),'error':None,'progress':'Na fila de produção','updatedAt':now()}
    claim=await db.educational_films.update_one({'id':film_id,'revision':body.revision,'status':'budget_approved',
        'budgetApproval.token':film['budgetApproval']['token']},{'$set':values})
    if not claim.modified_count:raise HTTPException(409,'Já existe uma produção para essa aprovação. Atualize o status, sem repetir o envio.')
    task=asyncio.create_task(run(film_id,run_id,db,PROJECTS_DIR));TASKS.add(task);task.add_done_callback(TASKS.discard)
    return view({**film,**values})

@router.post('/films/{film_id}/recover-interrupted')
async def interrupted(film_id:str,user=Depends(require_auth)):
    film=await authorized(film_id,user)
    stamp=datetime.fromisoformat(film.get('heartbeat') or film['updatedAt'])
    if film['status'] not in ('generating','planning') or datetime.now(timezone.utc)-stamp<timedelta(minutes=10):
        raise HTTPException(409,'A tarefa ainda pode estar ativa. Aguarde; nenhuma geração foi repetida.')
    uncertain=any(o.get('status') in ('sending','unknown') for o in film.get('operations',{}).values())
    await db.educational_films.update_one({'id':film_id,'status':film['status'],'updatedAt':film['updatedAt']},
        {'$set':{'status':'unknown' if uncertain else 'failed','error':'Execução interrompida. Resultados prontos preservados. Envios não confirmados não serão repetidos.','budgetApproval':None,'runId':None,'updatedAt':now()}})
    return view(await authorized(film_id,user))
