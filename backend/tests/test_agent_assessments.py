import asyncio
import copy
from unittest.mock import AsyncMock
import pytest
from services.agent_assessments import plan_assessments, media_options, generate_assessment, apply_media_assessments


def source():
    return {'id':'lesson','type':'content','title':'Procedimento da fonte','sourceExcerpt':'Explicação original com os critérios de execução.','elements':[{'type':'text','content':'Critérios ensinados'}]}


def answer(count=3):
    return {'title':'Avaliação contextual','instructions':'Responda com base no conteúdo ensinado.', 'questions':[
        {'title':'Questão '+str(i),'prompt':'Qual critério observar antes de iniciar?','options':['Verificar os requisitos','Ignorar os requisitos'], 'correct':0,'explanation':'A execução depende dos requisitos apresentados.'} for i in range(count)]}


def test_opt_in_adds_one_per_module_and_preserves_all_source_slides():
    lesson=source(); capture={'id':'capture','type':'content','sourceImageOnly':True,'sourceImage':{'filename':'original.png'}}
    structure={'modules':[{'title':'Unidade','slides':[lesson,capture,{'type':'summary','title':'Resumo'}]}]}
    original=copy.deepcopy(structure)
    assert plan_assessments(copy.deepcopy(structure),{})==original
    result=plan_assessments(structure,{'enabledResources':{'interactive_assessment':True},'assessmentQuestionCount':4})
    slides=result['modules'][0]['slides']
    assert slides[:2]==original['modules'][0]['slides'][:2]
    assert slides[2]['assessmentRequest']=={'questionCount':4,'images':True}
    assert slides[-1]['type']=='summary'
    assert len(plan_assessments(result,{'enabledResources':{'interactive_assessment':True}})['modules'][0]['slides'])==4


@pytest.mark.parametrize('count',[0,11,True,2.5,'3'])
def test_media_validation(count):
    with pytest.raises(ValueError):media_options({}, {'interactiveAssessment':{'enabled':True,'questionCount':count}})


def test_generated_questions_are_canonical_and_do_not_install_guided_host():
    request={**source(),'assessmentRequest':{'questionCount':2,'images':True}}
    ask=AsyncMock(return_value=answer(2))
    spec=asyncio.run(generate_assessment(request,'Fonte completa',ask))
    assert len(spec['questions'])==2
    assert spec['questions'][0]['options'][0]['isCorrect'] is True
    assert 'Fonte completa' in ask.call_args.args[1]
    from services.agent_assessments import render_assessment
    element=render_assessment(spec)
    assert element['agentAssessment']['imagesEnabled']
    assert 'guidedActivity' not in element
    assert 'guidedPath' not in element['assessmentConfig']
    assert 'assessment-data' in element['htmlContent']


def test_media_appends_without_replacing_original_image_and_keeps_all_slides():
    originals=[{'id':'a','elements':[{'type':'image','src':'original.png'}],'backgroundImage':'screenshot.png'}, {'id':'b','elements':[]}]
    before=copy.deepcopy(originals)
    result=asyncio.run(apply_media_assessments(originals,[source(),{'type':'summary'}],{'0':{'type':'youtube','url':'preserved','interactiveAssessment':{'enabled':True,'questionCount':2,'images':False}}},AsyncMock(return_value=answer(2))))
    assert len(result)==3 and result[0]=={**before[0],'order':0}
    assert result[2]['id']=='b'
    assert result[1]['backgroundImage'] is None
    assert result[1]['elements'][0]['agentAssessment']=={'imagesEnabled':False}


def test_conversion_only_replaces_explicit_quiz_and_never_resamples_bank():
    ask=AsyncMock(return_value=answer(1))
    result=asyncio.run(apply_media_assessments([{'id':'quiz','elements':[]}],[{**source(),'type':'quiz'}],{'0':{'interactiveAssessment':{'enabled':True,'questionCount':1,'images':True}}},ask))
    assert len(result)==1 and result[0]['contentType']=='interactive_assessment'


def test_mismatched_slide_counts_fail_instead_of_discarding_content():
    with pytest.raises(ValueError):asyncio.run(apply_media_assessments([{},{}],[source()],{},AsyncMock()))


def test_images_persist_in_bank_and_failures_preserve_questions(monkeypatch):
    from services.guided_path import populate_assessments
    from services.agent_assessments import render_assessment
    spec=asyncio.run(generate_assessment({**source(),'assessmentRequest':{'questionCount':2,'images':True}},'Fonte',AsyncMock(return_value=answer(2))))
    course={'slides':[{'elements':[render_assessment(spec)]}]}
    db=type('DB',(),{'assessment_questions':type('Bank',(),{'find_one':AsyncMock(return_value=None),'update_one':AsyncMock()})()})()
    image=AsyncMock(side_effect=[{'kind':'image','url':'/api/projects/p/assets/one.png'},ValueError('indisponível')])
    monkeypatch.setattr('services.assessment_images.create_support_image',image)
    status=asyncio.run(populate_assessments(course,{'id':'p','companyId':'c','userId':'u'},db,'.'))
    assert status=={'total':2,'ready':1,'failed':1}
    questions=course['slides'][0]['elements'][0]['assessmentConfig']['questions']
    assert len(questions)==2 and questions[0]['media']['url'].endswith('one.png')
    assert db.assessment_questions.update_one.await_count==2
    assert '_agentImagesEnabled' not in questions[0]
    record=db.assessment_questions.update_one.await_args.args[1]['$set']
    assert record['companyId']=='c' and record['createdBy']=='u'


def test_tutor_describes_both_agent_entry_points():
    from services.creator_guide import topics_for
    topic=next(t for t in topics_for({'role':'super_admin'}) if t['id']=='assessment')
    content=' '.join(topic['steps'])
    for value in ['Recursos Pedagógicos','Mídia','Banco','biblioteca','créditos','HTML/SCORM']:
        assert value in content


def test_compiler_preserves_cover_journey_source_and_summary_without_extra_ai(monkeypatch,tmp_path):
    from services import ai_agent
    request={**source(),'type':'interactive_assessment','assessmentRequest':{'questionCount':2,'images':False}}
    spec=asyncio.run(generate_assessment(request,'Fonte completa',AsyncMock(return_value=answer(2))))
    storyboard={'slides':[{'id':'cover','type':'title','title':'Curso'},
        {**source(),'moduleName':'Unidade'},
        {**request,'assessmentActivity':spec,'moduleName':'Unidade'},
        {'id':'summary','type':'summary','title':'Conclusão','elements':[{'type':'text','content':'Resumo original'}]}]}
    monkeypatch.setattr(ai_agent,'_new_chat',lambda *a,**k:pytest.fail('No paid calls in compilation of an approved assessment'))
    result=asyncio.run(ai_agent.generate_course_from_storyboard('test',storyboard,{'title':'Curso'},str(tmp_path),'p',media_config={str(i):{'type':'none'} for i in range(4)}))
    assert len(result['slides'])==5 # four authored slides plus automatic course journey
    assert result['slides'][-1]['title']=='Conclusão'
    assert sum(bool(e.get('assessmentConfig')) for s in result['slides'] for e in s['elements'])==1
    assert not result['quizQuestions']
    assert 'guidedPath' not in result['metadata']


def test_config_rejects_excessive_questions_before_generation():
    from routes.agent import AgentConfigUpdate
    from pydantic import ValidationError
    with pytest.raises(ValidationError):AgentConfigUpdate(assessmentQuestionCount=11)
