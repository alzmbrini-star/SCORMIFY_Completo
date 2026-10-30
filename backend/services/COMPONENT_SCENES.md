# Projetos de componentes visuais

## Estado da entrega

Fase 1: contrato, catálogo mínimo de prova e compilação optativa sobre o motor
`finite-rules-v1`. Não é a biblioteca visual completa nem um novo gerador por
tema. Não há seleção automática pelo Agente, novo botão no Editor, API externa,
dependência gráfica, geração de imagens ou migração de cursos nesta entrega.

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

O projeto declara version=1, catalogVersion=1, renderer=svg-v1, style=blueprint
ou studio, title, description, instances e teaching. Cada instância declara id
até 16 caracteres, component, version, label, position{x,y}, inputs e actions.
Cada entrada é `{var:ID,range:[mínimo,máximo]}` OU
`{value:número,range:[mínimo,máximo]}`. A faixa é crescente e compatível com a
variável; a constante fica dentro da faixa. O posicionamento usa coordenadas
do canvas 800 por 450 e mantém a caixa do componente dentro das margens.

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

Fase 2: biblioteca visual contextualizada e pilotos técnico, comportamental e
abstrato, com arte revisada. Fase 3: compositor e revisão no Agente e no Editor.
Fase 4: testes visuais, desempenho e homologação SCORM 1.2 no Didaxis. Fase 5:
motores gráficos e adaptadores especializados somente com necessidade provada.
