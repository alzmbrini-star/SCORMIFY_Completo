"""Opt-in slide-based guided learning. No topic-specific templates or execution of generated JS."""
import copy
import hashlib
import html
import json
import uuid
import asyncio
from datetime import datetime, timezone
from pathlib import Path

MODE = 'guided_practice_project'
ASSETS = Path(__file__).parent / 'export_assets'


def settings(config):
    def number(name, default, minimum, maximum):
        value = config.get(name, default)
        if isinstance(value, bool):
            raise ValueError('Configuração numérica inválida para o percurso.')
        try: value = int(value)
        except (TypeError, ValueError): raise ValueError('Configuração numérica inválida para o percurso.')
        if not minimum <= value <= maximum:
            raise ValueError(f'{name}: escolha um valor entre {minimum} e {maximum}.')
        return value
    return {'version': 1, 'unitPassingScore': number('guidedUnitPassingScore', 100, 0, 100),
            'passingScore': number('guidedPassingScore', 80, 0, 100),
            'questionsPerUnit': number('guidedQuestionsPerUnit', 3, 1, 10),
            'finalQuestionCount': number('guidedFinalQuestionCount', 12, 3, 100),
            'projectRequired': config.get('guidedProjectRequired', True) is not False,
            'assessmentImages': config.get('guidedAssessmentImages', True) is not False,
            'confirmReading': config.get('guidedConfirmReading', True) is not False}


def plan_guided_path(structure, config):
    """Add stages without changing a source lesson or replacing an original figure."""
    result = copy.deepcopy(structure)
    if result.get('guidedPath', {}).get('version') == 1:
        return result
    cfg = settings(config); units = []
    for module in result.get('modules', []):
        slides = module.get('slides', [])
        teaching = [s for s in slides if s.get('type') not in ('title', 'cover', 'summary', 'quiz') and not s.get('isComplement') and not s.get('sourceImageOnly')]
        if not teaching:
            teaching=[s for s in slides if s.get('type') not in ('title','cover','summary') and not s.get('isComplement')]
        if not teaching:
            continue
        unit_id = 'unit_' + uuid.uuid4().hex[:12]
        unit = {'id': unit_id, 'title': module.get('title') or teaching[0].get('title', 'Unidade'),
                'objective': module.get('description') or teaching[0].get('purpose', '')}
        units.append(unit)
        context = '\n\n'.join(s.get('sourceExcerpt') or s.get('purpose') or s.get('title', '') for s in teaching)
        for slide in slides:
            if slide.get('type') in ('title','cover','summary'):
                continue
            slide['guidedUnitId'] = unit_id
            slide['guidedStage'] = 'explore' if slide.get('sourceImageOnly') else ('learn' if slide in teaching else 'reinforcement')
        def stage(kind, title, purpose):
            return {'id': 'guided_' + uuid.uuid4().hex[:16], 'type': 'guided_activity', 'title': title,
                    'purpose': purpose, 'guidedUnitId': unit_id, 'guidedStage': kind,
                    'sourceExcerpt': context, 'guidedRequest': kind, 'estimatedDuration': 120}
        extra = []
        if not any(s.get('guidedStage') == 'explore' for s in slides):
            observation = stage('explore', 'Exploração visual — '+unit['title'],
                'Explicar um exemplo concreto do assunto, destacando três pontos de observação. Propor imagem contextual em Mídia; não inventar uma captura de interface.')
            observation.update(type='content'); observation.pop('guidedRequest')
            extra.append(observation)
        extra.append(stage('practice', 'Prática orientada — '+unit['title'],
                           'Praticar o assunto em caso fictício, com feedback e cartões de revisão. Não alterar sistemas reais.'))
        extra.append(stage('assessment', 'Avaliação interativa — '+unit['title'],
                           'Avaliação interativa com imagens de apoio relativas às questões. Não usar o Quiz tradicional.'))
        # Retain pre-existing resources as reinforcement; this mode's mastery
        # checks use the canonical interactive-assessment player below.
        for slide in slides:
            if slide.get('type') == 'quiz':
                slide.update(type='guided_activity', title='Avaliação interativa — '+unit['title'], guidedRequest='assessment', guidedStage='assessment', sourceExcerpt=context)
        if any(s.get('guidedStage')=='assessment' for s in slides):
            extra = [s for s in extra if s['guidedStage']!='assessment']
        conclusion = [s for s in slides if s.get('type')=='summary']
        assessments=[s for s in slides if s.get('guidedStage')=='assessment']
        module['slides'] = [s for s in slides if s not in conclusion and s not in assessments] + extra + assessments + conclusion
    if not units:
        raise ValueError('O percurso precisa de pelo menos uma unidade com conteúdo de ensino.')
    if len(units)>100:
        raise ValueError('Divida o material: o percurso suporta até 100 unidades por curso.')
    cfg['finalQuestionCount'] = max(cfg['finalQuestionCount'], len(units))
    cfg.update(id='path_'+uuid.uuid4().hex[:16], units=units,
               caseBrief='Caso aplicado de '+str(config.get('title') or result.get('title') or units[0]['title'])+'. '+
                   units[0]['objective']+'. O aprendiz prepara um plano de aplicação do conteúdo nas unidades seguintes. Use este contexto comum, sem inventar regras não documentadas; adapte o exemplo à fonte e declare que é fictício.')
    last = result['modules'][-1]
    conclusions = [s for m in result['modules'] for s in m['slides'] if s.get('type')=='summary']
    for module in result['modules']:
        module['slides']=[s for s in module['slides'] if s.get('type')!='summary']
    for kind,title,purpose in [('project','Projeto integrador','Aplicar as aprendizagens de todas as unidades em entregas com critérios explícitos de autoverificação.'),
                               ('final','Avaliação interativa final','Avaliar a compreensão de todas as unidades, usando o player de Avaliações interativas com imagens de apoio.')]:
        last['slides'].append({'id':'guided_'+uuid.uuid4().hex[:16], 'type':'guided_activity','guidedStage':kind,
            'guidedRequest':kind,'title':title,'purpose':purpose,'estimatedDuration':180})
    last['slides'].extend(conclusions)
    result['guidedPath']=cfg
    result['totalSlides']=sum(len(m['slides']) for m in result['modules'])
    return result


def text(value, limit=1600):
    if not isinstance(value,str) or not value.strip() or len(value)>limit:
        raise ValueError('Desenvolva os textos do recurso dentro dos limites informados.')
    return value.strip()


def validate_activity(raw, request, path):
    """Finite data only; never accepts HTML, formulas, code, URLs or new API calls."""
    if not isinstance(raw,dict): raise ValueError('Recurso didático ausente.')
    kind=request['guidedRequest']
    out={'version':1,'id':request['id'],'kind':kind,'title':text(raw.get('title') or request['title'],240),
         'instructions':text(raw.get('instructions'),1200)}
    unit_ids={u['id'] for u in path['units']}
    if kind in ('assessment','final'):
        questions=raw.get('questions')
        count=path['finalQuestionCount'] if kind=='final' else path['questionsPerUnit']
        if not isinstance(questions,list) or len(questions)!=count: raise ValueError(f'A avaliação requer {count} questões contextualizadas.')
        result=[]
        for i,q in enumerate(questions):
            if not isinstance(q,dict): raise ValueError('Questão inválida.')
            unit=q.get('unitId') if kind=='final' else request['guidedUnitId']
            if unit not in unit_ids: raise ValueError('Associe a questão a uma unidade existente.')
            options=q.get('options'); correct=q.get('correct')
            if not isinstance(options,list) or not 2<=len(options)<=6 or type(correct) is not int or not 0<=correct<len(options): raise ValueError('Alternativas ou resposta correta inválidas.')
            result.append({'id':request['id']+'_q'+str(i+1),'type':'single_choice','title':text(q.get('title') or q.get('prompt'),240),
                'prompt':text(q.get('prompt'),1200),'category':next(u['title'] for u in path['units'] if u['id']==unit),
                'unitId':unit,'instructions':'Selecione a alternativa correta.','explanation':text(q.get('explanation'),1200),
                'points':1,'media':None,'options':[{'id':'op_'+str(j),'text':text(v,600),'isCorrect':j==correct} for j,v in enumerate(options)],
                'imageGenerationStatus':'pending' if path['assessmentImages'] else 'disabled'})
        if kind=='final' and {q['unitId'] for q in result}!=unit_ids: raise ValueError('A avaliação final deve contemplar todas as unidades.')
        out['questions']=result
    elif kind=='project':
        deliveries=raw.get('deliverables')
        if not isinstance(deliveries,list) or not 1<=len(deliveries)<=12: raise ValueError('O projeto precisa de uma a doze entregas.')
        out['deliverables']=[]; covered=set()
        for d in deliveries:
            refs=d.get('unitIds',[])
            if not isinstance(refs,list) or not refs or any(u not in unit_ids for u in refs): raise ValueError('Relacione cada entrega às unidades estudadas.')
            covered.update(refs)
            out['deliverables'].append({'title':text(d.get('title'),240),'prompt':text(d.get('prompt')),'criterion':text(d.get('criterion'),800),'unitIds':refs})
        if covered!=unit_ids: raise ValueError('O projeto precisa contemplar todas as unidades.')
        out['minChars']=60
    elif kind=='practice':
        activity=raw.get('activity') or {}; typ=activity.get('type')
        if typ not in ('classification','ordering','decision','calculator','matrix'): raise ValueError('Escolha uma prática de classificação, ordenação, decisões, cálculo ou matriz.')
        out['cards']=[{'front':text(c.get('front'),400),'back':text(c.get('back'),1000)} for c in (raw.get('cards') or [])]
        if not 2<=len(out['cards'])<=6: raise ValueError('Inclua de dois a seis cartões de revisão.')
        a={'type':typ,'feedback':text(activity.get('feedback'),1200)}
        if typ in ('classification','matrix'):
            targets=activity.get('targets');rows=activity.get('rows')
            if not isinstance(targets,list) or not 2<=len(targets)<=6 or not isinstance(rows,list) or not 2<=len(rows)<=8: raise ValueError('Categorias e itens da prática inválidos.')
            a['targets']=[text(t,180) for t in targets];a['rows']=[]
            for r in rows:
                c=r.get('correct')
                if type(c) is not int or not 0<=c<len(targets):raise ValueError('Categoria de resposta inválida.')
                a['rows'].append({'text':text(r.get('text'),600),'correct':c})
        elif typ=='ordering':
            items=activity.get('items')
            if not isinstance(items,list) or not 3<=len(items)<=8:raise ValueError('A ordenação precisa de três a oito etapas em ordem correta.')
            a['items']=[text(t,400) for t in items]
        elif typ=='decision':
            steps=activity.get('steps')
            if not isinstance(steps,list) or not 2<=len(steps)<=5:raise ValueError('Inclua de duas a cinco decisões.')
            a['steps']=[]
            for s in steps:
                opts=s.get('options');correct=s.get('correct')
                if not isinstance(opts,list) or not 2<=len(opts)<=5 or type(correct) is not int or not 0<=correct<len(opts):raise ValueError('Decisão inválida.')
                a['steps'].append({'prompt':text(s.get('prompt'),700),'options':[text(t,400) for t in opts],'correct':correct,'feedback':text(s.get('feedback'),900)})
        else:
            rows=activity.get('rows')
            if not isinstance(rows,list) or not 2<=len(rows)<=8:raise ValueError('Inclua linhas numéricas para o cálculo didático.')
            a['unit']=text(activity.get('unit'),50);a['rows']=[]
            for r in rows:
                value=r.get('value')
                if type(value) not in (int,float) or not 0<=value<=100000 or type(r.get('accepted')) is not bool:raise ValueError('Valor ou situação do cálculo inválidos.')
                a['rows'].append({'text':text(r.get('text'),300),'value':value,'accepted':r['accepted'],'status':text(r.get('status'),100)})
        out['activity']=a
    else: raise ValueError('Etapa inválida.')
    return out


async def generate_activity(request, path, context, ask):
    schema = {
      'practice': 'cards:[{front,back}], activity: {type:classification|ordering|decision|calculator|matrix, feedback}. classification/matrix: targets:[nomes],rows:[{text,correct:indice}]; ordering:items:[etapas em ordem correta]; decision:steps:[{prompt,options:[textos],correct:indice,feedback}]; calculator:unit,rows:[{text,value:numero,accepted:boolean,status}]. Escolha só um tipo pertinente ao objetivo, sem modelos de assunto.',
      'assessment':'questions:[{title,prompt,options:[textos],correct:indice,explanation}].',
      'final':'questions:[{unitId,title,prompt,options:[textos],correct:indice,explanation}]. Ao menos uma questão por unidade.',
      'project':'deliverables:[{title,prompt,criterion,unitIds:[ids]}]. Entregas contextualizadas que juntas contemplem todas as unidades; propor autoverificação, sem prometer correção automática.'}
    count=path['finalQuestionCount'] if request['guidedRequest']=='final' else path['questionsPerUnit']
    prompt=f'''Crie um recurso para o percurso guiado de um curso em Português do Brasil.
Retorne SOMENTE JSON: {{title,instructions,{schema[request['guidedRequest']]}}}
Etapa: {request['guidedRequest']}. Quantidade de questões, se avaliação: {count}.
Unidades: {json.dumps(path['units'],ensure_ascii=False)}
Pedido: {json.dumps(request,ensure_ascii=False)}
Contexto aplicado compartilhado: {path.get('caseBrief','')}
Fonte integral pertinente: {context}
Use exemplos e casos fictícios ligados à fonte. Não invente regras do produto. Explique por que uma resposta é adequada.
Não retorne HTML, JavaScript, fórmulas executáveis ou URLs. As imagens das avaliações serão produzidas separadamente.
As avaliações usarão o player de Avaliações interativas, não Quiz tradicional. O mesmo caso aplicado deve conectar o módulo ao projeto.
'''
    error=''
    for attempt in range(2):
        try:return validate_activity(await ask(attempt,prompt+'\nCorreção necessária: '+error),request,path)
        except Exception as exc:error=str(exc)[:700]
    raise ValueError('Não foi possível preparar o recurso do percurso. '+error)


def activity_element(spec, width=1920, height=820):
    if spec['kind'] in ('assessment','final'):
        from services.assessment_renderer import assessment_element
        element=assessment_element(spec['questions'],spec['title'],False,width,height)
        element['assessmentConfig'].update(guidedPath=True,guidedActivityId=spec['id'])
        from services.assessment_renderer import refresh_assessment_documents
        refresh_assessment_documents({'course':{'slides':[{'elements':[element]}]}})
        element['id']=spec['id']
        element['guidedActivity']=spec
        return element
    payload=json.dumps(spec,ensure_ascii=False).replace('<','\\u003c')
    core=(ASSETS/'guided-core.js').read_text(encoding='utf-8')
    runtime=(ASSETS/'guided-activity.js').read_text(encoding='utf-8')
    css=(ASSETS/'guided-activity.css').read_text(encoding='utf-8')
    document=f'<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>{css}</style></head><body><main id="guided-app"></main><script id="guided-data" type="application/json">{payload}</script><script>{core}\n{runtime}</script></body></html>'
    return {'id':spec['id'],'type':'html','x':0,'y':0,'width':width,'height':height,'htmlContent':document,
            'htmlDisplayMode':'fit','startTime':0,'guidedActivity':spec}


def course_plan(course):
    cfg=(course.get('metadata') or {}).get('guidedPath')
    if not isinstance(cfg,dict) or cfg.get('version')!=1:return None
    result=copy.deepcopy(cfg);result['slides']=[]
    for i,s in enumerate(course.get('slides',[])):
        stage=s.get('guidedStage')
        if not stage:continue
        activities=[e['guidedActivity'] for e in s.get('elements',[]) if isinstance(e.get('guidedActivity'),dict)]
        # The host needs IDs and project/practice data, not duplicate media or keys.
        if activities and activities[0].get('kind') in ('assessment','final'):
            questions=[{k:v for k,v in q.items() if k in ('type','prompt','options','items','targets','correctOrder','points','unitId')} for q in activities[0].get('questions',[])]
            revision=hashlib.sha256(json.dumps(questions,sort_keys=True,ensure_ascii=True).encode()).hexdigest()[:16]
            activities=[{**{k:activities[0][k] for k in ('id','kind','title')},'revision':revision}]
        result['slides'].append({'id':s['id'],'index':i,'title':s.get('title',''),'unitId':s.get('guidedUnitId'),
                                 'stage':stage,'activity':activities[0] if activities else None})
    result['title']=(course.get('metadata') or {}).get('title','Percurso guiado')
    result['fingerprint']=hashlib.sha256(json.dumps(result,sort_keys=True,ensure_ascii=True).encode()).hexdigest()[:20]
    return result


def install_guided_host(document, course, plan=None):
    plan=plan or course_plan(course)
    if not plan:return document
    data=json.dumps(plan,ensure_ascii=False).replace('<','\\u003c')
    core=(ASSETS/'guided-core.js').read_text(encoding='utf-8')
    runtime=(ASSETS/'guided-host.js').read_text(encoding='utf-8')
    css=(ASSETS/'guided-host.css').read_text(encoding='utf-8')
    return document.replace('</head>',f'<style id="guided-host-style">{css}</style><script id="guided-path-plan" type="application/json">{data}</script><script>{core}\n{runtime}</script></head>',1)


async def populate_assessments(course, project, database, projects_dir, progress=None):
    """Persist canonical questions and images. Failed art never discards questions."""
    from services.assessment_images import create_support_image
    from services.assessment_renderer import refresh_assessment_documents
    cfg=(course.get('metadata') or {}).get('guidedPath') or {}
    entries=[]
    for slide in course.get('slides',[]):
        for element in slide.get('elements',[]):
            spec=element.get('guidedActivity') or {}
            if spec.get('kind') not in ('assessment','final'): continue
            questions=(element.get('assessmentConfig') or {}).get('questions',[])
            spec['questions']=questions
            entries.extend(questions)
    lock=asyncio.Semaphore(2); done=0; failed=0
    async def prepare(question):
        nonlocal done, failed
        async with lock:
            source_id=question.get('sourceQuestionId') or question['id']
            bank_id='guided_'+hashlib.sha256((str(project['id'])+':'+source_id).encode()).hexdigest()[:32]
            question.update(id=bank_id,sourceQuestionId=source_id)
            scope={'id':bank_id,'projectId':str(project['id'])}
            previous=await database.assessment_questions.find_one(scope,{'_id':0})
            if previous and (previous.get('media') or {}).get('url'):
                question.update(media=previous['media'],imageGenerationStatus='ready')
            elif cfg.get('assessmentImages',True):
                try:
                    question['media']=await create_support_image(question,project,database,projects_dir)
                    question['imageGenerationStatus']='ready'
                    question.pop('imageGenerationError',None)
                except Exception:
                    failed+=1
                    question.update(imageGenerationStatus='failed',imageGenerationError='Imagem indisponível. A questão foi preservada; gere a imagem novamente pelo Banco no Editor.')
            else:
                question['imageGenerationStatus']='disabled'
            now=datetime.now(timezone.utc).isoformat()
            record={**question,'projectId':str(project['id']),'companyId':project.get('companyId'),
                    'createdBy':project.get('userId'),'_creatorId':project.get('userId'),'updatedAt':now}
            await database.assessment_questions.update_one(scope,{'$set':record,'$setOnInsert':{'createdAt':now}},upsert=True)
            done+=1
            if progress: await progress(done,len(entries))
    await asyncio.gather(*(prepare(q) for q in entries))
    refresh_assessment_documents({'course':course})
    course.setdefault('metadata',{})['guidedAssessmentImages']={'total':len(entries),'ready':sum(q.get('imageGenerationStatus')=='ready' for q in entries),'failed':failed}
    return course['metadata']['guidedAssessmentImages']
