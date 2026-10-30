# Motor genérico de simulações: finite-rules-v1

Novas gerações do Agente, Editor e melhorias do Agente usam `generate_visual_simulator`
→ `generate_rule_simulator`. Não há seleção por tema nem fallback para HTML inventado.
Os renderizadores antigos permanecem para compatibilidade e regressão; documentos
existentes não são regenerados ou substituídos automaticamente.

## Contrato executável

### Guiado: demonstração qualitativa do processo

Por escolha do autor, novas gerações Guiadas usam didacticMode=process-demo-v1.
O Agente e o Editor selecionam um prompt próprio para demonstrações, sem as regras
contraditórias do desafio estrito. Uma variável de etapa, uma ação de avanço, uma
cena e um caminho curto são suficientes. Não se exige trajetória negativa, três
decisões, dois indicadores causais ou proibição de repetir um controle de avanço.
Fracasso ausente ou impossível nos limites é representado por false; um fracasso
possível pode continuar existindo, mas não é requisito para aprovar uma demonstração.
Consultas com effects:{} são conservadas como observationNotes e retiradas das
intervenções, sem inventar efeitos de estado. O briefing inclui as informações de
apoio e o aviso de representação simplificada, sem precisão de engenharia.

Continuam obrigatórios: dados tipados, referências existentes, limites de execução,
estado inicial utilizável, objetivo alcançável e controles funcionais. A busca para
aprovar a demonstração termina ao provar uma solução; não procura um fracasso fictício.
O campo de modo permanece no JSON para exportação/refino/revalidação; não se aceita
HTML/JS gerado. O modelo não pode impor esse modo quando o autor escolhe Aplicado ou
Avançado, cujos critérios de desafio permanecem. Dados legados sem o campo mantêm a
validação anterior; não há reescrita automática de cursos ou pacotes distribuídos.

O cenário da demonstração pode ser vinculado a uma única etapa, sem inventar métricas.
Novas cenas ilustradas ganham gradientes suaves de superfície, volume e sombras por
código SVG confiável, sem mudar geometria, ações ou equações. Backgrounds, textos,
traços técnicos e documentos legados não recebem esse tratamento indiscriminadamente.
O plano visual pede objetos reconhecíveis, proporções plausíveis e detalhes úteis,
não fidelidade fotográfica ou cálculos de engenharia. Uma nota visível identifica a
representação simplificada. Isso é uma política genérica de demonstração para qualquer
tema representável pelo contrato, não um modelo pronto de eclusa ou outro assunto.

No Guiado, a cena pode reagir por intensidade/opacidade, espessura, cor ou
visibilidade, sem exigir deslocamento geométrico. A validação exercita também
controles opcionais alcançáveis, não somente a sequência que conclui a atividade.
Texto dinâmico sozinho não comprova reação dos objetos; uma mudança apenas
declarada, mas nunca observada nos estados amostrados, continua sendo rejeitada.
A amostragem limita-se às primeiras 128 transições do explorador já limitado.
O piso numérico de 16 formas/dois grupos não bloqueia esse modo, embora o prompt
continue pedindo objetos reconhecíveis e acabamento; Aplicado/Avançado mantêm
seus critérios. Cores hexadecimais curtas (#RGB) são expandidas sem perda para
#RRGGBB antes de renderizar, sem aceitar CSS livre, URLs ou scripts.
Falhas de geração/refino visual preservam também o modelo das regras no registro
privado, para permitir reproduzir exatamente a combinação cena/controles.

A IA retorna exclusivamente dados JSON: variáveis inteiras limitadas, predicados,
ações com efeitos atômicos, cenas condicionais, objetivo e fracasso. O próprio
motor deriva os testes de trajetórias com os estados realmente calculados, sem
depender da aritmética declarada pela IA. Flags e estágios representam descobertas, dependências e histórico
relevante. Custos de tempo, esforço e orçamento são variáveis explícitas, não
efeitos implícitos ou cronômetros inventados.

O mesmo interpretador suporta combinações de decisões, investigação, alocação
discreta, ordenação de processos e experimentação. Os layouts são apresentações
do mesmo modelo, não motores por domínio. As operações disponíveis são comparação,
lógica booleana, soma, subtração, multiplicação, mínimo e máximo (inclusive de
três ou mais critérios). Erros indicam a ação/campo e a aridade problemática. Não há `eval`,
funções geradas, acesso a rede ou código vindo do modelo.

Na entrada JSON, somente os sinônimos booleanos exatos `and`/`or` são traduzidos
para `all`/`any`. A compilação mantém aridade, tipos, referências e limites de
profundidade/tamanho; não interpreta strings, JS ou operadores desconhecidos.
HTML e exportações recebem apenas os operadores canônicos já suportados.

Todos os efeitos leem o estado anterior e são aplicados juntos. Ações são
desabilitadas com explicação quando os requisitos não são satisfeitos, o efeito
ultrapassa limites ou não há mudança. Fracasso tem precedência sobre sucesso.
Limite de decisões ou ausência de ações viáveis encerra a tentativa sem sucesso;
reiniciar sempre restaura o estado e limpa comparações e histórico.

## Evidência de solução e limites

O servidor valida tipos, referências, tamanhos, limites numéricos e dependências
causais diretas ou indiretas do objetivo. Em seguida executa busca em largura limitada a 30.000 estados
expandidos e até 24 decisões. Exige caminho de sucesso com ao menos três decisões
e mudança da cena, além de teste negativo. Não exige três tipos distintos no
primeiro caminho encontrado, nem bloqueios artificiais: experimentos por parâmetros
podem alternar ajustes dos mesmos controles. Requisitos de descobertas e etapas
são usados quando fazem parte das regras declaradas, não como modelo universal.
O caminho comprovado e os testes ficam nos diagnósticos privados do autor, não no
HTML do aluno. Reuso direto de diagnósticos exige a versão 17 do gerador. Dados
JSON de versões conhecidas do mesmo contrato podem ser revalidados, sem IA,
somente se o hash corresponder exatamente ao pedido, contexto e modelo originais.
As rotas filtram proprietário, sessão e validade de retenção. O compilador atual
repete prova de solução e checagem contra atalhos e gera HTML próprio; nunca
executa HTML reprovado ou aceita dados antigos apenas por aprovação anterior.
O novo diagnóstico registra a versão de origem. Propostas de
testes inconsistentes são substituídas por trajetórias comprovadas e contabilizadas
nos metadados de verificação. Erros independentes de regras são reportados juntos;
cada reparo usa uma conversa nova. O compilador coloca cenas incondicionais como
fallback e garante cobertura de estados, sem alterar as ações ou os objetivos.

Quando a cena não muda na solução, a revisão recebe a trajetória executada com
estados e cenas selecionadas. Isso permite corrigir predicados e prioridade sem
adivinhar valores ou reduzir o desafio já comprovado.
Quando o objetivo não é comprovado, a revisão também recebe as faixas observadas
e as ações executáveis. As faixas não implicam combinações alcançáveis; numa
busca interrompida pelo orçamento, são parciais e não provam impossibilidade.

Além da validade formal, a geração de desafios testa cada ação repetida sozinha:
se uma delas já permite vencer por repetição, a IA recebe esse contraexemplo para
corrigir o atalho. Esta é uma política de qualidade do gerador, não uma restrição
do interpretador. Não exige três controles diferentes nem converte experimentos
de parâmetros em conversas. O teste não substitui a revisão pedagógica do autor.

Orçamento de busca esgotado significa **não comprovado**, nunca prova de que uma
simulação é impossível. Há até três tentativas de correção dos dados. Falhas não
inserem documento inválido nem alteram a estrutura do curso. A IA pode declarar
recurso não representável com uma explicação, em vez de inventar uma funcionalidade.

A prova verifica o modelo finito declarado; não certifica sua fidelidade científica,
qualidade pedagógica absoluta ou cobertura de qualquer simulação imaginável.
Física contínua precisa, manipulação livre de entidades ilimitadas e serviços
externos em tempo real não são suportados por este contrato. Esses pedidos exigem
extensões explícitas de primitivas, com semântica e testes próprios, não exceções
para um assunto. O tema, por si só, não restringe a geração.

## Apresentação, exportação e avaliação

HTML/CSS/JS confiáveis e autocontidos apresentam cena por estado, indicadores,
ações disponíveis e bloqueadas, consequências específicas, deltas, histórico,
comparação de estados e reinício. Texto é inserido com `textContent`; a serialização
escapa delimitadores HTML. A interface ocupa o slide sem rolagem da página ou
redução global da fonte. Textos longos e ações são paginados; contexto e histórico
abrem em diálogos. HTML, SCORM clássico e Single Page preservam esse viewport.

## Camada visual contextualizada

### Projetos de componentes optativos

A Fase 1 acrescenta `visualProject` versionado e catálogo mínimo de componentes
de prova, compilados para o mesmo grafo SVG confiável. Não altera a lógica,
não migra documentos e não ativa seleção automática na geração. Sem projeto,
o caminho anterior permanece. Ver [contrato e limites](COMPONENT_SCENES.md).

### Composição didática avançada

Novas gerações avançadas planejam ambiente, enquadramento e 2–4 mecanismos
observáveis antes de desenhar. O mesmo contrato serve a qualquer tema suportado,
sem selecionar modelos temáticos. Uma etapa independente revisa a relação entre
o plano, os objetos, as mudanças reais e as explicações. O revisor recebe JSON e
projeções executadas, não pixels: não é certificação estética ou de aprendizagem.

`visual.teaching` vincula objetos não textuais a variáveis existentes, com mudança
perceptível nas trajetórias positiva/negativa. Número isolado, referência inventada,
vínculo desconectado ou variação mínima imperceptível não bastam. Orientação e
valores antes/depois aparecem fora da ilustração; o botão **Como interpretar** abre
as explicações completas. A cena ocupa cerca de 2/3 do slide, indicadores essenciais
acompanham as ações à direita e instrumentos/histórico ficam em detalhes opcionais.
Objetos acionáveis continuam usando as mesmas ações e requisitos do motor, com
alternativa por botão e teclado. Reinício limpa os realces e a leitura da última ação.

O Editor permite **Refinar cenário** na prévia de IA. Em Colar HTML, um simulador
do motor de regras oferece **Preparar refino visual**: o autor escolhe nível/estilo
e solicita a nova arte. Somente JSON limitado e revalidado é enviado; HTML anterior
nunca é executado pelo servidor. Regras, objetivos e resultados permanecem iguais;
uma falha não substitui a prévia anterior. O curso só muda quando o autor insere.
O Agente pode reaproveitar regras do pedido exato e solicitar apenas a arte quando
uma ilustração antiga não possui os novos vínculos didáticos. Recursos antigos
salvos não são substituídos automaticamente. A revisão final do autor continua necessária.

Agente (Configurar) e Editor (HTML → Gerar com IA) permitem escolher interação
Guiada, Aplicada ou Avançada e abordagem ilustrada ou técnica. As opções fazem
parte da identidade do pedido e do plano `experience`, antes da criação da cena.
Não selecionam motores temáticos nem reduzem a qualidade gráfica no nível guiado.
O plano descreve ambiente, foco didático, objetos observáveis, composição,
indicadores essenciais e rótulos semânticos para estados discretos.

Guiado prioriza cena, até dois indicadores e ações disponíveis; histórico,
comparações, outros indicadores e ações bloqueadas ficam em detalhes opcionais.
Aplicado apresenta até três indicadores; Avançado mantém instrumentos completos.
As três apresentações preservam regras, efeitos, aprovação e reinício. Documentos
antigos sem esse plano conservam sua apresentação; as opções valem para novas
gerações. O autor deve revisar a pertinência e o acabamento: verificações
estruturais de objetos compostos e mudanças contextuais não certificam realismo
fotográfico nem qualidade pedagógica absoluta.

Novas cenas ilustradas passam ainda por um piso de detalhamento na geração:
ao menos dois objetos compostos e 16 formas não textuais. A orientação pede
detalhes funcionais, ambiente e volume, não preenchimento com formas inúteis.
Essa checagem não é uma avaliação estética e não revalida retroativamente
documentos salvos nem se aplica a esquemas técnicos. Falhas reparam somente
a arte; se a cena não for validada, o aviso de diagrama conceitual permanece.

Depois de aprovar a lógica, uma etapa separada solicita uma cena JSON original.
O grafo usa grupos e primitivas SVG (formas, caminhos, polígonos e texto), não
modelos temáticos nem código gerado. Interpolação limitada vincula variáveis
reais a posição, tamanho, rotação e opacidade. Predicados selecionam aparência
e visibilidade; textos podem mostrar valores existentes. Objetos acionáveis
usam os mesmos controles e requisitos do motor, nunca efeitos próprios.

`rule_visuals.py` valida referências, tipos, quantidade, atributos permitidos,
cores e coordenadas. Exige vínculos com pelo menos duas variáveis causais e
uma mudança geométrica, e executa as projeções de trajetórias positiva/negativa.
O compilador também normaliza grupos aninhados e coordenadas locais, verifica
objetos móveis e sobreposição estimada de rótulos nas trajetórias executáveis.
Rótulos estáticos próximos à borda podem ser reposicionados sem reduzir a fonte;
colisões são verificadas novamente. Erros independentes de enquadramento são
reportados juntos. Cenas JSON guardadas no diagnóstico do mesmo pedido podem
ser recompiladas, sem outra chamada de IA, após validação atual completa.
O renderizador confiável lê uma ponte de estado do motor; não interpreta JS
do modelo, não usa imagens externas e não altera notas ou variáveis. Animações
são curtas, respeitam movimento reduzido e são canceladas no reinício. A cena
pode ser ampliada sem perder a interação nem duplicar IDs.

São até duas tentativas para a cena, independentes dos reparos das regras. Se
ela não for validada ou o serviço estiver indisponível, a atividade mantém as
regras e exibe um **diagrama conceitual explicitamente identificado**, com aviso
de que a ilustração não está disponível. Não há garantia de fidelidade científica
da ilustração: a revisão didática e visual do autor continua necessária.

Documentos canônicos anteriores recebem a apresentação conceitual sem chamar
IA. Para criar uma cena ilustrada contextualizada, é necessária uma nova geração
ou a retomada do diagnóstico do mesmo pedido; nesse último caso as regras podem
ser revalidadas e somente a cena ausente usa IA. Simuladores legados ilustrados
não são convertidos nem substituídos. Pacotes já exportados exigem nova exportação.

O modelo é didático e fictício. Não envia nota/completion ao LMS por conta própria;
as regras existentes do curso continuam responsáveis pela aprovação. Comparação
é de estados em memória e não promete persistência no servidor ou desfazer decisões.

## Verificação

### Reparo de conclusões curtas

A busca considera o caminho de sucesso mais curto, e não a sequência proposta
pelo modelo. Quando ele tem menos de três intervenções, ShortSolutionError
devolve um contraexemplo estruturado: estado inicial, requisitos e efeitos de
cada ação executada, estados antes/depois e objetivo satisfeito. O gerador recebe
esses dados em repairDetails, além do histórico limitado às três tentativas, para
não repetir correções já rejeitadas. Isso é genérico e não escolhe uma receita de
simulação por tema nem modifica automaticamente a lógica produzida.

As instruções exigem corrigir dependências causais do processo, não acrescentar
contadores de cliques, esperas ou confirmações artificiais. O verificador continua
rejeitando atalhos de uma ou duas ações, repetição vencedora de um único controle,
objetivos inalcançáveis e regras inseguras. Somente regras aprovadas seguem para
a composição visual/biblioteca. Elementos visuais disponíveis não substituem a
prova de que o novo plano é executável. Esgotar reparos é reportado como defeito
do plano gerado; somente unsupported explícito é reportado como recurso não
representável. Os testes usam respostas simuladas, sem chamadas pagas de IA.

Falhas de pré-validação também enviam repairDetails: referências diretas do
objetivo, dependências transitivas, variáveis com escrita declarada, dependências
sem qualquer efeito e mapa de leituras/escritas por ação. A mensagem distingue
referenciar uma variável de realmente modificá-la. Não se adicionam efeitos
automáticos: a geração deve representar a operação causal solicitada e passar
novamente por todas as provas. Indicadores constantes do cenário não precisam
ser artificialmente modificados; outras decisões reais podem influenciar o
objetivo pelos requisitos/cálculos das ações.

Os jobs assíncronos do Editor preservam as últimas três tentativas e seus dados
de reparo no próprio registro privado, isolado por ContextVar. Não são enviados
no polling público nem incluídos nos logs. Aplicam-se o mesmo proprietário e
TTL de 24 horas do job existente; não se escreve no curso. Isso permite revisar
o JSON exato de uma falha futura em vez de depender somente de uma captura da
mensagem. Jobs antigos sem diagnóstico não ganham dados retroativamente.

Efeitos vazios não são classificados como referências inexistentes: o diagnóstico
identifica a ação com effects:{} e reúne seus demais defeitos de lógica antes do
reparo. Consultas sem mudança pertencem à orientação/interface, não à contagem de
intervenções; investigar pode registrar uma descoberta somente se houver uma
dependência causal real. Tipos inválidos e IDs não declarados recebem campo,
ação, nomes rejeitados e lista de IDs permitidos, sem descartar efeitos silenciosamente.

Uma análise conservadora de intervalos identifica condições impossíveis nos
limites declarados, incluindo comparações e árvores booleanas/aritméticas.
Resultado desconhecido não significa impossível. A busca diagnóstica adicional
é limitada a 2000 estados (ou ao orçamento menor solicitado); retorna o caminho
curto encontrado, não uma aprovação, e não altera regras nem limiares.

A prova de trajetória negativa exige atingir failure.when. Limite de passos e
deadlock continuam encerrando a tentativa do aluno sem sucesso, mas não comprovam
que o fracasso causal declarado é alcançável. Isso evita aceitar, por exemplo,
pressão >100 quando a variável só permite 0..100 porque uma consulta sem efeitos
pode ser repetida até acabar o limite de passos. O teste de regressão usa apenas
a topologia numérica do diagnóstico, sem publicar os textos do curso do autor.

`test_rule_simulators.py`: validação, busca, limites, segurança, integração canônica
Agente/Editor, exportação e correção de dados. `test_rule_engine.cjs`: os mesmos
cinco modelos com topologias distintas executados em Python e JS, comparando
cada estado; testes DOM exercitam controles, desfechos, comparação e reinício.
Os testes antigos exercitam explicitamente o gerador legado e seus formatos.
