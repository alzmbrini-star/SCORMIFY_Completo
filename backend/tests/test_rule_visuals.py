import asyncio
import copy
import json
import unittest
from unittest.mock import patch
from services.rule_simulators import validate_rules,render_rules,transition,trace_rules,single_action_shortcuts
from services.rule_visuals import validate_visual,visual_state,generate_visual,upgrade_visual_document
from test_rule_simulators import fixtures,base,var,action,op,ref


def shape(key,kind,label,attrs,**kwargs):return dict(id=key,type=kind,label=label,attrs=attrs,**kwargs)
def binding(prop,key,lo,hi,a,b):return dict(property=prop,var=key,input=[lo,hi],output=[a,b])


def lock_fixture():
    data=base('Travessia por uma eclusa didática',
        [var('nivel','Nível da câmara',0,2,'etapas'),var('entrada','Comporta de entrada',0,1),
         var('saida','Comporta de saída',0,1),var('barco','Posição do barco',0,2),var('risco','Alerta de segurança',0,1)],
        [action('abrir_entrada','Abrir entrada',op('all',op('eq',ref('nivel'),0),op('eq',ref('barco'),0)),{'entrada':1}),
         action('entrar','Entrar na câmara',op('all',op('eq',ref('entrada'),1),op('eq',ref('barco'),0)),{'barco':1}),
         action('fechar','Fechar entrada',op('eq',ref('barco'),1),{'entrada':0}),
         action('elevar','Encher câmara',op('all',op('eq',ref('entrada'),0),op('eq',ref('barco'),1),op('eq',ref('saida'),0)),{'nivel':2}),
         action('abrir_saida','Abrir saída',op('all',op('eq',ref('nivel'),2),op('eq',ref('barco'),1)),{'saida':1}),
         action('sair','Avançar barco',op('all',op('eq',ref('saida'),1),op('eq',ref('nivel'),2),op('eq',ref('barco'),1)),{'barco':2}),
         action('forcar','Forçar travessia sem equalizar',True,{'risco':1})],
        op('all',op('eq',ref('barco'),2),op('eq',ref('nivel'),2)),op('eq',ref('risco'),1),
        ['abrir_entrada','entrar','fechar','elevar','abrir_saida','sair'],['forcar'],'process')
    data['scenes']=[dict(id='concluido',when=op('eq',ref('barco'),2),title='Travessia concluída',description='O barco chegou à bacia superior.',facts=['Compare os níveis e a posição das comportas.']),
        dict(id='elevado',when=op('eq',ref('nivel'),2),title='Câmara elevada',description='A água e o barco subiram juntos; a entrada permanece fechada.',facts=['Observe a nova altura da superfície.']),
        dict(id='inicio',when=True,title='Prepare a travessia',description='Observe as superfícies da água e opere os controles.',facts=['Modelo didático simplificado, não destinado a operações reais.'])]
    nodes=[shape('ceu','rect','Céu',dict(x=0,y=0,width=800,height=450,fill='#102e49')),
        shape('nuvem','ellipse','Nuvem',dict(x=130,y=65,rx=90,ry=20,fill='#4a6e8a')),
        shape('margem','path','Estrutura da eclusa',dict(d='M0 370 H800 V450 H0 Z',fill='#536f78')),
        shape('agua_baixa','rect','Água da bacia inferior',dict(x=0,y=330,width=254,height=40,fill='#29b8df')),
        shape('agua_alta','rect','Água da bacia superior',dict(x=546,y=210,width=254,height=160,fill='#29b8df')),
        shape('agua_camara','rect','Água da câmara; altura real do modelo',dict(x=270,y=330,width=260,height=40,fill='#54d9ee'),bindings=[binding('y','nivel',0,2,330,210),binding('height','nivel',0,2,40,160)]),
        shape('gate_in','rect','Comporta de entrada; clique para abrir',dict(x=254,y=170,width=16,height=200,fill='#ffcc67'),bindings=[binding('height','entrada',0,1,200,30)],action='abrir_entrada'),
        shape('gate_out','rect','Comporta de saída; clique para abrir',dict(x=530,y=170,width=16,height=200,fill='#ffcc67'),bindings=[binding('height','saida',0,1,200,30)],action='abrir_saida'),
        shape('barco_grupo','group','Barco acompanhando posição e nível',dict(x=30,y=310),bindings=[binding('x','barco',0,2,30,650),binding('y','nivel',0,2,310,190)]),
        shape('casco','polygon','Casco do barco',dict(points=[[0,0],[110,0],[94,32],[20,32]],fill='#ffa24a'),parent='barco_grupo'),
        shape('cabine','rect','Cabine',dict(x=30,y=-28,width=48,height=28,rx=5,fill='#f5fbff'),parent='barco_grupo'),
        shape('janela','rect','Janela',dict(x=42,y=-20,width=24,height=12,fill='#356783'),parent='barco_grupo'),
        shape('bacia1','text','Bacia inferior',dict(x=25,y=415,text='Bacia inferior',fontSize=28,fill='#ffffff')),
        shape('bacia2','text','Câmara',dict(x=310,y=415,text='Câmara',fontSize=28,fill='#ffffff')),
        shape('bacia3','text','Bacia superior',dict(x=570,y=415,text='Bacia superior',fontSize=28,fill='#ffffff')),
        shape('valor','text','Nível atual da câmara',dict(x=300,y=135,text='Nível: {nivel}',fontSize=30,fill='#ffffff')),
        shape('warning','group','Alerta: operação insegura',dict(x=270,y=30),visibleWhen=op('eq',ref('risco'),1)),
        shape('warning_bg','rect','Alerta',dict(x=0,y=0,width=450,height=60,rx=8,fill='#8e2535'),parent='warning'),
        shape('warning_text','text','Operação insegura',dict(x=15,y=40,text='Operação insegura',fontSize=30,fill='#ffffff'),parent='warning')]
    data['visual']=dict(version=1,title='Eclusa com cena reativa',description='A água, o barco e as comportas acompanham as decisões. Esquema didático com níveis discretos, sem precisão de engenharia.',background='#102e49',nodes=nodes)
    return data


def sales_visual():
    data=fixtures()[0]
    data['visual']=dict(version=1,title='Conversa consultiva',description='Documentos são revelados pela investigação; a expressão do cliente acompanha a confiança e o acordo aparece na mesa.',background='#163b55',nodes=[
        shape('parede','rect','Sala de reunião',dict(x=0,y=0,width=800,height=450,fill='#163b55')),
        shape('janela','rect','Janela',dict(x=60,y=35,width=240,height=150,rx=12,fill='#7dc7dd')),
        shape('mesa','rect','Mesa',dict(x=80,y=330,width=640,height=50,rx=12,fill='#b27f55')),
        shape('corpo','rect','Cliente',dict(x=490,y=180,width=150,height=150,rx=30,fill='#5a9eab')),
        shape('cabeca','circle','Rosto do cliente',dict(x=565,y=160,r=58,fill='#efbd91')),
        shape('olho1','circle','Olho',dict(x=545,y=150,r=5,fill='#163b55')),
        shape('olho2','circle','Olho',dict(x=585,y=150,r=5,fill='#163b55')),
        shape('boca','path','Expressão conforme confiança',dict(d='M540 185 Q565 205 590 185',fill='none',stroke='#163b55',strokeWidth=5),states=[dict(when=op('eq',ref('confianca'),0),set={'d':'M540 197 Q565 175 590 197'})]),
        shape('papel','rect','Documento revelado pela investigação',dict(x=170,y=230,width=160,height=95,rx=8,fill='#ffffff'),bindings=[binding('height','descoberta',0,2,15,95)]),
        shape('acordo','text','Resultado da negociação',dict(x=170,y=305,text='Em análise',fontSize=28,fill='#163b55'),states=[dict(when=op('eq',ref('acordo'),1),set={'text':'Acordo'})]),
        shape('cliente','text','Cliente',dict(x=500,y=425,text='Cliente',fontSize=30,fill='#ffffff'))])
    return data


class VisualTests(unittest.TestCase):
    def test_nested_groups_compile_without_inventing_rules_or_bindings(self):
        raw=sales_visual();flat=copy.deepcopy(raw['visual']);nested=copy.deepcopy(flat)
        nested['nodes']=[{'id':'room','type':'group','x':0,'y':0,'nodes':nested['nodes']}]
        logic=dict(raw);logic.pop('visual');data=validate_rules(logic)
        scene=validate_visual(nested,data)
        self.assertEqual(len(scene['nodes']),len(flat['nodes'])+1)
        self.assertEqual(scene['nodes'][1]['parent'],'room')
        self.assertEqual(scene['nodes'][1]['attrs'],flat['nodes'][0]['attrs'])
        annotated=copy.deepcopy(flat);annotated['nodes'][10]['parent']='mesa'
        scene=validate_visual(annotated,data)
        self.assertEqual(next(n for n in scene['nodes'] if n['id']=='cliente')['parent'],'container_0')
        self.assertEqual(next(n for n in scene['nodes'] if n['id']=='mesa')['parent'],'container_0')
        self.assertEqual(next(n for n in scene['nodes'] if n['id']=='cliente')['attrs']['x'],500)
        bad=lock_fixture();bad['visual']['nodes'][5]['attrs']['y']=440
        bad['visual']['nodes'][5]['bindings']=[binding('height','nivel',0,2,40,160)]
        with self.assertRaisesRegex(ValueError,'fora do canvas'):validate_rules(bad)

    def test_different_subjects_share_one_graph_and_unchanged_rule_engine(self):
        for raw in (lock_fixture(),sales_visual()):
            data=validate_rules(raw);without=dict(raw);without.pop('visual')
            logic=validate_rules(without)
            self.assertEqual(data['checks'],logic['checks'])
            self.assertEqual(single_action_shortcuts(data),[])
            for check in data['checks']:
                initial={v['id']:v['initial'] for v in data['variables']}
                final=trace_rules(data,check['actions'])['expected']
                self.assertNotEqual(visual_state(data['visual'],initial),visual_state(data['visual'],final))
            document=render_rules(data)
            self.assertIn('scormify-rule-visual-v1',document)
            self.assertIn('scormify:rules-state',document)
            self.assertEqual(upgrade_visual_document(document),document)

    def test_physical_projection_uses_the_actual_state(self):
        data=validate_rules(lock_fixture());initial={v['id']:v['initial'] for v in data['variables']}
        state=dict(initial)
        for key in ['abrir_entrada','entrar','fechar','elevar']:
            state=transition(data,state,next(a for a in data['actions'] if a['id']==key))
        byid={n['id']:n for n in visual_state(data['visual'],state)}
        self.assertEqual(byid['agua_camara']['attrs']['y'],210)
        self.assertEqual(byid['barco_grupo']['attrs']['y'],190)
        self.assertEqual(byid['gate_in']['attrs']['height'],200)
        self.assertFalse(byid['warning']['visible'])
        self.assertEqual(initial['nivel'],0)

    def test_unsafe_unknown_and_decorative_graphs_are_rejected(self):
        raw=lock_fixture();logic=dict(raw);logic.pop('visual');data=validate_rules(logic)
        for mutate in (
            lambda v:v['nodes'][0].update(type='script'),
            lambda v:v['nodes'][0]['attrs'].update(onload='alert(1)'),
            lambda v:v['nodes'][0]['attrs'].update(fill='url(https://tracker)'),
            lambda v:v['nodes'][2]['attrs'].update(d='<script>'),
            lambda v:v['nodes'][5]['bindings'][0].update(var='missing'),
            lambda v:v['nodes'][5]['bindings'][0].update(input=[0,0]),
            lambda v:v['nodes'][0].update(parent='casco'),
            lambda v:v['nodes'][0]['attrs'].update(width=float('inf')),
            lambda v:v.update(nodes=v['nodes']*10),
        ):
            candidate=copy.deepcopy(raw['visual']);mutate(candidate)
            with self.assertRaises((ValueError,TypeError)):validate_visual(candidate,data)
        decorative=copy.deepcopy(raw['visual'])
        for n in decorative['nodes']:n.pop('bindings',None);n.pop('states',None);n.pop('visibleWhen',None)
        with self.assertRaisesRegex(ValueError,'variáveis causais'):validate_visual(decorative,data)

    def test_visual_repair_does_not_regenerate_logic_and_fallback_is_explicit(self):
        data=validate_rules(lock_fixture());calls=[]
        class Chat:
            def __init__(self,**kwargs):calls.append(kwargs)
            def with_model(self,*args):return self
            def with_params(self,**kwargs):return self
            async def send_message(self,message):return json.dumps(data['visual']) if len(calls)>1 else '{}'
        with patch('emergentintegrations.llm.chat.LlmChat',Chat):
            visual,notice=asyncio.run(generate_visual(data,'tema','conteúdo','qa','openai','test','test'))
        self.assertIsNotNone(visual);self.assertFalse(notice);self.assertEqual(len(calls),2)
        class Broken(Chat):
            async def send_message(self,message):raise RuntimeError('Service unavailable')
        with patch('emergentintegrations.llm.chat.LlmChat',Broken):
            visual,notice=asyncio.run(generate_visual(data,'tema','conteúdo','qa','openai','test','test'))
        self.assertIsNone(visual);self.assertIn('diagrama conceitual',notice)


if __name__=='__main__':unittest.main()
