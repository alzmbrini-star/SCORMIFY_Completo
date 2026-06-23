# Changelog


## 2026-02-XX (Feature: Toggle "Fundo Transparente" no Quiz — Exporters)

### Pedido / Contexto
- Continuação da iteração anterior: estender o toggle `quizConfig.transparentBackground` para os 3 exporters de modo que o quiz exportado (HTML zip, SCORM, single page) também respeite o flag e renderize com fundo transparente.

### Implementação
- **`html_exporter.py`** (HTML zip export, JS inline):
  - **Tela inicial do quiz** (start screen com botão "Iniciar Quiz"): conditional `quizStartBgStyle` baseado em `elem.quizConfig.transparentBackground`. Cores de título/meta também ajustadas + `text-shadow` para legibilidade.
  - **Tela de questão** (renderQuestion): `quizPlayBg` / `quizFooterBg` / `quizPlayRadius` ficam `transparent` / `0` quando `quiz.config.transparentBackground === true`. Cor da pergunta vira `#f8fafc` com drop-shadow.
  - **Tela de resultados** (showResults): `quizResultsOuterBg` vira transparent — card interno `#0f172a` permanece opaco para legibilidade do score.
- **`export_assets/player.js`** (SCORM start): o wrapper `slide-element quiz-element` agora seta `background:'transparent'`, `border:'none'` e `borderRadius:'0'` quando flag é true. Texto do placeholder também ajustado.
- **`export_assets/quiz-controller.js`** (SCORM play+results): mesmas variáveis condicionais (`quizPlayBg`, `quizFooterBg`, `quizQuestionColor`, `quizResultsOuterBg`). Inner card de resultados continua opaco.
- **`single_page_exporter.py`** + **`sp_runtime/styles.css`**:
  - `_render_quiz_element_inner` agora adiciona classe `sp-quiz-transparent` no wrapper quando flag é true.
  - Novo bloco CSS `.sp-quiz.sp-quiz-transparent { background:transparent!important; border-color:transparent!important; box-shadow:none!important; text-shadow:0 1px 2px rgba(0,0,0,.6) }` e rule equivalente para estado `[data-completed="true"]`. Body interno (`.sp-quiz-body` com perguntas) mantém seu fundo branco original.

### Verificação
- Pytest novo `tests/test_quiz_transparent_background.py` (7/7 PASSED): cobre `_render_quiz_element_inner` (true/false/omitido), template do `html_exporter` (compila + contém as 3 branches), `player.js` + `quiz-controller.js` (contêm branches), e CSS do `single_page` (regra `.sp-quiz-transparent`).
- Smoke `generate_html_template` compila para um curso com quiz transparente (154KB output válido).
- Lint clean nos arquivos modificados (warnings reportados são pré-existentes não relacionados).

### Próximo passo
- Validação visual end-to-end: exportar um curso SCORM/HTML com quiz transparente e abrir no navegador para confirmar o blend com o slide background. (recomendável usar testing agent para esse fluxo).


## 2026-02-XX (Feature: Toggle "Fundo Transparente" no Quiz — Frontend)

### Pedido / Contexto
- Usuário queria que o quiz pudesse ser embarcado sobre o background do slide sem ficar com a caixa escura `bg-gradient from-slate-800 to-slate-900` em volta. Isso permite combinar o quiz visualmente com slides que já têm imagens/cores próprias.

### Implementação (Frontend apenas — exporters será feito em iteração posterior por decisão do usuário)
- **ElementProperties.jsx**: adicionado checkbox `Fundo transparente (sobre o slide)` na seção `Configuracoes do Quiz`, ligado a `element.quizConfig.transparentBackground`. `data-testid="quiz-transparent-bg-checkbox"`.
- **SlideCanvas.jsx**: render do elemento `quiz` agora detecta `transparentBackground`. Quando ativo: troca o gradient por `bg-transparent`, usa borda tracejada para indicar o limite no editor, e ajusta cores de texto para `text-cyan-200 / text-cyan-100/90` com `drop-shadow` (legibilidade sobre slides claros).
- **CoursePreview.jsx** (`QuizPreviewPlayer`): wrapper externo do `QuizPlayer` agora condiciona `bg-slate-800` vs `bg-transparent` baseado em `quizConfig.transparentBackground`. Prop `transparentBackground` é passada ao `QuizPlayer`.
- **QuizPlayer.jsx**: novo prop `transparentBackground` (default `false`). Quando true (ou `quizConfig.transparentBackground === true`), `bgColor` vira `bg-transparent` para que a tela do quiz, a tela de resultado e a tela de loading sejam todas transparentes.

### Status backend / exporters
- **NÃO IMPLEMENTADO ainda** (intencionalmente pulado pelo usuário): `html_exporter.py`, `single_page_exporter.py`, `scorm_exporter.py` ainda emitem o background `bg-slate-800`. Será tratado em iteração posterior. No editor e na Preview do app o toggle já funciona.

### Verificação
- Lint passou nos 4 arquivos modificados (apenas warning pré-existente em `QuizPlayer.jsx:106` não relacionado).
- Screenshot da home OK (build compila, serviço rodando).


## 2026-02-XX (UX: Mensagens amigáveis no Tutor IA quando o orçamento da Universal Key acaba)

### Pedido / Contexto
- Usuário recebeu em produção a mensagem técnica `HTTP 500: AI service error: litellm.BadRequestError: OpenAIException - Budget has been exceeded! Current cost: 68.02..., Max budget: 68.0` no chat do Tutor IA. Esse erro é **operacional** (saldo da Universal Key esgotado), não um bug de código — mas a mensagem técnica não orienta o usuário sobre o que fazer.

### Implementação
- **Backend** (`routes/admin.py`): nova função pura `_map_tutor_llm_error(exc)` que retorna `(status, friendly_message)` reconhecendo 3 cenários:
  - **Budget exceeded** → 503 + instrução "Recarregar em Perfil → Universal Key → Add Balance (ou ativar auto top-up)".
  - **Rate limit / 429** → 429 + "Aguarde alguns segundos e tente novamente".
  - **Invalid API key / Unauthorized** → 503 + "Verifique a Universal Key em Perfil → Universal Key".
  - Outros erros → mantém comportamento antigo (raw text), para não esconder falhas novas.
- **Frontend** (`services/export_assets/tutor.js`): o `.catch` agora parseia o JSON de resposta de erro do backend, extrai o `detail` e mostra **verbatim** quando flagged como `friendly`. Quando não, faz fallback para a mensagem genérica de antes.

### Verificação
- Pytest novo `tests/test_tutor_friendly_errors.py` (5/5 PASSED): 3 cenários conhecidos mapeiam, erro desconhecido retorna (500, None) para fallback, mensagem de budget contém ação ("Add Balance" + "auto top-up").

### Próximo passo do usuário
- **Em produção**: precisa recarregar saldo em Perfil → Universal Key → Add Balance OU ativar auto top-up. Depois o Tutor IA volta imediatamente.
- **Para mostrar a mensagem amigável**: requer redeploy (preview já tem o fix).




## 2026-02-XX (Bugfix: Loader não aparecia no SCORM quando projeto já tinha brandKit)

### Sintoma
- Usuário reportou "Não está salvando a configuração do Loader". A configuração ESTAVA sendo salva no banco (PUT /brand-kit), e a UI mostrava os valores ao reabrir. Mas o SCORM exportado **não usava as configurações**.

### Causa raiz
- `_run_scorm_export_job` (em `routes/export.py`) usava lógica de short-circuit: "se o project_doc já tem `primaryColor` OU `loaderTitle`, pula o merge da brand kit da empresa". A maioria dos projetos JÁ tem `primaryColor` no `project.brandKit` (vem da geração inicial via Agente IA), então o merge nunca rodava → loader vinha do `companies.brandKit` mas nunca chegava no exporter.

### Implementação
- Merge agora é **per-field**, não all-or-nothing:
  ```python
  merged = dict(company_kit)
  for k, v in project_kit.items():
      if v not in (None, ""):
          merged[k] = v
  ```
- Project values vencem field-by-field, mas só quando explicitamente setados (não-vazios). Strings vazias são tratadas como "unset" → herdam do company default.

### Verificação
- Pytest novo `tests/test_brand_kit_merge.py` (5/5 PASSED): herança quando projeto só tem primary, override per-field, empty-string não clobbera, company kit vazio, missing keys.
- E2E live: salvo `loaderTitle="TESTE FINAL Loader da Empresa…"` + `loaderColor="#dc2626"` na empresa Didaxis, exportei SCORM real do projeto SCORMIFY (que já tem `primaryColor` no project.brandKit), baixei o zip de 76MB, abri `index.html` → todas as 3 verificações passaram ✅.




## 2026-02-XX (Bugfix + UI: Loader SCORM clássico + Tela de carregamento na Biblioteca de Marca)

### Pedido
- Usuário exportou para SCORM do Preview e o loader não apareceu.
- Não encontrou onde configurar o pré-loader em "Identidade das empresas".

### Causa raiz (loader ausente)
- Existem **3 caminhos** de geração HTML para o SCORM:
  1. `services/html_exporter.py` (HTML standalone + SCORM legado) — fix anterior cobriu ✅
  2. `services/single_page_exporter.py` (SCORM single-page scroll) — fix anterior cobriu ✅
  3. **`services/scorm_exporter.py` (SCORM clássico, default da maioria dos exports) — NÃO foi atualizado** ❌
- Adicionalmente, o `project_doc` chegava no exporter sem `brandKit` (que mora em `companies`), então mesmo se o loader existisse, ele não usaria a cor da marca.

### Implementação — Backend
- **`services/export_assets/player_template.html`**: injetado o overlay completo (CSS + JS de tracking) com 3 placeholders `__LOADER_TITLE__`, `__LOADER_PRIMARY__`, `__LOADER_ACCENT__`.
- **`services/scorm_exporter.py`**: `_build_html` aceita os 3 params do loader e faz `replace()` nos placeholders. `export_scorm_package` chama `resolve_loader_config(project)` para resolvê-los.
- **`routes/export.py` (`_run_scorm_export_job`)**: novo passo de **merge do brand kit da empresa** no `project_doc.brandKit` antes de chamar os exporters. Idempotente, project-level overrides são preservados.
- **`services/loader_config.py`**: prioridade estendida para incluir brand-kit-level overrides (`brandKit.loaderTitle`, `loaderColor`, `loaderAccent`) entre o per-course override e os defaults.
- **`models.py`**: `BrandKitUpdate` ganhou 3 campos opcionais (`loaderTitle`, `loaderColor`, `loaderAccent`).

### Implementação — Frontend
- **`components/admin/BrandLibraryDialog.jsx`** (aba Identidade da Biblioteca de Marca): nova seção **"Tela de carregamento (SCORM/HTML)"** com:
  - Input de texto "Mensagem personalizada" (max 80 chars, placeholder exemplificado, hint: vazio → "Carregando: <título>…").
  - Color picker + input hex para "Cor principal do loader".
  - Color picker + input hex para "Cor de destaque (barra)".
  - Texto explicativo curto sobre o propósito + comportamento de fallback.
- Persistido via PUT existente `/api/companies/{id}/brand-kit` (BrandKitUpdate aceita os novos campos).

### Verificação
- Pytest novo `test_classic_scorm_loader.py` (5/5 PASSED): SCORM clássico emite overlay, picka primaryColor da marca, honra loaderTitle override, faz fallback para título do curso, loaderColor sobrescreve primaryColor.
- Pytest existente `test_loader_branding.py` (9/9) + `test_scorm_loading_overlay.py` (4/4) continuam passando. Total: **18/18**.
- Screenshot real do UI: aba Identidade da Biblioteca de Marca mostra a nova seção logo após "Fonte", com placeholders de cor (laranja da Didaxis em destaque), separador horizontal, e instruções claras em português.




## 2026-02-XX (Feature: Loading overlay agora customizável por curso/marca)

### Pedido
- Permitir personalizar a mensagem e a cor do loader SCORM por curso (ex.: "Carregando: Treinamento da Empresa X…" com a cor primária do branding).

### Implementação
- **Novo módulo `services/loader_config.py`**: `resolve_loader_config(project)` retorna `{title_html, primary, accent}` com prioridades:
  1. Override per-curso: `project.course.loader.{title, color, accentColor}`.
  2. Brand kit: `project.brandKit.primaryColor` (+ `accentColor` se presente).
  3. Fallback neutro: título do curso ("Carregando: <title>…") + #3b82f6.
- **Defesa em profundidade**:
  - Validação rigorosa de hex (`^#[0-9a-fA-F]{3,6}$`) — cores malformadas (ex.: `rgb(...)`, lixo) caem silenciosamente para o fallback.
  - HTML-escape do título (proteção XSS via nome de curso).
  - Cap de 80 chars no título (não quebra layout em títulos longos).
  - Auto-derivação de accent (clarea o primary em 25% para a barra de progresso).
- **`services/html_exporter.py`**: `generate_standalone_html` injeta o config em `course_data["_loader"]`; `generate_html_template` lê e substitui `{loader_title}`, `{loader_primary}`, `{loader_accent}` na f-string. Strip do campo `_loader` antes de serializar para o JS bundle.
- **`services/single_page_exporter.py`**: 3 novos params no `_BUILD_PAGE` (`loader_title`, `loader_primary`, `loader_accent`); `generate_single_page_html` computa via `resolve_loader_config` e passa adiante.

### Verificação
- Pytest `tests/test_loader_branding.py` (9/9 PASSED): brand kit aplica cor, override per-curso vence, cor inválida → fallback, projeto vazio → defaults, XSS escapado, título longo capado, HTML standalone contém a cor da marca, título do curso aparece no loader, zip SCORM real contém ambos.
- Pytest existing `tests/test_scorm_loading_overlay.py` (4/4 PASSED) — sem regressões no overlay base.
- Screenshot visual: viewport 1280×720 com `brandKit.primaryColor=#dc2626` e `loader.title="Carregando: Treinamento Acme Corp…"` → spinner vermelho da marca + título personalizado em destaque.

### Como o autor usa
- **Automático**: basta ter `brandKit.primaryColor` setado no Brand Kit — o loader já adota a cor + título do curso.
- **Override total** (via Mongo / Editor Chat): `project.course.loader = { title, color, accentColor }`.




## 2026-02-XX (Feature: Loading overlay no SCORM/HTML para banda estreita)

### Pedido
- Em LMS com banda estreita, a primeira tela do SCORM mostrava imagens quebradas / placeholders antes dos assets carregarem completamente. O usuário pediu uma tela de loading que cobrisse o player até a primeira página estar pronta.

### Implementação
- Overlay full-viewport injetado **antes** de qualquer markup do player, em DUAS rotas de export:
  - **`services/html_exporter.py`** (Player do export HTML / SCORM clássico): overlay + JS rastreia `<img>`/`<video>` dentro do `#slide-elements` (a primeira slide renderizada pelo Player).
  - **`services/single_page_exporter.py`** (SCORM single-page / scroll): overlay + JS rastreia assets da primeira `<section>`.
- **Comportamento do JS**:
  - Mostra spinner + título "Carregando curso…" + barra de progresso + percentual.
  - Atualiza percentual conforme cada `<img>`/`<video>` da primeira tela termina (load + error events ambos contam para evitar travar em assets quebrados).
  - Fade-out de 0.5s ao chegar em 100%, remove do DOM após 0.6s para liberar memória.
  - **Safety net duplo**: hard timeout de 15s (nunca bloqueia o usuário para sempre) + progresso "coarse" de 5%→35% enquanto espera o DOMContentLoaded (sinal de vida em banda muito lenta).
- CSS self-contained (escopo `#scormify-loader`), sem dependências externas, z-index 99999 para garantir que cobre tudo. Visual: gradient slate escuro com spinner azul vibrante (#3b82f6 → #60a5fa).
- ARIA: `role="status"` + `aria-label="Carregando curso"` para leitores de tela.

### Verificação
- Pytest `tests/test_scorm_loading_overlay.py` (4/4 PASSED): markup presente, posição ANTES do player, hooks de progresso (img+video+timeout), zip SCORM real contém o loader.
- Pytest E2E `tests/test_scorm_loading_overlay_e2e.py` (1/1 PASSED): abre o `index.html` extraído do zip num Chromium real, verifica que o overlay (a) aparece em t=0, (b) some até t=2.5s quando não há assets.
- Smoke screenshot: viewport 1280×720, todos assets bloqueados via Playwright route abort → loader aparece centralizado, legível e cobrindo 100% da viewport.




## 2026-02-XX (Improvement: Mão realista em HD com ilustração vetorial)

### Pedido
- A versão anterior do `hand_real.png` (373×651, derivada de foto JPEG comprimida) ficava pixelada quando ampliada em telas grandes. Usuário enviou uma **ilustração vetorial nova** (`Mao.png`, 621×575, fundo já transparente) com traços muito mais limpos.

### Implementação
- Novo script `_generate_hand_real_v2.py` (pipeline simplificado já que a fonte tem fundo transparente):
  1. Detecta a ponta do marcador (topmost-leftmost dark+opaco) — mesmo algoritmo do v1.
  2. Recorta para que a ponta caia em (0,0).
  3. **Upscale 1.5×** com filtro LANCZOS → asset final 916×796 (vs. 373×651 antes), 2.45× mais pixels.
- Asset substitui o `hand_real.png` antigo — sem mudanças no `TOOL_PROFILES`, render code ou frontend. O `height_factor=3.6` continua adequado já que a proporção altura/largura é similar.

### Verificação
- Pytest `tests/test_whiteboard_tools.py` 8/8 PASSED (mesmo contrato, novo asset).
- Render visual: traços nítidos sem pixelação, tons de pele suaves, ponta do marcador alinhada perfeitamente ao texto sendo escrito. ✅




## 2026-02-XX (Feature: Whiteboard — terceira opção "Mão real" (foto))

### Pedido
- Adicionar uma 3ª opção de ferramenta no Whiteboard usando uma **foto real** de uma mão segurando um marcador (referência enviada pelo usuário), em vez da versão cartoon estilizada.

### Implementação
- **Novo asset** `assets/whiteboard/hand_real.png` (373×651 px), gerado por `_generate_hand_real.py` que processa a foto original do usuário:
  - Remove o fundo branco do quadro (threshold simples R/G/B > 230).
  - Remove a faixa cinza/azul da mesa abaixo do quadro (band y > 62% — qualquer pixel que NÃO é tom de pele é descartado).
  - Remove o texto "o de me" roxo que estava no quadro original (rect mask no canto superior esquerdo, threshold de cor).
  - Localiza a ponta do marcador automaticamente (topmost-leftmost dark pixel) e recorta o PNG final para que a ponta caia exatamente em (0, 0) — mesmo contrato dos outros assets.
- **`whiteboard_renderer.py`**: nova entrada `hand_real` em `TOOL_PROFILES` (`height_factor=3.6`, sem offset nudge porque a ponta já está exata). Constante `HAND_REAL_PATH` exportada.
- **`routes/whiteboard.py`**: regex do campo `tool` virou `^(pen|hand|hand_real)$`.
- **`WhiteboardDialog.jsx`**: 3ª opção `🤚 Mão realista` no select.
- **`tests/test_whiteboard_tools.py`**: tests parametrizados agora incluem `hand_real`; verifica que o render produz arquivo > 1MB (fall-back para pen daria <100KB), confirmando que o asset certo foi carregado.

### Verificação
- Pytest `tests/test_whiteboard_tools.py` (8/8 PASSED).
- API live: `GET /api/whiteboard/tools` → `[pen, hand, hand_real]` ✅.
- Render `tool=hand_real` produz APNG com a foto real da mão escrevendo, ponta do marcador alinhada ao texto ✅.




## 2026-02-XX (Feature: Whiteboard — escolha entre Caneta e Mão)

### Pedido
- Permitir ao autor escolher a ferramenta de desenho no Whiteboard: **caneta** (atual) ou **mão segurando caneta** (estilo VideoScribe / explainer video).

### Implementação
- **Novo asset**: `assets/whiteboard/hand_holding_pen.png` (274×294 px), gerado proceduralmente por `_generate_hand_holding_pen.py`. Antebraço estilizado + dedos contornando a mesma caneta minimalista existente. Ponta da caneta ancorada em (0,0) para reutilizar o contrato existente do renderer.
- **`services/whiteboard_renderer.py`**: nova tabela `TOOL_PROFILES` mapeando `pen`/`hand` para `(path, height_factor, offset_x, offset_y, label)`. Função `_resolve_tool(tool)` faz fallback silencioso para "pen" em entradas inválidas. Função `list_available_tools()` retorna só os tools cujos PNGs realmente existem no disco. `render_whiteboard_video(...)` agora aceita `tool: Optional[str]` e plumba `hand_offset_x/y` por todas as funções de frame (`_render_frame_writing`, `_write_apng_via_ffmpeg`, `_write_all_frames`).
- **`routes/whiteboard.py`**: campo `tool: Optional[str] = Field(default='pen', pattern='^(pen|hand)$')` no `WhiteboardGenerateRequest`. Novo endpoint `GET /api/whiteboard/tools` retorna o catálogo `[{id, label}]` para popular o seletor do frontend.
- **`pages/Editor/dialogs/WhiteboardDialog.jsx`**: novo estado `tool` persistido em localStorage, novo `<Select data-testid="whiteboard-tool-select">` com opções `🖊️ Caneta` e `✋ Mão`. Payload da chamada `/generate` agora envia `tool`.
- **Compat**: `HAND_PATH` mantido como alias de `PEN_PATH` (= `hand.png`) para não quebrar `whiteboard_plan_renderer.py` que reusa o asset legado para o AI-shapes flow.

### Verificação
- Pytest `tests/test_whiteboard_tools.py` (7/7 PASSED): catálogo, fallback, resolução, listagem, render real com cada tool (verifica que o asset certo foi carregado pelo tamanho do arquivo).
- API live: `GET /api/whiteboard/tools` → `{tools:[{id:pen,label:Caneta},{id:hand,label:Mão}]}` ✅. `POST /generate` com `tool=hand` completa job + render do APNG ✅. `tool=banana` → 422 (Pydantic rejeita) ✅.
- Smoke screenshot do diálogo no frontend mostra o novo seletor com as 2 opções visíveis.




## 2026-02-XX (Bugfix: HTML Export ignorando timeline)

### Sintoma
- Ao exportar para HTML, elementos com `startTime > 0` nunca apareciam ao longo da reprodução do slide, e elementos com `endTime < slideDuration` ficavam visíveis para sempre. O timeline visual do editor não era respeitado.

### Causa raiz (em `services/html_exporter.py`)
1. **`startTime` quebrado**: o elemento era renderizado com inline `visibility:hidden;opacity:0`. O timer disparava no instante correto e aplicava `animation: 'fadeIn 0.3s ease-out'`, **mas** o keyframe `fadeIn` só anima `opacity`, não tem `fill-mode: forwards`, e ninguém resetava `visibility` nem `opacity` no inline. Resultado: por 0.3s o elemento aparecia rápido, depois snapback para invisível.
2. **`endTime` quebrado**: análogo — o timer aplicava `fadeOut` sem `forwards`, e o elemento "ressuscitava" no final da animação até o `setTimeout(display='none', 300)` chegar (com brilho/flash visível).
3. **Prioridade de estilo inicial errada**: a branch `else if (!hasAnimations && elem.style.opacity !== undefined)` ficava ANTES de `else if (initiallyHidden)`. Se o usuário definia uma opacidade customizada (ex.: 0.8) E startTime > 0, o elemento era renderizado VISÍVEL desde t=0 — o timeline era completamente ignorado.

### Implementação
- Show timer agora reseta explicitamente `element.style.visibility = 'visible'` e `element.style.opacity = String(elementOpacity)` antes do `fadeIn`, garantindo que o fade encerre num estado visível persistente.
- Hide timer agora usa `fadeOut 0.3s ease-out forwards` + reset final de `visibility`/`opacity` para `hidden`/`0` — sem flash de volta.
- Reordenado o bloco de estilo inicial: `initiallyHidden` (startTime > 0 OU entrance animation) é avaliado ANTES de respeitar a opacidade customizada, então o timeline sempre vence.

### Verificação
- Pytest `tests/test_html_export_timeline.py` (2/2 PASSED): verifica que o HTML gerado contém os resets de visibility/opacity, o `forwards` no fadeOut, a nova ordem de prioridade no init, e que `startTime`/`endTime` chegam na JSON embedded.
- Pytest E2E `tests/test_html_export_timeline_e2e.py` (1/1 PASSED): gera HTML real, abre num Chromium via Playwright e verifica em 3 marcos temporais (0.2s / 1.3s / 2.0s) que elementos aparecem/somem nos instantes corretos via `getComputedStyle`.




## 2026-02-XX (Bugfix: AI Shapes — espaçamento entre formas e zonas)

### Sintoma
- Após o fix anterior do autofit, as caixas cresciam corretamente para abraçar o texto, MAS invadiam zonas adjacentes (e.g. caixa esquerda "PowerPoint/PDF/Word" engolia metade do círculo central "SCORMIFY"). Layout poluído e ilegível.

### Causa raiz
- O LLM gerava fonts grandes demais (fs=70-80) para textos longos (~19 chars), produzindo texto renderizado de ~600-700px de largura.
- Em um canvas dividido em 3 zonas de ~480px cada (LEFT/CENTER/RIGHT), o autofit não tinha como manter o texto dentro de uma zona — ele só sabia "fit text", não "fit text dentro de uma zona".

### Implementação (pipeline de espaçamento em 4 passos)
1. **`_cap_text_font_to_zone`** (novo): antes do autofit, reduz iterativamente `font_size` (passo de 4px, piso de 36px) até a largura renderizada caber em `MAX_BOXED_TEXT_WIDTH=420px`. Garante que após autofit + 40px de padding, a caixa não invada a zona vizinha.
2. **`_autofit_shapes`** (já existente, 2026-02): cresce caixas estreitas para conter texto.
3. **`_clamp_shapes_to_canvas`** (já existente): impede shapes de extrapolar bordas.
4. **`_enforce_shape_separation`** (novo): detecta pares de shapes (rect/circle) com AABBs sobrepostas e ENCOLHE a caixa mais próxima do conflito (mínimo 80px de largura, 30px de gap). Não move shapes para não quebrar referências de setas (`x1,y1`→`x2,y2`).
5. **Prompt do LLM atualizado**: explicitamente declara as 3 zonas X (`LEFT [140,620]`, `CENTER [700,1220]`, `RIGHT [1300,1780]`), a regra de ouro de font_size por largura, e avisa sobre os passes de post-processing.

### Verificação
- Pytest `tests/test_whiteboard_spacing.py` (5/5 PASSED) + `tests/test_whiteboard_autofit.py` (5/5 PASSED).
- Simulação local com o exato output que produziu a screenshot poluída → todos shapes ficam separados em suas zonas, **0 overlaps** detectados pelo teste de AABB intersection.




## 2026-02-XX (Bugfix: Auto-fit do Whiteboard AI Shapes — caixas estreitas em torno de textos largos)

### Sintoma
- No modo AI Shapes, caixas do lado esquerdo (textos longos como `PowerPoint/PDF/Word`, `Vídeos/Docs Técnicos`) ficavam coladas no texto, enquanto caixas do lado direito (`Curso SCORM 1.2`) tinham padding generoso. Resultado visualmente assimétrico.

### Causa raiz
- `_autofit_shapes` em `services/whiteboard_ai_plan.py` usava a regra "centro do texto dentro da caixa (±PAD)" para associar texto ↔ shape. Funciona quando a caixa do LLM é grande, mas **quebra** quando o LLM gera uma caixa estreita em torno de um texto longo: o centro do texto cai FORA do `x1` da caixa, o match falha e a caixa não cresce.
- Adicionalmente, `_measure_text_bbox` usava só `font.getlength()` (advance width) com 8% de margem — para fontes manuscritas inclinadas como Caveat, a tinta visível (`getbbox()[2]`) pode ser mais larga que o advance, e 8% não era suficiente.

### Implementação
- **`_autofit_shapes`**: nova regra de associação = (centro Y do texto dentro do range Y da caixa ±PAD) ∧ (qualquer sobreposição horizontal das AABBs ±PAD). Casa "texto que visualmente pertence à caixa" mesmo quando a largura do LLM está totalmente errada. Mesma lógica replicada para `circle` (usa a AABB da elipse).
- **`_measure_text_bbox`**: width = `max(getlength, getbbox[2])` para capturar tanto o advance quanto a borda direita da tinta; margem horizontal subiu de 1.08x → 1.12x, vertical de 1.15x → 1.18x.
- **`PAD`** subiu de 30 → 40 px para padding mais consistente entre lados.

### Verificação
- Pytest `tests/test_whiteboard_autofit.py` (5/5 PASSED): caixa estreita cresce, caixa larga não encolhe, texto longe não associa, duas caixas empilhadas casam só com seus textos respectivos, círculo cresce em torno de label largo.
- Simulação local: 3 caixas (2 com textos longos, 1 com texto curto) → todas terminam com **exatamente 40px de padding à direita** independentemente do comprimento do texto. ✅




## 2026-02-XX (Bugfix: Ctrl+V no diálogo de Whiteboard colando o último elemento de tela)

### Sintoma
- Ao abrir o diálogo de Whiteboard (AI Mode ou modo texto normal) e tentar colar um prompt vindo do clipboard externo (Ctrl+V), o campo recebia o **último elemento de canvas copiado** em vez do texto do clipboard.

### Causa raiz
- `components/editor/SlideCanvas.jsx` registrava um listener global de `keydown` no `window` que interceptava Ctrl+C / Ctrl+V / Ctrl+D / Delete / Backspace / setas a fim de operar nos elementos do canvas.
- A única guarda era `!editingElementId` — ela só desliga os atalhos durante a edição inline de texto no canvas, **não** quando o foco está em um input/textarea de um Dialog (Radix portala o diálogo para fora da árvore do canvas, então o `editingElementId` continua `null`).
- Resultado: pressionar Ctrl+V dentro do input do Whiteboard chamava `preventDefault()` + `onPasteElement()`, colando o elemento de canvas copiado em vez do clipboard externo.

### Implementação
- `SlideCanvas.handleKeyDown`: nova guarda lendo `document.activeElement` e retornando cedo quando o tag é `input`/`textarea`/`select` ou o elemento é `contentEditable`. `Escape` continua sendo respeitado (para permitir desselecionar). Comentário explicativo apontando o bug e o motivo.
- Cobre não só Ctrl+V mas também Ctrl+C/D e Delete/Backspace — antes do fix, apertar Backspace para apagar texto enquanto um elemento do canvas estava selecionado **deletava o elemento** em vez de apagar caracteres no input.

### Verificação
- Playwright in-browser: dispatch sintético de `Ctrl+V` no `window` enquanto `document.activeElement === TEXTAREA` → `defaultPrevented === false` ✅
- Idem com `Backspace` em textarea com foco → `defaultPrevented === false` ✅
- Editor segue carregando normalmente (smoke screenshot OK).




## 2026-02-XX (P0 Fix: PPT Import preencher Presenter Notes)

### Pedido
- Bug recorrente adiado por 3 forks: ao importar PPT, o painel "Notas do Apresentador" no Editor ficava vazio mesmo quando o slide tinha texto, deixando o autor sem contexto e o AI Tutor sem material.

### Causa raiz
- `services/ppt_image_parser.py` (fluxo high-fidelity ConvertAPI/LibreOffice) e `services/ppt_parser.py` (fallback python-only) só populavam `slide.notes` quando o PPTX tinha **notas de apresentador reais** (poucas vezes acontece).
- O texto dos shapes ia para `extractedText` (consumido pelo AI Tutor e SCORM exporter), mas a UI do Presenter Notes só lê `slide.notes`. Resultado: painel vazio.
- Adicionalmente, `extractedText` não estava declarado no model `Slide` — funcionava por causa de `extra="allow"`, mas era frágil.

### Implementação
- **`models.py`**: declarado `extractedText: Optional[str]` no `Slide` para tornar o contrato explícito.
- **`services/ppt_image_parser.py`**: notas vazias / só com whitespace agora são tratadas como ausentes; quando não há notas reais e há `extractedText`, este último é copiado para `slide.notes`. Logs estruturados (`using PPT presenter notes` vs `using extractedText as notes`) facilitam triagem em produção.
- **`services/ppt_parser.py`** (fallback): mesma lógica, e agora também extrai `extractedText` (antes só o high-fidelity tinha).
- **`tests/test_ppt_import_notes.py`**: 3 testes pytest cobrindo (a) notas reais preservadas, (b) fallback quando não há notas, (c) whitespace-only notas → fallback, (d) slide sem nada → não quebra, (e) serialização `model_dump` contém os dois campos.

### Verificação
- Pytest: `tests/test_ppt_import_notes.py` → 3/3 PASSED.
- E2E via API: upload de PPT com 2 slides (um com notas reais, um sem) → ambos retornam `notes` populado, `extractedText` independente preservado.
- Regressão: `tests/test_tutor_context.py` continua passando (AI Tutor segue usando `extractedText` separadamente).




## 2026-02-XX (Feature: Nomeação automática de elementos Whiteboard no Layers)

### Pedido
- Com múltiplos whiteboards no mesmo slide, o painel "Elementos" mostrava todos como genéricos "Imagem" / "Video", impossível distinguir qual era qual ao editar.

### Implementação
- **Backend** (`routes/whiteboard.py`): ao criar o elemento de whiteboard, define `name` com o valor do campo "Título" do diálogo. Se vazio, fallback automático **"Whiteboard N"** onde N é a sequência (conta whiteboards pré-existentes + 1 no slide).
- **Frontend** (`SortableLayerItem.jsx`): o label do item agora prioriza `element.name` (se setado), caindo para os defaults genéricos só pra elementos legados ou sem nome.

### Resultado no Layers
- Whiteboard com Título "Introdução" → mostrado como **Introdução** no painel
- Whiteboard sem título → **Whiteboard 1**, **Whiteboard 2**, … numerados automaticamente
- Funciona retroativamente para qualquer outro elemento que tenha `element.name` setado (ex: imagens da galeria com `alt`/`name`).

### Observação
- `SlideElement` no Pydantic já tem `model_config = ConfigDict(extra="allow")`, então `name` é persistido em Mongo sem precisar adicionar campo no schema.



## 2026-02-XX (Bugfix: Whiteboard perdia config entre aberturas do diálogo)

### Sintoma
- Ao gerar um segundo Whiteboard, mesmo com "Fundo transparente" aparentemente ativo, o resultado vinha como MP4 com fundo branco. Toggles "Apagar ao final", velocidade, fonte etc. também resetavam.

### Causa
- `<Dialog>` do Radix UI **desmonta os filhos** quando fecha (`open=false`). Como resultado, todo o estado interno do `WhiteboardDialog` voltava aos defaults do `useState(...)` na próxima abertura. Visualmente o usuário "lembrava" de ter ligado o toggle, mas o estado já estava em `false`.
- Pior: o usuário pode ter clicado "Gerar" sem perceber que os toggles tinham resetado, porque os valores DEFAULTS são todos `false` e cinza pálido.

### Correção
- **Persistência em `localStorage`** das preferências de render no `WhiteboardDialog.jsx`:
  - `transparent`, `eraseAtEnd`, `speed`, `fontSize`, `fontFamily` agora são lidos do `localStorage` no `useState(...)` inicial e gravados via `useEffect` a cada alteração.
  - Chaves prefixadas `wb:` para evitar conflito com outras features (ex: `wb:transparent`, `wb:eraseAtEnd`).
  - Try/catch em volta de cada acesso ao localStorage (privacy mode / quota / iframe sandboxed).
- **Não persistido**: `text`, `title`, `inkColor`, `result` — estes são por-slide / por-sessão, não fazem sentido reusar.

### Resultado esperado
- Usuário liga "Fundo transparente" no primeiro whiteboard, fecha, abre de novo → toggle continua ON. Gera o segundo → APNG transparente ✓
- Mesmo princípio para "Apagar ao final" e demais sliders.



## 2026-02-XX (Bugfix: Whiteboard sobrescrevia o anterior no mesmo slide)

### Sintoma
- Ao gerar um segundo Whiteboard no mesmo slide, ele removia o primeiro. Impossível encadear via Timeline porque só havia 1 elemento por vez.

### Causa
- `routes/whiteboard.py:_run_whiteboard_job` tinha um filtro `elements = [e for e in elements if not e.get("isWhiteboard")]` ANTES de adicionar o novo. Era proposital pra evitar "stacking" durante regenerações, mas atrapalha o caso de uso de múltiplos whiteboards encadeados.

### Correção
- Removido o filtro — agora cada geração apenas anexa.
- **Bônus UX**: posição inicial agora é deslocada em +24px (x,y) por whiteboard já existente no slide (até +200px). Assim no Editor os múltiplos não ficam exatamente sobrepostos visualmente — o autor consegue clicar/selecionar cada um pra ajustar timeline/posição.
- Limite máximo: ~9 whiteboards antes do offset saturar — mais que suficiente pra qualquer caso prático de encadeamento.

### Teste manual
- 2 POSTs sequenciais no mesmo slide → 2 elementos `isWhiteboard=true` coexistem ✓
- Posições: 1º em (320,50), 2º em (344,74) ✓



## 2026-02-XX (Feature: Whiteboard "Apagar ao final" — eraser sweep)

### Pedido do usuário
- Encadear vários whiteboards no Timeline sem o texto anterior ficar na tela. Solução: cada vídeo de whiteboard escreve, segura 1.5s, e depois APAGA com um apagador estilo lousa antes do próximo começar.

### Implementação
- **Backend renderer** (`whiteboard_renderer.py`):
  - Novo parâmetro `erase_at_end: bool = False`.
  - Quando ligado, calcula a bounding box do texto (`_compute_text_band`), divide em stripes horizontais (altura ≈ 1.05 × font_size), agenda frames por stripe (velocidade ≈ 2.5× a da escrita).
  - Pré-renderiza uma única camada com TODOS os chars desenhados (`_render_final_text_layer`) — depois a máscara progressiva simplesmente esconde a parte "já apagada" (eficiente: não re-renderiza glyphs).
  - `_render_frame_erasing`: para cada frame de apagamento, monta um RGBA com o background, título/sublinhado, máscara progressiva (stripes finalizadas + stripe atual até a posição do apagador) e desenha o bloco retangular cinza (`ERASER_COLOR=(110,110,115)`) com leve highlight `(170,170,175)` no topo para parecer um apagador de feltro.
  - Tanto APNG (`-c:v apng -plays 1`) quanto MP4 (libx264) suportam o fluxo write→dwell→erase de forma contínua.
  - Metadata expandida: `eraseAtEnd`, `eraseStripes`, `eraseFrames`, `eraseDuration`.
- **API** (`routes/whiteboard.py`): novo campo `eraseAtEnd: Optional[bool]` no `WhiteboardGenerateRequest`, passado direto para o renderer.
- **Frontend** (`WhiteboardDialog.jsx`): novo `<Switch>` "Apagar ao final" com ícone `<Eraser>` da lucide-react, abaixo do toggle de transparente. Estado `eraseAtEnd` enviado no payload.

### Teste manual (verificado por análise de frame com IA visual)
- MP4 opaco: 48 chars + dwell + 2 stripes (72 frames apagador) → 12.3s totais ✓
- APNG transparente: mesmo fluxo, 64 frames apagador ✓
- Frame inspecionado durante a fase de apagamento: bloco cinza horizontal visível, deslizando esquerda→direita, texto sendo coberto progressivamente. ✓

### Uso esperado
1. Autor escreve "Frase 1" + liga "Apagar ao final" → gera Vídeo A
2. Cria novo whiteboard, "Frase 2" + apagar → gera Vídeo B
3. Encadeia A e B no Timeline. Quando Vídeo A acaba, a tela está limpa. Vídeo B começa do zero. Sem sobreposição visual.



## 2026-02-XX (Feature: HTML export também embarca Whiteboard)

### Pedido
- Usuário precisa que slides com vídeo de Whiteboard funcionem também no export **HTML Standalone** (não só SCORM). Antes, o HTML saía com URL `/api/whiteboard/file/wb_*.mp4|.png` que não resolvia offline.

### Correção
- **`services/html_exporter.py`** (HTML tradicional):
  - Novo helper `_resolve_whiteboard_asset(src)` que lê `wb_*` direto de `backend/storage/whiteboard/` e devolve base64 data URI.
  - Branches `image` e `video` agora detectam `/api/whiteboard/file/` ANTES do fluxo padrão e usam o helper.
  - Slide-level `slide.videoUrl` também é processado (legado das gerações MP4 antigas) — evita URL leakage no JSON embutido.
- **`services/single_page_exporter.py`** (HTML single-page):
  - `_resolve_asset_url` ganhou pattern `/api/whiteboard/file/(.+)` → resolve de `storage/whiteboard/` para data URI. Como TODOS os renders de elemento usam essa função, tanto image quanto video são cobertos de uma vez.

### Cobertura
- MP4 (`type=video`, opaque) → embed como `data:video/mp4;base64`.
- APNG (`type=image`, `isAnimatedPng=true`, transparent) → embed como `data:image/png;base64` (browsers tocam APNG nativamente).

### Testes
- Novo `tests/test_html_whiteboard_embed.py` valida ambos exporters com arquivos reais do storage. 3 testes (HTML traditional, HTML single-page, SCORM) — todos passando.



## 2026-02-XX (Bugfix produção: Whiteboard 520 intermitente durante polling)

### Sintoma
- Após o fix anterior (async job), a geração do Whiteboard ainda apresentava erro 520 em produção — agora não mais no POST, mas no GET `/api/job/{jobId}` durante o polling. O erro era intermitente: bastava UM 520 do Cloudflare e o frontend abortava todo o fluxo, mesmo se a renderização continuasse em andamento no backend.

### Causa
- Cloudflare 520 é "origem retornou resposta vazia/inválida". Durante renders longos de APNG (1000+ frames), o pod de produção fica sob carga de CPU e o Cloudflare ocasionalmente perde a resposta do origin — comportamento normal sob carga, não um bug do código.
- O frontend tinha `if (!sres.ok) throw` — qualquer 5xx isolado matava o polling.

### Correção (resiliência client-side)
- **Frontend** (`WhiteboardDialog.jsx`): polling agora tolera 8 erros consecutivos (~16s de janela de instabilidade) sem abortar. Trata separadamente:
  - **Network errors** (`fetch` reject): incrementa contador, continua.
  - **5xx** (incluindo 502/503/504/520/521/522/523/524 do Cloudflare): incrementa contador, continua.
  - **4xx**: aborta imediatamente (auth/erro de cliente real).
  - Contador é resetado a cada resposta OK — só "queima" tentativas se a instabilidade for sustentada.
- Mantém o ceiling absoluto de 5 minutos para não travar indefinidamente.

### Por que isso resolve
- Renders normalmente finalizam em 30–90s. Mesmo que o Cloudflare derrube 2-3 polls intermediários, o frontend persiste e captura o `status=completed` no próximo poll bem-sucedido. A renderização no backend nunca foi o problema — só a fragilidade do client.

### Action item para o usuário
- **Redeploy to Production** para aplicar a tolerância no frontend.



## 2026-02-XX (Bugfix produção: Whiteboard 520 em renders longos)

### Sintoma (produção)
- Em https://backend-startup.emergent.host, gerar um Whiteboard com texto grande retornava `Failed to load resource: 520` no console. Em renders longos (APNG transparente com 1000+ frames levando 40–60s), a requisição síncrona ultrapassava o limite de upstream do Cloudflare (~100s para alguns paths) e era abortada antes do backend responder.

### Correção (async job pattern)
- **Backend** (`routes/whiteboard.py`): `POST /api/whiteboard/generate` agora enfileira um job (`{jobId, statusUrl}`) e retorna em <100ms. O render + bind no slide rodam em `asyncio.create_task`. Reaproveita o `create_job/update_job/get_job` que já existia para o SCORM export.
- **Frontend** (`WhiteboardDialog.jsx`): após enviar o POST, fica em loop polling `/api/job/{jobId}` a cada 2s até `status == 'completed' | 'failed'`. Ceiling de 5min. O resto do fluxo (mostrar duração, MB, etc.) é idêntico — pega tudo de `job.result`.

### Por que isso resolve
- A conexão HTTP do POST agora fecha em milissegundos, fora da janela do Cloudflare. Os polls subsequentes são GETs leves (<10ms), também imunes a timeout.
- Bonus: agora dá pra adicionar barra de progresso real no futuro (basta `update_job` com `progress` de dentro do renderer).

### Teste
- Curl simulando o fluxo no preview: POST devolveu jobId imediato, polling retornou `status=completed` com `result.videoUrl` em ~2s para texto curto. ✅

### Action item para o usuário
- Faça **Redeploy to Production** para aplicar o fix no link público.



## 2026-02-XX (Bugfix: Whiteboard APNG ficava em loop infinito)

### Sintoma
- Vídeos de Whiteboard com fundo transparente (APNG) reiniciavam sozinhos toda vez que terminavam de escrever o texto. Esperado: tocar até o fim e parar congelado no quadro final.

### Causa
- `whiteboard_renderer.py:_write_apng_via_ffmpeg` chamava `ffmpeg ... -plays 0` (que no APNG significa "loop infinito"). O chunk `acTL` da PNG saía com `num_plays=0`.

### Correção
- **Renderer**: trocado para `-plays 1` (toca uma única vez).
- **Migração dos arquivos existentes**: script utilitário em `/tmp/fix_apng_loop.py` patcheia o chunk `acTL` in-place (reescreve apenas `num_plays` + CRC32) em todos os APNGs já em `/app/backend/storage/whiteboard/*.png`. Muito mais rápido que re-encode (ms vs minutos por arquivo). Aplicado em 7 APNGs existentes.

### Como verificar
- Recarregue um curso com slide whiteboard APNG → o vídeo escreve o texto e fica parado no quadro final, sem reiniciar.



## 2026-02-XX (Bugfix: SCORM Export quebrando slides com Whiteboard)

### P0 fix: Vídeo/APNG do Whiteboard não embarcava no pacote SCORM
- **Sintoma**: Ao exportar um curso SCORM Multi-página, slides contendo um vídeo de Whiteboard (Hand Writer) apareciam como tela vermelha com ícone de imagem quebrada no canto. Outros slides funcionavam normalmente.
- **Causa raiz**: O `scorm_exporter.py` só tratava URLs `/assets/...` e URLs externas `http(s)://...`. O renderer de Whiteboard gera URLs relativas `/api/whiteboard/file/wb_*.mp4` (vídeo) ou `/api/whiteboard/file/wb_*.png` (APNG transparente). Essas URLs caíam no fallthrough, ficavam intactas no `course.json` exportado e não resolviam quando o pacote era aberto offline.
- **Correção** (`/app/backend/services/scorm_exporter.py`, ~linha 548): novo branch que detecta `/api/whiteboard/file/` no `element.src`, localiza o arquivo em `STORAGE_DIR/whiteboard/`, copia para `package/assets/` e reescreve o `src` para `assets/{nome}`. Funciona tanto para MP4 (`type=video`) quanto APNG (`type=image` + `isAnimatedPng=true`).
- **Teste**: novo `tests/test_scorm_whiteboard_asset.py` valida copy + rewrite para MP4 e APNG usando arquivos reais já presentes em `storage/whiteboard/`. Passa em verde.
- **Impacto**: usuário precisa **Redeploy to Production** para que a correção apareça no link público.



## 2026-02-XX (Whiteboard: Negrito + Sublinhado + Alinhamento + Listas)

### Feature: Set completo de formatação RTF
- **Backend renderer**: chars agora é `list[dict]` com `{ch, x, y, color, bold, underline}`. Parser HTML estendido para extrair:
  - **Negrito** via `<b>`, `<strong>`, `font-weight:bold|600+`
  - **Sublinhado** via `<u>`, `text-decoration:underline`
  - **Alinhamento** via `text-align:left|center|right` no bloco ancestral (consumido por linha-fonte, não por linha-quebrada)
  - **Listas** `<ul><li>...</li></ul>` — cada `<li>` vira uma linha começando com "• "
- **Render**:
  - **Bold** simulado por **dilatação 1-px do alpha** no `_make_glyph_image` (sem variante bold nas fontes manuscritas; dilatação fica visualmente como "mais pressão no marcador"). Cache de glifo é mantido — bold é aplicado no composite.
  - **Underline** desenhado por `ImageDraw.line` abaixo da baseline (offset 0.92×altura, thickness ≈ altura/28) em segmentos contíguos. Segmento cresce progressivamente conforme a caneta avança (sublinhado também "anima" junto da escrita).
  - **Alinhamento** aplicado por **linha-fonte** (parágrafo HTML) — cada wrap subline herda a alignment do parágrafo. X inicial calculado de `MARGIN_X + (max_w − line_w) / 2` para centro e `MARGIN_X + max_w − line_w` para direita.
- **Frontend** (`WhiteboardDialog.jsx`):
  - Segunda linha de toolbar com botões **B / U / ⇤ / ⇔ / ⇥ / •** (Bold, Underline, AlignLeft, AlignCenter, AlignRight, BulletList).
  - Cada botão usa `document.execCommand` (`bold`, `underline`, `justifyLeft/Center/Right`, `insertUnorderedList`) com `styleWithCSS=true` para gerar HTML semanticamente compatível com o parser do backend.
  - Detecção de payload expandida — envia `textHtml` se houver QUALQUER formatação (cor, bold, underline, alinhamento, ou lista).
- **Skip nesta iteração**: Itálico (Caveat/Marker não têm itálico nativo; faking via skew CSS ficaria visualmente ruim). Listas numeradas. Identação multi-nível. Tamanho por trecho.
- **Verificação visual**: HTML de teste com Título centralizado + negrito, Normal + sublinhado, 2 itens com bullet, e "Direita" alinhada à direita — todos os 4 features renderizaram corretamente no MP4.



## 2026-02-XX (Whiteboard: Cor da tinta + editor RTF mini)

### Feature: Color picker global + RTF inline para colorir trechos
- **Backend renderer** (`whiteboard_renderer.py`):
  - Estrutura de `chars` virou 4-tupla `(char, x, y, color)` (era 3-tupla). Cada caractere carrega sua própria cor RGB.
  - Nova função `_parse_html_to_runs` (HTMLParser stdlib) extrai inline `<span style="color:#XXX">` e `<font color="#XXX">` em sequências de `(char, color)`.
  - Novo `_parse_color` aceita `#RRGGBB`, `#RGB`, `rgb(r,g,b)`.
  - `_make_glyph_image` recebe cor: recolore o RGB do glifo mantendo o alpha (que preserva antialiasing). Cache de glifo continua keyed por char (cor aplicada no composite).
  - `_layout` aceita `default_color` e `text_html` opcionais; quando `text_html` está presente, faz parsing das runs e mapeia cada char para sua cor.
  - `render_whiteboard_video` aceita `ink_color` e `text_html` params; renderiza cada char com sua cor exata.
- **Backend route** (`whiteboard.py`): novos campos `inkColor` (hex/rgb) e `textHtml` (HTML max 8000 chars). Validados e passados ao renderer.
- **Frontend** (`WhiteboardDialog.jsx`):
  - **Editor mini-RTF**: substituí o Textarea por um `<div contentEditable>` com toolbar de cores. Paleta de 10 cores (alto contraste contra branco) + input `<input type="color">` para cor customizada + botão "Limpar" (`removeFormat`).
  - **Cor padrão das letras**: input color picker no rodapé do editor que define `inkColor` para todo o texto não-colorido.
  - **Comportamento de seleção**: usa `document.execCommand('foreColor', ...)` com `styleWithCSS=true` para envolver a seleção em `<span style="color:#XXX">`.
  - **Paste sanitization**: paste externo é convertido para plain text (`insertText`) para evitar HTML/CSS sujo de outros apps.
  - **Sync bidirecional**: `text` (plain) e `textHtml` (rich) sincronizados via `onInput`/`onBlur`. Quando IA preenche texto, o useEffect atualiza o contentEditable preservando o cursor.
  - **Payload smart**: só envia `textHtml` se detectou pelo menos uma tag de cor inline — caso contrário envia só `text` + `inkColor` global (payloads menores).
- **Verificação**:
  - ✅ Global red (#E11D48): "Vermelho!" todo na cor escolhida.
  - ✅ Mixed HTML: "Normal `VERMELHO` e `azul`" — cada palavra na sua cor exata, com a caneta tracejando o esqueleto em qualquer cor.
- **Skip nesta iteração**: variação de tamanho por trecho (exigiria reflow de layout para mixed font sizes — bem mais complexo). Documentado como backlog.



## 2026-02-XX (Whiteboard: Gerador de texto com IA — GPT-4o)

### Feature: Texto do whiteboard gerado por IA com contexto do slide
- **Botão "Gerar com IA"** no `WhiteboardDialog`: expande um painel violeta com um campo opcional de instrução livre e um botão "Gerar texto agora". O texto retornado preenche o textarea principal.
- **Híbrido** (slide + prompt):
  - Extrai automaticamente do slide: `title`, conteúdo de `elements` (texto/HTML, com tags strippadas), `narration`, `notes`, `extractedText` (PPT).
  - Instrução livre opcional do autor (ex: "tom motivacional", "incluir data X"). Pode ser deixada vazia se o contexto do slide é suficiente.
- **Modelo**: GPT-4o via Emergent LLM Key (`emergentintegrations.llm.chat.LlmChat`), seguindo o padrão já usado em `density_suggester.py`.
- **Post-processing**:
  - Remove aspas/backticks envolventes que o modelo às vezes adiciona.
  - Converte `\n` literal (que GPT às vezes emite como 2 chars) em quebra real, respeitada pelo renderer.
  - Hard-cap em `maxChars` (default 280, range 80..600) com elipse no fim.
  - Strip por linha + colapso de linhas vazias.
- **Endpoint**: `POST /api/whiteboard/generate-text` — payload `{userPrompt?, projectId?, slideId?, maxChars}` → `{text, charsUsed}`.
- **Validação**: 400 se nem userPrompt nem slide content estão presentes (evita "geração no escuro").
- **Aplicado em**: `routes/whiteboard.py` (endpoint + extrator de contexto), `pages/Editor/dialogs/WhiteboardDialog.jsx` (UI expansível com Wand2 icon).



## 2026-02-XX (Whiteboard: Fundo transparente + multi-fontes + tamanhos grandes)

### Feature: Fundo transparente via APNG animado
- **Motivação**: usuário queria sobrepor o vídeo do whiteboard no background do slide sem fundo branco.
- **Investigação de codec**: WebM VP9-alpha e VP8-alpha foram testados primeiro (parecem suportados via `-pix_fmt yuva420p`), mas tanto o `imageio_ffmpeg` bundled quanto o `ffmpeg` 5.1 do sistema **silenciosamente strippam o canal alpha** durante o encode. O output sempre saía como yuv420p mesmo com a flag `alpha_mode=1`.
- **Solução**: usamos **APNG (Animated PNG)** para outputs transparentes. APNG preserva alpha losslessly e tem suporte nativo em todos os browsers modernos via `<img>`. Trade-off: arquivos ~10x maiores que MP4 (3.4s = ~1.6MB), aceitável para animações curtas (recomendado <300 chars/slide).
- **Pipeline**: quando `transparent=True`, frames RGBA são pipeados diretamente para `ffmpeg -c:v apng -f apng -plays 0 -pred mixed` via stdin. Compositing testado sobre fundo colorido: 100% transparente, sem halos.
- **Binding ao slide**: APNG transparente é injetado como `element.type = "image"` (com `isAnimatedPng: true`) em vez de `"video"`, pois browsers renderizam APNG via `<img>` automaticamente. MP4 opaco continua como `"video"`.

### Feature: 7 fontes manuscritas + tamanhos até 240px
- **Fontes empacotadas** (todas OFL/Apache, baixadas do repositório oficial Google Fonts):
  - Caveat (manuscrita, default)
  - Architects Daughter (arquiteto)
  - Indie Flower (arredondada)
  - Patrick Hand (limpa)
  - Permanent Marker (marcador grosso)
  - Shadows Into Light (fina)
  - Kalam (caligráfica)
- **Catalog API**: `GET /api/whiteboard/fonts` retorna fontes presentes no disco com label e style hint.
- **Tamanhos**: `fontSize` agora aceita 40..240 (era 40..140), com presets na UI: Pequeno (64), Médio (96), Grande (140), Maior (180), Enorme (220), além de input numérico livre.
- **UI nova** (`WhiteboardDialog.jsx`):
  - Dropdown de fonte (fetched de `/api/whiteboard/fonts`)
  - Combinação preset + input numérico para tamanho
  - Toggle "Fundo transparente" com explicação do trade-off
  - Preview do resultado em `<img>` (APNG) ou `<video>` (MP4) com xadrez de fundo para visualizar transparência

### Files
- `services/whiteboard_renderer.py`: FONT_CATALOG, `_resolve_font_path`, `list_available_fonts`, `_write_apng_via_ffmpeg`, suporte transparent no `_render_frame_writing`.
- `routes/whiteboard.py`: fontFamily/transparent params, /fonts endpoint, binding APNG como image element, serve .png com mime image/apng.
- `assets/whiteboard/fonts/*.ttf`: 7 fontes empacotadas (~1.3MB total).
- `pages/Editor/dialogs/WhiteboardDialog.jsx`: UI completa.



## 2026-02-XX (Whiteboard: Caneta minimalista + escrita coluna-a-coluna)

### Feature: Asset de caneta minimalista (substitui mão cartunizada)
- **Asset**: `/app/backend/assets/whiteboard/_generate_hand.py` reescrito para gerar uma caneta minimalista (estilo fineliner) com nib, seção, barril, clip metálico e end cap. Mantida a convenção do tip em (0, 0) para compatibilidade com o renderer.
- **Output**: PNG 144×159 (`hand.png`), paleta restrita (preto/grafite/cinza metálico).
- **Renderer**: `hand_target_h` ajustado de 3.0× para 2.2× do `font_size` para proporção mais elegante. Offsets do tip ajustados para alinhamento preciso no traço.

### Bug fix: Caneta parecia "parada" no vídeo gerado
- **Root cause**: o `chars_per_second` default era 19 (~ritmo de digitação robótica). A 30 FPS isso dá só **1.58 frames por caractere**. Como o algoritmo usa ~14 sub-passos por letra para traçar o esqueleto, cada frame avançava ~9 sub-passos — o olho não captava movimento dentro de uma letra, parecia que a caneta pulava de letra em letra.
- **Fix #1 (backend)**: sub-passos por caractere agora são calculados em função de `FPS/cps` (clamp 6..24), garantindo aproximadamente 1 sub-passo por frame. Também adicionada duração mínima `total_substeps/FPS` para forçar ≥1 frame por sub-passo (slow-down automático se cps for muito alto).
- **Fix #2 (frontend)**: default reduzido de 19 → 6 cps (velocidade natural de manuscrita). Limites do input ajustados para 2..30 (era 4..40). Texto de ajuda reescrito.
- **Verificação**: gerei "O instrutor deve enfatizar" com título em cps=6. Grid de 16 frames mostra a caneta em posições nitidamente diferentes em cada frame, acompanhando o texto sendo escrito.
- **Aplicado em**: `services/whiteboard_renderer.py` (cálculo dinâmico de sub-passos + min duration), `pages/Editor/dialogs/WhiteboardDialog.jsx` (default + bounds + help text).


- **Problema da versão anterior**: a caneta usava varredura coluna-a-coluna com centroide vertical da tinta. Em letras com múltiplos traços (H, T, F), a caneta "ficava no vazio" entre os traços (média de duas regiões de tinta = espaço em branco).
- **Solução**: implementado **Zhang-Suen thinning em numpy puro** (sem scipy). Cada glifo é renderizado → binarizado → afinado em um esqueleto de 1 pixel → caminho do esqueleto é ordenado em "ordem de escrita":
### Feature: Animação de escrita seguindo o ESQUELETO da letra (Zhang-Suen)

  1. Componentes conectados ordenados pela esquerda-cima.
  2. Dentro de cada componente, começa do endpoint topo-esquerdo, anda buscando vizinhos com preferência por continuidade direcional.
- **Revelação por disco**: cada ponto do esqueleto "pinta" um disco de raio ≈ stroke-width na máscara de revelação — a tinta cresce naturalmente em volta da ponta da caneta, como tinta saindo do nib.
- **Caneta segue o esqueleto**: a posição da ponta a cada sub-passo é o ponto correspondente do caminho do esqueleto.
- **Resultado verificado**: para "H", a caneta desenha o vertical esquerdo, depois a travessa, depois o vertical direito — multi-stroke real. Para "o" cursivo, a caneta segue a curva continuamente.
- **Performance**: 44 chars em 2s de render, MP4 ~45 KB. Cache por glifo único garante reutilização para caracteres repetidos.
- **Sub-passos por caractere**: aumentados para `font_size/6` (clamp 8–20) para movimento mais suave.
- **Aplicado em**: `services/whiteboard_renderer.py` (Zhang-Suen + ordenação de path + reveal masks por disco).



## 2026-02-XX (Editor Chat: Brand Kit fix + logo size control)

### Bug fix: "Aplique o brand kit completo" só aplicava cores (sem logo, sem fonte)
- **Root cause**: o LLM mapeava a frase "brand kit completo" para `apply_brand_palette` em vez de `apply_brand_identity`, porque o System Prompt só tinha exemplos com "identidade visual completa" / "branding".
- **Fix**: adicionados exemplos explícitos ("aplique o brand kit", "kit da empresa", "kit completo da marca", "brand kit completo") apontando para `apply_brand_identity` em `routes/editor_chat.py`. Também adicionado padrão "logo grande/médio/pequeno" na descrição da op.

### Feature: Tamanho customizável do logo no Brand Kit
- **Modelo**: novo campo `logoSize` (int, default 96, range 32–320) em `BrandKit` + `BrandKitUpdate`.
- **Editor Chat**: op `apply_brand_identity` agora aceita `logoSize: int | "small" | "medium" | "large"`. Override em ordem: op-level > BrandKit-level > default(96).
- **Re-apply idempotente**: rodar o comando novamente com tamanho diferente agora SINCRONIZA o elemento `isBrandLogo` existente (atualiza width/height/posição/src) em vez de pular silenciosamente.
- **UI Super Admin**: `BrandLibraryDialog.jsx` ganhou seção "Tamanho do logo" com 3 presets (Pequeno=64, Médio=96, Grande=160) + input numérico personalizado (32–320 px).
- **Testes**: 8 testes pytest em `tests/test_editor_chat_logo_size.py` cobrem default size, preset overrides, clamping, idempotência e fallback sem logo URL.


## 2026-04-17 (Fork: AI Agent analyze_content Fix)

### CRITICAL Bug Fix: AI Agent Course Creation - `analyze_content` ImportError
- **Root Cause**: The `async def analyze_content()` function definition in `/app/backend/services/ai_agent.py` was accidentally placed INSIDE a prompt f-string instead of being a proper Python function declaration. This made the function invisible to Python imports, causing `ImportError: cannot import name 'analyze_content'` when the background analysis thread tried to execute.
- **Fix**: Moved the `async def analyze_content(...)` declaration to its correct position ABOVE the docstring and prompt string, restoring it as a proper top-level async function.
- **Applied in**: `services/ai_agent.py` (lines 121-125)
- **Status**: Tested - import verified, backend restarted clean

### Fix: Agent 404 Errors on Suggestions Polling + MongoDB Connection Leaks
- **Problem**: During AI course creation, the frontend polled `/api/agent/sessions/{id}/suggestions` indefinitely even on 404 errors, flooding the browser console. Backend background tasks (`_generate_improvement_suggestions`, `_generate_narrations`) each created their own MongoDB clients, risking Atlas M0 connection limit exhaustion.
- **Fix (Frontend)**: Added `res.ok` check in suggestions polling with max 5 retries before switching to error state. Prevents infinite 404 polling.
- **Fix (Backend)**: Replaced standalone `AsyncIOMotorClient()` creation in `_generate_improvement_suggestions` and `_generate_narrations` with the shared singleton `_get_bg_motor_db()` (maxPoolSize=3).
- **Applied in**: `GeneratedPanel.jsx` (polling logic), `agent.py` (background tasks)
- **Status**: Backend compiled, endpoint tested
- **Problem**: The Storyboard panel showed raw HTML tags (`<h1>`, `<p>`, `<strong>`) instead of rendered formatted content, making it hard for approvers to visualize the final slides.
- **Fix**: Added preview/edit toggle in `StoryboardPanel.jsx`. Default mode ("Visualizar") renders HTML content with proper prose styling. "Editar" mode shows original Textarea fields.
- **Applied in**: `frontend/src/pages/Agent/components/StoryboardPanel.jsx`
- **Status**: Implemented, lint clean



## 2026-03-27 (Fork: Video Export Production Fix)

### CRITICAL Bug Fix: Video Export 520 in Production (Event Loop Blocking)
- **Root Cause**: `create_slide_base_image()` (PIL/Pillow) and `get_media_duration()` (subprocess.run) were synchronous and blocked the FastAPI event loop for 2-3 seconds PER SLIDE. For a 14-slide course, this blocked the server for ~40 seconds total. Cloudflare's health checks couldn't reach the backend → returned **520 "Web server returned unknown error"**.
- **Fix**: Wrapped ALL blocking operations in `asyncio.to_thread()`:
  - `create_slide_base_image()` → runs in thread pool (PIL image creation)
  - Image padding operations → runs in thread pool  
  - `get_media_duration()` → runs in thread pool (ffprobe subprocess)
- **Result**: Event loop stays free during entire video processing. Poll response times: all < 0.7s (was 2-3s blocking per slide). Health checks respond in < 0.3s during video processing.
- **Applied in**: `services/video_exporter.py` (3 blocking operations wrapped in asyncio.to_thread)
- **Status**: Tested ✅ — 14-slide project processes while server handles all requests normally

### CRITICAL Bug Fix: Video Export 403 in Production (withCredentials conflict)
- **Root Cause**: The axios interceptor in `ProjectContext.jsx` set `withCredentials: true` on ALL requests. This sent Cloudflare cookies (`__cf_bm` bot management cookie) with every polling request. Cloudflare detected the automated polling pattern (every 3s with credentials) as bot activity and blocked with 403 Forbidden.
- **Fix**: Removed `withCredentials: true` from the global axios interceptor. Auth works via `Authorization: Bearer <token>` header from localStorage, cookies are unnecessary. Also changed `asyncio.ensure_future(create_job())` to `await create_job()` in the backend to guarantee job exists in MongoDB before the response is sent (prevents 404 in multi-worker deployments).
- **Applied in**: `frontend/src/contexts/ProjectContext.jsx` (axios interceptor), `backend/routes/export.py` (create_job await)
- **Status**: Tested ✅ — Login, dashboard, and video export all work without withCredentials

### CRITICAL Bug Fix: Video Export 502/504/Timeout in Production (P0 - RESOLVED)
- **Root Cause**: `POST /export-video` did heavy synchronous work BEFORE returning the jobId — importing `video_exporter` module (which downloads static-ffmpeg binaries ~50-100MB on first call), checking `is_ffmpeg_available()`, and fetching the project from MongoDB. In production, Cloudflare/Nginx proxy killed the connection after 30-60s timeout → 502/504.
- **Fix (Backend)**: Endpoint now returns jobId in **< 300ms** with ZERO heavy work. All validation (FFmpeg check, project fetch) moved to `asyncio.create_task(run_export())`. Job creation uses fire-and-forget `asyncio.ensure_future(create_job())`. Errors surface as job status "failed" instead of HTTP errors.
- **Fix (Frontend)**: `useEditorExport.js` now has: retry with exponential backoff on initial POST (3 attempts), tolerance for intermittent 502/504 during polling (up to 10 consecutive errors), 10-minute max polling timeout, and proper cleanup via `useRef`.
- **Applied in**: `routes/export.py` (export_video_endpoint), `frontend/src/pages/Editor/hooks/useEditorExport.js`
- **Status**: Tested ✅ (iteration_79) — 100% backend/frontend pass rate. POST: 0.24s, 10-slide export: ~40s.

---

## 2026-03-25 (Previous Session)

### CRITICAL Bug Fix: Video Export 502 in Production
- **Root Cause**: `run_ffmpeg()` used blocking `subprocess.run()` inside an async task. While FFmpeg processed 18 slides (30-60s), the entire asyncio event loop was blocked — the backend couldn't respond to ANY request, causing Cloudflare proxy to return 502.
- **Fix**: Created `run_ffmpeg_async()` using `asyncio.create_subprocess_exec()`. All FFmpeg/FFprobe calls in `export_video()` are now non-blocking. Backend responds to polling requests during video processing.
- **Also fixed**: Import of `video_exporter` wrapped in try/except (prevents backend crash if module fails), `_ensure_ffmpeg()` initialization wrapped in try/except, `static-ffmpeg` pip package as fallback (no root needed), startup event tries `static-ffmpeg` before `apt-get`
- **Applied in**: `services/video_exporter.py`, `routes/export.py`, `server.py`
- **Status**: Tested ✅ — backend responds HTTP 200 during all 18 slide processing

### Bug Fix: Video Export Job 404 in Production
- **Root Cause**: Job status was stored in-memory (`jobs` dict). In production, process restarts or multiple workers caused the job data to be lost, returning 404 on GET `/api/job/{jobId}`.
- **Fix**: Job data now persisted in **MongoDB** (`jobs` collection) with local cache for fast access. Jobs survive restarts, deploys, and multi-worker environments.
- **Applied in**: `routes/deps.py` (create_job, update_job, get_job), `routes/export.py`, `routes/projects.py`
- **Status**: Tested ✅ — job survives backend restart and is recoverable from MongoDB

### Bug Fix: SCORM Completion Not Triggering
- **Root Cause**: Completion logic required ALL scenarios to be completed in addition to quizzes. Scenarios are interactive branching exercises that users might skip or not complete fully, blocking SCORM "completed" status indefinitely.
- **Fix**: Changed completion rules in `player.js` to: Navigate to last slide + Complete all quizzes (if any). Scenarios are now optional (enrich learning but don't block completion).
- **Applied in**: `services/export_assets/player.js` (checkAndSetCompletion + finalCompletionCheck)
- **Status**: Tested ✅ — re-exported SCORM package contains updated logic

### Feature: AI Simulator/Game Generation in Course Creation
- **Modified**: `ai_agent.py` - Added `simulator` slide type to `generate_structure`, `generate_storyboard`, `generate_course_from_storyboard`, `generate_structure_from_template`
- **Modified**: `routes/agent.py` - Enhanced `_build_improved_elements` to handle HTML simulator elements, added `course_interactivity` category to improvement suggestions, enhanced `apply_course_improvements` prompt
- **What it does**: AI Agent now MANDATORY creates 1-2 interactive HTML+JS simulators per module (calculators, drag-and-drop, flashcards, memory games, quizzes, timelines, etc.)
- **Status**: Code deployed ✅ — needs user testing via course creation flow

### Video Export Fix: FFmpeg Persistence
- **Root Cause**: FFmpeg not available after fork/deploy because system packages are reset
- **Fix**: Triple-layer persistence:
  1. `start.sh` script installs FFmpeg before starting uvicorn (supervisor)
  2. FastAPI `startup_ensure_ffmpeg()` event auto-installs if missing
  3. `video_exporter.py` lazy-loads FFmpeg paths at runtime
- Added WebM media type to `serve_export` endpoint
- **Applied in**: `server.py`, `backend/start.sh`, `services/video_exporter.py`, `routes/export.py`
- **Status**: Tested ✅ (MP4: 54s/374KB, WebM: 54s/1.1MB)

### CRITICAL Bug Fix: AI Tutor CORS in Production (Recurring Issue #4)
- **Root Cause**: SCORM packages served from LMS domains (e.g., `didaxis.didaxis.com.br`) make cross-origin requests to the backend. Production proxy/infrastructure may strip CORS headers or not forward OPTIONS preflight to the app.
- **Fix**: Triple-layer CORS protection for `/api/tutor/chat`:
  1. Global `CORSMiddleware` with `allow_origins=["*"]` and fallback for empty env vars
  2. Custom `TutorCorsMiddleware` that explicitly handles OPTIONS and adds CORS headers for `/tutor/chat`
  3. Explicit CORS headers in `JSONResponse` at the route handler level
- **Applied in**: `server.py` (middleware), `routes/admin.py` (endpoint handlers)
- **Status**: Tested ✅ (preview) — User must **re-deploy and re-export SCORM** to test in production

### Bug Fix: Washed-Out Slide Thumbnails
- **Root Cause**: HTML element placeholders in thumbnails were empty transparent divs, hiding the actual slide content. AI-generated slides use HTML elements as main visual content covering the full area.
- **Fix**: Replaced empty placeholder with sandboxed `<iframe>` (`sandbox="allow-scripts"`, no `allow-same-origin`) that renders the actual HTML content safely without CSS leaking
- **Applied in**: `SlideThumbnailContent.jsx`
- **Status**: Verified ✅ — thumbnails now show full slide content (text, images, tables, buttons)

### CRITICAL Bug Fix: AI HTML CSS Leaking to Editor UI
- **Root Cause**: `SlideThumbnailContent.jsx` rendered HTML elements using `dangerouslySetInnerHTML` directly in the editor DOM (no iframe isolation). AI-generated HTML contains `<style>` tags with global CSS rules (e.g., `button { background: gradient(...) }`, `body { background: white }`) that cascade to ALL elements on the page, breaking toolbar icons, button visibility, and the dark theme.
- **Fix**: Replaced `dangerouslySetInnerHTML` with a safe placeholder (`</> HTML`) for HTML elements in thumbnails. Also removed `allow-same-origin` from all iframe sandboxes and added `contain: strict; isolation: isolate` on iframe containers.
- **Applied in**: `frontend/src/pages/Editor/components/SlideThumbnailContent.jsx`, `frontend/src/components/editor/SlideCanvas.jsx`, `CoursePreview.jsx`, `SplitPreview.jsx`, `Editor.jsx`
- **Status**: Tested ✅ — toolbar clean, dark theme restored, HTML renders correctly in iframe

### Feature: AI-Powered HTML Generation in Editor
- **What**: "Gerar com IA" tab in HTML dialog with prompt → preview → edit → insert
- **Backend**: `POST /api/generate-html` using Gemini
- **Status**: Tested ✅ (iteration_78)

### Bug Fix: Full HTML Documents Breaking iframe CSS
- **Fix**: Auto-detect `<!DOCTYPE html>` and render directly as srcDoc without wrapper
- **Applied in**: SlideCanvas, CoursePreview, SplitPreview, player.js, html_exporter.py
- **Status**: Tested ✅

### Bug Fix: AI Tutor 404 in Production SCORM Exports
- **Fix**: `_get_external_url()` now uses X-Forwarded headers from K8s proxy
- **Status**: Tested ✅ (iteration_77)

### CRITICAL Bug Fix: Missing Route Registrations
- **Fix**: Added 8 missing route modules to server.py
- **Status**: Tested ✅ (iteration_76)

## Previous Sessions
- SCORM completion, HTML scenario, deployment, background images, login fixes
- Before/After Preview + Undo, AI improvements layout fix
- Gamification, AI Agent scenario fix, Fix Simulators button
