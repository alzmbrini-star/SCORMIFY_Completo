"""Permission checks without a database, AI credits or full application boot."""
import ast,asyncio,copy,sys,unittest,uuid
from pathlib import Path
from types import SimpleNamespace,ModuleType
from unittest.mock import AsyncMock,patch
from services.simulator_permissions import can_create_simulators,permission_patch,restrict_config,restrict_structure,simulator_request
from test_html_generation_jobs import Jobs,HttpError

class SimulatorPolicy(unittest.TestCase):
    def test_legacy_access_explicit_denial_and_admin_override(self):
        self.assertFalse(can_create_simulators(None))
        self.assertTrue(can_create_simulators({'role':'editor'}))
        self.assertFalse(can_create_simulators({'permissions':{'createSimulators':False}}))
        self.assertTrue(can_create_simulators({'permissions':{'createSimulators':True}}))
        self.assertTrue(can_create_simulators({'roles':['editor','super_admin'],'permissions':{'createSimulators':False}}))
        self.assertFalse(can_create_simulators({'role':'company_admin','permissions':{'createSimulators':False}}))

    def test_admin_payload_is_boolean_allowlisted_and_cannot_change_other_permissions(self):
        self.assertEqual(permission_patch({'permissions':{'createSimulators':False}}),{'permissions.createSimulators':False})
        for value in (True,None,{'createSimulators':'true'},{'createSimulators':1},{'agentAccess':True}):
            with self.assertRaises(ValueError):permission_patch({'permissions':value})

    def test_agent_config_and_structure_restrict_saved_templates_without_mutating_original(self):
        user={'permissions':{'createSimulators':False}}
        config={'simulatorsAllowed':True,'enabledResources':{'simulator':True,'game':True},'visualCourseMode':'illustrated_journey'}
        old=copy.deepcopy(config);restricted=restrict_config(config,user)
        self.assertFalse(restricted['simulatorsAllowed']);self.assertFalse(restricted['enabledResources']['simulator']);self.assertTrue(restricted['enabledResources']['game']);self.assertEqual(config,old)
        structure={'modules':[{'slides':[{'type':'simulator','title':'Prática','elements':[{'htmlContent':'old'}]},{'type':'game'}]}]}
        result=restrict_structure(structure,user)
        self.assertEqual(result['modules'][0]['slides'][0],{'type':'content','title':'Prática'})
        self.assertEqual(structure['modules'][0]['slides'][0]['type'],'simulator')
        self.assertEqual(result['modules'][0]['slides'][1]['type'],'game')

    def test_editor_simulation_visualization_refinement_and_other_html(self):
        for request in ({'prompt':'Crie um simulador'},{'prompt':'Demonstração visual guiada'},{'prompt':'x','simulatorActivityType':'visualization'},{'prompt':'x','sourceSimulator':'{}'}):self.assertTrue(simulator_request(request))
        for prompt in ('Crie um quiz','Crie um estudo de caso','Crie um infográfico'):self.assertFalse(simulator_request({'prompt':prompt}))

class SimulatorJobGuards(Jobs):
    async def test_denied_job_never_queues_or_charges(self):
        api=ModuleType('fastapi');api.HTTPException=HttpError
        with patch.dict(sys.modules,{'fastapi':api}):
            for extra in ({},{'prompt':'Refinar arte','sourceSimulator':'{}'},{'prompt':'Explorar o tema','sourceSimulator':'','simulatorActivityType':'visualization'}):
                for key,value in extra.items():setattr(self.body,key,value)
                with self.assertRaises(HttpError) as caught:await self.start(dict(self.user,permissions={'createSimulators':False}))
                self.assertEqual(caught.exception.status_code,403)
        self.assertFalse(self.tasks);self.assertFalse(self.collection.docs)

class DirectGenerationGuards(unittest.IsolatedAsyncioTestCase):
    async def test_direct_editor_endpoint_and_agent_retry_deny_before_generation(self):
        source=Path(__file__).resolve().parents[1]/'routes/agent.py'
        names=('generate_html_with_ai','retry_simulator_diagnostic')
        nodes=[n for n in ast.parse(source.read_text(encoding='utf-8')).body if isinstance(n,ast.AsyncFunctionDef) and n.name in names]
        for n in nodes:n.decorator_list=[]
        scope=dict(GenerateHtmlRequest=object,SimulatorDiagnosticRetry=object,Depends=lambda _:None,require_auth=None,require_agent_access=None,HTTPException=HttpError,_html_generation_credentials=lambda:('fake-key','model'))
        exec(compile(ast.Module(body=nodes,type_ignores=[]),str(source),'exec'),scope)
        api=ModuleType('fastapi');api.HTTPException=HttpError
        denied={'user_id':'author','permissions':{'createSimulators':False}}
        with patch.dict(sys.modules,{'fastapi':api}):
            with self.assertRaises(HttpError) as caught:await scope['generate_html_with_ai'](SimpleNamespace(prompt='Crie um simulador',simulatorActivityType='simulation'),_user=denied)
            self.assertEqual(caught.exception.status_code,403)
            with self.assertRaises(HttpError) as caught:await scope['retry_simulator_diagnostic']('session',SimpleNamespace(slideIndex=0),denied)
            self.assertEqual(caught.exception.status_code,403)

class UserPermissionWrites(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.collection=SimpleNamespace(find_one=AsyncMock(),update_one=AsyncMock(),insert_one=AsyncMock(),count_documents=AsyncMock(return_value=0))
        self.scope=dict(Request=object,Dict=dict,Depends=lambda _:None,require_auth=None,require_company_admin=None,require_super_admin=None,HTTPException=HttpError,db=SimpleNamespace(users=self.collection,companies=SimpleNamespace(find_one=AsyncMock(return_value={'id':'one'}))),now_utc=lambda:'now',uuid=uuid)
        source=Path(__file__).resolve().parents[1]/'routes/users.py'
        nodes=[n for n in ast.parse(source.read_text(encoding='utf-8')).body if isinstance(n,ast.AsyncFunctionDef) and n.name in ('create_user','update_user')]
        for n in nodes:n.decorator_list=[]
        exec(compile(ast.Module(body=nodes,type_ignores=[]),str(source),'exec'),self.scope)
        auth=ModuleType('routes.auth');auth.has_role=lambda user,role: user.get('role')=='super_admin' or role==user.get('role') or role in user.get('roles',[])
        self.modules=patch.dict(sys.modules,{'routes.auth':auth});self.modules.start();self.addCleanup(self.modules.stop)
        self.target={'user_id':'target','role':'editor','companyId':'one'}
    async def update(self,actor,body):
        self.collection.find_one.side_effect=[copy.deepcopy(self.target),copy.deepcopy(self.target)]
        return await self.scope['update_user']('target',SimpleNamespace(json=AsyncMock(return_value=body)),actor)
    async def test_admin_can_grant_and_revoke_in_own_company(self):
        for value in (True,False):
            await self.update({'role':'company_admin','companyId':'one'},{'permissions':{'createSimulators':value}})
            self.assertEqual(self.collection.update_one.call_args.args[1]['$set']['permissions.createSimulators'],value)
    async def test_self_escalation_and_cross_company_changes_are_denied(self):
        for actor in ({'user_id':'target','role':'editor','companyId':'one'},{'role':'company_admin','companyId':'two'}):
            with self.assertRaises(HttpError) as caught:await self.update(actor,{'permissions':{'createSimulators':True}})
            self.assertEqual(caught.exception.status_code,403)
        self.collection.update_one.assert_not_awaited()
    async def test_new_user_defaults_disabled_and_admin_can_explicitly_enable(self):
        for permissions in (None,{'createSimulators':True}):
            self.collection.find_one.side_effect=None;self.collection.find_one.return_value=None
            body={'name':'Test author','email':'author@example.invalid','companyId':'one','roles':['editor']}
            if permissions is not None:body['permissions']=permissions
            result=await self.scope['create_user'](SimpleNamespace(json=AsyncMock(return_value=body)),{'role':'super_admin'})
            self.assertEqual(result['permissions']['createSimulators'],permissions is not None)

if __name__=='__main__':unittest.main()
