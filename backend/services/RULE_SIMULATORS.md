# Motor genérico de simulações: finite-rules-v1

Novas gerações do Agente, Editor e melhorias do Agente usam `generate_visual_simulator`
→ `generate_rule_simulator`. Não há seleção por tema nem fallback para HTML inventado.
Os renderizadores antigos permanecem para compatibilidade e regressão; documentos
existentes não são regenerados ou substituídos automaticamente.

## Contrato executável

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
HTML do aluno. Reuso direto de diagnósticos exige a versão 16 do gerador. Dados
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

`test_rule_simulators.py`: validação, busca, limites, segurança, integração canônica
Agente/Editor, exportação e correção de dados. `test_rule_engine.cjs`: os mesmos
cinco modelos com topologias distintas executados em Python e JS, comparando
cada estado; testes DOM exercitam controles, desfechos, comparação e reinício.
Os testes antigos exercitam explicitamente o gerador legado e seus formatos.
