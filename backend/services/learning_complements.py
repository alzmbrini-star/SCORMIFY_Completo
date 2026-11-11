"""Additive learning resources: pedagogical actions, never topic templates.

Source lessons and native figures remain untouched. References here reinforce
the source; they never count as teaching coverage in source_coverage.
"""
import re
import uuid
from collections import Counter

from services.source_coverage import normalized

KINDS = {
    'flashcard': ('Revisão ativa', 'Recuperar conceitos da memória, com pergunta na frente, resposta fundamentada e exemplo no verso.', r'conceit|defini|termo|vocab|concept|defin'),
    'quiz': ('Verificação de compreensão', 'Verificar a compreensão com situações contextualizadas, alternativas plausíveis e feedback explicativo.', r'identific|verific|reconhec|distingu|classific|identify|check'),
    'simulator': ('Exploração do mecanismo', 'Explorar visualmente o mecanismo ou processo, com ações e consequências observáveis; usar simplificações didáticas declaradas, não exigir precisão de engenharia.', r'process|mecanism|operac|funcion|ajust|etapa|proced|mechanism|operat'),
    'scenario': ('Decisão contextualizada', 'Escolher uma conduta em uma situação do assunto estudado e comparar consequências com feedback.', r'decis|escolh|condut|risco|conflit|decision|choos|risk'),
    'timeline': ('Sequência visual', 'Explorar a sequência e a relação entre etapas ou marcos, explicando o que muda em cada transição.', r'sequenc|etapa|evoluc|cronolog|histor|stage|sequence'),
    'infographic': ('Relações visuais', 'Visualizar relações, comparações ou estrutura do assunto, sem substituir sua explicação.', r'compar|relac|estrutur|dado|indicador|map|structur'),
    'case_study': ('Análise de caso', 'Analisar evidências de um caso fictício contextualizado e justificar decisões com base no conteúdo ensinado.', r'analis|evidenc|diagnost|avali|analy|evaluat'),
    'game': ('Desafio de fixação', 'Fixar o conteúdo em um desafio com questões próprias deste módulo e feedback, sem usar perguntas de banco fora do contexto.', r'pratic|fixac|revis|aplic|practice|review'),
}


def plan_complements(structure, config, enabled):
    """Idempotent, bounded enrichment after mandatory coverage is established."""
    available = [k for k in KINDS if enabled.get(k) is True
                 and (k != 'simulator' or config.get('simulatorsAllowed') is not False)]
    budget = {'baixa': 1, 'media': 2, 'alta': 3, 'maxima': 4}.get(
        str(config.get('resourceBalance') or config.get('interactivity') or 'media').lower(), 2)
    usage = Counter(s.get('type') for m in structure.get('modules', []) for s in m.get('slides', [])
                    if s.get('type') in KINDS)
    for module in structure.get('modules', []):
        slides = module.get('slides', [])
        anchors = [s for s in slides if s.get('sourceRequired') and not s.get('sourceImageOnly')
                   and s.get('type') in ('content', 'infographic', 'avatar_scene')]
        if not anchors:
            continue  # Legacy free-form outlines retain their existing planning behavior.
        refs = list(dict.fromkeys(r for s in anchors for r in s.get('sourceRefs', [])))
        context = '\n\n'.join(dict.fromkeys(s.get('sourceExcerpt') or s.get('purpose') or s.get('title', '') for s in anchors))
        topic = module.get('title') or anchors[0].get('title') or config.get('title') or 'Conteúdo estudado'
        existing = [s for s in slides if s.get('type') in available and not s.get('sourceRequired')]
        target = min(budget, len(available), max(1, len(anchors)))
        used = {s.get('type') for s in existing}
        for _ in range(max(0, target - len(existing))):
            options = [k for k in available if k not in used]
            if not options:
                break
            # Learning verbs determine suitability; course topics never select a fixed scene.
            evidence = normalized(topic + ' ' + context)
            kind = max(options, key=lambda k: (bool(re.search(KINDS[k][2], evidence)), -usage[k], -list(KINDS).index(k)))
            label, intent, _ = KINDS[kind]
            resource = {'id': 'complement_' + uuid.uuid4().hex[:16], 'type': kind,
                        'title': f'{label} — {topic}',
                        'purpose': f'{intent} Contexto obrigatório: {topic}. Use os trechos fornecidos; não invente regras do produto.',
                        'estimatedDuration': 90 if kind in ('quiz', 'flashcard') else 150}
            # Place activities after teaching, before a local or course conclusion.
            end = next((i for i,s in enumerate(slides) if s.get('type') == 'summary'), len(slides))
            slides.insert(end, resource)
            existing.append(resource); used.add(kind); usage[kind] += 1
        for resource in existing:
            resource.update(isComplement=True, complementOf=[s['id'] for s in anchors if s.get('id')],
                            reinforcesSourceRefs=refs, sourceExcerpt=context,
                            learningRationale=KINDS[resource['type']][1])
    structure['learningComplements'] = {
        'version': 1, 'policy': 'additive', 'reviewBeforeGeneration': True,
        'count': sum(bool(s.get('isComplement')) for m in structure.get('modules', []) for s in m.get('slides', [])),
        'enabledTypes': available,
    }
    return structure


def preserve_complement_metadata(completed, sources):
    """All generation paths (including specialized engines/checkpoints) keep links."""
    for item, source in zip(completed, sources):
        if source.get('isComplement') and source.get('type') in KINDS:
            item['type'] = source['type']
        for key in ('isComplement', 'complementOf', 'reinforcesSourceRefs', 'learningRationale', 'imageSuggestion'):
            if key in source:
                item[key] = source[key]
