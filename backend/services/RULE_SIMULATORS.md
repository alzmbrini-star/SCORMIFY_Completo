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
lógica booleana, soma, subtração, multiplicação, mínimo e máximo. Não há `eval`,
funções geradas, acesso a rede ou código vindo do modelo.

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
HTML do aluno. Reuso de diagnósticos exige a versão 10 do gerador. Propostas de
testes inconsistentes são substituídas por trajetórias comprovadas e contabilizadas
nos metadados de verificação. Erros independentes de regras são reportados juntos;
cada reparo usa uma conversa nova. O compilador coloca cenas incondicionais como
fallback e garante cobertura de estados, sem alterar as ações ou os objetivos.

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
escapa delimitadores HTML. A interface é responsiva e rola em vez de reduzir a
fonte para caber. HTML, SCORM clássico e Single Page preservam esse viewport.

O modelo é didático e fictício. Não envia nota/completion ao LMS por conta própria;
as regras existentes do curso continuam responsáveis pela aprovação. Comparação
é de estados em memória e não promete persistência no servidor ou desfazer decisões.

## Verificação

`test_rule_simulators.py`: validação, busca, limites, segurança, integração canônica
Agente/Editor, exportação e correção de dados. `test_rule_engine.cjs`: os mesmos
cinco modelos com topologias distintas executados em Python e JS, comparando
cada estado; testes DOM exercitam controles, desfechos, comparação e reinício.
Os testes antigos exercitam explicitamente o gerador legado e seus formatos.
