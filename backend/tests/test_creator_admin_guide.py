import json
from unittest.mock import AsyncMock
import pytest
from services.creator_guide import topics_for,search_topics
from services.creator_tutor import answer_question

def user(role):return {'user_id':'test','role':role,'company':{'permissions':{'agentAccess':True}}}

@pytest.mark.parametrize('role',['company_admin','super_admin'])
def test_admin_can_find_batch_export_with_the_exact_deep_link(role):
    topics=topics_for(user(role),'/editor/my-course')
    topic=next(t for t in topics if t['id']=='batch-export')
    assert topic['link']['href']=='/admin?tab=batch_export'
    assert any('100 cursos' in s for s in topic['steps'])
    assert any('Cada curso' in s and 'ZIP' in s for s in topic['steps'])
    for query in ['Onde exportar em massa?','Posso exportar vários cursos de uma vez?','Exportar SCORM em lote na Administração','Exportar todos os cursos de uma só vez']:
        assert search_topics(query,topics)[0]['id']=='batch-export'

def test_company_admin_only_sees_its_administrative_options():
    topics={t['id']:t for t in topics_for(user('company_admin'))}
    assert {'users','admin-overview','admin-game-bank','student-tutor','admin-reports','admin-tutor-dashboard','batch-export'}<=topics.keys()
    assert not {'companies','costs','admin-integrations','admin-migration','admin-cleanup','batch-export-access'}&topics.keys()

def test_super_admin_has_guides_for_every_actual_admin_tab():
    actions={t['action'] for t in topics_for(user('super_admin')) if t['target']=='admin'}
    assert {'companies','users','game_questions','tutor','reports','tutor_dashboard','integrations_health','cost_report','data_migration','plates_cleanup','batch_export'}<=actions

@pytest.mark.parametrize('role',['editor','aprovador'])
def test_other_roles_learn_that_batch_exists_without_an_admin_shortcut(role):
    topics=topics_for(user(role))
    assert not any(t['target']=='admin' for t in topics)
    topic=search_topics('Exportar cursos em lote',topics)[0]
    assert topic['id']=='batch-export-access'
    assert topic['link'] is None

@pytest.mark.asyncio
async def test_stale_history_or_model_cannot_deny_the_verified_batch_workflow():
    model=AsyncMock(return_value=json.dumps({'answer':'Não existe exportação em lote.','topicIds':['export']}))
    result=await answer_question('Como exportar cursos em massa?',user('company_admin'),history=[{'role':'assistant','content':'Só pode exportar individualmente.'}],generate=model)
    assert 'Sim, existe exportação em lote' in result['answer']
    assert result['links'][0]['href']=='/admin?tab=batch_export'
    assert result['mode']=='guide'
    assert 'IA indisponível' not in result['answer']
    model.assert_not_called()

@pytest.mark.asyncio
async def test_editor_does_not_receive_an_admin_link_or_model_call():
    model=AsyncMock()
    result=await answer_question('Onde exportar cursos em lote?',user('editor'),generate=model)
    assert 'possui exportação SCORM em lote' in result['answer']
    assert 'Solicite a um administrador' in result['answer']
    assert not result['links'];model.assert_not_called()
