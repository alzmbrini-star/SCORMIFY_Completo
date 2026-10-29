"""Author-selected interaction density, independent of subject and art quality."""
import json

LEVELS={'guided','applied','advanced'}
STYLES={'illustrated','technical'}


def options(complexity='guided',visual_style='illustrated'):
    return {'complexity':complexity if isinstance(complexity,str) and complexity in LEVELS else 'guided',
            'visualStyle':visual_style if isinstance(visual_style,str) and visual_style in STYLES else 'illustrated'}


def from_context(context):
    try:
        value=json.loads(context)
        value=value.get('simulatorOptions',{}) if isinstance(value,dict) else {}
        if not isinstance(value,dict):return options()
        return options(value.get('complexity'),value.get('visualStyle'))
    except (ValueError,TypeError):return options()


def has_options(context):
    try:
        value=json.loads(context)
        return isinstance(value,dict) and isinstance(value.get('simulatorOptions'),dict)
    except (ValueError,TypeError):return False


def with_options(context,preferences):
    if preferences is None:return context
    preferences=options(preferences.get('complexity'),preferences.get('visualStyle'))
    try:
        parsed=json.loads(context)
        if not isinstance(parsed,dict):parsed={'reference':context}
    except (ValueError,TypeError):parsed={'reference':context}
    parsed['simulatorOptions']=preferences
    return json.dumps(parsed,ensure_ascii=False)


def normalize_experience(raw,spec,preferences=None):
    raw=raw if isinstance(raw,dict) else {}
    selected=preferences or options(raw.get('complexity'),raw.get('visualStyle'))
    level=selected['complexity'];limit={'guided':2,'applied':3,'advanced':10}[level]
    compositions={'guided':{'scene-led'},'applied':{'scene-led','split'},'advanced':{'scene-led','split','instruments'}}[level]
    default={'guided':'scene-led','applied':'split','advanced':'instruments'}[level]
    variables={v['id']:v for v in spec['variables']}
    primary=[]
    for key in raw.get('essentialVariables',[]) if isinstance(raw.get('essentialVariables'),list) else []:
        if isinstance(key,str) and key in variables and key not in primary:primary.append(key)
    primary=(primary+list(k for k in variables if k not in primary))[:limit]
    def text(key,fallback,cap):
        value=raw.get(key)
        return value.strip()[:cap] if isinstance(value,str) and value.strip() else fallback[:cap]
    labels={}
    for key,values in (raw.get('stateLabels') or {}).items() if isinstance(raw.get('stateLabels'),dict) else []:
        if key not in variables or not isinstance(values,dict):continue
        labels[key]={}
        for state,label in list(values.items())[:8]:
            try:number=int(state)
            except (ValueError,TypeError):continue
            if str(number)!=str(state) or not variables[key]['min']<=number<=variables[key]['max']:continue
            if isinstance(label,str) and label.strip():labels[key][str(number)]=label.strip()[:50]
    return dict(selected,composition=raw.get('composition') if isinstance(raw.get('composition'),str) and raw['composition'] in compositions else default,
                palette=raw.get('palette') if isinstance(raw.get('palette'),str) and raw['palette'] in {'daylight','deep','warm'} else ('deep' if level=='advanced' else 'daylight'),
                environment=text('environment',spec.get('briefing','Ambiente da atividade'),600),
                learningFocus=text('learningFocus',spec.get('mission','Investigar e experimentar'),400),
                visualApproach=text('visualApproach','Objetos do cenário devem representar as mudanças reais do modelo; não apenas medidores.',800),
                essentialVariables=primary,stateLabels=labels)


EXPERIENCE_PROMPT='''Antes de desenhar, planeje a experiência didática em experience:
{complexity:"guided"|"applied"|"advanced",visualStyle:"illustrated"|"technical",
 composition:"scene-led"|"split"|"instruments",palette:"daylight"|"deep"|"warm",
 environment:descrição específica do ambiente até600,learningFocus:até400,
 visualApproach:até800 descrevendo os objetos, suas mudanças observáveis e por que ensinam o conteúdo,
 essentialVariables:[IDs existentes das variáveis realmente úteis ao aluno],
 stateLabels:{idDaVariavel:{"0":"Rótulo significativo","1":"Outro rótulo"}}}.
Use a complexidade e o estilo escolhidos pelo AUTOR em simulatorOptions.
Guiado: cena predominante, orientação contextual, poucas escolhas relevantes a cada momento,
até 2 indicadores essenciais; não simplifique a arte nem invente travas para criar um quiz.
Aplicado: experimentação com consequências, até 3 indicadores centrais e detalhes sob demanda.
Avançado: parâmetros/alternativas e restrições mais ricos, instrumentos e comparação opcionais.
Não confunda quantidade de campos visíveis com dificuldade conceitual ou qualidade gráfica.
Planeje composição segundo o aprendizado, não o mesmo painel administrativo em todo assunto.
Use o ambiente pertinente: processo técnico, circuito, equipamento, situação de trabalho ou
outro cenário justificado. Não transforme todo tema em escritório, boneco e barras coloridas.
Escolha rótulos semânticos para flags/etapas; o aluno não deve ver "0 flag". Nunca invente unidades,
porcentagens/probabilidades reais ou classificações que o modelo não calcula.
O mesmo motor validará a lógica; experience é apresentação e não altera efeitos ou aprovação.
'''
