import copy,io,json,sys,uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock,MagicMock,patch
import pytest
from fastapi import UploadFile,HTTPException
from services.educational_film import revision
from services.film_guided import coverage_review,STORYBOARD_SYSTEM
from services.creator_guide import topics_for
from tests.test_educational_films import scope,film

def test_coverage_bounded_and_missing_report_is_explicit():
    f=film();result=coverage_review({},f['board'],revision)
    assert result['warnings'] and result['revision']==f['revision']
    with pytest.raises(ValueError):coverage_review({'review':{'summary':'Resumo de teste válido.','coveredTopics':['x'*601]}},f['board'],revision)
    assert 'não confiáveis' in STORYBOARD_SYSTEM and 'notCoveredTopics' in STORYBOARD_SYSTEM

@pytest.mark.asyncio
async def test_extraction_reads_pdf_and_never_writes_course_or_film():
    import fitz
    with fitz.open() as doc:
        doc.new_page().insert_text((50,50),'Trabalho em equipe: dividir tarefas e revisar juntos.');raw=doc.tobytes()
    s=scope(film());upload=UploadFile(filename='equipe.pdf',file=io.BytesIO(raw))
    result=await s.extract_document(upload,{'id':'u','companyId':'c'})
    assert 'dividir tarefas' in result['text'] and 'OCR' not in result['text']
    assert upload.file.closed and 'não são importadas' in result['warning']
    s.db.projects.update_one.assert_not_awaited();s.db.educational_films.update_one.assert_not_awaited()
    s.run.assert_not_awaited();s.can_edit.assert_called_once()

@pytest.mark.asyncio
async def test_guided_create_keeps_full_source_in_new_workspace_only():
    s=scope(film());s.db.educational_films.find_one=AsyncMock(return_value=None)
    text='Referência completa. '*4500+'FIM DA FONTE'
    body=s.Create(title='Trabalho em equipe',topic='Objetivo: colaborar em uma entrega.',requestId=uuid.uuid4(),style='3d',sourceText=text,sourceName='ementa.docx',sourceProjectId='original')
    result=await s.create(body,{'id':'u','companyId':'c'})
    assert result['sourceText']==text and result['board']['style']=='3d'
    assert result['projectId']!='original' and result['status']=='draft'
    assert s.db.projects.update_one.call_args.args[0]['_id'].startswith('film-workspace:')
    assert not result.get('storyboardApproval') and not result.get('budgetApproval')
    s.run.assert_not_awaited()

@pytest.mark.asyncio
async def test_ai_receives_entire_reviewed_source_and_never_generates_media():
    f=film();f.update(sourceText='Primeiro tópico. '*5000+'ULTIMO TOPICO',sourceName='ementa.docx',sourceWarning='Uma página sem texto.')
    original=copy.deepcopy(f);s=scope(f)
    answer={'characters':f['board']['characters'],'scenes':f['board']['scenes'],
        'review':{'summary':'Uma história curta sobre cooperação e escuta.','coveredTopics':['Escuta da equipe'],'notCoveredTopics':['Tópicos adicionais que não cabem em 15s.'],'warnings':['Fonte parcialmente legível.']}}
    create=AsyncMock(return_value=SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(answer)))]))
    client=SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    manager=AsyncMock();manager.__aenter__.return_value=client
    with patch.dict(sys.modules,{'openai':SimpleNamespace(AsyncOpenAI=MagicMock(return_value=manager))}),patch('services.llm_config.require_openai_api_key',return_value='test'),patch('services.llm_config.openai_text_model',return_value='test-model'):
        result=await s.suggest(f['id'],s.Approval(revision=f['revision']),{'id':'u','companyId':'c'})
    sent=json.loads(create.call_args.kwargs['messages'][1]['content'])
    assert sent['document']==f['sourceText'] and sent['document'].endswith('ULTIMO TOPICO')
    assert result['planningReview']['notCoveredTopics'] and result['storyboardApproval'] is None and result['budgetApproval'] is None
    assert f==original
    s.run.assert_not_awaited();s.db.projects.update_one.assert_not_awaited();create.assert_awaited_once()

def test_tutor_explains_guided_and_advanced_scope_and_costs():
    topic=next(t for t in topics_for({'role':'superadmin'}) if t['id']=='guided-educational-film')
    for word in ('Modo avançado','20 MB','100.000','não há OCR','OpenAI','o que ficou fora','não gera mídia','aprovações'):
        assert word in str(topic)
