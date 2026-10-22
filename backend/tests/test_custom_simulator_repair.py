import asyncio
import copy
import json
import os
import unittest
from unittest.mock import patch

from services.visual_simulators import generate_visual_simulator, validate_custom_plan, normalize_review_issues
from test_visual_simulators import LOCK_PLAN, custom_document


class CustomRepairTests(unittest.TestCase):
    def plan(self):
        plan=copy.deepcopy(LOCK_PLAN)
        plan['title']='Desenvolvimento de Prompts Criativos'
        plan['learningDesign']['kind']='custom'
        for control in plan['controls']:
            control['enabledWhen']='Depois de criar um rascunho não vazio.'
            control['stateChange']='Atualiza a versão atual e preserva o histórico.'
        return plan

    def test_open_mechanic_and_state_contract_preserved(self):
        plan=validate_custom_plan(self.plan())
        self.assertEqual(plan['learningDesign']['kind'],'custom')
        self.assertIn('enabledWhen',plan['controls'][0])
        self.assertIn('stateChange',plan['controls'][0])

    def test_repair_receives_exact_document_structured_diagnostics_and_original_context(self):
        plan=self.plan()
        document=custom_document(plan['title'])
        issue={'issue':'Botão Gerar Resultado não é habilitado.',
               'context':'Criar rascunho > gerar: render não atualiza disabled.',
               'action':'Chamar updateControls depois de atualizar o rascunho.'}
        class Chat:
            repairs=[]
            reviews=0
            def __init__(self,**kwargs):self.session=kwargs['session_id']
            def with_model(self,*args):return self
            def with_params(self,**kwargs):return self
            async def send_message(self,message):
                if self.session.endswith('-plan'):return json.dumps(plan)
                if self.session.endswith('-scene'):
                    Chat.repairs.append(json.loads(message.text))
                    return document
                Chat.reviews+=1
                return json.dumps({'pass':Chat.reviews>1,'issues':[issue] if Chat.reviews==1 else []})
        with patch.dict(os.environ,{'OPENAI_API_KEY':'test-only','SIMULATOR_AI_PROVIDER':'openai'}),patch('services.visual_simulators.LlmChat',Chat):
            result=asyncio.run(generate_visual_simulator('Oficina livre de prompts','Curso de criatividade e revisão de prompts.'))
        self.assertEqual(result['spec']['learningDesign']['kind'],'custom')
        self.assertEqual(len(Chat.repairs),2)
        repair=Chat.repairs[1]
        self.assertEqual(repair['previousDocument'],document)
        self.assertEqual(repair['repairIssues'],[issue])
        self.assertEqual(repair['request'],'Oficina livre de prompts')
        self.assertIn('criatividade',repair['courseContext'])
        self.assertNotIn("{'issue'",repair['repairError'])
        self.assertIn('não apenas remova disabled',repair['repairInstruction'])

    def test_rejected_review_never_silently_inserted(self):
        plan=self.plan()
        class Chat:
            renders=0
            def __init__(self,**kwargs):self.session=kwargs['session_id']
            def with_model(self,*args):return self
            def with_params(self,**kwargs):return self
            async def send_message(self,message):
                if self.session.endswith('-plan'):return json.dumps(plan)
                if self.session.endswith('-scene'):
                    Chat.renders+=1
                    return custom_document(plan['title'])
                return json.dumps({'pass':False,'issues':[{'issue':'Controle bloqueado permanentemente.','action':'Corrigir condição de habilitação.'}]})
        with patch.dict(os.environ,{'OPENAI_API_KEY':'test-only','SIMULATOR_AI_PROVIDER':'openai'}),patch('services.visual_simulators.LlmChat',Chat):
            with self.assertRaisesRegex(ValueError,'Controle bloqueado permanentemente'):
                asyncio.run(generate_visual_simulator('Oficina de prompts'))
        self.assertEqual(Chat.renders,3)

    def test_review_issues_normalized_for_legacy_and_bad_review(self):
        self.assertEqual(normalize_review_issues(['Erro concreto'])[0]['issue'],'Erro concreto')
        self.assertTrue(normalize_review_issues(None)[0]['issue'])


if __name__=='__main__':unittest.main()
