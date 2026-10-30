"""Explicit QA compositions, not topic templates selected by the generator."""
from test_rule_visuals import lock_fixture
from test_rule_simulators import base,var,action,op,ref,fixtures


def source(var,low,high):return {'var':var,'range':[low,high]}
def constant(value,low,high):return {'value':value,'range':[low,high]}
def instance(key,kind,label,x,y,inputs=None,actions=None,variant=None):
    item={'id':key,'component':kind,'version':1,'label':label,'position':{'x':x,'y':y},'inputs':inputs or {},'actions':actions or {}}
    if variant:item['variant']=variant
    return item
def link(instance,port,change,meaning):return {'instance':instance,'input':port,'whatChanges':change,'whyItMatters':meaning}
def attach(raw,title,description,instances,links,read,style):
    raw.pop('visual',None);raw['experience']={'complexity':'advanced','visualStyle':'illustrated'}
    raw['visualProject']={'version':1,'catalogVersion':2,'renderer':'svg-v1','style':style,
        'title':title,'description':description,'instances':instances,
        'teaching':{'focus':description,'readScene':read,'links':links}}
    return raw


def technical_pilot(style='studio'):
    raw=lock_fixture()
    feedback={'abrir_entrada':'A passagem de entrada foi liberada; os níveis de água não mudaram.',
              'entrar':'A embarcação entrou na câmara, no nível atual da água.',
              'fechar':'A passagem de entrada foi fechada antes da elevação.',
              'elevar':'A água da câmara e a embarcação que está nela subiram juntas.',
              'abrir_saida':'A passagem de saída foi liberada no nível superior.',
              'sair':'A embarcação chegou à bacia superior.',
              'forcar':'A decisão acionou a condição de risco deste modelo. A travessia foi encerrada sem sucesso.'}
    for row in raw['actions']:row['feedback']=feedback[row['id']]
    return attach(raw,'Travessia por uma eclusa',
        'Observe a relação entre água, passagem e embarcação. Esquema discreto para aprendizagem, sem dimensões de engenharia.',
        [instance('harbor','harbor_backdrop','Paisagem e infraestrutura de navegação',20,20),
         instance('channel','lock_channel','Câmara, água, comportas e embarcação',20,110,
             {'level':source('nivel',0,2),'entry':source('entrada',0,1),'exit':source('saida',0,1),
              'position':source('barco',0,2),'risk':source('risco',0,1)},
             {'entry':'abrir_entrada','exit':'abrir_saida'})],
        [link('channel','level','A superfície da câmara sobe ou desce.','Compare-a com as superfícies das duas bacias.'),
         link('channel','entry','A comporta libera ou fecha a passagem.','Observe a condição de entrada antes de movimentar a embarcação.'),
         link('channel','position','A embarcação se desloca entre as bacias e a câmara.','Seu nível acompanha o local e o estado declarado.'),
         link('channel','risk','Um alerta aparece na operação insegura.','O alerta representa a condição de risco do modelo, não um cálculo de engenharia.')],
        'As superfícies da água, a lâmina das comportas e a embarcação representam os estados reais do caso. A embarcação só acompanha a elevação da câmara quando está nela. Use as comportas acionáveis ou os botões. O desenho é um modelo esquemático discreto, não uma ferramenta para operar eclusas.',style)


def feedback_rules():
    raw=base('Feedback eficaz em uma reunião de trabalho',
        [var('escuta','Contexto compreendido',0,2,'de 2'),var('abertura','Abertura ao diálogo',1,4,'índice didático'),var('acordo','Acordo registrado',0,1,'estado')],
        [action('ouvir','Ouvir a perspectiva do colaborador',op('eq',ref('escuta'),0),{'escuta':1,'abertura':2}),
         action('investigar','Discutir o impacto com fatos do caso',op('eq',ref('escuta'),1),{'escuta':2,'abertura':3}),
         action('acordar','Registrar um próximo passo conjunto',op('all',op('eq',ref('escuta'),2),op('ge',ref('abertura'),3)),{'acordo':1}),
         action('pressionar','Impor uma conclusão sem ouvir',True,{'abertura':0})],
        op('all',op('eq',ref('acordo'),1),op('ge',ref('abertura'),3)),op('eq',ref('abertura'),0),
        ['ouvir','investigar','acordar'],['pressionar'],'conversation')
    raw['mission']='Conduza a reunião até um próximo passo registrado, respeitando as restrições do caso.'
    raw['briefing']='Uma entrega de design ficou diferente do briefing. Converse sobre o contexto e os impactos. Os indicadores e gestos são representações didáticas fictícias; não medem emoções reais nem predizem o comportamento de pessoas.'
    raw['scenes'][0].update(title='A conversa ganha contexto',description='As escolhas mudaram os documentos disponíveis e a abertura representada.',facts=['Observe os fatos e as consequências da última decisão.'])
    raw['scenes'][1].update(title='Reunião de alinhamento',description='Há uma divergência sobre a entrega. Decida como conduzir a conversa.',facts=['Expressões e índices são qualitativos e fictícios.'])
    feedback={'ouvir':'O contexto começou a ser compreendido e a abertura ao diálogo mudou neste caso fictício.',
              'investigar':'Os fatos e impactos foram discutidos; os documentos e a expressão acompanham os novos estados.',
              'acordar':'O próximo passo foi registrado e o acordo aparece na pasta.',
              'pressionar':'A abertura caiu à condição de encerramento deste caso. Compare a expressão e reflita sobre a abordagem.'}
    for row in raw['actions']:row['feedback']=feedback[row['id']]
    return raw


def feedback_pilot(style='studio'):
    return attach(feedback_rules(),'Uma conversa com consequências',
        'Observe os gestos, os documentos e o registro do acordo. Expressões ilustrativas, não medição psicológica.',
        [instance('room','workplace_backdrop','Ambiente de trabalho e mesa de reunião',20,20),
         instance('speaker','conversation_person','Pessoa que conduz o feedback',92,95,{'engagement':constant(2,0,4)},variant='short_hair'),
         instance('listener','conversation_person','Colaboradora em diálogo',435,95,{'engagement':source('abertura',0,4)},variant='long_hair'),
         instance('table','meeting_table','Mesa de reunião em primeiro plano',85,325),
         instance('folder','evidence_folder','Fatos consultados e acordo registrado',285,260,{'review':source('escuta',0,2),'agreement':source('acordo',0,1)})],
        [link('listener','engagement','A expressão e o gesto mudam entre condições de diálogo.','A representação qualitativa torna a consequência da abordagem observável.'),
         link('folder','review','Os documentos ficam mais expostos conforme a investigação.','A investigação torna os fatos do caso visíveis.'),
         link('folder','agreement','O registro recebe um selo quando há acordo.','O selo indica o estado do acordo, não uma garantia sobre pessoas reais.')],
        'Compare o gesto e a expressão da colaboradora antes e depois de decidir. A pasta representa os fatos consultados e o acordo registrado. A relação entre escolhas e abertura é uma simplificação pedagógica; gestos não constituem diagnóstico, previsão ou avaliação psicológica.',style)


def planning_pilot(style='studio'):
    raw=fixtures()[1]
    raw['variables'][0].update(label='Etapas concluídas',unit='de 3');raw['variables'][2]['unit']='índice didático'
    raw['mission']='Organize a entrega em três etapas preservando o orçamento de tempo e a qualidade declarada.'
    raw['briefing']='Há seis blocos de tempo para analisar dependências, executar e revisar uma entrega. Interrupções consomem esse orçamento. A ampulheta representa blocos disponíveis, não segundos ou um cronômetro real.'
    raw['scenes'][0].update(title='A entrega está em andamento',description='O quadro e o orçamento refletem as decisões tomadas.',facts=['Compare o avanço das etapas com o tempo que permanece disponível.'])
    raw['scenes'][1].update(title='Planeje a entrega',description='Escolha uma intervenção e observe seus efeitos sobre o quadro e o tempo.',facts=['O tempo é um recurso discreto deste caso, não um relógio em contagem regressiva.'])
    feedback={'planejar':'A análise de dependências foi concluída, consumindo um bloco de tempo.',
              'executar':'O trabalho prioritário avançou, consumindo três blocos de tempo.',
              'revisar':'A revisão consumiu um bloco e atingiu o critério de qualidade da entrega.',
              'dispersar':'A interrupção consumiu dois blocos sem avançar as etapas ou a qualidade.'}
    for row in raw['actions']:row['feedback']=feedback[row['id']]
    return attach(raw,'Planejamento com recursos limitados',
        'Observe as etapas no quadro e o orçamento na ampulheta. A passagem do tempo depende das escolhas, não de um cronômetro.',
        [instance('room','workplace_backdrop','Sala de planejamento',20,20),
         instance('board','planning_board','Etapas e revisão da entrega',45,85,{'stage':source('fase',0,3),'quality':source('qualidade',0,4)},
                  {'plan':'planejar','execute':'executar','review':'revisar'}),
         instance('budget','time_budget','Orçamento de blocos de tempo',550,100,{'remaining':source('tempo',0,6)})],
        [link('board','stage','Os cartões passam da próxima etapa para a coluna de concluídos.','A posição mostra o avanço declarado da entrega.'),
         link('board','quality','O símbolo de revisão muda quando o critério de qualidade é atingido.','Avançar as etapas e revisar são estados que precisam ser observados.'),
         link('budget','remaining','A areia disponível diminui conforme o orçamento é consumido.','As decisões têm custo mesmo quando não avançam o trabalho.')],
        'Use os cartões acionáveis ou os botões alternativos. 01 representa planejamento, 02 execução e 03 revisão. A coluna Próxima indica a etapa pendente atual; Feito registra o que já foi realizado. O lápis indica revisão pendente e o visto indica o critério atendido. A ampulheta mostra blocos de tempo do modelo e não funciona como temporizador.',style)


def pilots(style='studio'):return [technical_pilot(style),feedback_pilot(style),planning_pilot(style)]
