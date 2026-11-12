"""Prepare typed, image-ready composition when vector-first art was unavailable.

No topic templates, new rules, generated JavaScript or remote image references.
Only an explicit object-images request may enter this bounded text-planning step.
"""
import asyncio
import json
import re


def check_image_slots(scene, data):
    from services.simulator_object_images import candidates
    from services.rule_visuals import visual_state
    pieces=[p for p in candidates(scene) if next(n for n in scene['nodes'] if n['id']==p['id']).get('artwork')]
    errors=[]
    if not 1<=len(pieces)<=4:
        errors.append('Planeje 1 a 4 peças elegíveis, não uma equipe/cena diferente por etapa. Não marque o fundo com artwork.')
    def drawable(ident):
        return any(n['type'] not in {'group','text'} or drawable(n['id']) for n in scene['nodes'] if n.get('parent')==ident)
    empty=[p['id'] for p in pieces if next(n for n in scene['nodes'] if n['id']==p['id'])['type']=='group' and not drawable(p['id'])]
    if empty:errors.append('Grupos sem desenho vetorial de apoio: '+','.join(empty)+'. Adicione formas filhas; peças não ilustradas precisam continuar visíveis.')
    projected={n['id']:n for n in visual_state(scene,{v['id']:v['initial'] for v in data['variables']})}
    definitions={n['id']:n for n in scene['nodes']}
    def visible(key):
        n=projected[key];parent=definitions[key].get('parent')
        return n['visible'] and n['attrs'].get('opacity',1)>0 and (not parent or visible(parent))
    if not any(visible(p['id']) for p in pieces):errors.append('A etapa inicial está vazia: mantenha pelo menos um objeto essencial visível desde o início, incluindo seus pais.')
    if errors:raise ValueError(' '.join(errors))
    return pieces


async def prepare_scene(data, prompt, context, session_id):
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    from services.llm_config import simulator_generation_config
    from services.rule_visuals import VISUAL_PROMPT, validate_visual
    from services.visual_parts import COMPOSITION_PROMPT
    from services.visual_schema import format_for_stage, omit_null_fields
    from services.simulator_object_images import candidates
    from services.simulator_diagnostics import record_attempt

    provider, key, model = simulator_generation_config()
    payload = {'request': prompt[:4000], 'context': context[:5000],
               'model': {k: data[k] for k in ('title', 'mission', 'variables', 'actions', 'scenes', 'checks', 'experience', 'didacticMode') if k in data}}
    visual_prompt = VISUAL_PROMPT
    if data.get('didacticMode') == 'process-demo-v1':
        visual_prompt = visual_prompt.replace('Representar >=2 variáveis afetadas por ações, com >=1 alteração de geometria/movimento.', 'Uma etapa/variável pode controlar várias partes por estados, movimento, aparência ou visibilidade.').replace('A cena deve mudar tanto na trajetória de sucesso quanto negativa.', 'Demonstre o processo sem exigir fracasso nem física exata.')
    system = visual_prompt + '\n' + COMPOSITION_PROMPT + '''
PREPARAÇÃO PARA IMAGENS INDIVIDUAIS, não revisão da aparência de vetores.
A cena anterior ficou indisponível. Componha uma cena própria para o assunto,
em 800x450, com 1..4 objetos inteiros essenciais em grupos com artwork.bounds e
description. Esses espaços receberão imagens recortadas DEPOIS desta preparação.
Não crie uma cópia da equipe ou cenário para cada etapa. Reutilize os mesmos
objetos/personagens e altere os elementos que demonstram o processo. Não atribua
artwork ao fundo inteiro. Cada grupo artwork deve ter formas filhas de apoio,
visíveis se a imagem não for gerada. Pelo menos um objeto deve aparecer na etapa 0.
Não desenhe uma fotografia dentro de cada peça; defina uma composição coerente,
objetos grandes, mesma perspectiva e relações espaciais que expliquem o processo.
Inclua formas vetoriais de apoio reconhecíveis dentro dos grupos, não um painel
de indicadores. Não use objetos irrelevantes apenas para preencher o cenário.
Mantenha estrutura fixa separada das partes móveis; líquidos/fluxos são vetoriais.
Vincule visibilidade/movimento às variáveis e etapas existentes. Não invente
ações, variáveis, precisão científica ou rotação de máquinas inteiras para mistura.
Uma etapa pode controlar várias peças. A cena inicial já deve ser compreensível.
Retorne apenas o contrato JSON da cena, nunca o modelo lógico ou código.'''
    for attempt in range(2):
        raw = None
        try:
            params = {'temperature': .2, 'max_tokens': 10000}
            fmt = format_for_stage(provider, model, '-image-scene', data, payload)
            if fmt:
                params['response_format'] = fmt
            chat = LlmChat(api_key=key, session_id=f'{session_id}-image-scene-{attempt}', system_message=system).with_model(provider, model).with_params(**params)
            response = await asyncio.wait_for(chat.send_message(UserMessage(text=json.dumps(payload, ensure_ascii=False))), 150)
            raw = omit_null_fields(json.loads(re.sub(r'^```(?:json)?\s*|\s*```$', '', str(response).strip(), flags=re.I)))
            scene = validate_visual(raw, data)
            check_image_slots(scene, data)
            # Eligibility and typed state execution are verified here. Image
            # silhouettes cannot be judged before those images actually exist.
            record_attempt(json.dumps(scene, ensure_ascii=False), {'mechanic': 'image-ready-scene-v1'}, [], review='Composição preparada; imagens ainda não geradas nem certificadas editorialmente.')
            return scene
        except Exception as exc:
            record_attempt(json.dumps(raw, ensure_ascii=False) if raw else '', {'mechanic': 'image-ready-scene-v1'}, [], error=str(exc)[:1200])
            payload.update(previousScene=raw, repairError=str(exc)[:1500])
    raise ValueError('Não foi possível preparar as peças para as imagens. A atividade anterior foi preservada; consulte o diagnóstico técnico.')
