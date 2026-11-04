import ast,asyncio,json,unittest,time,threading
from collections import deque
from pathlib import Path
from unittest.mock import AsyncMock
from services.creator_guide import GUIDE,topics_for,search_topics
from services.creator_tutor import answer_question

EDITOR={'user_id':'author','role':'editor','permissions':{'createSimulators':False},'company':{'permissions':{'agentAccess':True}}}

class ProductGuide(unittest.TestCase):
    def test_guide_has_unique_ids_and_supported_internal_destinations(self):
        ids=[t['id'] for t in GUIDE];self.assertEqual(len(ids),len(set(ids)))
        for user in (EDITOR,dict(EDITOR,role='super_admin'),dict(EDITOR,role='company_admin')):
            for path in ('','/editor/project_123','//evil.invalid','/editor/<script>'):
                for topic in topics_for(user,path):
                    link=topic['link']
                    if link:self.assertTrue(link['href'].startswith(('/editor/','/admin?tab=','/agent','/?help=','/')))
                    if link:self.assertNotIn('evil.invalid',link['href'])
                    self.assertGreater(len(topic['steps']),0)
    def test_user_permissions_limit_topics_and_admin_links(self):
        topics=topics_for(EDITOR,'/editor/project_123');ids={t['id'] for t in topics}
        self.assertNotIn('simulators',ids);self.assertNotIn('users',ids);self.assertNotIn('costs',ids)
        self.assertIn('simulator-access',ids);self.assertIn('assessment',ids)
        self.assertIn('simulators',{t['id'] for t in topics_for(dict(EDITOR,permissions={'createSimulators':True}))})
        self.assertNotIn('costs',{t['id'] for t in topics_for(dict(EDITOR,role='company_admin'))})
        self.assertIn('users',{t['id'] for t in topics_for(dict(EDITOR,role='company_admin'))})
        approver=topics_for(dict(EDITOR,role='aprovador',permissions={'createSimulators':True}))
        self.assertTrue(all(t['target'] in ('agent','here') for t in approver))
    def test_editor_shortcuts_point_to_current_project_or_require_project_selection(self):
        topics={t['id']:t for t in topics_for(EDITOR,'/editor/project_123')}
        self.assertEqual(topics['export']['link']['href'],'/editor/project_123?help=export')
        self.assertEqual(topics['assessment']['link']['href'],'/editor/project_123?help=assessment')
        outside={t['id']:t for t in topics_for(EDITOR)}
        self.assertEqual(outside['export']['link']['href'],'/')
    def test_search_covers_media_permissions_and_export(self):
        topics=topics_for(dict(EDITOR,role='super_admin'))
        for question,expected in [('Como inserir um vídeo do Bunny?','video'),('Onde exportar SCORM?','export'),('Quero mudar a permissão dos usuários','users'),('Como ajustar a fonte e contraste do Tutor?','creator-help')]:
            self.assertIn(expected,[t['id'] for t in search_topics(question,topics)])

class TutorAnswers(unittest.IsolatedAsyncioTestCase):
    async def test_ai_cannot_supply_external_or_unauthorized_links(self):
        generate=AsyncMock(return_value=json.dumps({'answer':'Confira https://evil.invalid.','topicIds':['users','costs','https://evil.invalid','export']}))
        result=await answer_question('Como exportar SCORM?',EDITOR,'/editor/project_123',generate=generate)
        self.assertEqual(result['mode'],'ai');self.assertNotIn('evil.invalid',result['answer'])
        self.assertEqual(result['links'],[{'label':'Abrir Exportar HTML ou SCORM','href':'/editor/project_123?help=export'}])
        payload=generate.call_args.args[0]
        self.assertFalse(payload['simulatorCreationAllowed']);self.assertNotIn('user_id',payload)
        self.assertTrue(all(t['id'] not in ('costs','users') for t in payload['guide']))
    async def test_provider_failure_bad_json_and_missing_credentials_fall_back_to_named_guide(self):
        for generate in (AsyncMock(return_value=None),AsyncMock(return_value='broken JSON'),AsyncMock(side_effect=RuntimeError('secret-key-test'))):
            result=await answer_question('Como usar vídeo do Bunny?',EDITOR,generate=generate)
            self.assertEqual(result['mode'],'guide');self.assertIn('Bunny',result['answer']);self.assertNotIn('secret-key-test',result['answer'])
    async def test_history_is_bounded_and_no_mutation_or_course_content_is_required(self):
        history=[{'role':'user','content':'Exportar SCORM'}]*12
        original=json.dumps(EDITOR)
        generate=AsyncMock(return_value={'answer':'Abra Exportar e revise as opções.','topicIds':['export']})
        result=await answer_question('E depois?',EDITOR,'/editor/project_123',history,generate=generate)
        self.assertEqual(len(generate.call_args.args[0]['history']),8)
        self.assertEqual(json.dumps(EDITOR),original);self.assertNotIn('ops',result)

class RateLimits(unittest.TestCase):
    def test_rate_limit_is_per_authenticated_user_and_expires(self):
        source=Path(__file__).resolve().parents[1]/'routes/creator_tutor.py'
        node=next(n for n in ast.parse(source.read_text(encoding='utf-8')).body if isinstance(n,ast.FunctionDef) and n.name=='check_rate')
        class Error(Exception):
            def __init__(self,status_code,*args,**kwargs):self.status_code=status_code
        scope={'time':time,'_lock':threading.Lock(),'_calls':{},'deque':deque,'HTTPException':Error}
        exec(compile(ast.Module(body=[node],type_ignores=[]),str(source),'exec'),scope)
        for _ in range(12):scope['check_rate']('one')
        with self.assertRaises(Error) as caught:scope['check_rate']('one')
        self.assertEqual(caught.exception.status_code,429);scope['check_rate']('two')
        scope['_calls']['one']=deque([time.monotonic()-65]);scope['check_rate']('one')

if __name__=='__main__':unittest.main()
