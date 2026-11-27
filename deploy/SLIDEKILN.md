# Importação interativa SlideKiln

Integração adicional; não substitui ConvertAPI e não executa migrações de cursos.
Uso comercial autorizado pelo fornecedor por escrito ao titular do plano Pro.

## Configuração

No serviço **backend** do Render, defina `SLIDEKILN_API_KEY` com a chave da
organização Pro. Nunca use variável `REACT_APP_*`, Git, logs ou chat para a chave.
Sem chave, a opção explica a configuração necessária e não envia conversões.
O aplicativo não cria chaves, assina planos ou modifica a assinatura.

## Orçamento e cobrança

Cada arquivo requer orçamento em reais e confirmação de direitos. Apenas Super
Admin aprova, inclusive chamadas possivelmente incluídas na franquia. Não há
consulta automática de saldo ou sincronização com uploads externos ao SCORMIFY.
Usa referência de US$ 1 por conversão, cotação/data BCB, antes de impostos/tarifas.
Se o fornecedor alterar a tarifa, revise a referência antes de habilitar uso.
Orçamento expira em 20 minutos. Aprovação é atômica e a chamada usa chave de
idempotência. Não existe retry de POST pago, mesmo após erro/timeout/redeploy.
Estado incerto exige conferir o histórico do fornecedor antes de novo orçamento.

## Escopo desta versão

PPTX até 32 MB, 1–500 slides. Importa o deck como **um bloco HTML interativo**
com navegação interna, não como slides nativos separados. Mantém player,
animações suportadas, links e mídias. Não transforma atividades em Quiz nativo,
não cria nota e não conecta automaticamente conclusão de cada slide interno ao
LMS. Critérios do bloco seguem o player SCORMIFY. Revise no LMS de destino.

Pacote ZIP até 24 MB / 64 MB expandido; HTML autocontido final até 32 MB.
Ativos `.sk.html` acima de 8 MB usam GridFS `slidekiln_assets`, com ponteiro
pequeno em `project_assets`, evitando o limite BSON sem recompressão. Arquivos grandes podem falhar depois da
chamada cobrável. Pré-orçamento avisa os limites; falha não repete a cobrança.
Entradas ficam no GridFS até aprovação/processamento. Ao preparar novo orçamento,
uploads abandonados e expirados do próprio autor são limpos, sem tocar em cursos.
Há limite de cinco orçamentos pendentes por autor. O mesmo arquivo pendente ou
em estado incerto é reaproveitado, sem criar outra chamada de conversão.

Pacote baixado imediatamente, hospedagem pública desativada. Recursos são
incorporados sem URLs temporárias e persistidos como ativos do novo projeto.
Novo projeto só aparece após persistência. `.sk.html` é servido com CSP sandbox;
o iframe não tem same-origin e o documento bloqueia conexão e recursos remotos.
HTML/SCORM clássico e Página Única incorporam o ativo; falham explicitamente se
ele não puder ser recuperado, sem gerar um arquivo offline quebrado silencioso.

## Acompanhamento e recuperação sem reconversão

`GET /api/ppt/slidekiln/jobs` lista as últimas 20 tentativas do próprio autor e
empresa; não expõe IDs do provedor, blobs ou credenciais. A UI restaura o
acompanhamento, mostra fases e falhas e oferece abrir o projeto concluído.
`POST /api/ppt/slidekiln/{id}/recover` exige a mesma propriedade e permissão de
edição. Faz claim atômico: não duplica workers, não chama `submit`, não reenvia
PPTX, não usa nova aprovação financeira. Reutiliza `packageBlob` salvo em
`slidekiln_packages` ou consulta/baixa o resultado anterior. A disponibilidade
externa continua limitada a 24 horas; pacote expirado não aciona conversão.
O ZIP é persistido antes da validação/importação. `pendingProjectId` permite
retomar o projeto da mesma tentativa após interrupção sem duplicá-lo nem
modificar cursos existentes. Processos sem atualização por 20 minutos aparecem
interrompidos e só retomam por recuperação explícita.

## Mobile

Controles de navegação, Play nativo, Ampliar/Ajustar e Tela cheia. Zoom não
reescreve texto nem distorce as imagens. O PPT continua paisagem; não há reflow
semântico ou conversão dos textos dentro de imagens. Conferir mobile e LMS.

## Publicação e testes

Testes unitários não usam a API real nem consomem a franquia. Pode reutilizar ZIPs
de teste já baixados para validar empacotamento/exportação. Não execute conversão
em produção sem orçamento aprovado na interface. Publicar não altera cursos.
