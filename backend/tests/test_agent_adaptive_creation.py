import copy
from unittest.mock import AsyncMock
import pytest
from services.adaptive_assessment import validate_generated_levels
from services.agent_assessments import plan_assessments, generate_assessment, media_options, render_assessment, apply_media_assessments
from services.guided_path import settings, generate_activity, activity_element
from services.ai_agent import generate_course_from_storyboard

def answer():
    return {'title':'Avaliação','instructions':'Responda conforme a fonte.','questions':[
        {'title':f'Nível {n}','prompt':f'Questão {n} sobre o procedimento?', 'options':['Verificar','Ignorar'],'correct':0,
         'difficulty':n,'learningObjective':'Procedimento','reinforcement':'Observe os critérios antes de executar.','explanation':'Verificar atende aos critérios da fonte.'} for n in (1,2,3)]}

def test_initial_contract_is_opt_in_and_rejects_fake_levels():
    from routes.agent import AgentConfigUpdate
    assert AgentConfigUpdate().adaptiveAssessments is False
    assert AgentConfigUpdate(adaptiveAssessments=True).adaptiveAssessments
    with pytest.raises(ValueError):AgentConfigUpdate(adaptiveAssessments='yes')
    valid=answer()['questions'];before=copy.deepcopy(valid)
    validate_generated_levels(valid,True);assert valid==before
    with pytest.raises(ValueError):validate_generated_levels([{**q,'difficulty':2} for q in valid],True)
    with pytest.raises(ValueError):validate_generated_levels([{**q,'reinforcement':''} for q in valid],True)
    validate_generated_levels([{}],False)
    assert media_options({'type':'quiz','adaptiveMode':True},{})=={'enabled':False,'questionCount':3,'images':True,'adaptiveMode':True}
    assert media_options({'type':'content','adaptiveMode':True},{})['enabled'] is False

@pytest.mark.asyncio
async def test_image_plan_storyboard_media_and_final_keep_opt_in_and_originals():
    source={'id':'lesson','type':'content','title':'Ensino','sourceExcerpt':'Verificar os critérios.'}
    original={'modules':[{'title':'Módulo','slides':[source]}]};before=copy.deepcopy(original)
    config={'adaptiveAssessments':True,'enabledResources':{'interactive_assessment':True}}
    planned=plan_assessments(copy.deepcopy(original),config)
    assert original==before
    request=planned['modules'][0]['slides'][1];assert request['assessmentRequest']['adaptiveMode']
    ask=AsyncMock(return_value=answer());spec=await generate_assessment(request,'Fonte',ask)
    assert 'AVALIAÇÃO ADAPTATIVA ATIVADA' in ask.call_args.args[1]
    assert spec['adaptiveMode'];assert [q['difficulty'] for q in spec['questions']]==[1,2,3]
    assert media_options(request,{})['adaptiveMode']
    sb={**request,'assessmentActivity':spec};snapshot=copy.deepcopy(sb)
    slides=await apply_media_assessments([{'id':'new','elements':[]}],[sb],{},ask)
    assert sb==snapshot
    element=slides[0]['elements'][0]
    assert element['assessmentConfig']['adaptiveMode']
    assert [q['difficulty'] for q in element['assessmentConfig']['questions']]==[1,2,3]
    assert media_options(request,{'interactiveAssessment':{'enabled':True,'questionCount':3,'adaptiveMode':False}})['adaptiveMode'] is False

@pytest.mark.asyncio
async def test_guided_mode_validates_levels_retries_only_invalid_candidate():
    path={**settings({'adaptiveAssessments':True}),'units':[{'id':'u','title':'Unidade'}]}
    request={'id':'new','title':'Teste','guidedRequest':'assessment','guidedUnitId':'u'}
    invalid=answer();invalid['questions'][0]['difficulty']=2
    ask=AsyncMock(side_effect=[invalid,answer()]);spec=await generate_activity(request,path,'Fonte',ask)
    assert ask.await_count==2
    assert activity_element(spec)['assessmentConfig']['adaptiveMode']
    bad=AsyncMock(return_value=invalid)
    with pytest.raises(ValueError):await generate_activity(request,path,'Fonte',bad)
    with pytest.raises(ValueError):settings({'adaptiveAssessments':True,'guidedQuestionsPerUnit':1})

@pytest.mark.asyncio
async def test_native_course_keeps_questions_levels_and_original_snapshot_without_conversion():
    questions=[{'text':q['prompt'],'type':'multiple_choice','alternatives':[{'text':'Verificar','isCorrect':True},{'text':'Ignorar','isCorrect':False}],
        **{k:q[k] for k in ('difficulty','learningObjective','reinforcement','explanation')}} for q in answer()['questions']]
    storyboard={'slides':[{'id':'quiz','type':'quiz','adaptiveMode':True,'title':'Teste','moduleName':'Módulo','quizQuestions':questions}]}
    before=copy.deepcopy(storyboard)
    result=await generate_course_from_storyboard('test',storyboard,{'title':'Novo curso','adaptiveAssessments':True},project_id='isolated-test',media_config={'0':{'type':'none'}})
    assert storyboard==before
    native=next(e for s in result['slides'] for e in s['elements'] if e['type']=='quiz')
    assert native['quizConfig']['adaptiveMode'] and native['quizConfig']['questionCount']==3
    assert [q['difficulty'] for q in result['quizQuestions']]==[1,2,3]
    assert all(q['reinforcement'] for q in result['quizQuestions'])
    assert not any(e.get('assessmentConfig') for s in result['slides'] for e in s['elements'])
