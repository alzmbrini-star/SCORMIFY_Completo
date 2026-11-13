import asyncio
import copy
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
import pytest
from services import gamma_assessments as service
from test_gamma import routes


def job():
    return {'id':'job1','projectId':'project1','title':'Curso específico','status':'assessment','actualSlides':5,
            'interactiveAssessment':{'enabled':True,'questionCount':2,'images':True},
            'assessmentSource':'Documento revisado: primeira unidade e última unidade importante.'}


def spec():
    return {'id':'spec1','title':'Avaliação final','instructions':'Responda com base no conteúdo.',
            'imagesEnabled':True,'questions':[{'id':'q1','type':'single_choice','title':'Questão',
            'prompt':'O que aplicar na situação?', 'options':[{'id':'a','text':'Opção A','isCorrect':True},{'id':'b','text':'Opção B','isCorrect':False}],
            'explanation':'Aplicação correta.','points':1}]}


def db():
    project={'id':'project1','gammaJobId':'job1','userId':'author','companyId':'company',
             'course':{'metadata':{},'slides':[{'id':'original','notes':'Notas do autor','elements':[{'id':'interaction','type':'text','content':'Conteúdo do autor'}]}]}}
    return SimpleNamespace(projects=SimpleNamespace(find_one=AsyncMock(return_value=project), update_one=AsyncMock(return_value=SimpleNamespace(modified_count=1))),
        gamma_generations=SimpleNamespace(update_one=AsyncMock(return_value=SimpleNamespace(modified_count=1))))


def test_options_default_off_strict_bounds_and_private_source():
    import uuid
    from pydantic import ValidationError
    model=routes().Generate
    base={'requestId':uuid.uuid4(),'title':'Teste','prompt':'Fonte para gerar apresentação'}
    assert model(**base).interactiveAssessment.enabled is False
    assert model(**base,interactiveAssessment={'enabled':True,'questionCount':10,'images':True}).interactiveAssessment.questionCount==10
    for cfg in [{'enabled':'true'},{'questionCount':0},{'questionCount':11},{'questionCount':True},{'images':'false'},{'unexpected':'value'}]:
        with pytest.raises(ValidationError):model(**base,interactiveAssessment=cfg)
    public=routes().public({**job(),'assessmentSpec':spec(),'assessmentSource':'PRIVATE','assessmentLease':'lease'})
    assert 'assessmentSource' not in public and 'assessmentSpec' not in public and 'assessmentLease' not in public


@pytest.mark.asyncio
async def test_source_is_complete_and_spec_is_cached_before_images():
    database=db();original=copy.deepcopy(database.projects.find_one.return_value)
    generated=AsyncMock(return_value=spec())
    async def populate(course, project, database, directory, progress):
        assert database.gamma_generations.update_one.await_count==1  # cached spec
        assert project['userId']=='author' and project['companyId']=='company'
        assert course['slides'][0]['elements'][0]['agentAssessment']['imagesEnabled'] is True
        await progress(1,1)
        return {'ready':1,'failed':0,'total':1}
    with patch('services.agent_assessments.generate_assessment',generated),patch('services.guided_path.populate_assessments',populate):
        slide,result=await service.prepare_slide(job(),original,database,'unused')
    assert generated.call_args.args[1]==job()['assessmentSource']
    assert generated.call_args.args[0]['sourceExcerpt']==job()['assessmentSource']
    assert generated.call_args.args[3]=={'questionCount':2,'images':True}
    assert slide['elements'][0]['assessmentConfig']['questions'][0]['prompt']=='O que aplicar na situação?'
    assert slide['elements'][0]['agentAssessment']['imagesEnabled'] is True
    assert original==database.projects.find_one.return_value


@pytest.mark.asyncio
async def test_cached_questions_are_reused_no_new_question_charge():
    database=db();cached={**job(),'assessmentSpec':spec()}
    with patch('services.agent_assessments.generate_assessment',AsyncMock()) as generate,patch('services.guided_path.populate_assessments',AsyncMock(return_value={'ready':0,'failed':1})):
        await service.prepare_slide(cached,database.projects.find_one.return_value,database,'unused')
    generate.assert_not_awaited()


@pytest.mark.asyncio
async def test_worker_appends_only_and_preserves_author_edits_and_partial_art():
    database=db();before=copy.deepcopy(database.projects.find_one.return_value)
    with patch.object(service,'prepare_slide',AsyncMock(return_value=({'id':'new','elements':[]},{'ready':1,'failed':1}))):
        await service._run(database,'unused',job())
    query,update=database.projects.update_one.call_args.args
    assert query['course.metadata.gammaAssessmentJob']=={'$ne':'job1'}
    assert set(update)=={'$push','$set'} and 'course.slides' in update['$push']
    assert 'course.slides' not in update['$set'] and 'course' not in update['$set']
    assert update['$push']['course.slides']['order']==1
    assert database.projects.find_one.return_value==before
    final=database.gamma_generations.update_one.call_args.args[1]['$set']
    assert final['status']=='completed' and final['assessment.imagesFailed']==1 and final['assessment.warning']


@pytest.mark.asyncio
async def test_failure_keeps_gamma_slides_available_and_retryable():
    database=db()
    with patch.object(service,'prepare_slide',AsyncMock(side_effect=ValueError('private details'))):
        await service._run(database,'unused',job())
    database.projects.update_one.assert_not_awaited()
    final=database.gamma_generations.update_one.call_args.args[1]['$set']
    assert final['status']=='completed' and final['assessment.status']=='failed'
    assert 'private details' not in str(final)


@pytest.mark.asyncio
async def test_append_already_finished_does_not_generate_or_duplicate():
    database=db();database.projects.find_one.return_value['course']['metadata']['gammaAssessmentJob']='job1'
    with patch.object(service,'prepare_slide',AsyncMock()) as prepare:
        await service._run(database,'unused',job())
    prepare.assert_not_awaited();database.projects.update_one.assert_not_awaited()


@pytest.mark.asyncio
async def test_lease_prevents_parallel_paid_work_and_expired_lease_needs_confirmation():
    database=db();database.gamma_generations.update_one.return_value=SimpleNamespace(modified_count=0)
    with patch.object(service,'_run',AsyncMock()) as work:
        await service.start_queued(database,'unused',job())
        await service.start_queued(database,'unused',{**job(),'assessmentLease':'2000-01-01'})
    work.assert_not_awaited()
    assert database.gamma_generations.update_one.call_args.args[1]['$set']['assessment.status']=='failed'


@pytest.mark.asyncio
async def test_assessment_poll_never_calls_gamma_generation_again():
    database=SimpleNamespace(gamma_generations=SimpleNamespace(find_one=AsyncMock(return_value=job())))
    module=routes(db=database,PROJECTS_DIR='unused')
    module.poll.__globals__['authorized']=AsyncMock(return_value=job())
    with patch.object(service,'start_queued',AsyncMock()) as start,patch('services.gamma_api.request',AsyncMock()) as gamma:
        await module.poll('job1',{'roles':['editor'],'id':'author'})
    start.assert_awaited_once();gamma.assert_not_awaited()


@pytest.mark.asyncio
async def test_opt_in_keeps_private_complete_source_and_does_not_change_gamma_payload():
    import uuid
    database=SimpleNamespace(gamma_generations=SimpleNamespace(find_one=AsyncMock(return_value=None),insert_one=AsyncMock(),update_one=AsyncMock()),projects=SimpleNamespace(insert_one=AsyncMock()))
    module=routes(db=database,resolve_company_id_for_creation=AsyncMock(return_value='tenant'))
    source='Prompt do autor\nDocumento completo: unidade inicial.\nÚltima unidade do documento.'
    with patch('services.llm_config.openai_api_key',return_value='test-key'),patch('services.gamma_api.configured',return_value=True),patch('services.gamma_api.request',AsyncMock(return_value={'generationId':'gen_abc'})) as provider:
        result=await module.generate(module.Generate(requestId=uuid.uuid4(),title='Curso Gamma',prompt=source,interactiveAssessment={'enabled':True,'questionCount':3,'images':True}),{'roles':['editor'],'id':'author'})
    stored=database.gamma_generations.insert_one.call_args.args[0]
    assert stored['assessmentSource']==source and stored['interactiveAssessment']['questionCount']==3
    assert 'assessmentSource' not in result and 'interactiveAssessment' not in provider.call_args.args[2]
    assert source == provider.call_args.args[2]['prompt']
    assert database.projects.insert_one.call_args.args[0]['companyId']=='tenant'


@pytest.mark.asyncio
async def test_explicit_retry_reuses_job_and_never_generates_gamma_slides():
    original={**job(),'status':'completed','assessment':{'status':'failed'},'assessmentSpec':spec()}
    database=SimpleNamespace(gamma_generations=SimpleNamespace(update_one=AsyncMock(return_value=SimpleNamespace(modified_count=1)),find_one=AsyncMock(return_value={**original,'status':'assessment'})))
    module=routes(db=database,PROJECTS_DIR='unused');module.retry_assessment.__globals__['authorized']=AsyncMock(return_value=original)
    with patch.object(service,'start_queued',AsyncMock()) as start,patch('services.gamma_api.request',AsyncMock()) as provider:
        await module.retry_assessment('job1',{'roles':['editor'],'id':'author'})
    start.assert_awaited_once();provider.assert_not_awaited()
    assert database.gamma_generations.update_one.call_args.args[0]['assessment.status']=='failed'


@pytest.mark.asyncio
async def test_missing_assessment_ai_blocks_before_any_paid_gamma_request():
    import uuid
    database=SimpleNamespace(gamma_generations=SimpleNamespace(find_one=AsyncMock(return_value=None),insert_one=AsyncMock()),projects=SimpleNamespace(insert_one=AsyncMock()))
    module=routes(db=database)
    with patch('services.llm_config.openai_api_key',return_value=''),patch('services.gamma_api.configured',return_value=True),patch('services.gamma_api.request',AsyncMock()) as provider:
        with pytest.raises(Exception) as error:
            await module.generate(module.Generate(requestId=uuid.uuid4(),title='Curso Gamma',prompt='Conteúdo suficientemente longo para o teste.',interactiveAssessment={'enabled':True}),{'roles':['editor'],'id':'author'})
    assert error.value.status_code==503
    provider.assert_not_awaited()
    database.gamma_generations.insert_one.assert_not_awaited()
    database.projects.insert_one.assert_not_awaited()
