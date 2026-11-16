"""Revision-scoped partial preview recovery. Never writes a project/course."""
import asyncio
import copy
import hashlib
import json
from services.course_resource_balance import validate_selection
from services.gamma_course_analysis import additive_result


def expected_items(selections):
    return {(i['slideIndex'],i['type']):i for i in selections}


def signature(item):
    return hashlib.sha256(json.dumps({k:item.get(k) for k in ('slideIndex','type','description','suggestion')},sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def usable(slide, expected):
    if not isinstance(slide,dict):return False
    key=(slide.get('afterIndex'),slide.get('type'))
    if key not in expected:return False
    if slide.get('type')=='scenario':
        return isinstance(slide.get('scenarioConfig'),dict) and bool(slide['scenarioConfig'].get('theme'))
    elements=slide.get('elements') or []
    if slide.get('type')=='quiz':
        ids={q.get('id') for q in slide.get('nativeQuizQuestions',[]) if isinstance(q,dict)}
        return bool(ids) and any(e.get('type')=='quiz' and set((e.get('quizConfig') or {}).get('questionIds',[]))==ids for e in elements if isinstance(e,dict))
    if slide.get('type')=='interactive_assessment':
        return any(isinstance(e,dict) and isinstance(e.get('assessmentConfig'),dict) and e['assessmentConfig'].get('questions') and (e.get('htmlContent') or e.get('content')) for e in elements)
    return any(isinstance(e,dict) and str(e.get('htmlContent') or e.get('content') or '').strip() for e in elements)


def coverage(result,selections):
    from services.assessment_formats import image_counts,canonical_element
    expected=expected_items(selections)
    content={(s.get('afterIndex'),s.get('type')) for s in result.get('newSlides',[]) if usable(s,expected)}
    found=set(content)
    for s in result.get('newSlides',[]):
        if s.get('type')=='interactive_assessment':
            images=image_counts({'newSlides':[s]})
            if not images['total'] or images['ready']<images['total']:found.discard((s.get('afterIndex'),s.get('type')))
    return {'expected':len(expected),'ready':len(found),'complete':len(found)==len(expected),
            'contentReady':len(content),'images':image_counts(result),
            'missing':[{'slideIndex':i,'type':t,'description':expected[(i,t)].get('description','')} for i,t in expected if (i,t) not in found]}


async def complete_preview(project,selections,previous,generate):
    validate_selection(project,selections)
    expected=expected_items(selections)
    from services.assessment_formats import migrate_preview
    previous=migrate_preview(previous)
    retained={}
    for slide in (previous or {}).get('newSlides',[]):
        if usable(slide,expected) and slide.get('requestSignature') in (None,signature(expected[(slide['afterIndex'],slide['type'])])):
            retained[(slide['afterIndex'],slide['type'])]=copy.deepcopy(slide)
    reused=len(retained)
    semaphore=asyncio.Semaphore(2)
    async def build(key,item):
        if key in retained:return
        async with semaphore:
            for attempt in range(2):
                request=copy.deepcopy(item)
                if attempt:
                    request['generationContract']='A tentativa anterior não entregou o recurso pedido. Retorne exatamente um newSlide completo com afterIndex='+str(key[0])+' e type='+key[1]+'. Narração exige também HTML com a transcrição; cenário exige scenarioConfig.'
                try:
                    result=additive_result(await generate(request),project)
                    matches=[s for s in result.get('newSlides',[]) if usable(s,{key:item})]
                    if len(matches)==1 and len(result.get('newSlides',[]))==1:
                        retained[key]=copy.deepcopy(matches[0]);retained[key]['requestSignature']=signature(item);return
                except Exception:
                    # A partial generation never becomes an apparently complete preview.
                    continue
    await asyncio.gather(*(build(k,v) for k,v in expected.items()))
    result={'updatedSlides':[],'newSlides':[retained[k] for k in expected if k in retained]}
    info=coverage(result,selections)
    info.update(reusedCount=reused,generatedCount=len(retained)-reused)
    return result,info
