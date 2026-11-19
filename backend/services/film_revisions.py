"""Insert-only revision copies. No AI/provider calls and no writes to the source."""
import copy
import re
import uuid
from services.educational_film import normalized_board,revision,media_keys
from services.film_worker import operation_signature

def revision_copy(source,owner,request_id,created):
    if source['status'] not in ('draft','storyboard_approved','budget_approved','completed','failed'):
        raise ValueError('Aguarde a preparação/produção terminar ou esclareça envios não confirmados antes de copiar.')
    if any(o.get('status') in ('sending','unknown','submitted') for o in source.get('operations',{}).values()):
        raise ValueError('Há envio não confirmado ou tarefa pendente no original. Nenhuma tarefa paga será copiada ou repetida.')
    ident=str(uuid.uuid5(uuid.NAMESPACE_URL,f'film-review:{owner}:{source["id"]}:{request_id}'))
    board=normalized_board(copy.deepcopy(source['board']))
    suffix=' — revisão '+ident[:6]
    board['title']=board['title'][:160-len(suffix)]+suffix
    result={'id':ident,'projectId':str(uuid.uuid5(uuid.NAMESPACE_URL,'workspace:'+ident)),
        'slideId':str(uuid.uuid5(uuid.NAMESPACE_URL,'slide:'+ident)),
        'sourceProjectId':source.get('sourceProjectId'),'ownerId':owner,'companyId':source.get('companyId'),
        'board':board,'revision':revision(board),'status':'draft','storyboardApproval':None,'budgetApproval':None,
        'operations':{},'createdAt':created,'updatedAt':created,'revisionOfFilmId':source['id'],
        'revisionOfTitle':source['board']['title'],'sourceRevision':source['revision'],
        'rootFilmId':source.get('rootFilmId') or source['id']}
    for key in ('sourceText','sourceName','sourceWarning','planningReview'):
        if key in source:result[key]=copy.deepcopy(source[key])
    # The title alone does not change educational coverage; bind the copied report to this snapshot.
    if result.get('planningReview') and result['planningReview'].get('revision')==source['revision']:
        result['planningReview']['revision']=result['revision']
    return result

async def copy_compatible_media(database,source,target):
    """Copy persisted ready binaries sequentially into the NEW project namespace."""
    missing=0
    for key in media_keys(target['board']):
        op=source.get('operations',{}).get(key) or {}
        if op.get('status')!='ready' or op.get('signature')!=operation_signature(target['board'],key):continue
        filename=op.get('filename','')
        if not re.fullmatch(r'[A-Za-z0-9_.-]{1,240}',filename) or filename in ('.','..'):
            missing+=1;continue
        asset=await database.project_assets.find_one({'project_id':source['projectId'],'filename':filename},
            {'_id':0,'data':1,'content_type':1})
        if not asset or not isinstance(asset.get('data'),str) or not asset['data']:
            missing+=1;continue
        await database.project_assets.update_one({'_id':f'film-review-asset:{target["projectId"]}:{filename}'},
            {'$setOnInsert':{'project_id':target['projectId'],'filename':filename,'data':asset['data'],
                'content_type':asset.get('content_type','application/octet-stream')}},upsert=True)
        # Never inherit task IDs, approval tokens, uncertain submissions or final film URLs.
        target['operations'][key]={'status':'ready','signature':op['signature'],'filename':filename,
            'kind':op.get('kind',''),'url':f'/api/projects/{target["projectId"]}/assets/{filename}',
            'reusedFromFilmId':source['id']}
    target['reuseNotice']=(f'{len(target["operations"])} mídias prontas compatíveis copiadas para esta revisão. '
        'Editar conteúdo pode invalidar parte do reaproveitamento; confira o novo orçamento.')
    if missing:target['reuseNotice']+=f' {missing} mídias prontas não estavam disponíveis e não foram reaproveitadas.'
    return target
