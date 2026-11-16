"""Two explicit formats: native quiz versus canonical illustrated assessment."""
import copy
import uuid
import re

FORMAT_VERSION=2

def canonical_element(slide):
    return next((e for e in slide.get('elements',[]) if isinstance(e,dict) and isinstance(e.get('assessmentConfig'),dict)),None)

def native_quiz(spec):
    questions=[]
    for source in spec['questions']:
        questions.append({'id':'quiz_'+uuid.uuid4().hex,'type':'multiple_choice','text':source['prompt'],
            'alternatives':[{'id':uuid.uuid4().hex,'text':o['text'],'isCorrect':o.get('isCorrect',False)} for o in source['options']],
            'explanation':source.get('explanation',''),'points':source.get('points',1),'tags':[source.get('category','')]})
    config={'id':'quiz_'+uuid.uuid4().hex,'title':spec['title'],'questionIds':[q['id'] for q in questions],
        'questionCount':len(questions),'shuffleQuestions':True,'shuffleAlternatives':True,
        'showFeedback':True,'showExplanation':True,'passingScore':70,'maxAttempts':0}
    element={'id':uuid.uuid4().hex,'type':'quiz','x':120,'y':140,'width':1680,'height':620,'quizConfig':config}
    return element,questions

def migrate_preview(previous):
    """Old mislabeled canonical quizzes remain canonical; never convert their questions."""
    out=copy.deepcopy(previous or {})
    for slide in out.get('newSlides',[]):
        e=canonical_element(slide)
        if e and slide.get('type')=='quiz':
            slide['type']='interactive_assessment';slide.pop('requestSignature',None)
        if e and slide.get('type')=='interactive_assessment':
            e.setdefault('agentAssessment',{})['imagesEnabled']=True
            slide['title']=re.sub(r'^Quiz\s*[:—-]\s*','Avaliação interativa: ',str(slide.get('title','')),flags=re.I)
    return out

def migrate_analysis(result):
    out=copy.deepcopy(result)
    visual=out.get('visualAnalysis') or {}
    if visual and visual.get('assessmentFormatsVersion',1)<FORMAT_VERSION:
        for item in [*out.get('improvements',[]),*(i for row in visual.get('slides',[]) for i in row.get('improvements',[]))]:
            if item.get('type')=='quiz':item['type']='interactive_assessment'
        visual['assessmentFormatsVersion']=FORMAT_VERSION
    return out

def image_counts(result):
    total=ready=failed=0
    for slide in result.get('newSlides',[]):
        if slide.get('type')!='interactive_assessment':continue
        element=canonical_element(slide)
        for question in (element or {}).get('assessmentConfig',{}).get('questions',[]):
            total+=1
            if (question.get('media') or {}).get('url'):ready+=1
            elif question.get('imageGenerationStatus')=='failed':failed+=1
    return {'total':total,'ready':ready,'failed':failed,'pending':total-ready-failed}
