"""Semantic artwork slots, independent of subject, physics and outcome rules."""
import math

COMPOSITION_PROMPT = '''COMPOSIÇÃO POR PEÇAS (Agente e Editor, qualquer assunto):
Planeje primeiro a cena inteira, as relações espaciais e o que muda em cada etapa.
Não selecione imagens para cabeça/corpo separados, sombras, etiquetas ou uma forma
minúscula de apoio. Cada peça rígida reconhecível deve ser um group próprio, com
detalhes vetoriais de reserva dentro dele, e artwork opcional no NODE:
artwork:{bounds:[xLocal,yLocal,largura,altura],description:"objeto inteiro, vista e função"}.
O retângulo é o espaço REAL da peça na composição, em coordenadas locais do group,
não o tamanho de uma primitiva interna. Dê espaço legível aos protagonistas
(em geral 90..260 unidades no canvas 800x450), sem preencher com decoração.
Use a mesma perspectiva, luz e escala visual para peças que se conectam. Mostre
conexões, transferência, aproximação, abertura ou transformação conforme o tema.
Anime x/y/rotation/opacity do group: sua imagem e seus detalhes acompanham juntos.
Antes de atribuir movimento, diferencie a estrutura fixa da parte móvel: motor,
carcaça, pés e suporte não giram junto com hélice, eixo, mistura ou conteúdo.
Rotacione apenas a peça que realmente gira, em torno do pivô local correto.
Para mostrar agitação dentro de um recipiente, mantenha a imagem do recipiente
fixa e anime separadamente o conteúdo ou marcadores vetoriais no seu interior.
Não use rotação ou pulsação da máquina inteira como substituto da operação.
Se a imagem contém estrutura e mecanismo inseparáveis, preserve-a estática;
represente o efeito em outra camada vetorial coerente com sua perspectiva.
Partes com movimentos independentes são grupos separados, nunca dentro de um
grupo marcado artwork que as achataria. Líquidos, fluxos e deformações continuam
vetoriais, sem artwork. Uma imagem por peça, não uma fotografia da cena inteira.
Não invente cálculos, precisão científica, nota, fracasso ou limites físicos.
Use etapas reais do plano: regras usam states/bindings/visibleWhen; visualizações
usam as janelas start/end dos movimentos e os nomes das etapas na timeline.
Não mova todas as peças aleatoriamente nem substitua o processo por trocar legendas.
O acabamento deve explicar o mecanismo. Não existe lista fixa de temas ou cenários.
'''


def validate_artwork(raw, kind):
    if kind not in {'group','rect','circle','ellipse','polygon','path'}:
        raise ValueError('Artwork exige uma peça visual, não texto ou linha')
    if not isinstance(raw, dict) or set(raw) != {'bounds','description'}:
        raise ValueError('Artwork exige bounds e description')
    box=raw['bounds']
    if not isinstance(box,list) or len(box)!=4 or any(type(v) not in (int,float) or not math.isfinite(v) for v in box):
        raise ValueError('Bounds da peça deve conter quatro números finitos')
    x,y,w,h=box
    if not -800<=x<=800 or not -450<=y<=450 or not 1<=w<=800 or not 1<=h<=450:
        raise ValueError('Área da peça fora do canvas suportado')
    description=raw['description']
    if not isinstance(description,str) or not description.strip() or len(description)>1200:
        raise ValueError('Descreva a peça inteira em até 1200 caracteres')
    return {'bounds':list(box),'description':description.strip()}
