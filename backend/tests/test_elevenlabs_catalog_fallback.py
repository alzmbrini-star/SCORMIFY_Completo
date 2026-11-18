import os
from types import SimpleNamespace
from unittest.mock import AsyncMock,patch
import httpx
import pytest
from services import runway_narration as n
from services.creator_guide import topics_for

def response(status=200,voices=None,**data):
    return SimpleNamespace(status_code=status,json=lambda:{'voices':voices or [],**data})

async def invoke(results,search=''):
    client=AsyncMock();client.get.side_effect=results
    manager=AsyncMock();manager.__aenter__.return_value=client
    with patch.dict(os.environ,{'ELEVENLABS_API_KEY':'private-test-key'}),patch.object(n.httpx,'AsyncClient',return_value=manager):
        result=await n.catalog(search)
    client.post.assert_not_awaited()
    return result,client

@pytest.mark.asyncio
async def test_primary_success_uses_one_get_and_omits_empty_search():
    result,client=await invoke([response(voices=[{'voice_id':'a','name':'Ana','labels':{'accent':'Brazilian'}}],has_more=True)])
    assert result['source']=='v2' and not result['fallback'] and result['hasMore']
    assert result['voices'][0]['brazilian']
    assert client.get.await_count==1
    assert 'search' not in client.get.call_args.kwargs['params']

@pytest.mark.asyncio
@pytest.mark.parametrize('failure',[response(502),response(503),response(404),response(410),httpx.ConnectError('private detail'),SimpleNamespace(status_code=200,json=lambda:{'unexpected':True})])
async def test_one_alternative_get_normalizes_filters_and_never_synthesizes(failure):
    result,client=await invoke([failure,response(voices=[{'voice_id':'b','name':'Bruno','labels':{'accent':'American'}},{'voice_id':'a','name':'Ana','description':'Acolhedora','labels':{'accent':'Brazilian'}},{}])],'acolhedora')
    assert result['fallback'] and result['source']=='v1'
    assert [r['id'] for r in result['voices']]==['a']
    assert result['voices'][0]['brazilian'] and not result['hasMore']
    assert 'alternativa' in result['notice'] and 'private' not in result['notice']
    assert client.get.await_count==2 and client.get.call_args.args[0].endswith('/v1/voices')

@pytest.mark.asyncio
@pytest.mark.parametrize('status,expected',[(401,'Autenticação'),(403,'permissão'),(429,'Limite'),(422,'recusou')])
async def test_auth_rate_and_request_failures_do_not_fallback(status,expected):
    client=AsyncMock();client.get.return_value=response(status)
    manager=AsyncMock();manager.__aenter__.return_value=client
    with patch.dict(os.environ,{'ELEVENLABS_API_KEY':'private-test-key'}),patch.object(n.httpx,'AsyncClient',return_value=manager):
        with pytest.raises(ValueError,match=expected):await n.catalog()
    assert client.get.await_count==1
    client.post.assert_not_awaited()

@pytest.mark.asyncio
async def test_both_failed_explain_unavailability_without_credential_or_balance_blame():
    with pytest.raises(ValueError,match='v1 alternativa, HTTP 503') as exc:
        await invoke([response(502),response(503)])
    assert 'Serviço indisponível' in str(exc.value)
    assert 'private-test-key' not in str(exc.value)

def test_tutor_documents_no_media_or_storyboard_mutations():
    topic=next(t for t in topics_for({'role':'superadmin'}) if t['id']=='elevenlabs-voice-catalog')
    for text in ('/v2/voices','/v1/voices','429','não modifica cursos','não seleciona uma voz automaticamente','sem síntese'):
        assert text in str(topic)
