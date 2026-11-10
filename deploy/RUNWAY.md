# Runway no Editor

Em Adicionar Vídeo → Criar com Runway. Não modifica a integração Kling.

## Configuração

1. Criar um projeto em https://dev.runwayml.com/ e adicionar créditos de API.
2. No serviço backend Render, cadastrar **RUNWAYML_API_SECRET** como variável
   secreta. Nunca colocar a chave no frontend, no Git, no prompt ou no chat.
3. Publicar/reiniciar o backend e publicar o frontend desta alteração.
4. Abrir a aba Runway no Editor. A verificação indica apenas presença da chave;
   validade, saldo e acesso ao modelo são conferidos pelo provedor ao gerar.

Nenhum novo servidor GPU é necessário. A geração é cobrada pela Runway.
Não há habilitação no Agente nesta versão.

## Escopo

- Gen-4.5: texto ou imagem; Gen-4 Turbo: imagem obrigatória.
- 5/10 segundos, horizontal/vertical. PNG/JPEG/WebP até 3 MB ou URL HTTPS pública.
- Ambos sem narração nesta integração. Não implementa dublagem PT-BR automática.
- Estimativa indicativa 0,12/0,05 USD por segundo; consultar preço antes de uso.
- Tarefas persistem no projeto. Polling no Editor a cada 15 segundos;
  reabrir o projeto/Atualizar tarefas retoma o acompanhamento, sem novo POST pago.
- Biblioteca própria na aba Runway: escopo do projeto, reutilização no slide.
- Resultado copiado por streaming limitado a 180 MB, salvo via asset_store/GridFS;
  o curso usa a URL local persistente, não o link temporário do provedor.
- Após mudanças, exportar novamente HTML/SCORM. Incorporação/offline segue o
  exportador de vídeos existente.
- Timeout de envio é ambíguo: não há retentativa automática. Consulte as tarefas
  no painel Runway antes de iniciar outra geração. Uma tarefa sem ID confirmado
  mantém o bloqueio do slide para evitar cobrança duplicada e exige reconciliação.

## Validação sem custos

Backend: `python -m pytest tests/test_runway.py tests/test_creator_tutor.py`
Frontend: `CI=true npm test -- --watchAll=false --runInBand RunwayVideoForm runwayJobs`
Executar geração real somente com autorização específica do responsável pelos créditos.

Referências:
- https://docs.dev.runwayml.com/guides/using-the-api/
- https://docs.dev.runwayml.com/api/
- https://docs.dev.runwayml.com/guides/pricing/
