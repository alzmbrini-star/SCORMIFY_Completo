"""Explicit, local image-shadow commands. No generated code, images or AI calls."""
import copy
import math
import re
import unicodedata

GUIDE = ('No Chat do Editor, use “Aplicar sombra média em todas as imagens”, '
         '“Aplicar sombra suave nas imagens do slide atual”, '
         '“Aplicar sombra forte na imagem selecionada” ou “Remover sombra de todas as imagens”. '
         'Também aceita cor em hexadecimal, intensidade em %, suavidade em px e deslocamentos horizontal/vertical em px. '
         'Só altera elementos de imagem; fundos e imagens dentro de HTML/simuladores ficam preservados. '
         'Esses comandos não usam créditos de IA. A última alteração pode ser revertida pelo Analisador de Estética.')
PRESETS={'soft':(16,6,18),'medium':(24,10,28),'strong':(32,14,40),'none':(16,6,18)}


def normalized(text):
    return ' '.join(''.join(c for c in unicodedata.normalize('NFKD',text or '') if not unicodedata.combining(c)).lower().split())


def shadow_targets(slides, operation):
    scope=operation.get('scope')
    if scope=='course':
        indices=range(len(slides))
    elif scope in ('slide','selection'):
        index=operation.get('slideIndex')
        if type(index) is not int or not 0<=index<len(slides):raise ValueError('Slide inválido')
        indices=[index]
    else:raise ValueError('Informe o escopo da sombra')
    if scope=='selection' and not isinstance(operation.get('elementId'),str):raise ValueError('Selecione uma imagem')
    return [(si,ei,element) for si in indices for ei,element in enumerate(slides[si].get('elements') or [])
            if element.get('type')=='image' and (scope!='selection' or element.get('id')==operation['elementId'])]


def shadow_configuration(existing, patch):
    if not isinstance(patch,dict) or not patch or set(patch)-{'preset','mode','color','opacity','blur','x','y'}:raise ValueError('Ajuste de sombra inválido')
    preset=patch.get('preset')
    if preset is not None and preset not in PRESETS:raise ValueError('Intensidade inválida')
    base=copy.deepcopy(existing) if isinstance(existing,dict) else {}
    if preset is not None or not base:
        blur,y,opacity=PRESETS.get(preset,PRESETS['soft'])
        base={'preset':preset or 'soft','mode':base.get('mode','contour'),'color':'#000000','blur':blur,'x':0,'y':y,'opacity':opacity}
    if 'mode' in patch and patch['mode'] not in ('contour','frame'):raise ValueError('Tipo de sombra inválido')
    if 'color' in patch and (not isinstance(patch['color'],str) or not re.fullmatch(r'#[0-9a-fA-F]{6}',patch['color'])):raise ValueError('Use cor hexadecimal #rrggbb')
    for key,low,high in (('opacity',0,70),('blur',0,60),('x',-40,40),('y',-40,40)):
        value=patch.get(key)
        if key in patch and (type(value) not in (int,float) or not math.isfinite(value) or not low<=value<=high):raise ValueError(f'{key}: use valor entre {low} e {high}')
    base.update(patch)
    if set(patch)-{'preset'} and preset!='none':base['preset']='custom'
    return base


def apply_image_shadow(slides, operation):
    patch=operation.get('shadow')
    # Validate before changing any image (including when there are zero targets).
    shadow_configuration(None,patch)
    targets=shadow_targets(slides,operation)
    updates=[(si,ei,el,shadow_configuration(el.get('imageShadow'),patch)) for si,ei,el in targets]
    applied=[]
    for si,ei,element,shadow in updates:
        if element.get('imageShadow')==shadow:continue
        element['imageShadow']=shadow
        applied.append({'type':'set_image_shadow','slideIndex':si,'elementIndex':ei,
                        'slideId':slides[si].get('id'),'elementId':element.get('id')})
    return applied


def plan_image_shadow(message, slides, current_slide_id=None, selected_element_id=None):
    text=normalized(message)
    if 'sombra' not in text or (not re.search(r'imagem|imagens',text) and re.search(r'texto|letras|titulo',text)):return None
    def clarify(reply):return {'reply':reply,'ops':[],'imageShadowCommand':True,'targetCount':0}
    if re.match(r'^(como|onde|quais|consigo|posso|e possivel)\b',text):return clarify(GUIDE)
    if re.search(r'imagens? de fundo|background|(?:dentro.{0,25}|\b(?:no|nos|do|dos)\s+)(?:html|simulador)',text):return clarify('Este comando só ajusta imagens selecionáveis no slide. Não altera imagens de fundo nem imagens internas de HTML ou simuladores. Nenhuma alteração feita.')
    if re.search(r'\bnao\b.{0,40}\b(?:apli\w*|colo\w*|adicion\w*|remov\w*|retir\w*|desativ\w*|ativ\w*|ajust\w*|alter\w*)\b.{0,25}\bsombra',text):return clarify('Nenhuma alteração feita. Informe apenas a sombra e o escopo desejados. '+GUIDE)
    if re.search(r'exceto|com excecao|menos (?:o|os|a|as)\b|primeira imagem|segunda imagem|terceira imagem|ultima imagem|penultima imagem|imagem\s+\d',text):return clarify('Para ajustar uma imagem específica ou excluir peças, selecione a imagem no Editor e peça a alteração na imagem selecionada; não apliquei mudanças em lote.')
    if not re.search(r'apli|colo|adicion|remov|retir|desativ|ativ|ajust|alter|mud|use\b|usar\b|quero|gostaria|deixe',text):return clarify(GUIDE)
    if re.search(r'\b(?:e|,)\s+(?:mude|altere|exclua|gere|adicione)\s+(?:o titulo|o texto|o fundo|slide|audio|video)',text):return clarify('Para este ajuste seguro, peça a sombra separadamente das outras alterações. '+GUIDE)
    names={'soft':r'\b(suave|leve|discreta)\b','medium':r'\b(media|moderada)\b','strong':r'\b(forte|intensa)\b'}
    presets=[key for key,pattern in names.items() if re.search(pattern,text)]
    remove=bool(re.search(r'remov|retir|desativ|sem sombra|nenhuma sombra|sombra nenhuma',text))
    if len(presets)>1:return clarify('Escolha uma intensidade: suave, média ou forte.')
    patch={'preset':'none'} if remove else {'preset':presets[0]} if presets else {}
    if not remove:
        color=re.search(r'#[0-9a-f]{6}\b',text)
        if color:patch['color']=color.group()
        else:
            colors={'preta':'#000000','preto':'#000000','branca':'#ffffff','branco':'#ffffff','azul':'#2563eb','vermelha':'#dc2626','vermelho':'#dc2626','cinza':'#64748b','verde':'#16a34a'}
            for word,value in colors.items():
                if re.search(r'\b'+word+r'\b',text):patch['color']=value;break
            if 'color' not in patch and ('#' in text or re.search(r'\bcor\b',text)):return clarify('Informe a cor da sombra em hexadecimal, por exemplo #334155.')
        for key,pattern in (('opacity',r'(?:intensidade|opacidade)(?: de)?\s+(-?\d+(?:[.,]\d+)?)\s*%'),
                            ('blur',r'(?:suavidade|desfoque)(?: de)?\s+(-?\d+(?:[.,]\d+)?)\s*px'),
                            ('x',r'(?:deslocamento )?horizontal(?: de)?\s+(-?\d+(?:[.,]\d+)?)\s*px'),
                            ('y',r'(?:deslocamento )?vertical(?: de)?\s+(-?\d+(?:[.,]\d+)?)\s*px')):
            match=re.search(pattern,text)
            if match:patch[key]=float(match.group(1).replace(',','.'))
        if re.search(r'moldura|retangular',text):patch['mode']='frame'
        elif 'contorno' in text:patch['mode']='contour'
    if not patch:return clarify('Qual sombra deseja: suave, média, forte ou nenhuma? Também posso ajustar cor, intensidade, suavidade e posição.')
    try:shadow_configuration(None,patch)
    except ValueError as error:return clarify(str(error)+'. Nenhuma imagem foi alterada.')
    current=next((i for i,s in enumerate(slides) if s.get('id')==current_slide_id),None)
    operation={'type':'set_image_shadow','shadow':patch}
    numbered=re.search(r'\bslide\s+(\d+)\b',text)
    if re.search(r'\bslides\s+\d',text):return clarify('Informe um slide por vez, o slide atual ou todas as imagens do curso.')
    if 'selecionad' in text:
        if current is None or not selected_element_id:return clarify('Selecione uma imagem no Editor antes de pedir este ajuste.')
        operation.update(scope='selection',slideIndex=current,elementId=selected_element_id)
    elif numbered:
        operation.update(scope='slide',slideIndex=int(numbered.group(1))-1)
    elif re.search(r'(?:neste|nesse|deste|desse) slide|slide atual',text):
        if current is None:return clarify('Não identifiquei o slide atual. Selecione-o no Editor ou informe o número do slide.')
        operation.update(scope='slide',slideIndex=current)
    elif re.search(r'todas?\s+(?:as\s+)?imagens|todo\s+o\s+curso|curso inteiro|todos\s+os\s+slides',text):
        operation.update(scope='course')
    else:return clarify('Em qual escopo: imagem selecionada, imagens do slide atual, um slide específico ou todas as imagens do curso?')
    try:count=len(shadow_targets(slides,operation))
    except ValueError as error:return clarify(str(error)+'. Nenhuma imagem foi alterada.')
    if not count:return clarify('Não encontrei elementos de imagem nesse escopo. Fundos e imagens dentro de HTML ou simuladores não são alterados por este comando.')
    return {'reply':'Vou ajustar apenas as sombras das imagens.','ops':[operation],'imageShadowCommand':True,'targetCount':count}


def shadow_result_reply(plan, applied):
    if not plan.get('ops'):return plan['reply']
    changes=[op for op in applied if op.get('type')=='set_image_shadow']
    if not changes:return 'As imagens já estavam com essa configuração de sombra. Nenhuma alteração foi necessária.'
    count=len(changes);slides=len({op['slideIndex'] for op in changes})
    action='Removi a sombra' if plan['ops'][0]['shadow'].get('preset')=='none' else 'Atualizei a sombra'
    return f'{action} de {count} imagem(ns) em {slides} slide(s). Arquivos originais, posição, perguntas, notas e demais conteúdos foram preservados. Comando sem créditos de IA; a última alteração pode ser revertida no Analisador de Estética. Reexporte HTML/SCORM para atualizar os pacotes.'
