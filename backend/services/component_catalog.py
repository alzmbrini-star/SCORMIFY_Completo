"""Versioned trusted visual primitives, not simulator templates or generated code.

All geometry is maintained in source. Inputs only project an existing variable
or a constant; component actions only name an existing interpreter action.
"""
from copy import deepcopy

CATALOG_VERSION = 2
SUPPORTED_CATALOGS = (1, 2)
COMPONENTS = {
    'liquid_vessel': {'version': 1, 'size': [220, 250],
        'description': 'Recipiente com superfície e volume de líquido.',
        'inputs': ['level'], 'actions': [], 'representation': 'schematic'},
    'lift_gate': {'version': 1, 'size': [100, 250],
        'description': 'Barreira vertical com abertura observável.',
        'inputs': ['opening'], 'actions': ['activate'], 'representation': 'schematic'},
    'floating_carrier': {'version': 1, 'size': [260, 250],
        'description': 'Embarcação com deslocamento horizontal e elevação.',
        'inputs': ['position', 'elevation'], 'actions': [], 'representation': 'schematic'},
    'status_marker': {'version': 1, 'size': [100, 100],
        'description': 'Sinal visual de condição do modelo, sem unidade física.',
        'inputs': ['severity'], 'actions': [], 'representation': 'symbolic'},
}
V1_COMPONENTS = frozenset(COMPONENTS)
COMPONENTS.update({
    'harbor_backdrop': {'version':1,'introducedIn':2,'size':[760,410],'inputs':[],'actions':[],
        'description':'Ambiente de navegação com margens, relevo e infraestrutura.','representation':'contextual'},
    'lock_channel': {'version':1,'introducedIn':2,'size':[760,300],'inputs':['level','entry','exit','position','risk'],'actions':['entry','exit'],
        'actionInputs':{'entry':['entry'],'exit':['exit']},
        'description':'Câmara, bacias, embarcação e comportas integradas; esquema discreto.','representation':'schematic'},
    'workplace_backdrop': {'version':1,'introducedIn':2,'size':[760,410],'inputs':[],'actions':[],
        'description':'Sala de trabalho com janela, cidade, mobiliário e mesa em perspectiva.','representation':'contextual'},
    'meeting_table': {'version':1,'introducedIn':2,'size':[650,105],'inputs':[],'actions':[],
        'description':'Mesa de reunião em primeiro plano para composição com personagens.','representation':'contextual'},
    'conversation_person': {'version':1,'introducedIn':2,'size':[220,300],'inputs':['engagement'],'actions':[],
        'variants':['short_hair','long_hair'],'description':'Pessoa com gestos e expressão em três estados qualitativos.','representation':'illustrative'},
    'evidence_folder': {'version':1,'introducedIn':2,'size':[230,160],'inputs':['review','agreement'],'actions':['inspect'],
        'actionInputs':{'inspect':['review']},
        'description':'Documentos consultados e registro de acordo visível.','representation':'symbolic'},
    'planning_board': {'version':1,'introducedIn':2,'size':[460,280],'inputs':['stage','quality'],'actions':['plan','execute','review'],
        'actionInputs':{'plan':['stage'],'execute':['stage'],'review':['stage']},
        'description':'Três etapas com cartões que avançam e registro de revisão.','representation':'symbolic'},
    'time_budget': {'version':1,'introducedIn':2,'size':[200,260],'inputs':['remaining'],'actions':[],
        'description':'Ampulheta de orçamento de tempo, sem cronômetro independente.','representation':'symbolic'},
})


# Search metadata is only a library UI aid, never simulator/template routing.
SEARCH_TERMS = {
    'liquid_vessel':['água','water','líquido','liquid','reservatório','reservatórios','reservoir','tanque','tank','bomba','pump','vazão','flow'],
    'lift_gate':['comporta','comportas','gate','barreira','barrier','portão'],
    'floating_carrier':['barco','barcos','boat','navio','embarcação','navegação','navigation'],
    'status_marker':['risco','risk','alerta','alert','severidade','severity'],
    'harbor_backdrop':['eclusa','lock','porto','harbor','navegação','navigation','barco','boat'],
    'lock_channel':['eclusa','lock','comporta','comportas'],
    'workplace_backdrop':['escritório','office','reunião','meeting','feedback','colaborador','workplace'],
    'meeting_table':['reunião','meeting','feedback','diálogo','dialogue','negociação'],
    'conversation_person':['pessoa','person','personagem','colaborador','cliente','vendedor','feedback','conversa','diálogo','dialogue'],
    'evidence_folder':['evidência','evidências','evidence','documento','documentos','relatório','acordo','agreement','feedback'],
    'planning_board':['planejamento','planning','cronograma','schedule','projeto','project','tarefas','tasks'],
    'time_budget':['tempo','time','prazo','deadline','cronograma','schedule','orçamento','budget'],
}


def catalog():
    """Return a detached capability manifest, safe for authoring clients."""
    components=deepcopy(COMPONENTS)
    for ident,definition in components.items():definition['searchTerms']=list(SEARCH_TERMS.get(ident,[]))
    return {'version': CATALOG_VERSION, 'renderer': 'svg-v1',
            'styles': ['blueprint', 'studio'], 'components': components,
            'limits': {'instances': 6, 'teachingLinks': 4},
            'limitations': ['Esquemas didáticos, não certificação científica.',
                            'Sem imagens externas, scripts ou efeitos lógicos.',
                            'A seleção automática de componentes ainda não está ativada.']}


def draw_component(instance, style):
    """Pure compiler to the existing safe SVG graph. No renderer dependency."""
    if instance['component'] not in V1_COMPONENTS:
        from services.context_components import draw_context_component
        return draw_context_component(instance,style)
    ident=instance['id'];kind=instance['component'];pos=instance['position']
    ink='#dceafb' if style=='blueprint' else '#193b54'
    surface='#193b54' if style=='blueprint' else '#f8fbff'
    shadow='#0b2238' if style=='blueprint' else '#c6d4df'
    frame='#8ab5cc' if style=='blueprint' else '#527589'
    rows=[{'id':ident,'type':'group','label':instance['label'], 'attrs':dict(pos)}]
    def node(suffix,kind,attrs,parent=None,**extra):
        item={'id':ident+'_'+suffix,'type':kind,'label':instance['label'],
              'parent':parent or ident,'attrs':attrs,**extra};rows.append(item);return item
    def bind(row,prop,port,a,b):
        source=instance['inputs'][port]
        if 'var' in source:
            row.setdefault('bindings',[]).append({'property':prop,'var':source['var'],
                'input':source['range'],'output':[a,b]})
        else:
            ratio=(source['value']-source['range'][0])/(source['range'][1]-source['range'][0])
            row['attrs'][prop]=a+ratio*(b-a)
    def rect(suffix,x,y,w,h,fill,**extra):
        return node(suffix,'rect',dict(x=x,y=y,width=w,height=h,fill=fill,**extra))
    if kind=='liquid_vessel':
        rect('shadow',18,24,190,212,shadow,rx=18)
        rect('frame',8,8,190,212,surface,rx=16,stroke=frame,strokeWidth=4)
        rect('interior',22,24,162,180,'#0e3554',rx=8)
        fluid=rect('liquid',22,184,162,20,'#24afdb')
        bind(fluid,'height','level',20,180);bind(fluid,'y','level',184,24)
        top=rect('surface',22,184,162,6,'#a4eeff',rx=3)
        bind(top,'y','level',184,24)
        rect('shine',30,32,8,163,'#d9f5ff',opacity=.22,rx=4)
        rect('foot',35,221,137,11,frame,rx=4)
        for i in range(4):rect('tick'+str(i),160,42+i*42,18,3,'#cfe7f3',rx=1)
        targets={'level':ident+'_liquid'}
    elif kind=='lift_gate':
        rect('shadow',16,20,72,215,shadow,rx=8)
        rect('left',9,20,12,210,frame,rx=4)
        rect('right',70,20,12,210,frame,rx=4)
        rect('lintel',4,9,84,18,ink,rx=4)
        rect('passage',23,32,45,192,'#0d2b43',rx=4)
        gate=rect('blade',24,32,44,190,'#edb754',rx=4,stroke='#93662c',strokeWidth=3)
        bind(gate,'height','opening',190,24)
        rect('guide',42,32,7,17,'#fff1bf',rx=2)
        node('winch','circle',dict(x=48,y=10,r=9,fill='#93b5c8',stroke=ink,strokeWidth=3))
        action=instance['actions'].get('activate')
        if action:rows[0]['action']=action
        targets={'opening':ident+'_blade'}
    elif kind=='floating_carrier':
        water=rect('water',0,215,250,12,'#74d7ef',rx=6)
        bind(water,'y','elevation',215,75)
        boat=node('moving','group',dict(x=0,y=140))
        bind(boat,'x','position',0,90);bind(boat,'y','elevation',140,0)
        parent=boat['id']
        node('hull','path',dict(d='M5 45 H155 L133 74 H31 Z',fill='#e89a3d',stroke='#774d29',strokeWidth=3),parent)
        node('hull_shade','path',dict(d='M31 65 H140 L133 74 H31 Z',fill='#bd6d26'),parent)
        node('deck','rect',dict(x=26,y=37,width=114,height=9,rx=3,fill='#fff0cf'),parent)
        node('cabin','rect',dict(x=48,y=5,width=65,height=34,rx=5,fill='#f4f9fc',stroke=frame,strokeWidth=3),parent)
        node('roof','rect',dict(x=44,y=0,width=75,height=8,rx=3,fill=frame),parent)
        for i in range(3):node('window'+str(i),'rect',dict(x=56+i*17,y=14,width=11,height=13,rx=2,fill='#39799a'),parent)
        node('mast','line',dict(x=130,y=9,x2=130,y2=37,stroke=ink,strokeWidth=3),parent)
        node('flag','polygon',dict(points=[[130,9],[150,17],[130,24]],fill='#5ed3bf'),parent)
        targets={'position':boat['id'],'elevation':boat['id']}
    elif kind=='status_marker':
        node('rim','circle',dict(x=50,y=50,r=36,fill=shadow,stroke=frame,strokeWidth=3))
        light=node('light','circle',dict(x=50,y=50,r=15,fill='#eab65a',stroke=ink,strokeWidth=3))
        bind(light,'r','severity',15,31)
        node('stem','line',dict(x=50,y=35,x2=50,y2=52,stroke=ink,strokeWidth=5))
        node('dot','circle',dict(x=50,y=63,r=3,fill=ink))
        targets={'severity':ident+'_light'}
    else:raise ValueError('Componente não registrado')
    return rows,targets
