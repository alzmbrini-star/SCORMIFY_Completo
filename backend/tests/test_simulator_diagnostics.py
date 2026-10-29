import asyncio
import copy
import ast
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock

from services.simulator_diagnostics import (capture_generation, diagnostic_scope,
    record_attempt, generation_key, simulator_request, simulator_sources, VERSION)


class DiagnosticTests(unittest.IsolatedAsyncioTestCase):
    async def test_saved_scene_json_is_recompiled_without_another_ai_call(self):
        from test_rule_visuals import sales_visual
        raw=sales_visual();scene=raw.pop('visual');scene['nodes'][10]['attrs']['x']=760;raw['mechanic']='finite-rules-v1'
        prior={'version':14,'status':'accepted','generationKey':generation_key('request','context',['p','m'],14),
               'plan':{'mechanic':'finite-rules-v1'},'result':{'spec':raw},'attempts':[{'document':json.dumps(scene)}]}
        generate=AsyncMock(side_effect=AssertionError('No additional AI call required'))
        saved=[]
        with diagnostic_scope(saved.append,[prior]):result=await capture_generation(generate,'request','context','session',['p','m'],enrich=AsyncMock(side_effect=lambda result,*args:result))
        generate.assert_not_awaited();self.assertEqual(result['spec']['verification']['visualMode'],'illustrated')
        self.assertTrue(result['spec']['verification']['visualRecompiled'])

    async def test_new_visual_checks_preserve_the_previous_rules(self):
        from test_rule_visuals import sales_visual
        raw=sales_visual();raw['visual']['nodes'][10]['attrs'].update(x=170,y=305)
        prior={'version':13,'status':'accepted','generationKey':generation_key('request','context',['p','m'],13),
               'plan':{'mechanic':'finite-rules-v1'},'result':{'spec':raw}}
        generate=AsyncMock(side_effect=AssertionError('Do not regenerate rules for an art error'))
        saved=[]
        with diagnostic_scope(saved.append,[prior]):result=await capture_generation(generate,'request','context','session',['p','m'])
        generate.assert_not_awaited();self.assertNotIn('visual',result['spec'])
        self.assertTrue(result['spec']['verification']['visualRevalidationRequired'])

    async def test_revalidated_logic_can_receive_only_the_missing_visual_layer(self):
        from test_rule_simulators import fixtures
        raw=fixtures()[0]
        prior={'version':12,'status':'accepted','generationKey':generation_key('request','context',['p','m'],12),
               'plan':{'mechanic':'finite-rules-v1'},'result':{'spec':raw}}
        generate=AsyncMock(side_effect=AssertionError('Do not regenerate rules'))
        async def enrich(result,*args):
            result['spec']['visualNotice']='Camada visual tratada separadamente'
            return result
        visual=AsyncMock(side_effect=enrich);saved=[]
        with diagnostic_scope(saved.append,[prior]):
            result=await capture_generation(generate,'request','context','session',['p','m'],enrich=visual)
        generate.assert_not_awaited();visual.assert_awaited_once()
        self.assertEqual(saved[-1]['result']['spec']['visualNotice'],result['spec']['visualNotice'])

    async def test_prior_json_is_recompiled_without_ai_only_for_exact_input_and_current_proof(self):
        from test_rule_simulators import fixtures
        raw=fixtures()[0]
        prior={'version':11,'status':'failed','generationKey':generation_key('request','context',['p','m'],11),
            'plan':{'mechanic':'finite-rules-v1'},'attempts':[{'document':json.dumps(raw),'truncated':False}]}
        saved=[];generate=AsyncMock(side_effect=AssertionError('Revalidation must not call or charge AI'))
        with diagnostic_scope(saved.append,[prior]):
            result=await capture_generation(generate,'request','context','session',['p','m'])
        generate.assert_not_awaited()
        self.assertEqual(saved[-1]['version'],VERSION)
        self.assertEqual(saved[-1]['status'],'accepted')
        self.assertIn('createRuleEngine',result['html'])
        self.assertEqual(result['spec']['verification']['revalidatedFromVersion'],11)
        self.assertTrue(result['spec']['verification']['noSingleActionShortcut'])
        for change in ('context','version','truncated','html','unsafe'):
            record=copy.deepcopy(prior)
            context='context'
            if change=='context':context='changed'
            elif change=='version':record['version']=7
            elif change=='truncated':record['attempts'][0]['truncated']=True
            elif change=='html':record['attempts'][0]['document']='<script>globalThis.executed=true</script>'
            else:
                invalid=copy.deepcopy(raw);invalid['actions'][0]['effects']['confianca']='eval(1)'
                record['attempts'][0]['document']=json.dumps(invalid)
            fresh=AsyncMock(return_value={'html':'fresh','spec':{}})
            with diagnostic_scope(saved.append,[record]):
                await capture_generation(fresh,'request',context,'session',['p','m'])
            fresh.assert_awaited_once()

    async def test_failure_preserves_source_and_structured_issues_without_approval(self):
        saved=[]
        issue={'issue':'O botão não atualiza o estado','context':'Adicionar tarefa > editar duração','action':'Renderizar após a alteração'}
        async def generate(*args):
            record_attempt('<html>reprovado</html>',{'title':'Cronograma'},[issue], 'Falha concreta', 'revisão')
            raise ValueError('Falha concreta')
        with diagnostic_scope(saved.append):
            with self.assertRaisesRegex(ValueError,'Falha concreta'):
                await capture_generation(generate,'{"title":"Montando Seu Cronograma"}','Gestão do Tempo','session_8',['openai','test'])
        self.assertEqual(saved[-1]['status'],'failed')
        self.assertEqual(saved[-1]['attempts'][0]['document'],'<html>reprovado</html>')
        self.assertEqual(saved[-1]['attempts'][0]['issues'],[issue])
        self.assertNotIn('result',saved[-1])
        self.assertEqual(saved[0]['status'],'running')

    async def test_only_exact_reviewed_result_is_reused_and_not_by_another_scope(self):
        result={'html':'<html>aprovado</html>','spec':{'title':'Cronograma'}}
        generate=AsyncMock(return_value=result)
        saved=[]
        with diagnostic_scope(saved.append):
            await capture_generation(generate,'pedido','contexto','session_1',['openai','test'])
        cached=saved[-1]
        self.assertEqual(cached['status'],'accepted')
        with diagnostic_scope(saved.append,[cached]):
            reused=await capture_generation(generate,'pedido','contexto','session_1',['openai','test'])
            reused['spec']['title']='alterado'
            self.assertEqual(cached['result']['spec']['title'],'Cronograma')
            self.assertEqual(generate.await_count,1)
            await capture_generation(generate,'pedido','outro contexto','session_1',['openai','test'])
        self.assertEqual(generate.await_count,2)
        with diagnostic_scope(saved.append):
            await capture_generation(generate,'pedido','contexto','session_1',['openai','test'])
        self.assertEqual(generate.await_count,3)
        for invalid in [dict(cached,status='failed'),dict(cached,truncated=True),dict(cached,version=0)]:
            with diagnostic_scope(saved.append,[invalid]):
                await capture_generation(generate,'pedido','contexto','session_1',['openai','test'])
        self.assertEqual(generate.await_count,6)

    async def test_concurrent_captures_do_not_mix_documents(self):
        saved=[]
        async def generate(prompt,*args):
            await asyncio.sleep(0)
            record_attempt(prompt,{},[],review=prompt)
            return {'html':prompt,'spec':{}}
        with diagnostic_scope(saved.append):
            await asyncio.gather(*(capture_generation(generate,p,'context',p,['provider','model']) for p in ('one','two')))
        final=[record for record in saved if record['status']=='accepted']
        self.assertEqual(len(final),2)
        for record in final:
            self.assertEqual(record['attempts'][0]['document'],record['result']['html'])

    def test_retry_request_matches_storyboard_context_and_slide_index(self):
        session={'structure':{'modules':[{'title':'Planejamento','slides':[{'type':'content'},
            {'title':'Montando Seu Cronograma','type':'simulator','purpose':'Planejar tarefas'}]}]},
            'config':{'title':'Gestão do Tempo','depth':'intermediario'},'contentText':'Prazo, foco e prioridades.'}
        sources=simulator_sources(session)
        self.assertEqual(sources[0][0],1)
        prompt,context=simulator_request(sources[0][1],session['contentText'],session['config'])
        self.assertEqual(json.loads(context)['module'],'Planejamento')
        self.assertEqual(json.loads(prompt)['title'],'Montando Seu Cronograma')
        self.assertNotEqual(generation_key(prompt,context,['a','b']),generation_key(prompt,context,['a','c']))


class DiagnosticRouteTests(unittest.IsolatedAsyncioTestCase):
    def namespace(self):
        source=Path(__file__).resolve().parents[1]/'routes/agent.py'
        tree=ast.parse(source.read_text(encoding='utf-8'))
        names={'_owned_diagnostic_session','get_simulator_diagnostics','_simulator_diagnostic_sink'}
        nodes=[node for node in tree.body if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and node.name in names]
        for node in nodes:
            node.decorator_list=[]
        class HttpError(Exception):
            def __init__(self,status,detail):self.status_code=status;super().__init__(detail)
        from datetime import datetime,timezone,timedelta
        ns={'db':SimpleNamespace(agent_sessions=SimpleNamespace(find_one=AsyncMock(return_value=None))),
            'HTTPException':HttpError,'Depends':lambda x:None,'require_agent_access':None,
            'datetime':datetime,'timezone':timezone,'timedelta':timedelta}
        exec(compile(ast.Module(body=nodes,type_ignores=[]),str(source),'exec'),ns)
        return ns

    async def test_other_owner_cannot_access_diagnostics(self):
        ns=self.namespace()
        with self.assertRaises(ns['HTTPException']) as caught:
            await ns['_owned_diagnostic_session']('session',{'user_id':'other'})
        self.assertEqual(caught.exception.status_code,404)
        ns['db'].agent_sessions.find_one.assert_awaited_once_with({'id':'session','userId':'other'},{'_id':0})

    async def test_diagnostics_are_bounded_private_and_no_source_in_polling(self):
        ns=self.namespace()
        ns['db'].agent_sessions.find_one.return_value={'id':'session','userId':'owner'}
        cursor=Mock();cursor.sort.return_value=cursor;cursor.limit.return_value=cursor;cursor.to_list=AsyncMock(return_value=[])
        ns['db'].simulator_diagnostics=SimpleNamespace(find=Mock(return_value=cursor))
        ns['db'].simulator_diagnostic_runs=SimpleNamespace(find_one=AsyncMock(return_value=None))
        await ns['get_simulator_diagnostics']('session',False,{'user_id':'owner'})
        query,projection=ns['db'].simulator_diagnostics.find.call_args.args
        self.assertEqual(query['ownerId'],'owner')
        self.assertIn('expiresAt',query)
        self.assertEqual(projection['attempts.document'],0)
        self.assertEqual(projection['result'],0)
        cursor.limit.assert_called_once_with(3)

    async def test_finished_record_recovers_running_status_without_running_again(self):
        ns=self.namespace()
        now=ns['datetime'].now(ns['timezone'].utc)
        ns['db'].agent_sessions.find_one.return_value={'id':'session','userId':'owner'}
        terminal={'status':'failed','generatorSessionId':'session_visual_simulator_8','updatedAt':now,'error':'Indicador constante'}
        cursor=Mock();cursor.sort.return_value=cursor;cursor.limit.return_value=cursor;cursor.to_list=AsyncMock(return_value=[terminal])
        ns['db'].simulator_diagnostics=SimpleNamespace(find=Mock(return_value=cursor))
        ns['db'].simulator_diagnostic_runs=SimpleNamespace(find_one=AsyncMock(return_value={
            'status':'running','slideIndex':8,'runId':'run','updatedAt':now-ns['timedelta'](minutes=1)}),update_one=AsyncMock())
        result=await ns['get_simulator_diagnostics']('session',False,{'user_id':'owner'})
        self.assertEqual(result['run']['status'],'failed')
        self.assertEqual(result['run']['error'],'Indicador constante')
        ns['db'].simulator_diagnostic_runs.update_one.assert_awaited_once()

    def test_private_sink_has_expiry_and_never_modifies_storyboard_or_structure(self):
        ns=self.namespace()
        collection=Mock();database=SimpleNamespace(simulator_diagnostics=collection)
        record={'generationKey':'hash','version':VERSION,'status':'failed','attempts':[]}
        ns['_simulator_diagnostic_sink'](database,{'id':'session','userId':'owner'})(record)
        query,stored=collection.replace_one.call_args.args
        self.assertEqual(query,{'_id':'session:hash'})
        self.assertEqual(stored['ownerId'],'owner')
        self.assertEqual((stored['expiresAt']-stored['updatedAt']).days,7)
        self.assertNotIn('structure',stored)
        self.assertNotIn('storyboard',stored)


if __name__=='__main__':unittest.main()
