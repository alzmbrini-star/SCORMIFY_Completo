"""Explicit, conservative redesign of saved courses, always into a new draft."""
import copy
import hashlib
import json
import re
import uuid
from services.astryx_agent import build_elements, compatible, TEMPLATE, safe_url
from services.astryx_appearance import normalize


def source_token(project):
    if not project:return ''
    return hashlib.sha256(json.dumps({k:project.get(k) for k in ('course','companyId','updatedAt','name')},sort_keys=True,default=str).encode()).hexdigest()


def revision_plan(project, selected, appearance):
    options=normalize(appearance)
    slides=project.get('course',{}).get('slides',[])
    ids=[s.get('id') for s in slides]
    if len(ids)!=len(set(ids)) or None in ids:
        raise ValueError('O curso possui identificação de slides incompleta; revise antes de converter.')
    if len(selected)!=len(set(selected)) or any(x not in ids for x in selected):
        raise ValueError('Selecione slides existentes, sem duplicação.')
    result=copy.deepcopy(project);rows=[]
    for index,(source,target) in enumerate(zip(slides,result['course']['slides'])):
        elements=source.get('elements',[])
        reason='';converted=None
        if not elements and not source.get('backgroundImage'):
            reason='Slide vazio.'
        elif source.get('guidedActivity') or source.get('assessmentActivity') or source.get('interactions') or source.get('hotspots') or any(
            e.get('type') not in ('text','html','image') or e.get('quizConfig') or e.get('assessmentConfig') or
            e.get('animations') or e.get('startTime',0) or any(e.get(k) for k in ('actions','action','link','hyperlink','onClick','events','interactions','trigger'))
            for e in elements):
            reason='Atividade, mídia, ação ou animação temporizada: mantida integralmente.'
        elif not compatible({**source,'sourceImageOnly':False}) or any(re.search(r'<(?:details|summary|select|textarea)\b|\bon\w+\s*=|@keyframes|\banimation\s*:',str(e.get('htmlContent') or e.get('content') or ''),re.I) for e in elements):
            reason='HTML interativo ou diagrama: mantido integralmente.'
        else:
            images=[e for e in elements if e.get('type')=='image']
            bg=source.get('backgroundImage')
            if isinstance(bg,dict):bg=bg.get('url') or bg.get('src')
            urls=[e.get('src') or e.get('url') or e.get('content') for e in images]
            if bg:urls.insert(0,bg)
            if any(not safe_url(u) for u in urls):
                reason='Imagem com endereço não suportado: mantida sem conversão.'
            else:
                import html
                blocks=[copy.deepcopy(e) for e in elements if e.get('type') in ('text','html')]
                from services.teaching_copy import visible_teaching_text
                for block in blocks:
                    raw=block.get('content') or block.get('htmlContent') or ''
                    if re.search(r'<img\b',raw,re.I) and not visible_teaching_text(raw):
                        block['content']=''
                        block['htmlContent']=raw+'<figcaption>Imagem original</figcaption>'
                # Every image is retained; do not choose one and drop the others.
                for number,url in enumerate(urls):
                    alt=images[number-(1 if bg else 0)].get('alt','') if number >= (1 if bg else 0) else source.get('title','')
                    label=html.escape(str(alt or 'Imagem original'),quote=True)
                    blocks.append({'type':'html','htmlContent':f'<figure><img src="{html.escape(url,quote=True)}" alt="{html.escape(str(alt),quote=True)}"><figcaption>{label}</figcaption></figure>'})
                candidate={**source,'sourceImageOnly':False,'elements':blocks}
                converted=build_elements(candidate,{**TEMPLATE['palette'],'astryxAppearance':options},source.get('moduleName',''))
        eligible=converted is not None
        chosen=source.get('id') in selected
        if eligible and chosen:
            for element in converted:
                element.update(width=source.get('width',1920),height=source.get('height',820))
            target['elements']=converted
            target.update(background=('#101827' if options['theme']!='light' else '#f4f7fc'),backgroundImage=None)
        rows.append({'id':source['id'],'slide':index+1,'title':source.get('title') or f'Slide {index+1}',
                     'eligible':eligible,'selected':chosen and eligible,'reason':reason or 'Texto e imagens estáticos: visual Astryx com conteúdo preservado.',
                     **({'html':converted[0]['htmlContent']} if eligible and chosen else {})})
    if selected and not any(r['selected'] for r in rows):raise ValueError('Nenhum slide selecionado é compatível. O curso não foi alterado.')
    return result,rows


def remap(value, replacements):
    if isinstance(value,dict):return {k:remap(v,replacements) for k,v in value.items()}
    if isinstance(value,list):return [remap(v,replacements) for v in value]
    if isinstance(value,str):
        for old,new in replacements.items():value=value.replace(old,new)
    return value


async def create_revision(db, project, selected, appearance, token, request_id, user_id, now, projects_dir):
    if token!=source_token(project):raise ValueError('O curso mudou. Salve e prepare outra prévia.')
    uuid.UUID(request_id)
    new_id=str(uuid.uuid5(uuid.NAMESPACE_URL,f'astryx-revision:{user_id}:{project["id"]}:{request_id}'))
    request_hash=hashlib.sha256(json.dumps({'source':token,'selected':sorted(selected),'appearance':normalize(appearance)},sort_keys=True).encode()).hexdigest()
    old=await db.projects.find_one({'id':new_id})
    if old:
        if (old.get('astryxRevision') or {}).get('requestHash')!=request_hash:
            raise ValueError('Esta solicitação já criou uma cópia com outras opções. Feche e abra a ferramenta para outra revisão.')
        return {'projectId':new_id,'name':old['name']}
    draft,rows=revision_plan(project,selected,appearance)
    if not any(r['selected'] for r in rows):raise ValueError('Selecione pelo menos um slide compatível.')
    replacements={project['id']:new_id}
    records=[]
    for collection,field in [('questions','projectId'),('assessment_questions','projectId'),('game_questions','projectId'),('scenarios','project_id')]:
        query={field:project['id']}
        # Legacy banks can contain global questions referenced by the course.
        if collection=='questions':
            refs=[q for s in project['course']['slides'] for e in s.get('elements',[]) for q in (e.get('quizConfig') or {}).get('questionIds',[])]
            query={'$or':[query,{'id':{'$in':refs}}]}
        async for record in db[collection].find(query):
            record=copy.deepcopy(record);record.pop('_id',None)
            if collection=='questions' and record.get('companyId') and record['companyId']!=project.get('companyId'):
                raise ValueError('Uma questão pertence a outra empresa. A cópia não foi publicada.')
            if record.get('id'):
                replacements[record['id']]=str(uuid.uuid5(uuid.NAMESPACE_URL,new_id+':'+collection+':'+record['id']))
            else:raise ValueError('Registro didático sem identificação; cópia não publicada.')
            records.append((collection,field,record))
    referenced={q for s in project['course']['slides'] for e in s.get('elements',[]) for q in (e.get('quizConfig') or {}).get('questionIds',[])}
    if referenced-{r['id'] for c,f,r in records if c=='questions'}:
        raise ValueError('Há perguntas do Quiz ausentes no Banco. Nenhuma cópia parcial foi publicada.')
    draft=remap(draft,replacements);draft.pop('_id',None)
    draft.update(id=new_id,name=str(project.get('name') or 'Curso')+' (Revisão Astryx)',status='draft',source='astryx_revision',userId=user_id,createdAt=now,updatedAt=now)
    draft['course'].update(id=new_id,createdAt=now,updatedAt=now)
    draft['astryxRevision']={'sourceProjectId':project['id'],'selectedSlideIds':[r['id'] for r in rows if r['selected']],'sourceFingerprint':token,'requestHash':request_hash}
    if len(json.dumps(draft,ensure_ascii=False).encode())>14*1024*1024:raise ValueError('A cópia excede 14 MB. Nenhum curso foi criado.')
    # Persist independent assets before publishing the draft. Never write source data.
    async for asset in db.project_assets.find({'project_id':project['id']}):
        asset=dict(asset);asset.pop('_id',None);asset['project_id']=new_id
        await db.project_assets.update_one({'project_id':new_id,'filename':asset['filename']},{'$setOnInsert':asset},upsert=True)
    from services.asset_store import store_asset_async
    source_dir=projects_dir/project['id']/'assets'
    if not source_dir.resolve().is_relative_to(projects_dir.resolve()):raise ValueError('Pasta de mídia inválida.')
    if source_dir.exists():
        for path in source_dir.iterdir():
            if path.is_symlink():raise ValueError('Arquivo de mídia com vínculo não suportado; cópia não publicada.')
            if path.is_file() and not await db.project_assets.find_one({'project_id':new_id,'filename':path.name}):
                if not await store_asset_async(db,new_id,path.name,str(path)):raise ValueError('Falha ao preservar uma mídia; cópia não publicada. Tente novamente.')
    from urllib.parse import unquote
    filenames=set(re.findall(r'/api/projects/'+re.escape(project['id'])+r'/assets/([^\s"\'<>?\\]+)',json.dumps(project,ensure_ascii=False)))
    for filename in filenames:
        if not await db.project_assets.find_one({'project_id':new_id,'filename':unquote(filename)}):
            raise ValueError('Uma mídia local não está disponível. Restaure-a antes de criar a cópia; original intacto.')
    for collection,field,record in records:
        record=remap(record,replacements);record[field]=new_id
        await db[collection].update_one({'id':record['id']},{'$setOnInsert':record},upsert=True)
    # Source may have changed while assets were copied. No stale revision is published.
    current=await db.projects.find_one({'id':project['id']},{'_id':0})
    if source_token(current)!=token:raise ValueError('O original mudou durante a cópia. Prepare nova prévia; o original está intacto.')
    await db.projects.update_one({'id':new_id},{'$setOnInsert':draft},upsert=True)
    return {'projectId':new_id,'name':draft['name'],'styledSlides':sum(r['selected'] for r in rows),'slidesCount':len(rows)}
