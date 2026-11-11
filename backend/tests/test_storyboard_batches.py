import json
import pytest
from services.storyboard_batches import teaching_prompt, decode_batch


def test_teaching_contract_keeps_assigned_source_without_interactive_requirements():
    slides = [{'id':'s1','type':'title','title':'Capa'}, {'id':'s2','type':'content',
        'sourceExcerpt':'Diferencie salvar de sincronizar e preserve a rastreabilidade.', 'sourceRefs':['SRC001.I002']}]
    prompt = teaching_prompt(slides, {'title':'Curso completo'}, 'Todas as onze unidades e conclusão.')
    assert 'exatamente 2' in prompt
    assert 'sourceExcerpt' in prompt and 'SRC001.I002' in prompt
    assert 'Diferencie salvar de sincronizar' in prompt
    assert 'OBRIGATÓRIO em cada módulo' not in prompt
    assert 'Slides a gerar: ' in prompt
    assert teaching_prompt([{'type':'game'}], {}, '') is None


def test_decoder_handles_fence_and_preserves_order_without_filling_gaps():
    requested = [{'id':'one'}, {'id':'two'}]
    raw = {'slides':[{'id':'two','elements':[{'content':'Segunda'}]}, {'id':'one','elements':[{'content':'Primeira'}]}]}
    result = decode_batch('```json\n'+json.dumps(raw)+'\n```', requested)
    assert [s['id'] for s in result['slides']]==['one','two']
    assert result['slides'][1]['elements'][0]['content']=='Segunda'
    for response in ['{"slides": [', '{"slides": []}', '{"slides": [{"id":"one"}]}',
                     '{"slides":[{"id":"one"},{"id":"one"}]}',
                     '{"slides":[{"id":"one"},{"id":"other"}]}']:
        with pytest.raises(ValueError): decode_batch(response, requested)


@pytest.mark.asyncio
async def test_storyboard_retry_gets_actual_format_error_and_keeps_source(monkeypatch):
    from services import ai_agent
    from services.source_coverage import ensure_coverage
    source='Unidade 1 Operação\n\nExplicar a diferença entre gravar e sincronizar, com cuidados de rastreabilidade.'
    plan=ensure_coverage({'modules':[]}, source); prompts=[]
    body='<h2>Operação</h2><p>'+'Explicação detalhada com exemplo fictício e cuidado para preservar evidências e a rastreabilidade. '*6+'</p>'
    class Chat:
        async def send_message(self,message):
            prompts.append(message.text)
            if len(prompts)==1:return '{"slides": []}'
            batch=json.loads(message.text.split('Slides a gerar: ',1)[1].split('\n',1)[0])
            return json.dumps({'slides':[dict(s,elements=[{'type':'text','content':body}]) for s in batch]})
    monkeypatch.setattr(ai_agent,'_new_chat',lambda *a,**k:Chat())
    async def no_sleep(*a):pass
    monkeypatch.setattr(ai_agent.asyncio,'sleep',no_sleep)
    result=await ai_agent.generate_storyboard('retry-test',source,plan,{})
    assert 'foram recebidos 0' in prompts[1]
    assert 'gravar e sincronizar' in prompts[1]
    assert result['sourceCoverage']['status']=='generated'
    assert result['slides'][0]['elements'][0]['content']==body
