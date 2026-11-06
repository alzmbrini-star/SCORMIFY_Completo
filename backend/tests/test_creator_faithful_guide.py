from unittest.mock import AsyncMock
import pytest
from services.creator_guide import topics_for,search_topics
from services.creator_tutor import answer_question

AUTHOR={'role':'editor','company':{'permissions':{'agentAccess':True}}}

@pytest.mark.parametrize('question',['Posso usar o MODO FIEL para fazer isso pelo Agente?','Como converter um PDF preservando o layout original?','Modo fiel converte PPTX?','Gerar em modo fiel recria textos editáveis?'])
def test_faithful_questions_retrieve_the_specific_verified_workflow(question):
    topic=search_topics(question,topics_for(AUTHOR))[0]
    assert topic['id']=='agent-faithful'
    assert topic['link']['href']=='/agent'

@pytest.mark.asyncio
async def test_stale_denial_cannot_override_the_faithful_guide_or_spend_ai_credits():
    generate=AsyncMock(return_value={'answer':'O Modo Fiel não é mencionado no guia.','topicIds':['agent']})
    result=await answer_question('Posso usar MODO FIEL pelo Agente?',AUTHOR,'/editor/project1',history=[{'role':'assistant','content':'Não posso confirmar o Modo Fiel.'}],generate=generate)
    assert 'Sim, o Agente permite converter um PDF' in result['answer']
    assert 'imagem de fundo' in result['answer']
    assert 'não exige reescrever' in result['answer']
    assert 'Não promete transformar' in result['answer']
    assert result['links'][0]['href']=='/agent'
    assert result['mode']=='guide';generate.assert_not_called()

@pytest.mark.asyncio
async def test_user_without_agent_access_gets_an_explanation_not_a_privileged_link():
    generate=AsyncMock()
    result=await answer_question('Onde usar o modo fiel?',{'role':'editor','company':{'permissions':{}}},generate=generate)
    assert 'não tem acesso autorizado' in result['answer']
    assert not result['links'];generate.assert_not_called()
