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
- Voz em off opcional em PT-BR via ElevenLabs, incorporada ao MP4; não é lip-sync.
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

## Narração PT-BR

Ative em Criar com Runway → Adicionar narração PT-BR (ElevenLabs).
Requer ELEVENLABS_API_KEY, FFmpeg e FFprobe no PATH do backend (o Docker já
inclui ambos) e permissão `elevenlabs` da empresa ou perfil super_admin.
Não altera HeyGen/Kling nem vídeos antigos. Não precisa de nova chave Runway.

O autor revisa até 600 caracteres e escolhe uma voz da conta ElevenLabs. Busca
de vozes via `/v2/voices`; vozes com rótulo brasileiro/locale verificado pt-BR
são priorizadas. Outras vozes exigem opt-in explícito e podem ter outro sotaque.
Narração usa `eleven_flash_v2_5`, `language_code=pt`; idioma não garante sotaque
brasileiro sem uma voz adequada. Prévia é um sample já existente, sem novo TTS.

A fala é gerada e persistida antes de solicitar o clipe Runway. Em falha de voz,
o vídeo não é solicitado. POST pago não tem retry automático, nem no polling.
Após a geração visual, o servidor restaura a fala persistida e incorpora com
FFmpeg/AAC ao MP4. Caso a fala seja mais longa, congela apenas o último quadro
(não acelera, não corta a frase). Duração final até 90 s; slide/elemento acompanham.
O MP4 sem voz e MP3 ficam preservados nos assets, assim como o resultado narrado.
Erros de composição podem ser recuperados por Atualizar tarefas sem gerar de novo.

Testes: `pytest tests/test_runway.py tests/test_runway_narration.py`.
Trilha instrumental opcional usa `POST /v1/text_to_music`, modelo
`eleven_music_v2_5`, mesma chave Runway. Cobrança separada do vídeo, indicativamente
20 créditos/minuto solicitado, mínimo 1 crédito. MP3 persistido; sem retry de POST.
FFmpeg incorpora música com fades e sidechain ducking sob a voz. Sem voz cantada.
O catálogo autenticado `/api/videos/library` reúne HeyGen, Runway, Kling e HeyGem,
com paginação e escopo por empresa/projeto (HeyGem por proprietário).
Não inicia gerações ao listar nem contrata GPU. A biblioteca antiga HeyGen mantém
seu comportamento de armazenamento; links antigos expirados não são recuperados.
Referências: https://elevenlabs.io/docs/api-reference/text-to-speech/convert
e https://elevenlabs.io/docs/api-reference/voices/search .

Referências:
- https://docs.dev.runwayml.com/guides/using-the-api/
- https://docs.dev.runwayml.com/api/
- https://docs.dev.runwayml.com/guides/pricing/
