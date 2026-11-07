"""Shared art direction, not subject-specific scene templates or logical rules."""

ART_DIRECTION = '''DIREÇÃO DE ARTE · MECANISMO EM PRIMEIRO PLANO
Escolha o enquadramento pelo que o aluno precisa observar, não por um layout fixo.
Se o assunto é uma peça, encaixe ou transformação local, use vista ampliada,
corte esquemático ou vista explodida: não desenhe um consultório/fábrica inteiro
com o mecanismo minúsculo. Se a relação depende do ambiente, preserve a paisagem
ou situação contextual. Para relações humanas, priorize gestos e interação.
Para temas abstratos, use uma situação concreta ou metáfora explicitamente indicada.
O conjunto essencial deve dominar a área útil. Reserve espaço para movimentos e
legendas; não aumente objetos a ponto de recortar sua trajetória ou ocultar partes.
Desenhe silhueta, interior e detalhes funcionais reconhecíveis, com materiais e
luz coerentes. Gradientes e sombras não transformam uma esfera em uma engrenagem
nem um retângulo em uma máquina. Formas simples continuam válidas para objetos
realmente simples. Não há cota de detalhes, personagens ou formas decorativas.
Use uma paleta contida, contornos claros, superfícies e luz suaves. Planos de fundo
devem apoiar a leitura, não receber o mesmo brilho/volume dos componentes.
Identifique os componentes essenciais com nomes didáticos e explanation curta.
Prefira labels nos grupos semânticos; detalhes internos não repetem a legenda do
objeto inteiro. Rótulos visíveis curtos e linhas de chamada devem apontar para a
peça correta em cada etapa, sem atravessar textos ou se sobrepor aos mecanismos.
Os movimentos e estados mostram montagem, abertura, fluxo, postura ou outra
transformação pertinente ao tema. Não substitua a transformação por números ou
troca de título. Nunca invente precisão, dados, decisões, acertos ou regras para
embelezar a cena. Preserve controles, pausa e velocidade existentes.
O acabamento é adaptado ao tema e ao estilo técnico/ilustrado, em todos os níveis.
Nenhum cenário, profissão ou conjunto de objetos é obrigatório para todo assunto.
'''


def illustration_brief(data, prompt, plan=None):
    """Explicit focus shared by planning, drawing and image review."""
    experience = data.get('experience') or {}
    plan = plan or {}
    return {
        'version': 'mechanism-first-v1',
        'subject': str(prompt)[:1800],
        'learningFocus': plan.get('focus') or experience.get('learningFocus') or
                         data.get('learningGoal') or data.get('mission') or data.get('title', ''),
        'visualStyle': experience.get('visualStyle', 'illustrated'),
        'cameraDecision': 'Escolha detalhe ampliado, conjunto, ambiente ou interação pela relação que precisa ser visível; justifique em composition.',
        'semanticObjects': [
            {k: o[k] for k in ('id', 'label', 'features', 'explanation') if k in o}
            for o in plan.get('objects', []) if o.get('layer') != 'background'
        ],
        'reviewPriorities': ['Reconhecimento das peças e de sua relação',
                             'Enquadramento e tamanho útil do mecanismo',
                             'Legibilidade, materiais e contraste',
                             'Mudanças observáveis nas etapas reais'],
        'precision': 'Representação qualitativa; sem exigir cálculo ou realismo fotográfico.',
        'rules': 'Somente apresentação. Nunca alterar lógica, estados, decisões ou notas.',
    }
