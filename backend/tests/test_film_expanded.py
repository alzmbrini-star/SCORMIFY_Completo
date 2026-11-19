"""Five-minute multi-character films: no live AI/media calls."""
import copy,uuid,json,sys
from types import SimpleNamespace
import pytest
from unittest.mock import AsyncMock,MagicMock,patch
from services.educational_film import normalized_board,revision,quote,require_ready
from services.film_worker import scene_references,operation_signature
from services.creator_guide import GUIDE
from services.film_guided import storyboard_format,planning_diagnostic
from tests.test_educational_films import board,film,scope

def expanded():
    b=board()
    b['characters']=[{'name':n,'description':'Pessoa adulta com roupa corporativa original.','voiceId':''} for n in ['João','Ana','Carlos','Mariana','Gestora','Psicóloga']]
    b['scenes']=[{**copy.deepcopy(b['scenes'][0]),'duration':10,'speaker':'character6','visibleCharacters':[2,6]} for _ in range(30)]
    return b

def test_five_minutes_six_characters_voice_and_approvals():
    b=normalized_board(expanded(),True);assert sum(s['duration'] for s in b['scenes'])==300
    f={'board':b,'revision':revision(b),'operations':{}}
    with pytest.raises(ValueError):require_ready(f,f['revision'])
    f['storyboardApproval']=f['revision'];q=quote(f)
    assert q['duration']==300 and q['imageCount']==36 and q['items'][1]['quantity']==300
    with pytest.raises(ValueError):require_ready(f,f['revision'])
    f['budgetApproval']={'revision':f['revision'],'quoteId':q['id'],'ceilingUsd':q['suggestedCeilingUsd']}
    assert require_ready(f,f['revision'])==b

@pytest.mark.parametrize('field,value', [('characters',[]),('scenes',[])])
def test_empty_expanded_board_refused(field,value):
    b=expanded();b[field]=value
    with pytest.raises(ValueError):normalized_board(b,True)

@pytest.mark.parametrize('ids', [[],[0],[7],[1,1],[1,2,3,4]])
def test_invalid_or_missing_scene_cast_refused(ids):
    b=expanded();b['scenes'][0]['visibleCharacters']=ids
    with pytest.raises(ValueError):normalized_board(b,True)

def test_limits_and_missing_speaker():
    b=expanded();b['scenes'].append(copy.deepcopy(b['scenes'][0]))
    with pytest.raises(ValueError):normalized_board(b)
    b=expanded();b['characters'].append(copy.deepcopy(b['characters'][0]))
    with pytest.raises(ValueError):normalized_board(b)
    b=expanded();b['characters']=b['characters'][:4]
    with pytest.raises(ValueError):normalized_board(b)

def test_worker_only_passes_scene_cast_and_cast_edits_invalidate_assets():
    b=expanded();refs=[{'tag':f'character{i+1}'} for i in range(6)]
    assert scene_references(b,b['scenes'][0],refs)==[refs[1],refs[5]]
    changed=copy.deepcopy(b);changed['scenes'][0]['visibleCharacters']=[1,4,5]
    assert operation_signature(b,'frame_0')!=operation_signature(changed,'frame_0')
    assert operation_signature(b,'voice_0')==operation_signature(changed,'voice_0')

def test_old_board_revision_and_assets_stay_compatible():
    b=board();before=copy.deepcopy(b)
    assert 'visibleCharacters' not in b['scenes'][0]
    assert normalized_board(b,True)==before and revision(normalized_board(b))==revision(before)
    assert scene_references(b,b['scenes'][0],[{'tag':'character1'}])==[{'tag':'character1'}]

@pytest.mark.asyncio
async def test_expanded_create_is_only_an_independent_unapproved_workspace():
    s=scope(film());s.db.educational_films.find_one=AsyncMock(return_value=None)
    result=await s.create(s.Create(title='Filme NR-01',topic='Prevenção dos fatores de riscos psicossociais no trabalho.',scenes=30,characterCount=6,requestId=uuid.uuid4()),{'id':'u','companyId':'c'})
    assert len(result['board']['scenes'])==30 and len(result['board']['characters'])==6
    assert result['sourceProjectId'] is None and result['status']=='draft'
    assert not result.get('storyboardApproval') and not result.get('budgetApproval')
    s.run.assert_not_awaited()
    with pytest.raises(ValueError):s.Create(title='Filme NR-01',topic='Conteúdo completo para roteiro.',scenes=31,requestId=uuid.uuid4())
    with pytest.raises(ValueError):s.Create(title='Filme NR-01',topic='Conteúdo completo para roteiro.',characterCount=7,requestId=uuid.uuid4())

def test_tutor_documents_new_limits_and_both_gates():
    t=str(next(t for t in GUIDE if t['id']=='guided-educational-film'))
    for term in ('300 segundos','6 personagens','três personagens','9.000','aprovações','não gera imagens'):
        assert term in t

def test_strict_schema_requires_exact_scene_and_cast_counts_and_bounded_fields():
    schema=storyboard_format(expanded())['json_schema']
    assert schema['strict'] and schema['schema']['additionalProperties'] is False
    props=schema['schema']['properties']
    assert props['scenes']['minItems']==props['scenes']['maxItems']==30
    assert props['characters']['minItems']==props['characters']['maxItems']==6
    assert props['scenes']['items']['properties']['narration']['maxLength']==110
    assert props['scenes']['items']['properties']['visibleCharacters']['maxItems']==3

@pytest.mark.asyncio
async def test_invalid_paid_text_is_preserved_with_safe_diagnostics_no_retry_or_media():
    f=film();s=scope(f);bad={'characters':f['board']['characters'],'scenes':copy.deepcopy(f['board']['scenes'])}
    bad['scenes'][0]['narration']='PRIVATE_TEXT_'*20
    create=AsyncMock(return_value=SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(bad)))]))
    manager=AsyncMock();manager.__aenter__.return_value=SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    with patch.dict(sys.modules,{'openai':SimpleNamespace(AsyncOpenAI=MagicMock(return_value=manager))}),patch('services.llm_config.require_openai_api_key',return_value='test'),patch('services.llm_config.openai_text_model',return_value='test'):
        with pytest.raises(Exception) as error:await s.suggest(f['id'],s.Approval(revision=f['revision']),{'id':'u','companyId':'c'})
    saved=s.db.educational_films.update_one.call_args.args[1]['$set']
    assert saved['planningCandidate']==bad and saved['storyboardApproval'] is None and saved['budgetApproval'] is None
    assert 'scenes.0.narration' in saved['planningDiagnostic'] and 'PRIVATE_TEXT' not in str(error.value)
    assert create.call_args.kwargs['response_format']['type']=='json_schema'
    create.assert_awaited_once();s.run.assert_not_awaited();s.db.projects.update_one.assert_not_awaited()
