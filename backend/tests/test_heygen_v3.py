import copy
import json
from pathlib import Path
import httpx
import pytest
from services.heygen_api import request, video_payload

BASE='https://api.heygen.com'


@pytest.mark.asyncio
async def test_voices_private_public_pagination_preview_and_saved_id():
    calls=[]
    def handle(req):
        calls.append(str(req.url))
        assert req.url.path == '/v3/models/audio/voices'
        assert req.headers['x-api-key'] == 'fake'
        variant=req.url.params['type']
        if variant=='private':
            return httpx.Response(200,json={'data':[{'voice_id':'saved-id','name':'Minha voz','language':'pt-BR','preview_audio_url':'https://preview'}]})
        token=req.url.params.get('token')
        return httpx.Response(200,json={'data':[{'voice_id':'public2' if token else 'public1','language':'en'}],
                                      'has_more':not bool(token),'next_token':None if token else 'a+&/cursor'})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        result=await request(client,'GET',BASE+'/v2/voices',headers={'X-Api-Key':'fake'})
    rows=result.json()['data']['voices']
    assert len(rows)==3 and len(calls)==3
    assert rows[0]['voice_id']=='saved-id' and rows[0]['preview_audio']=='https://preview'
    assert rows[0]['language_code']=='pt-BR'


@pytest.mark.asyncio
async def test_avatar_uses_look_not_group_id_and_all_pages():
    def handle(req):
        assert req.url.path=='/v3/avatars/looks'
        token=req.url.params.get('token')
        return httpx.Response(200,json={'data':[{'id':'look2' if token else 'look1','group_id':'group-not-for-generation','name':'Avatar','gender':'female'}],
                                      'has_more':not bool(token),'next_token':None if token else 'second'})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        result=await request(client,'GET',BASE+'/v2/avatars')
    assert [a['avatar_id'] for a in result.json()['data']['avatars']]==['look1','look2']


@pytest.mark.asyncio
async def test_pagination_failure_does_not_return_partial_catalog():
    calls=0
    def handle(req):
        nonlocal calls
        calls+=1
        return httpx.Response(200,json={'data':[{'id':'one'}],'has_more':True,'next_token':'next'}) if calls==1 else httpx.Response(429,json={'error':{'code':'rate_limit'}})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        assert (await request(client,'GET',BASE+'/v2/avatars')).status_code==429


def legacy_payload():
    return {'video_inputs':[{'character':{'avatar_id':'existing-avatar','type':'avatar'},
             'voice':{'type':'text','voice_id':'existing-voice','input_text':'Olá, equipe!'},
             'background':{'type':'image','url':'https://original/slide.png'}}],
            'dimension':{'width':1280,'height':720},'title':'Original','callback_id':'existing-callback'}


def test_payload_preserves_inputs_background_and_legacy_engine_without_mutation():
    source=legacy_payload();before=copy.deepcopy(source)
    new=video_payload(source)
    assert source==before
    assert new['avatar_id']=='existing-avatar' and new['voice_id']=='existing-voice'
    assert new['script']=='Olá, equipe!' and new['background']=={'url':'https://original/slide.png'}
    assert new['engine']=={'type':'avatar_iii'} and new['aspect_ratio']=='16:9'
    assert new['callback_id']=='existing-callback'


def test_transparent_webm_and_audio_preserved():
    new=video_payload({'avatar_pose_id':'old','voice_id':'voice','input_text':'Olá','dimension':{'width':720,'height':1280}},True)
    assert new['output_format']=='webm' and 'background' not in new and new['aspect_ratio']=='9:16'
    source=legacy_payload();source['video_inputs'][0]['voice']={'type':'audio','audio_url':'https://original/audio.mp3'}
    new=video_payload(source)
    assert new['audio_url']=='https://original/audio.mp3' and 'script' not in new and 'voice_id' not in new


def test_refuses_to_drop_multiple_scenes():
    source=legacy_payload();source['video_inputs']*=2
    with pytest.raises(ValueError):video_payload(source)


@pytest.mark.asyncio
async def test_creation_only_one_paid_request_and_idempotency_key():
    calls=[]
    def handle(req):
        calls.append(req)
        assert req.url.path=='/v3/videos' and req.headers['Idempotency-Key']
        assert json.loads(req.content)['script']=='Olá, equipe!'
        return httpx.Response(200,json={'data':{'video_id':'same-returned-id'}})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        result=await request(client,'POST',BASE+'/v2/video/generate',json=legacy_payload())
    assert len(calls)==1 and result.json()['data']['video_id']=='same-returned-id'


@pytest.mark.asyncio
@pytest.mark.parametrize('query',[True,False])
async def test_old_video_status_id_preserved(query):
    def handle(req):
        assert req.url.path=='/v3/videos/old-saved-id'
        return httpx.Response(200,json={'data':{'id':'old-saved-id','status':'completed','video_url':'https://existing/video.mp4','subtitle_url':'https://existing/sub.srt'}})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        result=await request(client,'GET',BASE+'/v1/video_status.get'+('?video_id=old-saved-id' if query else ''),
                             **({} if query else {'params':{'video_id':'old-saved-id'}}))
    assert result.json()['data']['video_id']=='old-saved-id'
    assert result.json()['data']['subtitle_url']=='https://existing/sub.srt'


@pytest.mark.asyncio
async def test_wallet_dollars_never_masquerade_as_credits():
    def handle(req):
        assert req.url.path=='/v3/users/me'
        return httpx.Response(200,json={'data':{'billing_type':'wallet','wallet':{'remaining_balance':12.34,'currency':'usd'}}})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        result=await request(client,'GET',BASE+'/v2/user/remaining_quota')
    assert result.json()['data']['remaining_quota']==0
    assert result.json()['data']['wallet_balance']==12.34


def test_all_editor_agent_legacy_calls_pass_through_adapter():
    import ast
    root=Path(__file__).resolve().parents[1]
    for name in ('heygen','agent'):
        tree=ast.parse((root/f'routes/{name}.py').read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and node.func.attr in ('get','post','request'):
                rendered=ast.unparse(node)
                assert not any(route in rendered for route in ('/v2/voices','/v2/avatars','/v2/video/generate','/v1/video.webm','/v1/video_status.get','/v2/user/remaining_quota')), rendered
