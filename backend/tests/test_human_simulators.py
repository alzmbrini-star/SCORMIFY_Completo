import copy
import json
import os
import unittest
from unittest.mock import patch
from services.human_simulators import validate_dialogue, render_dialogue


def dialogue_fixture():
    return {'profile':{'name':'Marina','role':'Analista','goal':'Entregar com clareza de prioridades',
        'constraint':'Duas demandas urgentes','opening':'Quero conversar sobre os últimos prazos.'},
        'metrics':['Confiança','Clareza','Compromisso'],
        'facts':[{'id':f'f{i}','text':f'Informação descoberta {i}'} for i in range(4)],
        'milestones':[{'title':f'Etapa {i}','factIds':[f'f{i}']} for i in range(3)],
        'turns':[{'title':f'Conversa {i}','openPrompt':f'Posso explicar o contexto {i}.',
            'guardedPrompt':f'Não estou à vontade para explicar o contexto {i}.',
            'choices':[{'label':f'Ação {i}.{q}', 'openResponse':f'Reação aberta {i}.{q}',
                'guardedResponse':f'Reação defensiva {i}.{q}', 'feedback':f'Consequência da estratégia {i}.{q}',
                'quality':q,'effects':[[-15,-5,0],[0,5,2],[15,10,10]][q],
                'reveals':[f'f{min(i,3)}'] if q==2 else (['f0'] if q==1 else []),
                'requiresFact':'f0' if i==1 and q==2 else ''} for q in range(3)]} for i in range(6)]}


def human_plan():
    return {'title':'Feedback corretivo com escuta','mission':'Entenda as causas e combine acompanhamento.',
        'debrief':'Compare a forma de perguntar com as reações e com o acordo alcançado.',
        'subtitle':'Conversa de desenvolvimento','briefing':'Investigue antes de propor uma solução.',
        'scene':'Escritório com colaboradora e líder','mechanism':'A confiança muda as reações e as informações disponíveis.',
        'controls':[{'label':'Escolher resposta','action':'Selecionar uma fala concreta'},
                    {'label':'Reiniciar','action':'Restaurar a conversa'}],
        'indicators':[{'label':'Confiança','meaning':'Disposição para conversar'}, {'label':'Compromisso','meaning':'Acordo alcançado'}],
        'learningDesign':{'kind':'human','audience':'Lideranças','difficulty':'Intermediário: investigar causas e negociar prioridades.',
            'courseConnection':'Feedback baseado em fatos observáveis e acompanhamento.', 'visualHierarchy':'Conversa à esquerda, decisões à direita.',
            'objectives':['Investigar as causas dos atrasos','Combinar acompanhamento verificável'],
            'stages':[{'title':f'Etapa {i}','challenge':f'Investigar aspecto {i}','consequence':f'Atualizar o entendimento {i}'} for i in range(6)],
            'endings':[{'label':'Acordo','condition':'Confiança e compreensão suficientes'},
                       {'label':'Ruptura','condition':'Abordagem acusatória persistente'}]}}


class HumanSimulatorTests(unittest.TestCase):
    def test_state_data_requires_meaningful_consequences_and_history(self):
        self.assertEqual(len(validate_dialogue(dialogue_fixture(),human_plan())['turns']),6)
        for invalid in ('effects','reactions','requires','condition'):
            bad=dialogue_fixture()
            if invalid=='effects':
                for c in bad['turns'][0]['choices']: c['effects']=[10,10,10]
            if invalid=='reactions': bad['turns'][0]['choices'][0]['guardedResponse']=bad['turns'][0]['choices'][0]['openResponse']
            if invalid=='requires': bad['turns'][0]['choices'][0]['requiresFact']='f0'
            if invalid=='condition':
                for t in bad['turns']:
                    for c in t['choices']: c['requiresFact']=''
            with self.assertRaises(ValueError): validate_dialogue(bad,human_plan())

    def test_offline_player_safely_embeds_text_and_preserves_agent_runtime(self):
        from services.ai_agent import _normalize_interactive_storyboard_slide, _wrap_interactive_fullbleed
        spec=human_plan(); data=validate_dialogue(dialogue_fixture(),spec)
        data['profile']['opening']='</script><img src=x onerror=alert(1)>'
        document=render_dialogue(data,spec)
        self.assertNotIn(data['profile']['opening'],document)
        self.assertNotIn('<img ',document)
        self.assertIn('data-human-simulator-version="1"',document)
        self.assertEqual(_wrap_interactive_fullbleed(document),document)
        self.assertEqual(_normalize_interactive_storyboard_slide({'type':'simulator','elements':[{'type':'html','htmlContent':document}]})['elements'][0]['htmlContent'],document)

    def test_human_generation_uses_verified_runtime_without_html_review_loop(self):
        import asyncio
        from services.visual_simulators import generate_visual_simulator
        calls=[]
        class Chat:
            def __init__(self,**kwargs): self.session=kwargs['session_id']
            def with_model(self,*args): return self
            def with_params(self,**kwargs): return self
            async def send_message(self,message):
                calls.append((self.session,message.text))
                if self.session.endswith('-plan'): return json.dumps(human_plan())
                if self.session.endswith('-dialogue'): return json.dumps(dialogue_fixture())
                raise AssertionError('Human simulation must not regenerate unverified HTML')
        with patch.dict(os.environ,{'OPENAI_API_KEY':'test-only','SIMULATOR_AI_PROVIDER':'openai'}), patch('services.visual_simulators.LlmChat',Chat):
            result=asyncio.run(generate_visual_simulator('Simulador de feedback corretivo','Curso: fatos observáveis e escuta.'))
        self.assertEqual(len(calls),2)
        self.assertIn('Curso: fatos observáveis e escuta.',calls[1][1])
        self.assertIn('data-human-simulator-version="1"',result['html'])


if __name__=='__main__': unittest.main()
