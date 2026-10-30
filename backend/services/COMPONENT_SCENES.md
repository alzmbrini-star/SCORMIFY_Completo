# Projetos de componentes visuais

## Estado da entrega

Fases 1 e 2: contrato, compilação optativa e biblioteca vetorial inicial sobre o
motor `finite-rules-v1`. A Fase 2 inclui 12 componentes e três pilotos explícitos
para revisão. Não é uma biblioteca universal nem um novo gerador por tema. Não
há seleção automática pelo Agente, novo botão no Editor, API externa, dependência
gráfica, geração de imagens ou migração de cursos nesta entrega.

O catálogo atual tem versão 2. Projetos do catálogo 1 continuam válidos e usam
exatamente os mesmos quatro componentes anteriores. Não são convertidos nem
recebem novas peças silenciosamente. Componentes introduzidos na versão 2 exigem
catalogVersion=2. A versão individual de cada componente permanece explícita.

## Fronteira de confiança

`visualProject` é um campo opcional do modelo. `validate_rules` comprova primeiro
as regras e depois chama `component_scenes.compile_project`. O resultado é o
mesmo grafo SVG seguro usado pelo renderizador existente. Projetos ausentes
mantêm integralmente o caminho anterior. Se houver projeto e visual compilado,
o projeto versionado é a autoridade; a cópia compilada é reconstruída, nunca
aceita como substituição de código. Um projeto inválido falha explicitamente.

`project_schema()` fornece JSON Schema draft-07 para ferramentas de autoria.
O schema verifica estrutura; o compilador verifica referências reais, limites,
versões, faixa das variáveis, capacidades, vínculos didáticos e geometria.
Não se deve usar apenas o schema como certificação de um projeto.

Componentes não calculam métricas nem definem efeitos. Entradas leem variável
existente, com faixa explícita de interpolação, ou constante limitada. Não há
fórmula livre nem conversão implícita de unidade. Uma ação visual nomeia uma
ação existente; teclado e clique passam pelas mesmas guardas do motor.
Reinício e movimento reduzido continuam no runtime confiável. Os checks privados
de solução não são enviados ao documento do aluno.

## Catálogo inicial

`catalog()` retorna cópia destacada das capacidades e versões. Os desenhos são
mantidos no código, não baixados de URLs nem gerados a cada execução.

| Componente v1 | Entradas | Ação opcional | Tamanho SVG |
| --- | --- | --- | --- |
| liquid_vessel | level | nenhuma | 220 por 250 |
| lift_gate | opening | activate | 100 por 250 |
| floating_carrier | position e elevation | nenhuma | 260 por 250 |
| status_marker | severity | nenhuma | 100 por 100 |

São esquemas didáticos. O marcador é simbólico, não medição física. A biblioteca
não certifica dimensões, física, anatomia ou relações psicológicas. Componentes
novos exigem registro, semântica e testes: componente desconhecido não vira um
gráfico genérico silenciosamente. Alterações incompatíveis exigem nova versão.

## Contrato

O projeto declara version=1, catalogVersion=1 ou 2, renderer=svg-v1, style=blueprint
ou studio, title, description, instances e teaching. Cada instância declara id
até 16 caracteres, component, version, label, position{x,y}, inputs e actions.
Cada entrada é `{var:ID,range:[mínimo,máximo]}` OU
`{value:número,range:[mínimo,máximo]}`. A faixa é crescente e compatível com a
variável; a constante fica dentro da faixa. O posicionamento usa coordenadas
do canvas 800 por 450 e mantém a caixa do componente dentro das margens.
O campo variant é opcional apenas nos componentes que declaram variantes no
catálogo; valores desconhecidos e variantes em componentes antigos são rejeitados.

Teaching declara focus, readScene e 2 a 4 links. Cada link usa instance, input,
whatChanges e whyItMatters. Pelo menos duas variáveis distintas precisam causar
mudanças perceptíveis nos objetos nas transições alcançáveis. Constantes não
são evidências de causalidade. A mesma validação das cenas anteriores permanece
ativa: sem atalhos para desenhos do catálogo.

Até seis instâncias e 24 KB por projeto. Sem campos adicionais, scripts,
expressões, URLs, novos efeitos ou importação de SVG arbitrário. O compilador
não recebe chaves, rede ou serviços externos. O pacote usa apenas a cena
compilada e os runtimes já incluídos; não precisa chamar Python ao executar.

O refino livre anterior troca a camada visual: remove visualProject antes de
pedir outra ilustração e mantém as regras. O projeto original não é modificado
em memória nem salvo automaticamente. Edição estruturada por componente fica
para a fase de autoria; não confundir refino livre com editor de componentes.

## Prova e próximos marcos

`test_component_scenes.py` define a bancada explícita de teste. Usa as mesmas
regras da eclusa com duas composições/paletas, não gera um curso de produção.
As peças estão isoladas para verificar a fronteira do contrato: a bancada não
é uma representação completa da geografia de uma eclusa. Isso não deve ser
apresentado como o cenário final da Fase 2.

Testes verificam igualdade de ações, variáveis, objetivos, fracasso, cenas,
checks, desfechos e reinício. O teste DOM executa teclado e botões, verifica
geometria real, guardas e ausência de erros JS. O round-trip de exportação
Single Page preserva projeto e visual. Isso não substitui homologação no LMS.

## Biblioteca contextual da Fase 2

O módulo context_components mantém somente desenhos e projeções. Nenhuma peça
seleciona assunto, cria métricas, calcula emoção ou modifica o motor. Fundos
estáticos não aceitam entradas: não se deve vincular a paisagem a uma pontuação
e chamá-la de consequência. A composição e a revisão são explícitas.

| Componente v1 no catálogo 2 | Entradas | Ações opcionais |
| --- | --- | --- |
| harbor_backdrop | nenhuma | nenhuma |
| lock_channel | level, entry, exit, position e risk | entry e exit |
| workplace_backdrop | nenhuma | nenhuma |
| meeting_table | nenhuma | nenhuma |
| conversation_person | engagement | nenhuma |
| evidence_folder | review e agreement | inspect |
| planning_board | stage e quality | plan, execute e review |
| time_budget | remaining | nenhuma |

conversation_person permite short_hair ou long_hair. Expressões têm três
condições qualitativas observáveis e gestos distintos, não apenas variação
imperceptível da espessura de um traço. Isso não é medição psicológica nem
previsão do comportamento humano. No canal, elevação da água e posição do barco
se combinam: somente a embarcação dentro da câmara acompanha seu nível. A
ampulheta representa um orçamento discreto em faixas, não escoamento físico nem
um cronômetro. O quadro representa três etapas; não é um planejador ilimitado.
Slots acionáveis novos declaram actionInputs: a ação vinculada precisa declarar
um efeito em uma variável de entrada esperada da peça. Isso rejeita, por exemplo,
ligar a abertura da comporta ao comando de risco ou o cartão de planejamento a
uma interrupção que apenas consome tempo. É uma checagem estrutural de coerência,
não certificação semântica completa nem garantia de mudança em qualquer estado.

Os três pilotos em tests/component_pilots.py são composições de QA, não modelos
escolhidos pelo tema no gerador. Contêm explicações, consequências específicas e
associações explícitas. Suas fontes não são usadas para substituir conteúdo de
um usuário. HTML gerado continua autocontido, sem chamar uma API ao executar.

test_context_components.py verifica duas paletas, limites, compatibilidade,
consequências perceptíveis, preservação lógica, posição/elevação e três expressões
distintas. Verifica também contraste dos rótulos da eclusa e números dos cartões
em pelo menos 4,5:1 e da areia contra o vidro em pelo menos 3:1. Esses pontos não
certificam acessibilidade de todo o produto. O teste DOM executa os seis pilotos
(três contextos por duas paletas) por teclado e botões, incluindo estados
terminais e reinício. Revisão visual em navegador complementa esses testes.

Homologação no Didaxis e avaliação com alunos continuam pendentes. A arte é
vetorial ilustrativa ou esquemática, não realismo fotográfico nem fidelidade
científica certificada. As opções de interação Guiado, Aplicado e Avançado não
mudam a lógica dessas composições. Escolha automática, editor de peças e
regeneração pontual ainda pertencem à Fase 3.

Próximos marcos: Fase 3, compositor e revisão no Agente e no Editor.
Fase 4: testes visuais, desempenho e homologação SCORM 1.2 no Didaxis. Fase 5:
motores gráficos e adaptadores especializados somente com necessidade provada.

## Fase 3A: revisão e composição manual

O botão `Revisar projeto visual` está disponível para documentos do motor de
regras no diálogo HTML do Editor (Colar HTML e resultado da IA) e na prévia do
slide do Storyboard do Agente. Não altera automaticamente cursos existentes.
O modelo lógico precisa já ter sido gerado; este passo não substitui a geração
do storyboard nem a validação anterior de arte livre.

A interface separa objetivo/relações, cenário/peças e prévia/aprovação. Permite
adicionar/remover até seis peças, posicionar, ordenar camadas, escolher variantes,
associar entradas a variáveis existentes ou constantes e ligar hotspots a ações
existentes. As relações didáticas são editáveis. A prévia é invalidada após cada
alteração; somente uma composição validada pode ser aplicada. Nenhuma chamada
de IA, vetorizador ou Kling é feita por essa interface.

Endpoints autenticados sob `/api/generate-html/jobs/components`:
`GET /catalog`, `POST /preview` e `POST /sessions/{session_id}`. O último exige
o proprietário da sessão e índices explícitos de slide/elemento. Rejeita regras
ou apresentação de origem desatualizadas e faz compare-and-set somente no HTML
daquele elemento, preservando as demais edições. Preview recebe JSON limitado,
nunca executa HTML recebido; o compilador revalida regras e projeções, e produz
um documento novo pelo renderizador confiável. O Agente persiste apenas após
aprovação explícita; no Editor a mudança fica na prévia, que ainda precisa ser
inserida no slide e salva pelo fluxo normal.

Este é o primeiro incremento da Fase 3. Seleção automática por capacidade,
planejamento antes da geração inicial, produção de componentes ausentes,
regeneração pontual, importação de imagens/vetores e clipes de transição Kling
ainda não estão integrados. A biblioteca declara suas limitações; não há
substituição automática de um objeto desconhecido por outro fora do contexto.

## Visualização didática (modalidade separada)

`simulatorActivityType` aceita `simulation` (padrão legado) ou `visualization`.
Editor e configuração do Agente expõem a seleção antes de gerar. A seleção é
preservada no job, no contexto e na chave de cache; o despacho explícito não
depende da palavra “simulador” no prompt. Os slides simulator do Agente usam a
modalidade escolhida; a opção não converte automaticamente atividades salvas.

`didactic_visualizations.py` compila o contrato `didactic-visualization-v1`:
formas vetoriais planas e movimentos de órbita ilustrativa, translação senoidal,
rotação e pulsação. Não é integração física, simulação quântica, modelo 3D ou
gerador de vídeos. Não exige estados de sucesso/fracasso, prova de solução,
pontuação ou decisões. O núcleo finite-rules-v1 permanece inalterado.

O resultado funciona offline: iniciar/pausar, velocidade 0,5/1/2×, linha do tempo,
reinício e legendas, com explicações acessíveis dos objetos. Começa parado;
pausa ao ocultar a página e cancela o único requestAnimationFrame ao sair ou
reiniciar. Não escreve resultados no LMS nem envia eventos de pontuação.
Conclusão do curso continua seguindo a configuração normal do pacote.

A geração faz planejamento JSON limitado e revisão conceitual em outra chamada
ao mesmo provedor/modelo configurado. Isso consome geração de IA ao usar o
recurso, mas não exige API externa adicional. A revisão pede correção de falsas
premissas e identificação de simplificações em scientificNote; não certifica
ciência nem substitui revisão humana do conteúdo. Nenhum código, URL ou script
gerado pela IA entra no renderizador. Novos temas dependem de poderem ser
representados pelos objetos/movimentos 2D disponíveis; limites devem ser
declarados, não ocultados em uma ilustração que se apresenta como física real.

### Refino visual: referência e reparo quantitativo

O Editor preserva os dados SVG da cena ao extrair o modelo de origem por parsing
inerte. O backend revalida essa arte antes de usá-la como referência no refino;
arte inválida não é encaminhada. HTML/JS de origem nunca é executado. A referência
não altera as regras nem entra no documento final como campo privado.

A geração avançada recebe orientações numéricas dos vínculos: intervalo da
variável, passos observados, deslocamento projetado e amplitude necessária para
alcançar o critério de perceptibilidade. Exemplo de teste: passo de 10 numa faixa
0–100 com amplitude 40 produz 4 pixels; para 8 pixels, a amplitude é 80. Esses
números são orientações para reparo da arte, não reescala automática nem alteração
de física/causalidade. Uma comporta não deve ser ligada ao nível da água apenas
para cumprir movimento. Zoom/representação qualitativa exige explicação.

Falhas de perceptibilidade de vários vínculos são reunidas na mesma revisão, sem
reduzir os critérios de aprovação. O reparo continua limitado às tentativas já
existentes; falha final mantém a prévia e apresenta uma mensagem curta, enquanto
os detalhes técnicos permanecem nos diagnósticos do serviço.

### Origem explícita das órbitas ilustrativas

Novas gerações usam `origin:"center"` em movimentos `orbit`. A posição absoluta
da âncora é `(cx + dx*cos(ângulo), cy + dy*sin(ângulo))`; o renderizador subtrai
attrs.x/y ao montar a transformação SVG, evitando somar a posição inicial duas
vezes. O envelope de movimento usa o mesmo centro e inclui o tamanho do objeto.
Movimentos antigos sem `origin` mantêm exatamente a semântica anterior,
centrada em attrs.x/y. Nenhum curso salvo é migrado ou reescalado implicitamente.
Somente a geração nova normaliza a omissão de origin para center; leitura e
renderização de documentos já salvos não aplicam essa normalização.

Recortes continuam sendo rejeitados. Os problemas de vários objetos são
reunidos, com centro, amplitude, envelope e amplitudes máximas possíveis naquele
centro. O reparo da geração recebe esses dados estruturados em vez de somente
um nome de objeto. Não existe regra especial para átomos: a origem explícita
vale para qualquer órbita ilustrativa suportada pelo contrato 2D.

### Acabamento das visualizações didáticas

O acabamento é uma camada de apresentação compartilhada, não um catálogo de
simuladores por tema. Novas gerações escolhem paleta (midnight/daylight/warm),
atmosfera (studio/technical/natural) e materiais por objeto (flat/matte/metal/
glass/liquid/emissive), usando somente enums e cores hexadecimais validados.
Gradientes, sombras e iluminação são produzidos por código confiável; o modelo
não fornece filtros SVG, CSS, URLs ou JavaScript. Os cenários e suas geometrias
continuam sendo planejados para o conteúdo de cada atividade.

Editor, leitura e exportação também acrescentam esse acabamento aos documentos
legados identificados por didactic-visualization-v1 e pelo plano JSON embutido.
A atualização é idempotente e preserva plano, movimentos, posição e dimensões
dos elementos já editados. Não há migração em massa do banco nem nova chamada
de IA para atualizar a apresentação. HTML arbitrário sem esses metadados não é
alterado. Pacotes HTML/SCORM já distribuídos precisam ser exportados novamente.

Melhorar materiais e contraste não inventa detalhes que não existem na geometria
antiga: para obter novos objetos ou uma composição mais detalhada é necessário
gerar/refinar a atividade. A revisão conceitual e os limites científicos do
modelo didático continuam obrigatórios; brilho não é usado indiscriminadamente
como substituto da ilustração contextual.

### Biblioteca contextual na revisão visual

A seleção de peças mostra por padrão apenas os tipos presentes no projeto
visual salvo ou no rascunho atual. Remover uma instância original não impede
adicioná-la novamente. A opção explícita “Mostrar biblioteca completa” permite
compor novas peças sem alterar automaticamente as instâncias existentes.

Quando o simulador usa SVG personalizado e não possui instâncias do catálogo,
a interface apresenta sugestões por termos do título, objetivo, indicadores,
ações e objetos da cena. Essas sugestões são identificadas como sugestões,
não como peças já existentes. Sem correspondência, mostra um estado vazio;
nunca abre silenciosamente toda a biblioteca. Os termos do catálogo são apenas
metadados de busca, não modelos temáticos nem regras do motor. O filtro não
faz chamadas de IA, não altera a cena e não invalida uma prévia já validada.
