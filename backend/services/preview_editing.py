"""Text-only editing of preview snapshots, never authored courses or question banks."""
import copy
import hashlib
import json


def revision(slide):
    return hashlib.sha256(json.dumps(slide,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def question_bank(slide):
    if slide.get('type')=='quiz':
        return slide.get('nativeQuizQuestions',[]), 'text', 'alternatives'
    if slide.get('type')=='interactive_assessment':
        from services.assessment_formats import canonical_element
        return (canonical_element(slide) or {}).get('assessmentConfig',{}).get('questions',[]), 'prompt', 'options'
    return [], 'text', 'alternatives'


def editor_data(slide):
    questions,prompt,options=question_bank(slide)
    return {'revision':revision(slide),'title':slide.get('title',''),
        'scenario':{k:v for k,v in (slide.get('scenarioConfig') or {}).items() if k in ('theme','objectives') and isinstance(v,str)},
        'questions':[{'id':q['id'],'prompt':q.get(prompt,''),'title':q.get('title',''),
            'explanation':q.get('explanation',''),'correctOptionIds':[o['id'] for o in q.get(options,[]) if o.get('isCorrect')],
            'options':[{'id':o['id'],'text':o.get('text','')} for o in q.get(options,[])]}
            for q in questions if q.get('id') and all(o.get('id') for o in q.get(options,[]))]}


def plain(value,allow_empty=False):
    if not isinstance(value,str) or len(value)>8000 or (not allow_empty and not value.strip()):
        raise ValueError('Texto inválido: use de 1 a 8000 caracteres (explicação pode ficar vazia).')
    if '<' in value or '>' in value:
        raise ValueError('Use somente texto, sem marcação HTML.')
    return value


def edit_result(result,after_index,kind,expected_revision,changes,question_id=None):
    out=copy.deepcopy(result)
    matches=[s for s in out.get('newSlides',[]) if s.get('afterIndex')==after_index and s.get('type')==kind]
    if len(matches)!=1 or revision(matches[0])!=expected_revision:
        raise LookupError('A prévia mudou. Reabra a edição antes de salvar; o curso foi preservado.')
    slide=matches[0]
    if not isinstance(changes,dict) or not changes:
        raise ValueError('Informe os textos a corrigir.')
    if question_id is None:
        if set(changes)-{'title','scenario'}:raise ValueError('Campo de recurso não editável.')
        if 'title' in changes:
            slide['title']=plain(changes['title'])
            for element in slide.get('elements',[]):
                cfg=element.get('quizConfig') or element.get('assessmentConfig')
                if isinstance(cfg,dict):cfg['title']=slide['title']
        if 'scenario' in changes:
            script=changes['scenario']
            if kind!='scenario' or not isinstance(script,dict) or set(script)-{'theme','objectives'}:
                raise ValueError('Roteiro inválido.')
            cfg=slide.get('scenarioConfig') or {}
            for key,value in script.items():
                if not isinstance(cfg.get(key),str):raise ValueError('Campo de roteiro não editável.')
                cfg[key]=plain(value)
            slide['scenarioConfig']=cfg
    else:
        if set(changes)-{'prompt','title','explanation','options'}:raise ValueError('Campo de questão não editável.')
        bank,prompt,options=question_bank(slide)
        questions=[q for q in bank if q.get('id')==question_id]
        if len(questions)!=1:raise ValueError('Questão não encontrada na prévia.')
        q=questions[0]
        for key in ('prompt','title','explanation'):
            if key in changes:
                if key=='title' and kind!='interactive_assessment':raise ValueError('Título de questão indisponível neste formato.')
                q[prompt if key=='prompt' else key]=plain(changes[key],allow_empty=key=='explanation')
        if 'options' in changes:
            incoming=changes['options'];original=q.get(options,[])
            if (not isinstance(incoming,list) or len(incoming)!=len(original)
                or any(not isinstance(o,dict) or set(o)!={'id','text'} or not isinstance(o.get('id'),str) for o in incoming)
                or len({o['id'] for o in incoming})!=len(incoming)
                or {o['id'] for o in incoming}!={o['id'] for o in original}):
                raise ValueError('As alternativas e seus identificadores devem ser preservados.')
            texts={o['id']:plain(o['text']) for o in incoming}
            for option in original:option['text']=texts[option['id']]
    if kind=='interactive_assessment':
        from services.assessment_renderer import refresh_assessment_documents
        refresh_assessment_documents({'course':{'slides':[slide]}})
    return out
