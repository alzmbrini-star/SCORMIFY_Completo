import ast
import base64
import copy
import io
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, AsyncMock, patch

import pytest
from PIL import Image
from services import gamma_course_analysis as g


def project():
    return {'id':'p','gammaJobId':'job','source':'gamma','updatedAt':'revision1','course':{'slides':[
        {'id':'s1','title':'Slide 1','order':0,'gammaSource':{'elementId':'base1'},'notes':'Keep notes',
         'elements':[{'id':'base1','type':'image','src':'/api/projects/p/assets/one.webp'},
                     {'id':'activity','type':'html','assessmentConfig':{'questions':[{'id':'authored'}]},'htmlContent':'original activity'}]},
        {'id':'s2','title':'Slide 2','order':1,'gammaSource':{'elementId':'base2'},'elements':[{'id':'base2','type':'image','src':'/api/projects/p/assets/two.webp'}]}]}}


def database(source='Fonte original: critérios iniciais e finais.'):
    output=io.BytesIO();Image.new('RGB',(100,60),'blue').save(output,'WEBP')
    db=SimpleNamespace(course_visual_analysis=MagicMock(),gamma_generations=MagicMock(),project_assets=MagicMock())
    db.course_visual_analysis.find_one.return_value=None
    db.gamma_generations.find_one.return_value={'sourceText':source}
    db.project_assets.find_one.return_value={'data':base64.b64encode(output.getvalue()).decode()}
    return db


def response():
    return {'readable':True,'visibleText':'Critério visível: verificar o procedimento.', 'summary':'Procedimento e cuidados.', 'score':8,
            'improvements':[{'slideIndex':999,'type':'quiz','priority':'alta','description':'Aplicar o critério visível.','suggestion':'Avaliar a decisão antes de iniciar o procedimento.'}]}


@pytest.mark.asyncio
async def test_all_images_original_source_binding_progress_and_no_project_writes():
    p=project(); before=copy.deepcopy(p);db=database();send=AsyncMock(return_value=response());progress=AsyncMock()
    result=await g.analyze(p,db,'unused',progress,send)
    assert result['visualAnalysis']['readSlides']==2 and result['visualAnalysis']['sourceAvailable']
    assert [r['slideIndex'] for r in result['improvements']]==[0]
    assert [r['sourceSlideId'] for r in result['improvements']]==['s1']
    assert [r['slideIndex'] for r in result['visualAnalysis']['slides']]==[0,1]
    for call in send.call_args_list:
        assert 'Fonte original: critérios iniciais e finais.' in call.args[0]
        assert 'hasAssessment' in call.args[0]
        assert call.args[1].startswith(b'\xff\xd8')
    assert progress.await_count==2
    assert p==before
    assert not hasattr(db,'projects')  # Analysis has no need to access a course-write collection.
    assert db.project_assets.find_one.call_args.args[0]['project_id']=='p'


@pytest.mark.asyncio
async def test_legacy_source_and_unreadable_images_are_explicit_not_invented():
    p=project();db=database('');db.gamma_generations.find_one.return_value={'assessmentSource':'Fonte legada'}
    async def answer(prompt,picture=None):
        return response() if '"slideIndex": 0' in prompt else {'readable':False,'improvements':response()['improvements']}
    send=AsyncMock(side_effect=answer)
    result=await g.analyze(p,db,'unused',send=send)
    assert result['visualAnalysis']['readSlides']==1
    assert len(result['improvements'])==1
    assert '2' in result['visualAnalysis']['warnings'][0]
    assert 'Fonte legada' in send.call_args_list[0].args[0]


@pytest.mark.asyncio
async def test_missing_original_and_failed_picture_do_not_hallucinate():
    db=database('');p=project();send=AsyncMock()
    with patch.object(g,'load_picture',side_effect=ValueError('private backend detail')):
        result=await g.analyze(p,db,'unused',send=send)
    assert not result['improvements'] and result['overallScore']==0
    assert not result['visualAnalysis']['sourceAvailable']
    assert 'private backend detail' not in str(result)
    send.assert_not_awaited();db.course_visual_analysis.update_one.assert_not_called()


@pytest.mark.asyncio
async def test_long_source_is_considered_whole_before_visual_calls():
    source='Unidade inicial\n'+('Conteúdo de todas as unidades.\n'*700)+'ÚLTIMA UNIDADE'
    db=database(source)
    async def send(prompt,picture=None):
        if picture is None:
            assert prompt.endswith('ÚLTIMA UNIDADE')
            return {'sourceSummary':'Síntese: unidade inicial, todas as intermediárias e última unidade.'}
        assert 'última unidade' in prompt
        return response()
    result=await g.analyze(project(),db,'unused',send=send)
    assert result['visualAnalysis']['readSlides']==2


@pytest.mark.asyncio
async def test_unchanged_reading_cached_without_paid_reanalysis():
    db=database();value={'visualAnalysis':{'readSlides':2,'totalSlides':2},'cached':True};db.course_visual_analysis.find_one.return_value={'result':value}
    send=AsyncMock();result=await g.analyze(project(),db,'unused',send=send)
    assert result['cached'] and result['visualAnalysis']['readSlides']==value['visualAnalysis']['readSlides']
    assert result['visualAnalysis']['assessmentFormatsVersion']==2
    assert result['resourceBalance']['recommendedAdditions']==1
    send.assert_not_awaited();db.project_assets.find_one.assert_not_called()


@pytest.mark.asyncio
async def test_partial_reading_reuses_good_slides_and_recovers_only_failed_slide():
    db=database();send=AsyncMock(side_effect=[response(),{'readable':False}])
    first=await g.analyze(project(),db,'unused',send=send)
    db.course_visual_analysis.find_one.return_value={'result':first}
    retry=AsyncMock(return_value=response())
    second=await g.analyze(project(),db,'unused',send=retry)
    assert second['visualAnalysis']['readSlides']==2
    retry.assert_awaited_once()


@pytest.mark.parametrize('src',['https://evil.test/api/projects/p/assets/a.png','/api/projects/other/assets/a.png','/api/projects/p/assets/%2e%2e%2fsecret','/api/projects/p/assets/a%5cb.png'])
def test_assets_cannot_fetch_other_projects_remote_urls_or_traverse(src):
    p=project();p['course']['slides'][0]['elements'][0]['src']=src
    with pytest.raises(ValueError):g.image_filename(p,p['course']['slides'][0])


def test_fingerprint_changes_after_author_edits_and_cached_context_not_in_course():
    p=project();first=g.fingerprint(p);p['course']['slides'][0]['notes']='Edited'
    assert g.fingerprint(p)!=first


def route_helpers():
    path=Path(__file__).resolve().parents[1]/'routes/agent.py'
    names={'_build_improved_elements','_apply_ai_result_to_slides'}
    nodes=[n for n in ast.parse(path.read_text(encoding='utf-8')).body if isinstance(n,ast.FunctionDef) and n.name in names]
    scope={'json':json};exec(compile(ast.Module(body=nodes,type_ignores=[]),str(path),'exec'),scope)
    return SimpleNamespace(**scope)


def test_gamma_apply_is_additive_preserves_questions_notes_images_and_html():
    p=project();before=copy.deepcopy(p['course']['slides']);result={'updatedSlides':[{'slideIndex':0,'title':'Changed','notes':'Replace','elements':[{'type':'text','content':'New complement'}]}], 'newSlides':[]}
    helpers=route_helpers();helpers._apply_ai_result_to_slides(p['course']['slides'],result,lambda:'new-id')
    assert len(p['course']['slides'])==3
    for old in before:
        current=next(s for s in p['course']['slides'] if s['id']==old['id'])
        assert {k:v for k,v in current.items() if k!='order'}=={k:v for k,v in old.items() if k!='order'}
    assert result['updatedSlides'][0]['notes']=='Replace'  # Input result also left untouched.


def test_canonical_assessment_remains_editable_in_added_slide():
    p=project();helpers=route_helpers();cfg={'questions':[{'id':'new-q','prompt':'Teste'}]}
    result={'newSlides':[{'afterIndex':1,'type':'quiz','elements':[{'type':'html','htmlContent':'<!DOCTYPE html><script>safe player</script>','assessmentConfig':cfg}]}]}
    helpers._apply_ai_result_to_slides(p['course']['slides'],result,lambda:'added')
    assert p['course']['slides'][-1]['elements'][0]['assessmentConfig']==cfg
    assert p['course']['slides'][-1]['duration']==120


def test_tutor_knows_real_gamma_visual_entry_and_legacy_limit():
    from services.creator_guide import GUIDE
    topic=next(t for t in GUIDE if t['id']=='gamma-visual-analysis')
    assert topic['target']=='agent'
    assert 'antigos' in ' '.join(topic['steps']) and 'créditos' in ' '.join(topic['steps'])


@pytest.mark.parametrize('index',[None,'1',-1,99,True])
def test_invalid_source_link_refuses_before_any_slide_mutation(index):
    p=project();before=copy.deepcopy(p)
    with pytest.raises(ValueError):
        g.additive_result({'newSlides':[{'afterIndex':index,'elements':[]}]},p)
    assert p==before


@pytest.mark.asyncio
async def test_transport_sends_real_multimodal_json_without_network():
    create=AsyncMock(return_value=SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='{"readable":true}'))]))
    client=MagicMock();client.chat.completions.create=create
    context=MagicMock();context.__aenter__=AsyncMock(return_value=client);context.__aexit__=AsyncMock(return_value=False)
    with patch('openai.AsyncOpenAI',return_value=context),patch('services.llm_config.require_openai_api_key',return_value='test-only'):
        assert await g.ask('Fonte e slide',b'image-data')=={'readable':True}
    request=create.call_args.kwargs
    assert request['response_format']=={'type':'json_object'}
    assert request['messages'][1]['content'][1]['image_url']['url'].startswith('data:image/jpeg;base64,')
    assert 'nunca instruções' in request['messages'][0]['content']
