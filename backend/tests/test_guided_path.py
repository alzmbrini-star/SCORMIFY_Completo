import asyncio
import copy
import json
import re
import subprocess
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from services.guided_path import plan_guided_path, validate_activity, activity_element, course_plan, populate_assessments, generate_activity


def structure(topic='Planejamento'):
    return {'modules':[{'title':topic,'description':'Planejar a atividade e verificar seus resultados.','slides':[
        {'id':'cover','type':'title','title':topic},
        {'id':'lesson','type':'content','title':'Preparar e conferir','sourceRequired':True,'sourceRefs':['original-1'],'sourceExcerpt':'Preparar o ambiente, executar e conferir o resultado.'},
        {'id':'original','type':'content','title':'Tela original','sourceImageOnly':True,'sourceImage':'original.png'},
        {'id':'oldquiz','type':'quiz','title':'Verificação'},
        {'id':'end','type':'summary','title':'Conclusão'}]}]}


def sample_course():
    planned=plan_guided_path(structure(),{'guidedQuestionsPerUnit':1,'guidedFinalQuestionCount':3})
    path=planned['guidedPath'];unit=path['units'][0]['id'];slides=[]
    for request in planned['modules'][0]['slides']:
        kind=request.get('guidedRequest')
        if kind in ('assessment','final'):
            count=1 if kind=='assessment' else 3
            raw={'title':request['title'],'instructions':'Observe a situação e responda.','questions':[
                {'unitId':unit,'title':'Conferência do ambiente','prompt':'O que fazer antes de iniciar a atividade?',
                 'options':['Conferir as condições de trabalho.','Ignorar as condições do ambiente.'],'correct':0,
                 'explanation':'A conferência reduz falhas e permite planejar a execução.'} for _ in range(count)]}
        elif kind=='practice':
            raw={'title':request['title'],'instructions':'Organize as etapas da atividade.',
                 'cards':[{'front':'Quando preparar?','back':'Antes de executar.'},{'front':'Quando conferir?','back':'Depois de executar.'}],
                 'activity':{'type':'ordering','items':['Preparar','Executar','Conferir'],'feedback':'Prepare antes de executar e confira o resultado ao final.'}}
        elif kind=='project':
            raw={'title':request['title'],'instructions':'Registre seu plano e confira o critério.',
                 'deliverables':[{'title':'Plano de execução','prompt':'Descreva como preparar, executar e conferir a atividade.',
                     'criterion':'O plano inclui preparação, execução e conferência.','unitIds':[unit]}]}
        else:
            elements=[{'id':request['id']+'_e','type':'text','x':80,'y':80,'width':1650,'height':620,'content':request['title']}]
            slides.append({**request,'elements':elements,'width':1920,'height':820,'duration':60});continue
        spec=validate_activity(raw,request,path)
        slides.append({**request,'elements':[activity_element(spec)],'width':1920,'height':820,'duration':120})
    return {'slides':slides,'metadata':{'title':'Percurso de planejamento','guidedPath':path}}


@pytest.mark.parametrize('theme',['Culinária','Segurança digital','Gestão de pessoas'])
def test_plan_is_additive_across_topics_and_replaces_traditional_quiz(theme):
    original=structure(theme);before=copy.deepcopy(original)
    result=plan_guided_path(original,{})
    assert original==before
    slides=result['modules'][0]['slides']
    assert next(s for s in slides if s['id']=='lesson')['sourceRefs']==['original-1']
    assert next(s for s in slides if s['id']=='original')['sourceImage']=='original.png'
    assert next(s for s in slides if s['id']=='oldquiz')['guidedRequest']=='assessment'
    assert not any(s['type']=='quiz' for s in slides)
    assert {s.get('guidedStage') for s in slides}>={'learn','explore','practice','assessment','project','final'}
    assert next(i for i,s in enumerate(slides) if s.get('guidedStage')=='practice')<next(i for i,s in enumerate(slides) if s.get('guidedStage')=='assessment')
    assert plan_guided_path(result,{})==result


def test_final_covers_all_units_and_settings_have_bounds():
    source=structure();source['modules']*=13
    path=plan_guided_path(source,{})['guidedPath']
    assert path['finalQuestionCount']==13
    with pytest.raises(ValueError):plan_guided_path(structure(),{'guidedQuestionsPerUnit':11})
    request={'id':'final','title':'Final','guidedRequest':'final'}
    with pytest.raises(ValueError):validate_activity({'instructions':'Responda.','questions':[]},request,path)


def test_assessment_is_canonical_and_host_omits_answer_keys_and_duplicate_media():
    course=sample_course()
    assessment=next(e for s in course['slides'] for e in s['elements'] if e.get('guidedActivity',{}).get('kind')=='assessment')
    assert assessment['assessmentConfig']['guidedPath'] is True
    assert 'assessment-data' in assessment['htmlContent'] and 'scormify-guided-assessment-result' in assessment['htmlContent']
    assert assessment['assessmentConfig']['questions'][0]['imageGenerationStatus']=='pending'
    plan=course_plan(course)
    assert all('questions' not in (s['activity'] or {}) for s in plan['slides'])
    before=plan['fingerprint'];assessment['assessmentConfig']['questions'][0]['media']={'url':'data:image/png;base64,large','kind':'image'}
    assert course_plan(course)['fingerprint']==before
    assessment['guidedActivity']['questions'][0]['prompt']='Outra situação de aprendizagem.'
    assert course_plan(course)['fingerprint']!=before


def test_generation_repairs_once_without_executing_generated_code():
    path=plan_guided_path(structure(),{})['guidedPath']
    request={'id':'project','title':'Projeto','guidedRequest':'project'}
    ask=AsyncMock(side_effect=[{}, {'instructions':'Aplique o conteúdo.','deliverables':[{'title':'Entrega','prompt':'Registre seu plano.','criterion':'Todos os passos explicados.','unitIds':[path['units'][0]['id']]}]}])
    spec=asyncio.run(generate_activity(request,path,'Preparação e conferência.',ask))
    assert spec['kind']=='project' and ask.await_count==2
    assert 'Correção necessária' in ask.await_args.args[1]


def test_project_repair_names_missing_units_and_preserves_previous_deliveries():
    path=plan_guided_path(structure(),{})['guidedPath']
    path['units'].append({'id':'second_unit','title':'Rastreabilidade e evidências'})
    request={'id':'project','title':'Projeto','guidedRequest':'project'}
    first={'instructions':'Aplique o conteúdo.','deliverables':[{'title':'Preparação','prompt':'Prepare o processo.',
        'criterion':'Preparação registrada.','unitIds':[path['units'][0]['id']]}]}
    repaired=copy.deepcopy(first)
    repaired['deliverables'][0].update(prompt='Prepare o processo e registre suas evidências rastreáveis.',
        criterion='Preparação e evidências rastreáveis registradas.',unitIds=[u['id'] for u in path['units']])
    ask=AsyncMock(side_effect=[first,repaired])
    result=asyncio.run(generate_activity(request,path,'Conferência e evidências.',ask))
    prompt=ask.await_args.args[1]
    assert 'Faltam vínculos explícitos' in prompt and 'second_unit' in prompt
    assert 'Rastreabilidade e evidências' in prompt and 'Resposta anterior a corrigir' in prompt
    assert 'Preparação registrada.' in prompt
    assert result['deliverables'][0]['unitIds']==[u['id'] for u in path['units']]


def test_images_are_associated_to_bank_and_snapshot_retry_reuses_durable_asset(monkeypatch,tmp_path):
    course=sample_course();records={};calls=[]
    async def find(query,*args):return copy.deepcopy(records.get(query['id']))
    async def update(query,patch,**kwargs):records[query['id']]={**patch['$set']}
    async def image(q,project,*args):
        calls.append(q['id']);return {'kind':'image','url':f"/api/projects/{project['id']}/assets/{q['id']}.png",'name':'Situação da questão'}
    monkeypatch.setattr('services.assessment_images.create_support_image',image)
    db=SimpleNamespace(assessment_questions=SimpleNamespace(find_one=find,update_one=update))
    project={'id':'test-course','userId':'author','companyId':'company'}
    stats=asyncio.run(populate_assessments(course,project,db,tmp_path))
    assert stats=={'total':4,'ready':4,'failed':0} and len(records)==4
    assert all(q['createdBy']=='author' and q['companyId']=='company' for q in records.values())
    assert all(q['media']['url'].startswith('/api/projects/test-course/assets/') for q in records.values())
    for s in course['slides']:
        for e in s['elements']:
            if e.get('assessmentConfig'):
                assert e['guidedActivity']['questions']==e['assessmentConfig']['questions']
                assert '/api/projects/test-course/assets/' in e['htmlContent']
    asyncio.run(populate_assessments(course,project,db,tmp_path))
    assert len(calls)==4


def test_failed_image_preserves_question_and_reports_warning(monkeypatch,tmp_path):
    course=sample_course();db=SimpleNamespace(assessment_questions=SimpleNamespace(find_one=AsyncMock(return_value=None),update_one=AsyncMock()))
    monkeypatch.setattr('services.assessment_images.create_support_image',AsyncMock(side_effect=ValueError('Provider unavailable')))
    stats=asyncio.run(populate_assessments(course,{'id':'p'},db,tmp_path))
    assert stats['failed']==4 and db.assessment_questions.update_one.await_count==4
    e=next(e for s in course['slides'] for e in s['elements'] if e.get('assessmentConfig'))
    assert len(e['assessmentConfig']['questions'])==1
    assert e['assessmentConfig']['questions'][0]['imageGenerationStatus']=='failed'


def test_compiler_keeps_canonical_assessments_not_quiz(monkeypatch,tmp_path):
    from services import ai_agent
    course=sample_course();storyboard={'guidedPath':course['metadata']['guidedPath'],'slides':[]}
    for slide in course['slides']:
        if not slide.get('guidedRequest'):continue
        storyboard['slides'].append({**slide,'guidedActivity':slide['elements'][0]['guidedActivity']})
    monkeypatch.setattr(ai_agent,'_new_chat',lambda *a,**k:pytest.fail('No paid generation in deterministic compilation'))
    result=asyncio.run(ai_agent.generate_course_from_storyboard('test',storyboard,{'title':'Planejamento','visualCourseMode':'guided_practice_project'},str(tmp_path),'test-project'))
    assert result['metadata']['guidedPath']==storyboard['guidedPath']
    assert not result['quizQuestions']
    assert sum(bool(e.get('assessmentConfig')) for s in result['slides'] for e in s['elements'])==2


def test_html_and_scorm_install_host_without_changing_existing_mode(tmp_path):
    from services.html_exporter import generate_standalone_html
    from services.scorm_exporter import export_scorm_package
    from models import Project
    from services.guided_path import install_guided_host
    course=sample_course();project={'id':'guided-test','name':'Percurso de planejamento','enableVlibras':False,'course':course}
    document=asyncio.run(generate_standalone_html(project,str(tmp_path)))
    assert 'id="guided-path-plan"' in document and 'data-guided-id=' in document
    assert 'window.ScormifyGuided.slide(currentSlide)' in document
    streamed=tmp_path/'streamed.html'
    asyncio.run(generate_standalone_html(project,str(tmp_path),output_path=str(streamed)))
    assert 'id="guided-path-plan"' in streamed.read_text(encoding='utf-8')
    package=export_scorm_package(Project(**project),str(tmp_path/'storage'),str(tmp_path/'exports'))
    with zipfile.ZipFile(package) as archive:
        assert 'guided-path-plan' in archive.read('index.html').decode()
        assert 'ScormifyGuided.canComplete()' in archive.read('scripts/player.js').decode()
        data=json.loads(archive.read('course.json'))
        assert sum(bool(e.get('assessmentConfig')) for s in data['slides'] for e in s['elements'])==2
    assert install_guided_host('<head></head>',{'metadata':{}})=='<head></head>'


def test_progress_core_and_grade_contracts():
    result=subprocess.run(['node',str(Path(__file__).with_name('guided_path.cjs'))],capture_output=True,text=True)
    assert result.returncode==0,result.stdout+result.stderr


def test_frontend_runtime_matches_exported_core():
    base=Path(__file__).parents[2]
    for source,target in [('guided-core.js','guidedCore.js'),('guided-host.js','guidedHost.js')]:
        assert (base/'backend/services/export_assets'/source).read_text(encoding='utf-8')==(base/'frontend/src/utils'/target).read_text(encoding='utf-8')


def test_tutor_knows_interactive_assessments_credits_and_portfolio_limits():
    from services.creator_guide import topics_for
    topic=next(t for t in topics_for({'role':'super_admin'}) if t['id']=='guided-path')
    text=' '.join(topic['steps'])
    for word in ['Avaliações interativas','biblioteca','créditos','melhor nota','somente progresso','TXT']:
        assert word.lower() in text.lower()


def test_editor_render_is_project_scoped_no_ai_and_preserves_canonical_media(monkeypatch):
    from routes import agent
    project={'id':'project','course':sample_course()}
    question_element=next(e for s in project['course']['slides'] for e in s['elements'] if e.get('assessmentConfig'))
    original=copy.deepcopy(question_element)
    spec=copy.deepcopy(original['guidedActivity']);spec['title']='Avaliação revisada';spec['questions'][0]['prompt']='Como preparar o ambiente antes de executar?'
    monkeypatch.setattr(agent,'load_authorized_project',AsyncMock(return_value=project))
    request=agent.GuidedRenderRequest(projectId='project',elementId=original['id'],spec=spec)
    result=asyncio.run(agent.render_guided_edit(request,{'id':'author'}))
    assert result['assessmentConfig']['guidedPath'] is True
    assert result['guidedActivity']['id']==original['guidedActivity']['id']
    assert 'Como preparar' in result['htmlContent']
    assert question_element==original, 'Rendering does not write or mutate the saved course'
    request.elementId='another-project-element'
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:asyncio.run(agent.render_guided_edit(request,{'id':'author'}))
    assert exc.value.status_code==404
