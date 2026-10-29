import asyncio
import copy
import json
import os
import unittest
from unittest.mock import patch

from services.visual_simulators import _generate_legacy_visual_simulator as generate_visual_simulator, validate_custom_plan, normalize_review_issues
from services.visual_simulators import apply_simulator_repairs
from services.visual_simulators import validate_simulator_candidate, SimulatorCandidateError
from test_visual_simulators import LOCK_PLAN, custom_document


class CustomRepairTests(unittest.TestCase):
    def test_literal_repairs_are_atomic_unambiguous_and_never_execute_code(self):
        source='<html><script>function calculate(){return 50;}</script></html>'
        response=json.dumps({'replacements':[{'old':'return 50;','new':'return tasks.reduce((sum,task)=>sum+task.duration,0);'}]})
        self.assertIn('tasks.reduce',apply_simulator_repairs(response,source))
        with self.assertRaisesRegex(ValueError,'única ocorrência'):
            apply_simulator_repairs(response,source.replace('return 50;','return 50;return 50;'))
        self.assertEqual(apply_simulator_repairs('```html\n'+source+'\n```',source),'```html\n'+source+'\n```')

    def test_independent_faults_are_reported_together_not_one_per_paid_repair(self):
        spec=validate_custom_plan(self.plan())
        document=custom_document(spec['title']).replace('</body>',
            '<img src="https://example.invalid/image.png"><script>function pending(){// Implementar lógica de cálculo\nreturn 50;}function edit(){prompt("Nome");alert("Salvo");}</script></body>')
        with self.assertRaises(SimulatorCandidateError) as captured:
            validate_simulator_candidate(document,spec)
        descriptions=' '.join(issue['issue'] for issue in captured.exception.issues)
        self.assertIn('externo',descriptions)
        self.assertIn('implementação adiada',descriptions)
        self.assertIn('prompt/alert/confirm',descriptions)
        self.assertEqual(len(captured.exception.issues),3)

    def plan(self):
        plan=copy.deepcopy(LOCK_PLAN)
        plan['title']='Desenvolvimento de Prompts Criativos'
        plan['learningDesign']['kind']='custom'
        plan['stateDesign']={'representation':'entities','initialState':'Rascunho vazio, nenhuma versão gerada.',
            'derivedIndicators':[{'label':indicator['label'],'source':'versões e rascunho','calculation':'Derivar do histórico de versões.'} for indicator in plan['indicators']],
            'checks':[{'actions':[action],'expected':'O estado e os controles refletem a mudança.'} for action in ['Criar rascunho','Gerar versão','Reiniciar']]}
        for control in plan['controls']:
            control['enabledWhen']='Depois de criar um rascunho não vazio.'
            control['stateChange']='Atualiza a versão atual e preserva o histórico.'
        return plan

    def test_open_mechanic_and_state_contract_preserved(self):
        plan=validate_custom_plan(self.plan())
        self.assertEqual(plan['learningDesign']['kind'],'custom')
        self.assertIn('enabledWhen',plan['controls'][0])
        self.assertIn('stateChange',plan['controls'][0])
        self.assertEqual(plan['stateDesign']['representation'],'entities')

    def test_state_design_maps_every_indicator_and_requires_acceptance_sequences(self):
        plan=self.plan()
        plan['stateDesign']['derivedIndicators'][0]['label']='Outro indicador'
        with self.assertRaisesRegex(ValueError,'corresponder exatamente'):
            validate_custom_plan(plan)
        plan=self.plan();plan['stateDesign']['checks']=[]
        with self.assertRaisesRegex(ValueError,'cenários de aceitação'):
            validate_custom_plan(plan)

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

    def test_incomplete_calculation_is_repaired_with_literal_patch_before_review(self):
        plan=self.plan()
        stub='function metric(){\n// Implementar lógica de cálculo\nreturn 50;\n}'
        document=custom_document(plan['title']).replace('</script>',stub+'</script>')
        class Chat:
            scenes=0
            reviews=0
            def __init__(self,**kwargs):self.session=kwargs['session_id']
            def with_model(self,*args):return self
            def with_params(self,**kwargs):return self
            async def send_message(self,message):
                if self.session.endswith('-plan'):return json.dumps(plan)
                if self.session.endswith('-scene'):
                    Chat.scenes+=1
                    if Chat.scenes==1:return document
                    self_test=json.loads(message.text)
                    assert 'implementação adiada' in self_test['repairError']
                    return json.dumps({'replacements':[{'old':stub,'new':'function metric(){return Number(level.value); }'}]})
                Chat.reviews+=1
                return json.dumps({'pass':True,'issues':[]})
        with patch.dict(os.environ,{'OPENAI_API_KEY':'test-only','SIMULATOR_AI_PROVIDER':'openai'}),patch('services.visual_simulators.LlmChat',Chat):
            result=asyncio.run(generate_visual_simulator('Oficina','Contexto do curso'))
        self.assertEqual(Chat.scenes,2)
        self.assertEqual(Chat.reviews,1)
        self.assertNotIn('Implementar lógica',result['html'])

    def test_diagnostic_scope_retains_all_rejected_documents_and_reviews(self):
        from services.simulator_diagnostics import diagnostic_scope
        plan=self.plan()
        saved=[]
        class Chat:
            def __init__(self,**kwargs):self.session=kwargs['session_id']
            def with_model(self,*args):return self
            def with_params(self,**kwargs):return self
            async def send_message(self,message):
                if self.session.endswith('-plan'):return json.dumps(plan)
                if self.session.endswith('-scene'):return custom_document(plan['title'])
                return json.dumps({'pass':False,'issues':[{'issue':'Indicador congelado','context':'Após ajustar a duração','action':'Atualizar o indicador a partir do estado'}]})
        with patch.dict(os.environ,{'OPENAI_API_KEY':'test-only','SIMULATOR_AI_PROVIDER':'openai'}),patch('services.visual_simulators.LlmChat',Chat),diagnostic_scope(saved.append):
            with self.assertRaisesRegex(ValueError,'Indicador congelado'):
                asyncio.run(generate_visual_simulator('Oficina de revisão de prompts','Gestão do Tempo'))
        failure=saved[-1]
        self.assertEqual(failure['status'],'failed')
        self.assertEqual(len(failure['attempts']),3)
        self.assertEqual(failure['attempts'][0]['document'],custom_document(plan['title']))
        self.assertIn('Indicador congelado',failure['attempts'][0]['review'])
        self.assertNotIn('test-only',json.dumps(failure))


if __name__=='__main__':unittest.main()
