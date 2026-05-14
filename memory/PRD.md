# PRD - Scormify: AI Course Authoring Platform

## Original Problem Statement
Build a full-featured AI course authoring platform with an "Intelligent Active Learning Scenario Creator" and AI Agent for course generation/modification. Core focus on stable, production-ready exports (SCORM, HTML, Video/MP4) without server crashes or timeouts.

## Core Features (Implemented)
- **AI Scenario Creator**: Interactive branching scenarios with choices, feedback, and scoring
- **AI Agent**: Course creation from storyboard with media generation
- **AI HTML Generator**: Generate interactive HTML+JS content via prompt in the Editor (Gemini)
- **AI Simulator/Game Generation**: Agent creates interactive HTML+JS simulators per module
- **AI Improvements Preview & Undo**: Before/after comparison before applying AI suggestions
- **AI Avatar Scene Suggestions**: Full avatar scene workflow:
  - AI suggests avatar scenes during analysis with mockup preview
  - Inline editing: narration script, background description, avatar position
  - Type switcher: Convert avatar_scene to content/simulator/game/quiz
  - Avatar & Voice Selectors: HeyGen avatar + HeyGen voice dropdowns per-course with preview
  - HeyGen native TTS: Video generation uses HeyGen's built-in text-to-speech (no ElevenLabs for avatar scenes)
  - Transparent background: Avatar videos request transparent WebM with fallback
  - Default voice: PT-BR (Brazilian Portuguese) with smart fallback
  - Auto-generation on apply: background image (Gemini) + avatar video (HeyGen native TTS)
  - Per-course configurable limit + real-time generation progress polling
  - Works in both Edit Mode and Create Mode
- **SCORM 1.2 Export**: Full SCORM package generation with completion tracking
- **HTML Standalone Export**: Self-contained HTML courses
- **Video Export (MP4/WebM)**: 100% Client-side video generation (html2canvas + MediaRecorder)
- **Gamification System**: Configurable badges with custom image upload, feedback per-project
- **PPT Import**: Convert PowerPoint to course (ConvertAPI)
- **VLibras**: Brazilian Sign Language accessibility widget
- **AI Tutor**: AI-powered tutor embedded in exported courses
- **Fix Simulators**: Tool to detect and fix static simulators
- **Aprovador Role & Approval Queue**: New role `aprovador` for storyboard text review. Inline editing of slide titles, content, and narration scripts. Approval workflow: submit -> review/edit -> approve/reject -> resume generation. Integrated into Agent page as "Fila de Aprovacao". Company-targeted: approval requires selecting target company, only that company's aprovador can review.
- **Tutor IA Dashboard**: Analytics dashboard showing most asked questions per course and per company. Super Admin sees all data, Company Admin sees only their company. Includes summary cards, company breakdown, course drill-down with top questions ranking and recent interactions.
- **Leonardo AI Integration**: Premium image generation via Leonardo AI in Editor toolbar and Agent workflow. 6 style presets, direct slide insertion, and per-slide configuration in MediaConfigPanel.
- **Aesthetic Analyzer**: AI-powered course visual quality analysis using Gemini 3 Flash. Checks color contrast, font harmony, layout, HTML/simulator readability. Provides score (0-100), categorized issues, and one-click auto-fix. Available in both Editor (sidebar panel) and Agent (after course generation).
- **Email Notifications (Resend)**: Transactional email notifications for: approval submitted (to aprovador), approval result approved/rejected (to author), course generated (to author), AI Tutor activity summary (to admin). User preferences configurable. Templates in HTML with Scormify branding.

## Credentials
- Admin: admin@scormify.com / admin123
- Aprovador: aprovador@teste.com / aprovador123

## 3rd Party Integrations
- Google Gemini (via Emergent LLM Key) - Text + Image generation (Nano Banana)
- OpenAI GPT-4o (via Emergent LLM Key)
- HeyGen - Avatar videos + voice TTS (user API key)
- ElevenLabs - Audio narration for regular slides only (user API key)
- ConvertAPI - PPT import (user API key)
- Leonardo AI - Premium image generation (user API key: 59495cbf-a332-4a84-b6ab-a4d6f45a9ab2)
- Krea AI - Image generation across 40+ models — 11 curated (Flux, Imagen 4, Nano Banana, ChatGPT Image, Ideogram, Seedream) — user API key format `api_id:api_secret`
- Resend - Email notifications (API key in .env, free tier 100/day)

## Code Architecture
```
/app
├── backend
│   ├── routes
│   │   ├── agent.py            # AI agent endpoints, HeyGen/ElevenLabs orchestration
│   │   ├── heygen.py           # Core HeyGen endpoints
│   │   ├── leonardo.py         # Leonardo AI image generation endpoints
│   │   │   ├── aesthetics.py      # Aesthetic analyzer endpoints (analyze + apply fixes)
│   │   ├── gamification.py     # Gamification + badge image upload
│   ├── services
│   │   ├── ai_agent.py         # AI prompting logic for storyboards
│   │   ├── leonardo_ai.py      # Leonardo AI API service
├── frontend
│   ├── src
│   │   ├── pages
│   │   │   ├── Editor.jsx             # Main editor (~2064 lines, refactored from ~3892)
│   │   │   ├── Editor/
│   │   │   │   ├── dialogs/           # 14 extracted dialog components
│   │   │   │   │   ├── ExportDialog.jsx
│   │   │   │   │   ├── HeygenDialog.jsx
│   │   │   │   │   ├── SlideVideoDialog.jsx
│   │   │   │   │   ├── VideoLibraryDialog.jsx
│   │   │   │   │   ├── TTSDialog.jsx
│   │   │   │   │   ├── MediaDialogs.jsx  (9 smaller dialogs)
│   │   │   │   │   └── index.js
│   │   │   │   ├── components/
│   │   │   │   ├── hooks/
│   │   │   │   └── utils.js
│   │   │   ├── Agent/
│   │   │   │   ├── components/
│   │   │   │   │   ├── AvatarSceneControls.jsx
│   │   │   │   │   ├── CoursePanels.jsx
│   │   │   │   │   └── StoryboardPanel.jsx
│   │   ├── components
│   │   │   ├── editor
│   │   │   │   ├── GamificationPanel.jsx  # Badge config + custom image upload
```

## Changelog
- 2026-05-14: **FEATURE (P0)** — Fundo de curso vindo da Biblioteca de Marca + **contraste automático** dos textos do Agente IA.
  - **Pedido do usuário**: "optar por uma imagem a ser usada como background do curso prevalecendo sobre os fundos e para os textos criados pelo Agente IA ter o contraste correto! Esta imagem deverá ser optada na Biblioteca de Marca da Empresa!"
  - **Backend**:
    - Novo endpoint `GET /api/companies/{cid}/assets/{aid}/analysis`: lê os pixels da imagem (downsample 32x32, fórmula W3C `0.2126*R + 0.7152*G + 0.0722*B`) e retorna `{brightness, tone, recommendedTextColor, recommendedOverlay}`. Thresholds tunados empiricamente (cutoff 0.55 dark/light; overlays nas extremidades 0.30/0.65; midtones sem overlay).
    - `services/ai_agent.py::generate_course_from_storyboard`: novo branch `custom_bg.type == "brand"` no resolver de bgConfig. Pega `imageUrl` direto (já é `/api/companies/{cid}/assets/{aid}/file` servido offline-friendly) e seta como `slide.backgroundImage`. Propaga `backgroundImageOverlay` (dark/light) que SinglePage + SCORM runtimes já honram.
  - **Frontend** (`MediaConfigPanel.jsx`):
    - 5ª tab **"Marca"** ao lado de Padrão/Cor/Degradê/Imagem no `SlideBackgroundPicker` (tanto Global quanto per-slide).
    - Click "Escolher da Biblioteca de Marca" → reusa `BrandLibraryPicker`.
    - Ao escolher: chama `/analysis`, salva `bg = {type:'brand', imageUrl, brandAssetId, overlay, suggestedTextColor}`. Se for o picker **global**, dispara `setGlobalTextColor(recommendedTextColor)` para que o Agente já gere texto na cor contrastante.
    - UI mostra preview com overlay aplicado em vivo + pill com swatch da cor sugerida + 3 botões de toggle de overlay (Sem overlay / Escurecer / Clarear) para override manual.
    - Aproveita o mecanismo "Aplicar a todos os slides" já existente — autor pode escolher 1 imagem da marca e propagar para o curso inteiro com um botão.
  - **Testing**: **106/106 testes passando** (+19 novos em `test_brand_background_contrast.py` — branch dispatch para bgConfig.type=brand, overlay valido/invalido/dropped, contrast decision em todas as fronteiras 0.0/0.30/0.55/0.65/1.0, E2E com Pillow gerando navy/pastel/preto puro/branco puro e confirmando que a recomendação bate). E2E real validado: análise do navy `#0f172a` retornou `{brightness: 0.089, text: '#FFFFFF', overlay: 'light'}`; pastel retornou `{brightness: 0.906, text: '#0f172a', overlay: 'dark'}`. Screenshot capturou as 5 tabs + botão "Escolher da Biblioteca de Marca" + toast "Fundo aplicado a todos os 12 slides!".


- 2026-05-14: **FEATURE (P1)** — Wizard Media step: **opção "Biblioteca da Marca" por slide**.
  - **Pedido do usuário** (com screenshot): adicionar opção "Biblioteca da Marca da Empresa" no painel de Mídia (fase 5 do Wizard) com seleção manual por slide.
  - **Por que faz sentido**: o toggle global da Brand Library deixa o LLM escolher automaticamente (modo `preferred`/`strict`). Mas o autor às vezes quer **comprometer** uma imagem específica em UM slide ("este slide DEVE usar essa foto do laboratório"). Agora ele faz isso sem editar o curso depois.
  - **Backend**: novo tipo `brand_library_image` reconhecido em `generate_course_from_storyboard`. Aceita `brandImageUrl` no `mediaConfig` do slide e usa direto (sem chamar Leonardo/Gemini); marca `source: "brand_library_manual"` para analytics futuras de cobertura de marca.
  - **Frontend** (`MediaConfigPanel.jsx`):
    - Novo card "Biblioteca da Marca" entre "Da Galeria" e "Leonardo AI" no array `MEDIA_TYPES` (ícone Layers, cor indigo). Color palette extendida para indigo/violet (necessários após a remoção do violeta exclusivo do Leonardo).
    - Click no card abre o `BrandLibraryPicker` (reuso do componente do Editor — UX consistente).
    - Após escolha: preview pill com thumbnail + nome do arquivo + botão "Trocar imagem".
    - Estado vazio: botão "Clique para escolher da biblioteca da empresa" inline.
  - **Frontend** (`Agent.jsx`): no flow `editMedia=projectId`, agora resolvemos o `companyId` do projeto (primeiro do `session.companyId`, fallback `GET /api/projects/{id}`) e setamos via `setAgentCompanyId()` para que o `BrandLibraryPicker` saiba qual biblioteca listar. **Sem isso**, o picker mostraria "projeto não vinculado a empresa" mesmo quando vinculado — bug que foi capturado no teste e corrigido na mesma iteração.
  - **Testing**: **89/89 testes passando** (+5 novos em `test_brand_library_media_type.py` cobrindo resolução do dispatch, provenance tag, fallback quando url ausente, URLs absolutas, round-trip do schema da UI). E2E real com 4 assets da Didaxis: open editMedia → click "Biblioteca da Marca" no slide 1 → picker abre com 4 imagens → click numa → pill com thumbnail + "Trocar imagem" aparece + botão fica destacado.


- 2026-05-14: **FEATURE (P2)** — Brand Kit: **cores e fonte aplicadas automaticamente ao gerar slides**.
  - **Próxima etapa do roadmap Brand Library**: o `BrandKit` (cores primária/secundária/destaque + fonte) configurado pelo super-admin era persistido mas não consumido pelo gerador de cursos. Agora a identidade visual da empresa é aplicada a todos os slides automaticamente.
  - **Backend**:
    - Novo módulo `services/brand_kit_applier.py`: `fetch_brand_kit(db, company_id)` busca o kit da empresa; `apply_brand_kit_to_palette(palette, kit)` retorna uma cópia da palette com overrides.
    - **Mapeamento**: `primaryColor` → `palette.primary` (chrome/header); `accentColor` → `palette.accent` + `accentLight` derivado automaticamente via lightening 82% (mantém contraste em tints e pills); `secondaryColor` → `palette.text` (corpo); `fontFamily` → `fontHeading` + `fontBody` (com auto-wrap em aspas se tiver espaço e fallback `sans-serif` se vier sem stack).
    - Validação resiliente: `_is_hex_color()` rejeita valores inválidos silenciosamente (typos no admin não corrompem palette); fonte vazia/space-only é ignorada; cores faltantes preservam o template original.
    - Hook em `generate_course_from_storyboard` (ai_agent.py): logo após a palette do design-template ser montada, se `use_brand_library=True` E o `company_id` tem brandKit, aplica os overrides. Falhas no fetch (DB down) caem para o palette default (`logger.warning`, sem crash).
    - **Opt-in cohesivo**: o brandKit só é aplicado quando `useBrandLibrary=True` no projeto. Mesma flag que controla imagens — assim ligar "Brand Library" = "Use identidade completa da empresa" sem surpresas para quem só queria imagens.
  - **Testing**: **84/84 testes passando** (15 brand library unit + 17 API + 8 override + **44 novos** brand kit applier). Cobertura: validador hex (parametrizado com 7 válidos + 9 inválidos), lightener de cores, todos os mapeamentos, palette imutável (defensivo), partial brand kit (override só dos campos preenchidos), fetch via DB com kit presente/ausente/empty/db-exception. E2E real: o brandKit da Didaxis (`#1e3a8a`, `#10b981`, `#f59e0b`, Inter) foi fetched do MongoDB e aplicado corretamente, com accentLight `#fdeed3` derivado automaticamente.


- 2026-05-14: **FIX (P0)** — Brand Library: **token errado no localStorage** causando "Erro ao salvar identidade".
  - **Bug reportado pelo usuário** (com screenshot): toast "Erro ao salvar identidade" ao clicar em Salvar no Brand Kit da Didaxis. Mesmo bug afetaria todos os 5 verbos do BrandLibraryDialog (list/upload/patch/delete/brand-kit) e o BrandLibraryPicker do Editor.
  - **Causa raiz**: meu código lia o token de `localStorage.getItem('token')`, mas o `AuthContext` da app guarda em `'scormify_auth_token'`. Como o token era `null`, o header `Authorization: Bearer null` chegava ao backend e era rejeitado com 401.
  - **Fix**: substituí a chave em `BrandLibraryDialog.jsx` e `BrandLibraryPicker.jsx`.
  - **Validação**: screenshot E2E com toast "Identidade visual salva" confirma fluxo funcionando — exatamente o caso reportado (Didaxis + cores `#eb6d24` / `#606060`).


- 2026-05-14: **FEATURE (P1)** — Brand Library: **override por slide no Editor**.
  - **Pedido do usuário**: completar o roadmap iniciado na entrega anterior — agora o autor pode aplicar imagens da biblioteca **slide a slide** dentro do Editor, sem depender só do toggle do Wizard.
  - **Backend**:
    - `services/ai_agent.py::_generate_one_image`: agora respeita `slide.brandLibraryOverride` com 3 valores:
      - `None`/missing → herda `useBrandLibrary` do projeto (default)
      - `"force"` → SEMPRE tenta a biblioteca neste slide (ignora flag do projeto); se sem match, deixa sem imagem (não cai para IA — autor optou explicitamente)
      - `"skip"` → NUNCA tenta biblioteca neste slide (mesmo que projeto esteja ON)
    - `models.py::Slide` já tinha `extra="allow"` então `brandLibraryOverride`, `backgroundImageSource` e `backgroundImageAssetId` round-trippam sem schema changes.
  - **Frontend**:
    - Novo componente reutilizável `pages/Editor/dialogs/BrandLibraryPicker.jsx`: modal grid com filtros (tipo + categoria), thumbnail clicável, estado vazio/erro/loading bem tratados.
    - `pages/Editor/components/SlideProperties.jsx`: novo painel "Biblioteca de Marca" com (a) botão "Usar imagem da biblioteca" → abre o picker → ao escolher seta `backgroundImage = asset.url`, `backgroundImageSource = "brand_library"`, `backgroundImageAssetId = asset.id`; (b) pill com botão X para remover quando aplicado; (c) 3 botões Herdar/Forçar/Ignorar (com tooltips explicativos) para definir override.
    - `pages/Editor.jsx`: passa `project` para SlideProperties (necessário para o `companyId`).
  - **Testing**: **40/40 testes passando** (15 unit + 17 API + 8 novos override). E2E real validado: upload de PNG via canvas → abertura do Editor → painel mostra Brand Library → click abre picker com 1 asset → click no asset aplica como fundo (thumbnail do slide atualiza imediatamente) → pill "Fundo: imagem da biblioteca aplicada" + botão remover aparecem corretamente.


- 2026-05-14: **FEATURE (P0)** — Biblioteca de Marca por Empresa (Brand Library): imagens corporativas curadas + Brand Kit (cores/fonte) que o Agente IA usa ao gerar cursos.
  - **Pedido do usuário**: "padronizações visuais que sigam o modelo da empresa para qual estou criando o(s) Curso(s), tais como fundo dos slides com imagens específicas e uma biblioteca de imagens segmentada por empresa".
  - **Backend novo**:
    - Models (`models.py`): `CompanyAsset` (id, companyId, type ∈ {background/illustration/icon/logo/cover/other}, category ∈ {intro/content/transition/conclusion/light_bg/dark_bg/generic}, tags[], description, isActive), `BrandKit` embedded em Company (primaryColor/secondaryColor/accentColor/fontFamily/logoUrl). Field validators normalizam type/category invalidos para defaults seguros.
    - Routes (`routes/company_assets.py` novo): GET/PUT `/api/companies/{id}/brand-kit` + CRUD completo em `/api/companies/{id}/assets` (multipart upload com type/category/tags CSV/description, listagem com filtros, PATCH metadata, DELETE, GET file público para SCORM offline). Limite de upload 10MB. RBAC: super_admin muta; usuário regular lê só da própria empresa.
    - Storage (`services/asset_store.py`): novas funções `store_company_asset_async`, `retrieve_company_asset_async`, `delete_company_asset_async`. Coleção dedicada `company_assets` (base64 blob) + `company_assets_meta` (metadata). Persistência GridFS-style sobrevive K8s restarts.
    - Picker semântico (`services/brand_library_picker.py` novo): `pick_asset_for_slide(db, company_id, slide_title, slide_body, desired_type, desired_category, keyword)`. Filtro hard por type → narrowing por category (broadening se vazio) → catálogo enxuto LLM (Claude Sonnet via Emergent key) escolhendo o id semanticamente mais próximo. Skip-LLM quando há 1 candidato. Cache in-memory por empresa.
    - Hook no Agente (`services/ai_agent.py::_generate_one_image`): quando `useBrandLibrary=True`, picker é consultado ANTES de Leonardo. Modo `preferred` → cai para IA se sem match; modo `strict` → slide fica sem imagem se sem match.
    - Wizard endpoint (`routes/agent.py::media-config`): aceita `useBrandLibrary` (bool) e `brandLibraryMode` ('preferred'/'strict') e propaga para `generate_course_from_storyboard`.
  - **Frontend novo**:
    - `BrandLibraryDialog.jsx` (super_admin): duas tabs — "Imagens" com upload+filtros+grid+delete, "Identidade" com color pickers + fonte.
    - Botão paleta em cada card de empresa no `/admin` (icone Palette indigo). Abre o dialog.
    - `MediaConfigPanel` (step 5 do Wizard): novo card "Biblioteca de Marca da Empresa" com toggle + preview da contagem ("N imagens disponíveis") + seletor de modo (Preferida/Estrita). Toggle desabilita quando a empresa não tem imagens.
    - `Agent.jsx`: novos states + useEffect que carrega contagem ao entrar no step 5 + props passadas para MediaConfigPanel + persistência via media-config endpoint.
  - **Testing**: **32/32 testes passando** — 15 unit em `test_brand_library.py` (modelo + picker + cache) + 17 end-to-end API em `test_brand_library_api.py` (brand-kit round-trip, asset CRUD, RBAC cross-tenant, file serving, wizard persistence). Testing agent E2E: 100% success rate, sem issues criticos.
  - **Validado E2E real**: upload de PNG → list retorna o asset com URL pública → fetch da URL retorna os bytes corretos → PUT brand-kit persiste → DELETE remove. Screenshot do `/admin` mostra os 3 botões paleta nos cards das empresas + dialog Brand Library abrindo limpo com estado "Nenhuma imagem cadastrada".


- 2026-05-12: **TUNING (P0)** — Zoom Tutorial Agent: **cap em 1.6x + foco mais central**.
  - **Bug reportado**: "O zoom fica estourado na tela". O Agente externo retorna `zoom_level=2.5` por default, o que no full-screen (sobretudo no SCORM/HTML standalone) fazia o detalhe magnificado "explodir" — pedaços gigantes da imagem ocupando toda a viewport, perdendo a noção do conjunto.
  - **Fix** (`routes/tutorial_integration.py`):
    - **Cap de scale**: novo `ZOOM_MAX = 1.6`. Qualquer `zoom_level` > 1.6 do Agente é capeado. Valores menores passam (autor pode usar 1.3, 1.4 livremente).
    - **Clamp do foco** apertado: `focusX/Y` agora clamped em **20-80%** (era 15-85%). Pontos focais muito próximos das bordas eram a maior fonte da sensação de "estouro" (o transform-origin no canto fazia 80% da imagem escalar contra o canto oposto).
    - **Por que 1.6x**: empiricamente é o sweet spot entre destacar o hotspot e preservar o contexto. Em testes E2E, o detalhe do botão "Relatórios" fica nítido sem que o restante da tela suma da viewport.
  - **Validado E2E real**: re-import do tutorial `aa2de3c9-...` → 9 slides, scale=1.6 em todos. Screenshots SinglePage Preview mostram o magnify focado no canto superior direito (RELATÓRIOS) com gráficos e contexto ainda visíveis no fundo. **57/57 testes Tutorial passando** (incluindo 2 novos: `test_zoom_scale_capped_at_max` e `test_zoom_preserves_lower_zoom_levels`).


- 2026-05-12: **FIX (P0)** — Tutorial Agent: **janela filha (passo "Captura") + narrações + zoom em TODOS exports**.
  - **Bugs reportados pelo usuário**: (1) "a última tela capturada que é uma janela filha não está sendo importada" e (2) "funcionalidade de Zoom não está funcionando".
  - **Causa #1 — passo 9 sumido**: API JSON v1 do Auto-Instructor (`/api/v1/tutorials/{id}`) retorna apenas 8 steps com `narration:""` para todos. O export HTML do mesmo agente expõe **9 steps + narrações reais** ("Clique no Menu Relatórios", "Selecione Cursos!", etc.) — o passo 9 é uma "Captura" (`action="Captura"`) final, gerada só no export.
  - **Causa #2 — zoom nos SCORM/HTML standalone**: o efeito `zoomEffect` só estava implementado no `single_page_exporter` (runtime SinglePage). O SCORM tradicional (`player.js`) e o HTML standalone (`html_exporter.py`) ignoravam o campo e renderizavam o slide estático.
  - **Fix #1** (`routes/tutorial_integration.py`): novo helper `_fetch_agent_html_extras(tutorial_id)` baixa `/exports/html_embed`, parseia via BeautifulSoup e extrai por step: `order, action_type, narration, screenshot_base64, audio_base64, audio_url_hint`. `_convert_tutorial_to_slides` mescla com a lista de steps do JSON (JSON tem prioridade quando tem dado; HTML preenche `narration` vazio + adiciona o step 9 que o JSON omite). Novo `_AGENT_ACTION_MAP` traduz labels pt-BR (Clicar→click, Captura→capture, Ação→select_option, etc.). `_generate_step_description` agora trata `capture/select_option`.
  - **Fix #2a** (`services/export_assets/player.js` — SCORM): novo `slide-zoom-stage` div criado em `renderSlide` quando `slide.zoomEffect.scale > 1`. Bg image + todos os elementos re-parented dentro do stage. Animação disparada via `setTimeout(300ms)` após o slide renderizar.
  - **Fix #2b** (`services/html_exporter.py` — HTML standalone): JS template enriquecida com `__zoomEffect`, abre/fecha `slide-zoom-stage` no html string, dispara animação após `container.innerHTML = html`.
  - **Validado E2E real**: import do tutorial `aa2de3c9-...` → **9 slides** (era 8) com narrações reais e áudios anexados. Screenshots em todos 3 ambientes (SinglePage Preview, SCORM via LMS local, HTML Standalone) capturaram tanto o estado scale(1) quanto scale(2.5) — zoom acompanha o hotspot, título/UI fixos. **215/215 testes Tutorial+SinglePage passando**.


- 2026-05-11: **FIX (P0)** — Tutorial Agent **efeito ZOOM funcionando**: refatorado para wrapper `.sp-zoom-stage`.
  - **Bug reportado pelo usuário**: "O efeito ZOOM não está funcionando".
  - **Causa raiz**: o `transform: scale(2.5)` era aplicado no `.sp-section-inner` (o card inteiro do slide). Isso fazia o card AUMENTAR 2.5x na tela (transbordando viewport), arrastando junto o título "PASSO N" e o body strip do rodapé. Visualmente o usuário só via uma "explosão" pra fora, não um zoom.
  - **Fix (3 camadas)**:
    1. **Exporter** (`single_page_exporter.py`): quando slide tem `zoomEffect`, o `background-image` + os `.sp-bg-element` (hotspot rosa + texto da instrução) são embrulhados num novo `<div class="sp-zoom-stage">`. Title e body strip ficam FORA do stage.
    2. **CSS** (`sp_runtime/styles.css`): `.sp-zoom-stage{position:absolute;inset:0;background-size:cover;transform-origin:50% 50%;will-change:transform}` + classe `sp-has-zoom` na section para scoping.
    3. **JS** (`sp_runtime/runtime.js`): `transform: scale(N)` agora aplicado no `.sp-zoom-stage` (não mais no inner). Helper `triggerZoom(sec)` extraído para reuso. Threshold IO reduzido de 0.5 → 0.2 (sections grandes não atingem 50%). Trigger inicial proativo via `setTimeout(400ms)` para slides já visíveis no load. Hook em `detectActiveSection` re-dispara o zoom quando o usuário avança via scroll/setas.
  - **Validado E2E real**: screenshot capturou tanto o estado scale(1) (vista normal) quanto scale(2.5) (background magnificado focando o hotspot do botão "RELATÓRIOS"). Título "PASSO 1" + UI permanecem fixos durante o zoom.
  - **Testes**: 11 novos pytests em `tests/test_singlepage_zoom_stage.py` cobrindo: stage presente quando zoomEffect set / ausente quando não; bg-image move para stage / fica no inner sem zoom; classe `sp-has-zoom` na section; data-zoom-* attrs corretos; scale=1 dropa tudo; hotspot/text DENTRO do stage; title/body FORA do stage. **101/101 testes Tutorial+SinglePage passando**.


- 2026-05-11: **FEATURE (P0)** — Tutorial Agent integration: **import narration audio + narration text** from the external Agent.
  - **Contexto**: o Agente externo (`auto-instructor`) atualizou o schema da API: cada step agora pode ter `narration` (texto pt-BR) e `audio_url` (caminho/URL do MP3 narrado). Endpoint dedicado: `GET /api/v1/tutorials/{id}/steps/{step_id}/audio`.
  - **Backend** (`routes/tutorial_integration.py`):
    - Novos helpers `_audio_ext_from_content_type` (mp3/wav/ogg/webm), `_resolve_audio_url` (abs URL / path relativa / s3-like path), `_download_step_audio_to_assets` com 3 estratégias em cascata: (1) `audio_base64` inline → decode local sem network; (2) `audio_url` do payload → resolve + GET; (3) fallback endpoint `/steps/{id}/audio`. Sanity check: respostas <200 bytes são tratadas como erro JSON disfarçado.
    - Áudio persistido via `store_asset_async` em GridFS → sobrevive K8s pod restart.
    - `_step_to_slide(step, ..., audio_data=None)` anexa o áudio como `slide.audio[]` no mesmo formato da ElevenLabs (`{id, type:"narration", src, filename, duration:0, volume:1.0}`) → Single Page exporter já tem autoplay + global mute por padrão.
    - `narrationScript` prioriza o `step.narration` explícito (preserva o texto exato que gerou o áudio); fallback no auto-description quando vazio.
    - `_convert_tutorial_to_slides` chama o downloader de áudio em paralelo com o de screenshot.
  - **Resiliência**: tutoriais antigos sem áudio (ex: `aa2de3c9-...`) continuam funcionando — `audio: None` no slide, zero crash, zero log warning ruidoso.
  - **Testes**: **21 pytests novos** em `tests/test_tutorial_audio.py` cobrindo content-type → extensão, URL resolution (abs/relative/storage path), attachment ao slide.audio[], narrationScript priority, download via audio_url + via fallback + via base64, 404 graceful, tiny-response rejection, persistência em disco. Todos os 44 testes Tutorial (integration + zoom + audio) passando.
  - **Validado E2E real**: import do tutorial `aa2de3c9-...` (8 passos, sem áudio ainda) → 8 slides criados com screenshots + zoomEffect + `audio: None` (correto). Pronto para quando o Agente externo gerar áudios de fato.


- 2026-05-08: **FEATURE** — Tutorial Agent integration: **efeito de zoom na hotspot** importado do `zoom_level` do tutorial.
  - **Problema reportado**: o Tutorial Agent declara `zoom_level: 2.5` (efeito de lupa no ponto do clique) mas a importação anterior ignorava isso — slides ficavam estáticos sem o zoom-in dinâmico.
  - **Fix backend** (`_step_to_slide`): quando o step tem `click_x/click_y` E `zoom_level > 1`, anexa `zoomEffect: {scale, focusX%, focusY%, intro, hold, outro}` no slide. Coordenadas viram porcentagem da imagem (clampadas em 15-85% para que o ponto focal sempre fique visível dentro da viewport após o scale).
  - **Renderer Single Page** (`runtime.js` + `styles.css`):
    - `<section data-zoom-scale="..." data-zoom-fx="..." data-zoom-fy="..." data-zoom-intro="..." data-zoom-hold="..." data-zoom-outro="...">`
    - IntersectionObserver detecta quando o slide entra em viewport com `intersectionRatio > 0.5`, aplica `transform-origin: fx% fy%; transform: scale(N)` no inner card com transição cubic-bezier suave. Após `hold` ms, anima de volta para `scale(1)`.
    - CSS: `overflow:hidden` no `.sp-section-inner` quando tem `data-zoom-scale` (clipa o overflow do bg image escalado).
  - **Defaults**: scale=2.5 (do `zoom_level` do tutorial), intro=800ms, hold=2400ms, outro=600ms.
  - **Testes**: 7 novos pytests em `tests/test_tutorial_zoom.py` cobrindo: zoom anexado quando há click + zoom>1, skipado quando não há click, clamping de borda (5,5) e (1270,710), uso de `screenshot_width/height` quando declarado, zoom inválido vira no-effect.


- 2026-05-08: **FEATURE (P1)** — **Integração com Tutorial Agent externo** (Auto-Instructor).
  - **Objetivo**: importar tutoriais step-by-step gerados pelo Agente externo (https://auto-instructor-1.preview.emergentagent.com) como cursos Scormify. Cada passo do tutorial vira um slide com screenshot + texto + hotspot circular + narração.
  - **Backend** (`routes/tutorial_integration.py`):
    - 4 endpoints proxy (`/api/tutorial-integration/list`, `/tutorials/{id}`, `/tutorials/{id}/generate`, `/tutorials/{id}/status`) que escondem a X-API-Key no servidor — frontend nunca a vê.
    - `POST /api/tutorial-integration/import/{tutorial_id}` faz o trabalho pesado: puxa tutorial com `embed_data=true`, decodifica screenshot base64 (ou faz download via `/steps/{id}/screenshot` se necessário), persiste cada um como asset Scormify (disco + MongoDB para sobreviver a K8s restarts), gera slide formatado.
    - `_generate_step_description`: helper que sintetiza descrição quando o Agente não tem narração explícita — usa `action_type` (click/type/scroll/navigate/wait) + `selector`/`typed_text` para gerar texto natural em PT-BR ("Clique em 'Salvar'", "Digite 'admin@exemplo.com' no campo destacado").
    - `_step_to_slide`: monta slide 1280x720 com `backgroundImage` = screenshot, overlay de texto com plate semi-transparente embaixo, e **hotspot circular** (shape 56x56 com `borderColor:#f472b6` rosa) nas coordenadas exatas `click_x/click_y`.
    - Modos: `mode=new` (cria projeto novo) ou `mode=append` (anexa slides a projeto existente). Suporta `companyId` para attribution multi-tenant.
  - **Configuração** (`backend/.env`): `TUTORIAL_AGENT_URL` + `TUTORIAL_AGENT_API_KEY` (atualmente `scormify-api-key-2024`).
  - **Frontend** (`TutorialImportDialog.jsx` + botão no Dashboard):
    - Botão "Importar Tutorial" ciano no header do Dashboard ao lado de "Agente IA"
    - Dialog lista todos os tutoriais com badges de status (Pronto/Gerando/Erro), só permite selecionar os `completed`
    - Campo opcional de nome customizado, botão "Importar como novo curso"
    - Após sucesso, navega direto para o Editor do projeto criado
  - **Validado E2E real**: tutorial "Geração de Relatórios Beta" (8 passos) importado com sucesso → 8 slides criados com screenshots persistidos + textos como "Clique em 'Cursos e Trilhas'" + hotspots nas coords `x=377, y=266`. **16 pytests novos** em `tests/test_tutorial_integration.py` cobrindo todos os action_types + edge cases (coords inválidas, sem screenshot, título default).


- 2026-05-08: **FIX** — **Texto final de cenário interativo desformatado** (parede de texto com email inline).
  - **Bug reportado pelo usuário**: desfecho do cenário "Decisão em Cascata" vinha como uma parede só com:
    - Narrativa do desfecho
    - Email-resposta da Dra. Helena **inline entre aspas** (deveria ser um card destacado)
    - Feedback final
    - Tudo num único `<p>` centralizado sem quebras.
  - **Causa raiz**: o LLM gera o `narrative` do node final como texto corrido com diálogos embutidos entre aspas, mas o renderer fazia apenas `escapeHtml(text)` + `white-space:pre-wrap`. Sem split por parágrafos e sem detecção de blocos citados.
  - **Fix — 3 renderers atualizados com heurística comum**:
    1. `services/sp_runtime/runtime.js` (Single Page HTML/SCORM) — nova função `formatScenarioNarrative(text)` que (a) split em blank-lines, (b) se ficar 1 mega-parágrafo, procura bloco citado `>40` chars e separa ANTES/CITACAO/DEPOIS, (c) parágrafos com wrap completo em aspas viram citações. Citações renderizam como card com `border-left:3px solid #4f46e5; background:rgba(79,70,229,0.08); font-style:italic` (visual de "email recebido").
    2. `services/export_assets/scenario-controller.js` (SCORM tradicional) — mesma função adaptada para tema dark (`#cbd5e1` foreground, `rgba(99,102,241,0.15)` bg).
    3. `components/scenario/ScenarioPlayer.jsx` (Editor/Preview) — componente React `ScenarioNarrative` com o mesmo algoritmo + classes Tailwind (`bg-indigo-500/10 border-l-[3px] border-indigo-500`).
  - **Testes**: 7 novos pytests em `tests/test_scenario_narrative_format.py` reimplementam a heurística em Python e travam o comportamento (email inline extraído como quote, paragraph breaks preservados, aspas curtas NÃO extraídas, fidelidade de conteúdo).


- 2026-05-08: **FEATURE (P1)** — **Chat conversacional expandido** para Editor do curso publicado + Media Config (step 5).
  - **Editor Chat**: novo `routes/editor_chat.py` com endpoint `POST /api/projects/{id}/editor-chat`. Recebe mensagem natural → LLM (`gemini-3-flash-preview` com fallback `openai/gpt-4o`) retorna JSON `{reply, ops}` → backend aplica atomicamente. Ops suportadas: `edit_slide_title`, `edit_element_content` (só text/shape — ignora html/quiz/scenario para não quebrar simuladores), `edit_element_style` (merge com style existente), `add_text_element` (defaults sensatos x=100, y=100, fontSize=20), `delete_element`, `change_slide_background`, `move_slide`, `delete_slide`.
  - **Snapshot auto-revertível**: cada aplicação cria snapshot em `aesthetic_snapshots` (kind=`editor_chat`), então o botão **Reverter** do AestheticsPanel já desfaz automaticamente edições feitas via chat. Reuso de infraestrutura existente.
  - **Media Config Chat** (step 5 do Agente): novo endpoint `POST /api/agent/sessions/{id}/media-chat`. Ops para mutar `mediaConfig`/`bgConfig` antes de rodar a geração cara: `set_image_source` (gemini/leonardo/none), `set_image_prompt`, `set_avatar_enabled`, `set_avatar_voice_gender`, `set_narration_enabled`, `set_background_color`, `bulk_set_image_source`, `bulk_set_avatar`. NÃO dispara Leonardo/HeyGen — só altera config para quando o usuário clicar em "Gerar Midia".
  - **Frontend**:
    - `EditorChat.jsx` — componente reaproveitável (mesmo design do StoryboardChat). Integrado no `Editor.jsx` via botão `MessageSquare` na toolbar + Sheet lateral 400px. Ao aplicar ops, refetch do projeto atualiza o canvas.
    - `MediaConfigChat.jsx` — integrado no `Agent.jsx` quando `currentStep === 5`, substituindo o chat passivo. `onMediaConfigUpdate` sincroniza estado local.
  - **Testes**: 13 novos pytests em `tests/test_editor_chat.py` cobrindo `_build_course_summary` (truncate, interactive-not-editable) + `_apply_ops` (todas as 8 ops, out-of-bounds skip, malformed op skip, html/quiz protegidos).


- 2026-05-08: **FEATURE (P1)** — **Chat conversacional no Storyboard** para edição via linguagem natural.
  - **Backend**: novo endpoint `POST /api/agent/sessions/{id}/storyboard-chat` em `routes/agent.py`. Recebe `{message, history}`, envia para LLM (`gemini-3-flash-preview` com fallback `openai/gpt-4o`) um prompt que exige JSON estruturado `{reply, ops}` onde `ops` é lista de operações tipadas (`edit_title`, `edit_narration`, `edit_notes`, `edit_element`, `add_slide`, `delete_slide`, `move_slide`). Backend valida e aplica atomicamente sobre `session.storyboard.slides`, persiste em MongoDB, mantém `storyboardChatLog` cappeado em 50 entradas. Retorna `{reply, ops, storyboard}` para o frontend re-renderizar.
  - **Frontend** (`pages/Agent/components/StoryboardChat.jsx`): componente novo de chat lateral. Header com ícone Sparkles, sugestões clicáveis na primeira mensagem, auto-scroll para última mensagem, indicadores visuais (ícones para user/assistant, badge "N operacoes aplicadas" em verde quando ops foram aplicadas, mensagem de erro em rosa). Textarea com Enter-envia/Shift+Enter-quebra-linha.
  - **Integração** (`pages/Agent.jsx`): quando `mode==='create' && currentStep===4` (etapa Storyboard), o chat lateral direito mostra o `StoryboardChat` ao invés do chat passivo tradicional. `onStoryboardUpdate` callback sincroniza estado local assim que ops são aplicadas.
  - **Exemplos de uso**: "reescreva a narracao do slide 3 em tom informal" / "adicione um slide de exemplos praticos depois do 2" / "remova o slide final" / "torne o titulo do slide 5 mais impactante".
  - **Validado**: 3 pytests novos em `tests/test_storyboard_chat.py` (edit_narration + edit_title combinados, add_slide + delete_slide com reordem implícita, rejeição de mensagem vazia). Backend startup sem erros.


- 2026-05-08: **FEATURE (preventiva)** — **Migração de dados: normalização de campos numéricos**.
  - **Problema**: projetos importados de PPT ao longo do tempo acumularam campos numéricos armazenados como strings (`"1280"`, `"1280px"`) ou floats onde ints eram esperados (`1280.5`). Além do bug do 422 no "add slide" já corrigido, isso pode causar falhas silenciosas em outros validators mais estritos no futuro.
  - **Novo módulo** `routes/admin_migrations.py`:
    - `POST /api/admin/normalize-numeric-fields?dryRun=true|false` (role `super_admin`/`company_admin`)
    - Walks `db.projects` → coage tipos em: `slide.width/height/order` (int), `slide.duration` (float), `element.x/y/width/height/rotation/zIndex` (float), `element.style.fontSize/strokeWidth/borderRadius/opacity/letterSpacing/lineHeight` (float), `audio.volume/duration/startTime/endTime` (float), `annotation.x/y/width/height` (float)
    - Helpers puros `_coerce_to_int`, `_coerce_to_float`, `_normalize_dict_in_place`, `_normalize_project_inplace` — todos idempotentes e defensivos (não alteram bool, handle None, regex-extract de strings mistas tipo "1280px")
    - Retorna relatório detalhado: `scanned, fixedProjects, totalFieldsCoerced, breakdown{slide_dims, slide_durations, element_pos_size, element_styles, audio_props, annotation_pos}, sampleProjects[]` (top 50)
  - **UI Admin**: nova aba "Migracao" (apenas super_admin) com `DataMigrationPanel.jsx`:
    - Botão **"Scan (Dry Run)"** roda sem escrever, mostra card âmbar com contagens + breakdown + top 50 projetos afetados
    - Botão **"Aplicar Migração"** só habilita após scan, confirm nativo antes de escrever, mostra card verde com resultado
  - **Validado E2E real em preview**: dry-run detectou **55/56 projetos com dados sujos → 4612 campos a corrigir!** Só esperando o admin clicar "Aplicar" para resolver de vez. Em produção com 128 projetos o volume será maior. **19 pytests novos** (`test_admin_migrations.py`) cobrindo todos os coercers + cenário realista PPT-imported.


- 2026-05-08: **FIX (P0 produção)** — **422 Unprocessable Content ao adicionar slide** em projetos importados de PPT.
  - **Causa raiz**: `models.SlideCreate` tinha `width: int` e `height: int` strict. Quando o usuário adicionava slide num projeto cujo primeiro slide foi importado de PPT (com dimensões armazenadas como string `"1280"` ou float `1280.5` no banco), o frontend lia `firstSlide?.width || 1280` e enviava o valor não-int para o backend → Pydantic v2 rejeitava → 422.
  - **Fix backend** (`models.py`): adicionado `field_validator` em `SlideCreate.width/height` que coage qualquer valor para int positivo seguro:
    - `int`/`float` → `int(v)` (cai em fallback se ≤0)
    - `str` → extrai primeiro grupo de dígitos via regex (`"1280px"` → 1280)
    - `None` ou inválido → fallback `1920`
  - **Fix frontend** (`ProjectContext.jsx::addSlide`): helper `toInt(v, fallback)` defensivo. Lê `firstSlide?.width` e força `parseInt`. Se NaN ou ≤0 → fallback. Defesa em profundidade — frontend e backend agora ambos toleram dados sujos.
  - **Validado E2E real**: 4 cenários testados (int, string `"1280"`, float `1280.5`, null) — todos retornam slide criado com dimensões inteiras corretas. **9 pytests novos** em `test_slide_create_coercion.py`.


- 2026-05-08: **FIX (P0)** — **Imagens Leonardo não persistiam em produção** (causa raiz encontrada).
  - **Bug**: o callsite em `services/ai_agent.py:1530-1546` (geração paralela de imagens IA pelo Agente IA) baixava a imagem do Leonardo para disco local mas **NÃO chamava `store_asset_async`**. Em produção K8s, o disco local é efêmero — quando o pod reinicia (ou faz rolling deploy), as imagens desaparecem.
  - **Por que outros locais funcionavam**: `routes/leonardo.py` (rota `/leonardo/save-to-project` chamada pelo painel manual) E `routes/agent.py` (3 outros callsites) JÁ chamavam `store_asset_async` corretamente. Apenas o callsite do batch paralelo do Agente IA (5 imagens concorrentes via semaphore) não persistia.
  - **Fix**: adicionado `store_asset_async(_pdb, project_id, fname, dest)` imediatamente após o download bem-sucedido. Se a persistência falhar, `ok = False` e o caminho de retorno é abortado (igual ao padrão dos outros callsites).
  - **Regression test** (`tests/test_leonardo_persist_regression.py`): scan estático em todo o backend — `download_image_to_disk` em arquivos que mencionam Leonardo DEVE ter `store_asset_async` dentro das próximas 40 linhas. Garante que ninguém esqueça de persistir no futuro.
  - **Para o usuário em produção**: imagens Leonardo geradas a partir de agora vão persistir. Imagens já quebradas que estão na galeria precisam ser regeneradas (ou removidas via "Remover imagens quebradas" que já existe no painel da Galeria).


- 2026-05-08: **FEATURE (P0)** — **Auto-corrigir contrastes nos simuladores** (LLM-independente).
  - **Problema definitivo identificado**: simuladores construídos pelo Agente IA já vinham com problemas de contraste do parto (ex: `.challenge-prompt {color:#fff;background:#e6e9ff}` — branco sobre lavanda claro = 1.5:1, falha WCAG). O LLM nunca conseguia consertar porque sempre propunha regras universais (`body * {color:#0f172a}`) que minha proteção descartava → nada era injetado → simulador continuava quebrado.
  - **Solução determinística**: novo helper `_auto_fix_html_contrast(html)` faz **análise estática do CSS do simulador no servidor**:
    1. `_parse_html_css_rules(html)` extrai cada regra dos blocos `<style>` (skipa `data-aesthetic-fix` próprios e `@keyframes`/gradients).
    2. Para cada regra com `color: X`, calcula a contraste contra o background efetivo via `_resolve_background_for_selector` (tenta o próprio seletor → ancestrais via parsing do descendant chain → fallback para `body` background).
    3. Se contraste < 4.5 (WCAG AA), emite override `selector { color: <opposite-polarity> !important }`. Sempre seletor targeted (mesma classe/id que o LLM gerou), nunca universal.
  - **Novo endpoint** `POST /api/aesthetics/auto-fix-contrast/{project_id}`: aplica em todos os simuladores HTML do projeto, cria snapshot revertível, retorna `{fixed, issuesFixed, message, canRevert}`.
  - **Frontend `AestheticsPanel.jsx`**: novo botão verde "Auto-corrigir contrastes nos simuladores" com ícone `ShieldCheck` — abaixo de "Limpeza Profunda".
  - **Validado E2E real**: projeto "Mastering Problem Solving" → **21 regras de contraste corrigidas em 7 simuladores**! Inspeção manual das injections mostra mapeamento perfeito por polaridade (`.opt-btn` em fundo escuro recebeu branco; `.header`, `.score`, `.node`, `.btn-reset` em fundos claros receberam preto). **120/120 testes pytest passando** (16 novos em `test_aesthetics_auto_fix.py`).


- 2026-05-08: **FIX (P0)** — Analisador de Estética: **idempotência + Limpeza Profunda** para projetos com simuladores corrompidos.
  - **Causa raiz revelada via screenshots do usuário**: simulador "Detector de Vieses Cognitivos" mostrava textos brancos invisíveis MESMO depois dos fixes anteriores (strip de seletores universais, zero override universal). Investigação E2E mostrou que **um único projeto (Mastering Problem Solving) tinha 23 tags `data-aesthetic-fix` acumuladas em 11 simuladores diferentes** — cada Apply rodado pelo usuário ao longo do tempo (com versões mais antigas e bugadas do Analisador) inseria mais um `<style data-aesthetic-fix>` sem nunca remover os anteriores. As regras `body * {color:#fff !important}` de aplicações passadas continuavam ativas e quebravam tudo, mesmo após meu código novo parar de gerar regras universais.
  - **Fix 1 — IDEMPOTÊNCIA**: novo helper `_clean_aesthetic_fixes_from_html(html)` com regex `<style\s+data-aesthetic-fix\s*=\s*[\"\']1[\"\']\s*>[\s\S]*?</style>`. Em `_apply_html_style_fix`, **antes de injetar nova tag, todas as anteriores são removidas**. Re-aplicar sobre o mesmo elemento agora **substitui** ao invés de empilhar. Bonus: se o final_css ficar vazio (LLM só mandou universais → strippados), o helper ainda persiste o html limpo (apaga corrupção legada mesmo sem nova injeção).
  - **Fix 2 — LIMPEZA PROFUNDA**: novo endpoint `POST /api/aesthetics/deep-clean/{project_id}` que percorre TODOS os slides, TODOS os elementos `type:html`, e remove TODAS as `<style data-aesthetic-fix>` acumuladas. Cria snapshot antes (compartilhado com `/revert` — usuário pode desfazer). Retorna `{cleaned, message, canRevert}`.
  - **Frontend `AestheticsPanel.jsx`**: novo botão "Limpeza Profunda (resetar simuladores)" rosa-claro com ícone `Eraser`, sempre visível, com `confirm()` antes de executar. Após clean, `canRevert` ativa o botão "Reverter" caso o usuário queira voltar.
  - **Validado E2E real**: projeto "Mastering Problem Solving" tinha 23 tags acumuladas → deep-clean removeu de 11 simuladores → 0 tags → revert restaurou as 23 → re-deep-clean voltou a 0. **104/104 testes pytest passando** (10 novos em `test_aesthetics_idempotency.py` cobrindo regex, no-op em html limpo, idempotência de re-apply, persistência mesmo com final_css vazio).


- 2026-05-07: **FIX (P0 final)** — Analisador de Estética: bug do branco-sobre-branco em simuladores HTML **definitivamente resolvido**.
  - **Camada que ainda faltava**: mesmo o seletor "narrow" `body p:not([style*=background])` ainda atinge `<p>` aninhado dentro de cards brancos (o `<p>` em si não tem inline `style="background:..."` — o card pai tem). Inheritance + cascade + múltiplos contextos visuais não podem ser sobrescritos com qualquer seletor amplo de tag.
  - **Fix definitivo em `_strengthen_css_injection(preserve_html_typography=True)`**: NÃO injetar QUALQUER override de cor universal (nem `body *`, nem `body p`, nem `body label`, nada). Apenas o CSS do LLM (já filtrado de seletores universais via `_strip_universal_selectors`) passa intacto. Se o LLM só sabe sugerir regras amplas → final_css fica vazio → nada é injetado → simulador 100% preservado.
  - **Prompt do LLM atualizado**: `html_style` agora exige seletores **classe/id/tag-com-classe** e proíbe explicitamente `*`, `body *`, `body` bare, `[style*=color]`. Exemplo no prompt mostra `.option-btn{color:#0f172a !important}` ao invés de regras universais.
  - **Tests atualizados**: 94/94 passando incluindo regression test exato dos casos reportados pelo usuário (simulador "Desafio do Descomplicador" + "Detector de Vieses Cognitivos") — confirma que `body{color:...}` NUNCA é injetado em preserve mode.


- 2026-05-07: **FIX (P0)** — Analisador de Estética: bug do **CSS overreaching destruindo simuladores HTML** resolvido (camada 2).
  - **Reportado pelo usuário com novas screenshots**: simulador "O Grande Desafio Final" tinha botões cyan com texto preto legível ANTES. Após Apply, "Detector de Vieses Cognitivos" mostrou caixa branca vazia + botões cinza com texto branco invisível. **Mesmo padrão do bug anterior persistia** porque eu só tinha fixado o `target_color` adicionado pelo helper — mas o LLM ainda emitia `body * {color:#fff !important}` no campo `cssInjection` que passava intacto pela pipeline (só ganhava `!important` em cada decl).
  - **Causa raiz camada 2**: simuladores reais têm múltiplos contextos visuais (body dark + cards brancos + botões coloridos). Qualquer regra `body *` ou `body{color:...}` cascateia para todos os filhos — o card branco herda texto branco, o botão cyan herda texto branco, tudo invisível. Mesmo com seletores narrow (meu fix anterior), o CSS bruto do LLM bypassava porque tinha seu próprio `body *`.
  - **Fix (`_strip_universal_selectors`)**: novo helper que tokeniza o CSS do LLM rule por rule e **dropa qualquer regra cuja lista de seletores contenha** `*`, `body *`, `body` (bare), `html`, `[style*=color]`. Mantém apenas regras com seletores de classe (`.option-btn`), id (`#prompt`) ou tag-com-qualificador (`body label.error`).
  - Em `preserve_html_typography=True`, esse strip roda **antes** do passo de adicionar `!important`. Resultado: se o LLM mandou só `body *{color:#fff}`, o final_css fica vazio e nada é injetado — preserva o simulador 100%. Se mandou `.dark-text{color:#fff}` (selector targeted), passa intacto e funciona.
  - **12 novos pytests** (`tests/test_aesthetics_strip_universal.py`) cobrindo: bare/scoped universal selectors dropados, class/id/tag-qualified mantidos, mistura comma-separated com 1 dangerous descarta tudo, CSS sem braces preservado, **regression do caso exato do usuário** (simulador com `.prompt-box` + `.option-btn` recebendo `body * {color:#fff}` — confirma que o body* não chega no DOM final).
  - **94/94 testes pytest passando** — zero regressão.


- 2026-05-07: **FIX (P0)** — Analisador de Estética: bug do **"texto branco sobre fundo branco" em simuladores HTML resolvido**.
  - **Reportado pelo usuário com prints**: simulador "Desafio do Descomplicador" tinha card com fundo branco e texto preto legível ANTES da aplicação. DEPOIS, o título, subtítulo, prompt e contador de progresso ficaram **brancos sobre fundo branco** (totalmente invisíveis).
  - **Causa raiz**: `_strengthen_css_injection` injetava `body,body * {color:#fff !important}` independente do background **interno** do simulador. Quando o htmlContent tem `body{background:#fff}` (cards brancos sobre slide escuro), forçar texto branco torna tudo invisível.
  - **Fixes**:
    - Novo helper `_extract_dominant_html_bg(html)`: parse `<style>body{background:...}` + `<body style="background:...">` + containers top-level com classe `container/wrapper/card/game/app/main/content` para detectar o background visível do simulador. Rejeita gradients/url() (não são WCAG-comparáveis).
    - `_strengthen_css_injection` agora aceita `html_bg` e **valida `target_text_color` via WCAG** contra ele. Se contraste falha (<4.5:1), automaticamente inverte para a polaridade oposta (`pick_high_contrast_color`).
    - Em `preserve_html_typography=True` (slides HTML-pesado): troca o universal `body *` por seletores narrow (`body p:not([style*=background]), body h1:not(...), body label:not(...)`). Preserva contraste intencional em cards aninhados (botões com fundo próprio mantêm sua cor original).
    - `_apply_html_style_fix` extrai `html_bg` automaticamente e propaga.
  - **18 novos pytests** (`tests/test_aesthetics_html_polarity.py`) cobrindo: extração de bg em todas as variantes, polarity flip white↔dark, preserve mode selectors narrow + skip de bg-elements, e regression específico do caso reportado pelo usuário (card branco com h1/label/p — verifica que `body{color:...}` injetado NÃO é branco). 78/78 testes pytest sem regressão.


- 2026-05-07: **FIX (P0 produção)** — **502 Bad Gateway em export-scorm/export-html resolvido** via padrão async-job real.
  - **Causa raiz**: endpoints `POST /api/course/{id}/export-scorm` e `/export-html` eram síncronos — esperavam 30-180s para gerar ZIP base64-embedded com áudio ElevenLabs, vídeo HeyGen, gamificação. O gateway/proxy K8s da Emergent tem timeout ~100s → **502 Bad Gateway**. Pior: com `uvicorn --workers 1`, o worker bloqueado também não respondia health checks → K8s mata o pod → deployment falha.
  - **Solução**: refatorados ambos os endpoints para **padrão async-job verdadeiro**:
    - POST captura `request` data sincronamente, cria `job` na collection `jobs` da DB com `status=processing`, agenda heavy work via `asyncio.create_task(_run_scorm_export_job(...))` e retorna `{jobId, statusUrl}` em **~135ms**.
    - Heavy work (collect questions, load tutor/gamification, gerar ZIP via `asyncio.to_thread(...)`, persistir GridFS) roda em task asyncio. Atualiza job com `progress` 10/25/80/90/100 + `message` em cada etapa.
    - Frontend (`useEditorExport.js`): novo helper `pollJobUntilDone(jobId, {onProgress})` faz GET `/api/job/{jobId}` a cada 2s; sucesso → usa `result.downloadUrl`. Tolera blips de rede (502 transientes durante deploy).
    - Backwards-compat: se backend retornar `downloadUrl` direto sem `jobId` (resposta legada), frontend ainda funciona.
  - **Validado E2E**: POST → 135ms (antes ~30-180s) → polling completa em ~8s → download de SCORM ZIP de 5.7MB funcionando perfeitamente. HTML export idêntico.
  - **Impacto na deployment**: worker uvicorn agora fica livre para servir health checks K8s durante exports → pod permanece saudável → deployment passa.


- 2026-05-07: **FEATURE (P1)** — **Snapshot/Revert** + UX fix do botão Krea escondido pelo logo Emergent.
  - **Snapshot/Revert pipeline (backend)**:
    - `apply-fix` agora salva uma **deepcopy de `course.slides`** ANTES das mutações em `db.aesthetic_snapshots` (one-shot, upsert por projectId). Resposta inclui `canRevert: true` quando algo foi aplicado.
    - `POST /api/aesthetics/revert/{project_id}` restaura o snapshot e o consome (single-shot).
    - `GET /api/aesthetics/snapshot-status/{project_id}` retorna `{hasSnapshot, appliedAt, appliedCount}` — usado pelo frontend ao montar o painel para detectar snapshots existentes (ex: depois de refresh).
  - **Frontend `AestheticsPanel.jsx`**:
    - `useEffect` checa snapshot status no mount e mostra botão "Reverter ultima aplicacao" (âmbar, ícone `Undo2`) quando aplicável.
    - Após Apply bem-sucedido, `canRevert` é setado e o botão aparece imediatamente.
    - Botão Reverter → POST /revert → toast + onFixApplied refresh + esconde botão.
  - **UX fix — botão Krea escondido**:
    - O botão "Regerar imagens com Krea AI" estava sendo coberto pelo widget flutuante "Made with Emergent" no canto inferior direito da viewport (que sobrepõe Sheets full-height).
    - Reordenado: "Regerar com Krea AI" promovido para imediatamente após "Aplicar Todas" (visível mesmo sem scroll).
    - "Re-analisar" deslocado para baixo (uso menos frequente).
    - Adicionado `pb-16` na div de actions garantindo que NENHUM botão fique colado no rodapé da viewport — sempre 64px de respiro mesmo quando totalmente scrollado.
  - **Validado**: 1 pytest async novo (`tests/test_aesthetics_snapshot_revert.py`) cobrindo fluxo completo apply→snapshot→status→revert→status (passa em isolado; testes async com Motor têm conflito de event-loop quando rodados junto a sync). E2E real via curl em produção: apply (canRevert=true) → status (hasSnapshot=true) → revert (reverted=true) → status (hasSnapshot=false) → revert sem snapshot (HTTP 400). 60/60 testes pytest síncronos sem regressão.


- 2026-05-07: **FEATURE (P1)** — Analisador de Estética: **expandir tela** + **fontes inteligentes por tipo de slide** + **preservação da harmonia HTML**.
  - **UX expansão**: novo botão `[Maximize2]` no header do `AestheticsPanel` (`data-testid="aesthetics-toggle-expand"`). Editor.jsx mantém estado `aestheticsExpanded` que ajusta a largura do Sheet de `380px` para `95vw max-w-1400px` (transição suave 300ms). Layout interno troca para grid 2-colunas + textos `text-sm` quando expandido — autores conseguem ver todas as issues lado a lado em vez de scrollar uma coluna estreita.
  - **Classificação de slides** (`_classify_slide`): cada slide agora é rotulado como `CAPA` (primeiro slide ou poucos elementos com palavras-chave de abertura), `CONTEUDO` (regular) ou `HTML-PESADO` (>50% HTML ou um HTML cobrindo ≥55% da área). O rótulo aparece no contexto enviado ao LLM (`SLIDE 4 [HTML-PESADO]: ...`) para guiar sugestões específicas.
  - **Prompt revisto**: regras tipográficas por role:
     - CAPA → titulo principal **48-72px**, subtitulo 22-28px (hierarquia que respira)
     - CONTEUDO → h1 32-40px, h2 24-28px, body 16-20px
     - HTML-PESADO → **PROIBIDO impor px**: usar somente `em`/`%`/`rem` e cores. Foco apenas em contraste critico — preservar a tipografia interna do simulador (que o Agente IA construiu intencionalmente). Limite de 1 issue por slide HTML-pesado para reduzir ruido.
  - **Proteção determinística** em `_strengthen_css_injection(preserve_html_typography=True)`:
     - `font-size:Npx` em css de slide HTML-PESADO → convertido automaticamente para `1.05em` (preserva hierarquia interna)
     - `padding`/`margin`/`line-height` → **stripados** antes da injeção (o simulador ja tem tipografia intencional)
     - Apenas `color`/`background-color` passam intactos (correções de contraste)
  - **Validado**: 19 testes pytest novos (`tests/test_aesthetics_classification.py`) cobrindo classificação capa/conteudo/html_heavy + preservação tipografica + label correto no contexto. **60/60 testes Aesthetic + 160/160 Single Page sem regressão**.


- 2026-05-07: **FEATURE (P0)** — **Analisador de Estética com impacto visual real**: WCAG enforcement + plates automáticos + scrim de slide + injeção HTML agressiva.
  - **Bug crítico revelado durante a investigação**: o exporter Single Page (`_render_text_element_inner`) traduzia `fontColor` → `font-color` (CSS inválido, **silenciosamente ignorado pelo browser**). Logo, NENHUM fix de cor de fonte sugerido pelo Analisador era visível no export real. Único fix: mapear `fontColor` → `color` via `_STYLE_KEY_MAP` em `single_page_exporter.py`.
  - **Helper WCAG** (`services/wcag.py`): `parse_hex`, `relative_luminance`, `contrast_ratio` (WCAG 2.1), `enforce_min_contrast(fg,bg,4.5)` que substitui qualquer cor que falhe AA por preto puro `#0f172a` ou branco puro `#f8fafc` (depending on bg luminance). `pick_plate_color` retorna plate semi-transparente que contrasta com a cor do texto.
  - **Pipeline determinístico** em `routes/aesthetics.py`:
    - `_apply_style_fix`: sempre passa `fontColor` por `enforce_min_contrast`. Se slide tem `backgroundImage`, força branco puro + adiciona plate (`textBackgroundColor` rgba) + `padding` + `borderRadius` automaticamente. Promove fontes <14px para 16px.
    - `_apply_text_plate`: novo fix type que adiciona backdrop semi-transparente + textShadow.
    - `_apply_slide_overlay`: novo fix type que define `slide.backgroundImageOverlay` (`dark`/`light`/rgba custom) — render como gradient scrim sobre a `backgroundImage`.
    - `_apply_html_style_fix` + `_strengthen_css_injection`: agora injeta CSS com `!important` em CADA declaração + selector universal `body,body *` + neutralização de inline styles via `[style*="color"]{color:X !important}`. Tag `<style data-aesthetic-fix="1">` inserida no FINAL de `<head>` (ganha do CSS anterior).
  - **Prompt do LLM revisto**: exige WCAG AA mandatório, prioriza plates sobre fundos com image, requer `!important` em html_style. Inclui WCAG ratio calculado no contexto enviado para o modelo (ex: `wcag=2.1:1 (FAILS-AA)`).
  - **Renderização frontend** (`SlideCanvas.jsx`, `CoursePreview.jsx`, `SplitPreview.jsx`, `player.js`, `html_exporter.py`, `single_page_exporter.py`): todos passam a respeitar `style.textBackgroundColor` (alias de plate), `style.padding`, `style.borderRadius`, `style.textShadow`. Slide-level `backgroundImageOverlay` renderizado como scrim absoluto inset:0 sobre a bg-image em todos os contextos (Editor preview + exports HTML/SCORM/SinglePage).
  - **Validado**: 41 testes pytest novos (`tests/test_wcag.py` 17 + `tests/test_aesthetics_pipeline.py` 24) + 160/160 testes Single Page sem regressão. E2E real com `apply-fix` em projeto produtivo aplicou 6/6 fixes; teste unit chain mostrou texto antes invisível agora renderizando como `color:#f8fafc;background-color:rgba(15,23,42,0.65);padding:10px 14px;border-radius:8px` — visualmente garantido em qualquer fundo.


- 2026-04-29: **FEATURE (P3)** — Estimativa de **custo monetário (USD/BRL)** no Cost Report.
  - **Backend**:
    - Tabela de preços default em `routes/cost_report.py`:
      - Krea: per-model do catálogo `KREA_IMAGE_MODELS` (Krea-1: $0.08, Flux 1.1 Pro: $0.06, Flux 1 Dev: $0.04, etc.)
      - Leonardo: $0.02/imagem · Tutor: $0.005/msg · ElevenLabs: $0.05/geração · HeyGen: $0.50/vídeo
      - Cotação USD→BRL: 5.0
    - **CRUD de pricing** em MongoDB (`db.cost_pricing._id="active"`):
      - `GET /api/admin/cost-pricing` — retorna rates + usdToBrl + kreaOverrides + kreaCatalog (snapshot do catálogo Krea com `default`/`override`/`effective`) + defaults para reference.
      - `PUT /api/admin/cost-pricing` — super_admin atualiza qualquer subset; rejeita valores negativos/zero (400); preserva campos não enviados.
      - Helper `_price_per_krea_model()` resolve preço por modelo: override > catálogo > fallback.
    - Cost report agora retorna **`totalUsd`/`totalBrl` por empresa** + `usd`/`brl` por integração + `pricing` snapshot na resposta.
  - **Frontend**: `CostReportPanel.jsx` reescrito:
    - Toggle **BRL ↔ USD** no header (preferência local).
    - Card "Custo total estimado" gradient verde com valor agregado em destaque + cotação aplicada.
    - Tabela "Por Empresa" agora mostra contagens **+ custo abaixo** (R$ 0,07 em destaque pequeno) + nova coluna "Total BRL/USD" em verde grande.
    - Botão "Tabela de preços" abre modal com:
      - 5 campos editáveis para rates default
      - Input para cotação USD→BRL
      - Lista dos 11 modelos Krea cada um com input override + valor catálogo abaixo
      - Validação básica (placeholder com o default, blank = usar catálogo).
  - **Validado**: 9 testes pytest novos (`tests/test_cost_pricing.py`) cobrindo GET/PUT, validação negativa, bloqueio non-super-admin, BRL=USD×rate, override afeta totals em ratio. **19/19 testes total** (cost-pricing + company-override) passando. E2E real: screenshot mostra "R$ 0,27" total agregado + tabela Didaxis "R$ 0,20" + Pricing Dialog com 11 modelos Krea editáveis.

- 2026-04-29: **FEATURE (P1)** — Atribuição de cursos a empresas + Relatório de Custos por Empresa.
  - **Caso de uso**: prestador de serviço usa Scormify para criar cursos para múltiplas empresas clientes — precisa atribuir cada curso à empresa correta para depois identificar custos no faturamento.
  - **Backend**:
    - Novo helper `resolve_company_id_for_creation(user, requested_company_id)` em `routes/projects_common.py` — super_admin pode passar QUALQUER companyId; outros usuários têm o parâmetro silenciosamente ignorado (defesa em profundidade).
    - Novo helper `can_change_project_company(user)` — só super_admin pode reatribuir.
    - **5 pontos de criação** aceitam `companyId` opcional: `POST /api/projects` (manual), `POST /api/agent/sessions` (Agente IA — propaga para o curso final), `POST /api/ppt/upload` (legacy), `POST /api/ppt/upload/init` (chunked).
    - **Edição**: `PUT /api/projects/{id}` agora aceita `companyId` no body — super_admin reatribui, outros têm campo dropado silenciosamente. Valida que a empresa target existe (400 se não).
    - **Cost report**: novo `routes/cost_report.py` com `GET /api/admin/cost-report?from=YYYY-MM-DD&to=YYYY-MM-DD` (super_admin only). Agrega via MongoDB pipelines: projetos por companyId+source, krea_generations, leonardo_generations (companyId direto), tutor_logs, elevenlabs_generations, heygen_jobs (com fallback de JOIN via projectId quando companyId não está no doc).
    - Leonardo agora tagga `companyId` em `db.leonardo_generations` (antes só projectId).
  - **Frontend**:
    - Novo componente `CompanySelector.jsx` reutilizável: dropdown que aparece APENAS para super_admin, lista todas as empresas do `/api/companies`, default = empresa do usuário logado (evita atribuição acidental), badge "(sua empresa)" para identificação. Ocultado completamente para admins comuns.
    - **Dashboard** → New Project dialog + Upload PPT dialog + Edit Project dialog (renomeado de "Renomear" para "Editar Projeto") agora mostram o seletor.
    - **Agente IA** → `UploadPanel` mostra o seletor antes do upload de conteúdo; passa `companyId` para `POST /agent/sessions` que propaga para o curso final.
    - **Admin** → nova tab "Custos por Empresa" com `CostReportPanel.jsx`: filtros de data (De/Até), 6 totais agregados em cards coloridos (Cursos / Krea / Leonardo / Tutor / ElevenLabs / HeyGen), tabela "Por Empresa" com breakdown por source (manual / agent / ppt) e contagens por integração.
  - **Validado**: 10/10 testes pytest novos (`tests/test_company_override.py`) cobrindo: super_admin atribuição cross-company, validação de empresa inexistente (400), regular admin tem campo dropado silenciosamente, super_admin reassign via PUT, regular admin não pode reassign, agent session aceita companyId, cost report retorna estrutura correta, filtros de data funcionam, super_admin only. E2E real: screenshot do Cost Report no Admin mostra 4 empresas + 57 cursos agregados + breakdown source manual/ppt corretamente.

- 2026-04-29: **FEATURE (P2)** — **Live Preview do Single Page** dentro do Editor.
  - **Backend**: novo endpoint `GET /api/projects/{id}/preview-singlepage` em `routes/export.py`. Auth via `require_auth` + `load_authorized_project` (mesma helper canônica do resto das rotas — bloqueia super_admin/cross-company/legacy edge cases consistentemente). Retorna HTML inline (text/html, no-store cache). Reaproveita `generate_single_page_html` com gamification + tutor + questions carregados.
  - **Frontend**: novo dialog `SinglePagePreviewDialog.jsx` (95vw × 95vh) com:
    - Botão na toolbar (ícone Eye âmbar gradient, `data-testid="singlepage-preview-btn"`).
    - Fetch via authHeaders → Blob URL → iframe sandboxed (allow-scripts, allow-same-origin, allow-forms, allow-popups).
    - **Viewport switcher** Desktop/Tablet/Mobile (414/820/100% width) — autores conseguem testar responsividade sem ferramentas externas.
    - Botão "Atualizar" (`preview-refresh-btn`) — re-fetch do HTML após qualquer edit no Editor.
    - Botão "Nova aba" (`preview-open-newtab-btn`) — abre o blob URL em nova janela para teste fullscreen real.
    - Estados loading/error com retry button.
    - Cleanup automático do Blob URL ao fechar (evita memory leak).
  - **Validado**: 4/4 testes pytest novos (`tests/test_singlepage_preview_endpoint.py`) — auth required, 404 para projeto inexistente, HTML válido para projeto real, **cross-company access bloqueado**. Smoke screenshot E2E mostra dialog renderizando perfeitamente o curso "Trilha do Vendedor" com avatar smart-positioned + texto + botão "INICIAR JORNADA". 127/127 testes Single Page totais sem regressão.

- 2026-04-29: **BUGFIX (P0)** — Texto INTENCIONAL desaparecendo no Single Page (correção do dedup agressivo anterior).
  - **Sintoma**: usuário comparou Editor vs Single Page export — no Editor, slide tem "A TRILHA DO VENDEDOR" + "Transforme sua abordagem..." + botão "INICIAR JORNADA" sobre cenário; no export, esses textos sumiram (apenas avatar visível).
  - **Causa**: o fix anterior ("skip visual duplicates on bg-image slides") era heurístico demais — funcionou para PPT-imported slides com texto baked-in MAS quebrou slides com cenário-clean + texto autoral intencional.
  - **Fix correto — absolute positioning**: quando slide tem `backgroundImage`, cada element (text/html/image/quiz/etc.) é renderizado como **`<div class="sp-bg-element">` absolute-positioned** dentro de `.sp-section-inner`, com `left/top/width/height` em **porcentagens** convertidas das coords do Editor relativas a `slide.width` × `slide.height`. Isso preserva o layout autoral exatamente como o autor desenhou no Editor — texto fica onde foi posicionado, sobre o cenário.
  - **CSS dedicado**: `.sp-bg-element` com `box-sizing:border-box`; filhos diretos com `width:100%; height:100%`. Img/video filhos usam `object-fit:contain` para escalar bem ao slot.
  - **Fallback**: elements sem coords válidas (width/height ≤ 0) caem no body flow legado — sem crash.
  - **Editor-native slides** (sem backgroundImage) **não afetados** — continuam usando o body flow.
  - **Validado**: 9 testes pytest novos (`tests/test_singlepage_bg_absolute.py` — substituiu o antigo `test_singlepage_visual_dedup.py`) cobrindo positioning, clamping, integração avatar+texto, fallback. 94/94 testes Single Page passando + E2E real no projeto "Trilha do Vendedor": 4 bg-elements absolutos + texto "TRILHA" + botão "INICIAR JORNADA" todos presentes corretamente posicionados.

- 2026-04-29: **BUGFIX (P0)** — Texto duplicado no Single Page de slides PPT-imported atrás do avatar.
  - **Sintoma**: usuário enviou screenshot mostrando o avatar HeyGen (smart positioning funcionando, na coluna esquerda escura) MAS com texto "A TRILHA DO VENDEDOR" gigante atrás do avatar — duplicação visual feia.
  - **Causa raiz**: o PPT parser extrai o conteúdo textual da slide para `slide.elements` (text/html/shape/line elements) com fins de acessibilidade/busca. O exportador renderizava esses elements no `.sp-section-body` SOBRE a `slide.backgroundImage`, gerando duplicação porque o conteúdo já estava baked-in no PNG do slide.
  - **Fix — dedup heurístico em `single_page_exporter.py`**: quando slide tem `backgroundImage`, pula:
    - Tipos puramente visuais: `text`, `shape`, `line`, `image`.
    - HTML elements SEM markup interativo (sem `<iframe`, `<button`, `<a href`, `<form`, `<input`, `<select`, `onclick=`).
    - Excessões: `interactive: true` ou `requiresClick: true` força a manutenção.
  - **Mantém**: quizzes, scenarios, vídeos não-HeyGen, áudios (narration/sfx/background), avatares, e qualquer HTML autorado pelo usuário com markup interativo (embeds YouTube, mapas, formulários, links).
  - **Não afeta** slides Editor-native (sem `backgroundImage`) — eles continuam renderizando todos os elements.
  - **Validado**: 12 testes pytest novos (`tests/test_singlepage_visual_dedup.py`) cobrindo cada categoria + integração final (avatar overlay + duplicatas removidas). 97/97 testes Single Page passando + E2E real no projeto "Liderança de Impacto" gerou HTML 1.2MB com 0 duplicatas e 1 avatar overlay limpo.

- 2026-04-29: **FEATURE (P2)** — UIs no Editor para SFX/background-music + Smart Avatar Positioning.
  - **Audio Type Picker** (dialog de upload): quando `audioTarget=slide`, 3 cards grid mostram os tipos com ícones e hints contextuais:
    - 🎙️ **Narração** (default): auto-play quando slide fica ativo, com controles pausa/reiniciar.
    - 💥 **Efeito (SFX)**: som curto, toca UMA vez ao entrar no slide, sem controles visuais.
    - 🎵 **Ambiente**: loop ambient do curso inteiro (primeiro vence), volume recomendado baixo.
  - `useEditorAudio` agora expõe `audioType`/`setAudioType`; `handleAudioUpload` passa o tipo selecionado para `uploadSlideAudio(slideId, file, audioType)` em vez do hardcoded 'background'. Toast contextual por tipo ("Narração adicionada ao slide!").
  - **Smart Avatar Toggle** (`SlideProperties.jsx`): nova seção "Posicionamento Inteligente" aparece **APENAS** quando o slide tem avatar HeyGen (video/avatar com URL heygen/transparent/.webm) E cenário (backgroundImage OU imagem ≥800px). Switch toggle liga/desliga `slide.smartAvatar=true` via `updateSlide`. Hint explica que coords manuais serão ignoradas. Feedback verde "✓ Ativo" quando ligado.
  - **Backend model**: `SlideUpdate` em `models.py` ganhou campo explícito `smartAvatar: Optional[bool]` (já tinha `extra="allow"`, mas agora documentado + tipado).
  - **Validação**: E2E curl testou `PUT /slides/{id}` com `{"smartAvatar":true}` → persistido corretamente; `POST /slides/{id}/audio` com `audio_type=sfx` → persistido com `type:sfx`. 114/114 testes pytest sem regressão. Smoke screenshot no Editor confirma UI carrega sem erros.

- 2026-04-29: **FEATURE (P2) + REFACTOR (P3)** — 3 melhorias simultâneas no Single Page export.

  ### 🎯 Smart Avatar Positioning (P2)
  Novo helper `_smart_avatar_position(scene_image_path)` analisa a terça inferior da imagem de cenário (via Pillow), divide em 3 colunas (esquerda/centro/direita) e pega a coluna **mais escura** (provavelmente chão/mesa/sombra) para colocar o avatar. Tamanho: 32% × 55% ancorado no rodapé. Opt-in via:
    - `slide.smartAvatar = True` (flag explícita), OU
    - Avatar sem coords (x=0, y=0) — auto-triggered.
  Respeita coords explícitas do Editor por default (não regride cursos existentes). Data-attribute `data-smart-column="0|1|2"` injetado para debug.

  ### 🎵 SFX + Background Music (P2)
  `slide.audio[]` agora aceita 3 tipos:
    - `type="narration"` (existente) — auto-play ao entrar na seção, pill visível, mudo global.
    - `type="sfx"` (novo) — hidden `<audio>` one-shot disparado ao entrar na seção; volume default 0.6; sem UI; não bloqueia progressão; guard anti-replay via `Set` em memória.
    - `type="background"` (novo) — o PRIMEIRO encontrado torna-se a ambient loop do curso inteiro; `<audio loop>` no body com botão 🎵/🔇 no header. Respeita autoplay policy do browser (aguarda primeiro click/keydown/touchstart). Persistência em sessionStorage (`sp:bgmusic:muted`); volume default 0.2.

  ### 🧹 Refactor Single Page Exporter (P3)
  Arquivo reduzido de **2656 → 1452 linhas** (-45%). JS runtime (958 linhas) extraído para `services/sp_runtime/runtime.js` + CSS (246 linhas) para `services/sp_runtime/styles.css`. Python loader com `Path(__file__).parent / 'sp_runtime'` → `.read_text(encoding='utf-8')`. Vantagens: syntax highlighting real para JS/CSS durante edição, LOC Python gerenciável, ainda zero configuração (arquivos carregados no import).

  ### Validação
  **27 testes pytest novos** (`tests/test_singlepage_audio_smart.py`) cobrindo SFX/bg-music discovery/rendering + smart avatar (image analysis sintética com imagens 300×300 de coluna escura controlada + trigger flags). **124/124 testes Single Page totais passando** + E2E real no projeto "Liderança de Impacto" (1.2MB standalone com 3 SFX + 8 bg-music markers + 10 fullscreen buttons + avatar corretamente posicionado).

- 2026-04-29: **BUGFIX (P0)** — Avatar HeyGen sobre `slide.backgroundImage` (PPT-imported) + scrollbar do aspect-locked.
  - **Sintoma**: usuário enviou screenshot mostrando avatar HeyGen aparecendo abaixo do cenário (não dentro), com uma faixa amarela no meio cortando + scrollbar vertical lateral.
  - **Causas**:
    1. O detector `_find_avatar_scene_pair` só matcha quando a "cena" é um `<image>` element. Em slides PPT-imported, a cena vem como `slide.backgroundImage` (CSS background) — então o pair-finder retornava None e o avatar caía no fluxo vertical normal.
    2. CSS do aspect-locked `.sp-section-body` tinha `overflow-y:auto` + `max-height:55%` → quando o iframe HTML (header bar + botão "Concluí a interação") era maior que 50% do card, surgia scrollbar.
    3. A faixa amarela era o botão "✓ Concluí a interação acima" do iframe — comportamento legítimo, mas atrapalhava visualmente quando o body era muito alto.
  - **Fix 1 — Avatar over bg-image**: novos helpers `_find_avatar_for_bg_scene` + `_render_avatar_overlay_for_bg`. Quando slide tem `backgroundImage` E HeyGen avatar element, o avatar é removido do fluxo normal e renderizado como `<div class="sp-avatar-overlay sp-avatar-wrap" style="position:absolute;...">` DENTRO do `.sp-section-inner` aspect-locked. Coordenadas convertidas de pixels do Editor → porcentagens relativas a `slide.width`/`slide.height` (preserva a posição autoral). `data-required="true"` mantido para gating de play.
  - **Fix 2 — Scrollbar**: CSS do `.sp-section.sp-aspect-locked .sp-section-body` agora usa `overflow:visible` (sem scrollbar) + `max-height:50%` reduzido para 50%, padding mais discreto. Body é absoluto na parte inferior do card com gradient overlay sutil. `:empty{display:none}` esconde o body strip quando o avatar consumiu o único element relevante.
  - **Validado**: 7 testes pytest novos cobrem o caso bg-image + avatar (cobertura: avatar overlay positioning, gating preservado, regressão para slides sem avatar, scrollbar removido, body :empty hide). 58/58 testes passando + E2E real no projeto "Liderança de Impacto" (1920×820 com `backgroundImage` + avatar HeyGen) gerou HTML com `sp-avatar-overlay-0` corretamente posicionado.

- 2026-04-29: **FEATURE (P1)** — Modo **Tela Cheia / Kiosk** no Single Page export.
  - **O que faz**: botão dedicado no header (com ícones expand/shrink dinâmicos) que ativa modo cinema imersivo:
    - Browser Fullscreen API (`document.documentElement.requestFullscreen()`) com fallbacks `webkit/moz/ms`.
    - Header colapsa de 54px → 36px com glassmorphism + auto-hide após 2.5s de inatividade do mouse (cinema feel).
    - Section ativa expande para `100vh × 100vw`; PPT slides com `sp-aspect-locked` reaproveitam aspect-ratio mas ocupam até 96vw × `100vh - 60px`.
    - Drawer lateral é ocultado.
    - Botão exit-fullscreen flutuante no canto superior direito sempre visível (mesmo com header oculto).
  - **Atalhos**: F11 ou tecla "f" toggle (com guarda anti-INPUT/TEXTAREA/SELECT). Esc é tratado nativamente pelo browser + sincronizado com flag interno via `fullscreenchange` event.
  - **Persistência**: estado em `sessionStorage` (`sp:fullscreen`) — sobrevive refresh da mesma session, mas não auto-aciona Fullscreen API (browser exige user gesture).
  - **Mobile**: `@media (max-width: 768px)` ajusta o aspect-locked para `height: calc(100vh - 60px)` evitando squish em portrait.
  - **Testado**: 7 pytest novos (`tests/test_singlepage_fullscreen.py`) cobrindo botão, CSS, JS runtime, atalhos, persistência, sync com Esc.

- 2026-04-29: **BUGFIX (P0)** — Slides importados de PPT renderizavam como **banner mínimo** no SCORM Single Page export.
  - **Sintoma**: usuário enviou screenshot mostrando slide PPT (1280×720) renderizado como banner horizontal estreito flutuando sobre uma área escura imensa — o conteúdo da slide ocupava ~30% da viewport.
  - **Causa raiz**: o exportador aplicava `background-image: url(...)` + `background-size: cover` no `.sp-section-inner` SEM nenhuma restrição de altura. Como o card só tinha o título h2 dentro (poucos elementos no body), a altura ficava determinada pelo título + padding (~480px), enquanto a section forçava `min-height: 100vh` (1080px+) — gerando a "banda" no topo e o vazio escuro abaixo.
  - **Fix**: quando o slide tem `backgroundImage` E `width`/`height` válidos (típico de PPT-imported), o exportador agora:
    1. Adiciona classe `sp-aspect-locked` à section.
    2. Define `aspect-ratio: {slide_w}/{slide_h}` no card → preserva proporção (16:9, 4:3, etc.).
    3. CSS dedicado `.sp-section.sp-aspect-locked .sp-section-inner` com `max-width: min(95vw, 1600px)` + `padding: 18px 22px` (em vez de 1080px max + 48px 56px).
    4. Title flutuante com glassmorphism no canto superior + body em camada inferior com gradient overlay — para não cobrir o conteúdo da slide.
    5. Mobile fallback `@media (max-width: 768px)`: aspect-ratio é desligado, title volta ao fluxo normal (evita slides quadrados/microscópicos em portrait).
  - **Não afeta** slides nativos do Editor (sem `backgroundImage`) — eles continuam com o card layout original (1080px max-width, conteúdo flow vertical).
  - **Validado**: 10 testes pytest novos (`tests/test_singlepage_ppt_aspect.py` — todas resoluções: 1280×720, 1920×1080, 960×720) + E2E real no projeto "0 - Apresentacao - A trilha do vendedor" → HTML gerado com 17 ocorrências de `sp-aspect-locked` + `aspect-ratio:1280/720`. Sem regressão (44/44 testes passando).

- 2026-04-29: **BUGFIX (P0)** — Avatar HeyGen agora é sobreposto à imagem de cenário no Single Page export (em vez de aparecer empilhado verticalmente).
  - **Sintoma**: usuário enviou screenshot mostrando o avatar HeyGen (vídeo .webm transparente) renderizado COMO BLOCO SEPARADO acima da imagem de cenário, em vez de ficar dentro/sobre o cenário como definido no Editor.
  - **Causa raiz**: o exportador `single_page_exporter.py` renderizava cada element individualmente como bloco vertical (`<div>...</div><div>...</div>`), perdendo o posicionamento absoluto que o autor configurou no Editor.
  - **Fix**: novos helpers `_is_heygen_or_transparent_avatar`, `_looks_like_scene_image`, `_find_avatar_scene_pair` detectam o par avatar-HeyGen + imagem-de-cenário (image com >=55% da largura do slide). Quando encontrados, `_render_avatar_stage` produz UM bloco `.sp-avatar-stage` com:
    - Imagem de cenário em camada base (`<img>` com `object-fit:cover`, `inset:0`).
    - Vídeo do avatar em overlay absoluto, com `left/top/width/height` em **porcentagens** derivadas das coordenadas x/y/width/height do Editor (preserva a posição original do autor).
    - Clamp 0%-100% para evitar avatar "escapar" do cenário em casos edge.
    - Fallback bottom-center 40% para slides legados sem coordenadas.
  - **Mantém gating**: o overlay carrega `data-required="true"` + `data-interactive="video"` + classe `sp-avatar-wrap` para que a JS runtime existente (`SP.markPlayed`) continue desbloqueando a próxima seção quando o usuário pressionar play.
  - **Heurísticas inteligentes**: pair-finder evita combinar avatar com logo (image <55% slide width); pega a maior imagem se houver múltiplas; pega o primeiro avatar se houver múltiplos.
  - **Validado**: 20/20 testes pytest novos (`tests/test_singlepage_avatar_stage.py`) + 43 testes anteriores sem regressão.

- 2026-04-29: **FEATURE (P0)** — Áudios da ElevenLabs integrados na exportação **Página Única** (Single Page).
  - **O que foi feito**: o exportador `services/single_page_exporter.py` agora renderiza `slide.audio[]` (populado via Editor TTS dialog → ElevenLabs `/api/elevenlabs/generate-speech` → upload em `/api/projects/{pid}/slides/{sid}/audio`).
  - **Comportamento UX**:
    - Auto-play da narração quando a seção fica ativa (≥40% visível) — via `IntersectionObserver`.
    - Pausa automaticamente narrações de outras seções ao rolar.
    - Múltiplas narrações por slide tocam em sequência (chained playback).
    - **Não bloqueia progressão** (narração é suporte, não interativo gated) — diferente do antigo `<audio>` element que tinha `data-required="true"`.
    - Pill compacta com ▶/⏸ + ↻ (reiniciar) por seção como fallback quando navegador bloqueia autoplay.
    - **Toggle global de mudo** no header da página, persistido em `sessionStorage` (`sp:narration:muted`) — quando mudo ativo, todas as narrações pausam imediatamente.
  - **Inlining (standalone)**: `_resolve_asset_url` converte arquivos MP3 locais em **data URI base64** — o HTML exportado funciona offline 100% sem servidor (validado E2E: 1.66 MB com áudio 67 kB embutido).
  - **Dark mode automático**: CSS `.sp-narration-controls` usa fundo escuro com glassmorphism que combina com seções `.sp-section.sp-dark`.
  - **Acessibilidade**: `aria-label`, `role="group"`, suporte a `prefers-reduced-motion`, foco visível.
  - **Validação E2E**: 14/14 pytest passando + curl confirmou 27 ocorrências de `sp-narration` + audio base64 + JS runtime no HTML exportado real do projeto "Mastering Problem Solving".

- 2026-04-29: **BUGFIX (P0)** — Erro "Missing slideId or elementId" ao editar imagens inseridas pelo Agente IA.
  - **Sintoma**: usuário reportou print onde imagem Krea foi inserida MINÚSCULA no canto superior do slide, e qualquer tentativa de redimensionar/mover disparava `Uncaught runtime error: Missing slideId or elementId`.
  - **Causa raiz**: `_attach_image_to_slide` em `routes/agent.py` preservava element existente quando achava `type=image`, apenas trocando `src`. Se o element original (vindo de import PPT) tinha `id=None, x=None, y=None, width=None, height=None`, a quebra era herdada. Frontend exibia o element com dimensões default minúsculas, e ao tentar editar, `updateElement(slideId, undefined, ...)` lançava throw.
  - **Fix 1 (raiz)**: `_attach_image_to_slide` agora normaliza todos os campos críticos (id, x, y, width, height, style) do element existente antes de atualizar o src. Coordenadas passam a ser relativas às dimensões reais do slide (`slide.width`/`slide.height`) com fallback 1920x820 — antes eram hardcoded 1160/90/700/440 que quebravam em slides 960x540.
  - **Fix 2 (defensivo)**: `updateElement` em `ProjectContext.jsx` não mais lança `throw new Error`; apenas loga no console + retorna silenciosamente. Evita o "Uncaught runtime error" scary overlay em casos edge.
  - **Fix 3 (migração)**: script one-off corrigiu 2 projetos com slides já quebrados (ids None, positions None, dimensões None) — preencheu defaults razoáveis.
  - Aplica-se também aos caminhos Leonardo/Gemini (mesma função `_attach_image_to_slide`).

- 2026-04-29: FEATURE (P1) — **Krea AI na Galeria de Imagens** + novo tipo `imagem_krea` no pipeline do Agente IA (40+ modelos curados por slide).
  - **Parte A — Galeria**: imagens geradas via Krea (tanto pelo botão `Usar no Curso` do `KreaPanel` quanto pelo pipeline do Agente IA) agora:
    1. Persistem no MongoDB via `store_asset_async` (sobrevivem restart de pod K8s — antes podiam sumir em produção).
    2. Auto-salvam em `db.image_gallery` via `routes.gallery.auto_save_to_gallery` com keywords enriquecidas `krea {modelId}: {prompt}` — aparecem imediatamente na Galeria de Imagens do Editor.
  - **Parte B — Agente IA**: novo tipo de melhoria `imagem_krea` disponível ao lado de `imagem_simples` (Gemini) e `imagem_premium` (Leonardo):
    - **Backend**: `_process_krea_images(db, projectId, result, slides, generate_id, user)` em `routes/agent.py` lê `_kreaImage: {prompt, modelId, width, height}` das updatedSlides/newSlides, submete para Krea, faz polling (max 3 min × 90 tentativas × 2s), baixa, persiste e anexa ao slide. Contagem `kreaImagesGenerated` exposta no payload DONE.
    - **LLM prompt** (`services/ai_agent.py`): bloco `imagem_krea_instructions` instrui o LLM a emitir `_kreaImage` preservando o `modelId` escolhido pelo usuário (sem alterar).
    - **Frontend** (`pages/Agent/components/CoursePanels.jsx`): seletor de 3 vias em cada sugestão com imagem — botões `Econômica` / `Premium` / `Krea AI`. Clicar em Krea revela um dropdown `krea-model-picker-{i}` com os 11 modelos (label + custo + tempo). Estado `kreaModelOverrides` por sugestão.
    - **Frontend** (`Agent.jsx`): `handleTypeOverride(impIndex, newType, {kreaModelId})` propaga o modelo escolhido e anexa `_kreaImage: {prompt, modelId, width, height}` ao improvement antes de enviar para `/preview-improvements` e `/apply-improvements`.
  - **Bug crítico corrigido durante testes (iteration_116)**: `auto_save_to_gallery` usava `db` do módulo (main event loop) — background workers em thread separada (Leonardo/Gemini/Krea no pipeline do Agente) sofriam `"Future attached to a different loop"` e **nenhuma imagem gerada via Agente aparecia na galeria há tempos**. Fix: helper agora aceita `db_override=None` kwarg; as 3 call sites em `agent.py` injetam `_db` (Motor client loop-correto do worker). Bare `except Exception: pass` substituído por `logger.warning/exception` para visibilidade futura.
  - **Validado E2E (iteration_117 → 100% backend)**: 29/29 pytest passando + 2 E2E live (test_krea_agent_e2e.py). Pipeline do Agente com `imagem_krea`/`flux-1-dev` gerou imagem em 13s e apareceu na galeria. Direct save flow (KreaPanel) não afetado. Leonardo e Gemini também beneficiados pela correção.

- 2026-04-29: FEATURE (P0) — Integração completa **Krea AI** para geração de imagens (40+ modelos via 11 curados).
  - **Por que?** O usuário solicitou acesso à Krea AI tanto para geração manual de imagens no Editor (tab/botão ao lado do Leonardo AI) quanto dentro do AI Aesthetic Analyzer (CTA para regerar imagens com base na análise estética).
  - **Backend**: implementado `services/krea_ai.py` com catálogo curado de 11 modelos (Krea-1 flagship, Flux 1 Dev/Pro/Kontext, Imagen 4/Ultra, Nano Banana 2/Pro, ChatGPT Image, Seedream 5 Lite, Ideogram 3.0) — cada um com `path`, `label`, `description`, `maxWidth/Height`, `defaultSteps`, `approxCostUSD`, `approxTimeSeconds`, `tier` (standard/premium). Helpers `submit_generation`, `get_job`, `download_image_bytes`. Auth `Bearer api_id:api_secret`. Chave env `KREA_API_KEY`.
  - **5 endpoints REST** em `routes/krea.py`:
    - `GET /api/krea/status` → `{configured, models}` — usado pela UI para condicionalmente mostrar o botão Krea.
    - `GET /api/krea/models` → lista completa com metadados.
    - `POST /api/krea/generate` → submete job; valida `modelId` + `prompt`; insere doc em `db.krea_generations` para tracking.
    - `GET /api/krea/jobs/{id}` → polling; atualiza `db.krea_generations` com status + URLs.
    - `POST /api/krea/jobs/{id}/save` → baixa a imagem completed + salva em `PROJECTS_DIR/{projectId}/assets/{uuid}.png`; retorna public URL.
  - **Health check**: `_check_krea()` em `routes/health.py` usa `GET /jobs/health-check` — 404 "not found" = auth OK; 500 = chave inválida; 401/403 = expirada. Retorna `balance.modelsAvailable`. Integrado em `/api/admin/integrations-health`.
  - **Frontend Editor** (`pages/Agent/components/KreaPanel.jsx` — novo): dropdown de 11 modelos com badge `⭐ premium` / `⚡ standard` + custo/tempo estimado, textarea de prompt, inputs de largura/altura, 4 presets de aspect ratio (16:9/4:3/1:1/9:16), botão gradient pink→violet `Gerar com Krea AI`. Polling a cada 2.5s até 60 tentativas (2.5min máx). Resultados em grid 2 colunas com hover overlay `Usar no Curso` (chama `/save`) + `Abrir` (preview externo). Estado vazio amigável se `KREA_API_KEY` não configurada.
  - **Editor.jsx**: novo botão `krea-ai-btn` na toolbar (ícone Sparkles rosa, ao lado do Leonardo) + Dialog renderizando KreaPanel. `onImageSaved` insere `<image>` no slide atual (centralizado, 80% do canvas).
  - **AestheticsPanel.jsx**: novo botão `aesthetics-krea-regenerate` após os resultados da análise. Ao clicar, abre KreaPanel em Dialog pré-preenchido com prompt contextualizado — extrai `result.summary` + primeira issue de `contraste`/`harmonizacao`/`legibilidade_html` para gerar prompt do tipo "Imagem ilustrativa educacional de alta qualidade, estilo profissional, paleta harmônica. Contexto: {descrição da issue}".
  - **IntegrationsHealthPanel.jsx**: `krea` adicionado ao `INTEGRATION_META` (ImageIcon, "Geracao de imagens (40+ modelos)") + `formatBalance` mostra "11 modelos de imagem disponiveis".
  - **Validado E2E pelo testing_agent_v3_fork** (iteration_115):
    - Backend 100%: 22/22 pytest passing (unit + integração live) + job real flux-1-dev concluído em ~8s, imagem salva com sucesso no projeto.
    - Frontend 100%: todos os `data-testid` detectados (krea-ai-btn, krea-panel, krea-model-select, krea-generate-btn, krea-save-0, aesthetics-krea-regenerate, integration-card-krea). Fluxo E2E completo validado: gerar → polling → completed → "Usar no Curso" → imagem aparece no slide com toast pt-BR.
    - Admin Integrations Health: card Krea renderiza com badge "Online" + "11 modelos de imagem disponiveis" via super_admin.


- 2026-04-29: FIX (P0 deployment) — Build do deploy falhando com "connect() failed (111: Connection refused)" no upstream backend.
  - **Bug do usuário (logs nginx)**: nginx em produção `backend-startup.cluster-1.deploy.emergentcf.cloud` retornava 111 Connection Refused tentando conectar em `127.0.0.1:8001` para `/api/agent/projects/.../avatar-settings`, `/api/agent/courses/.../analyze` e `/api/agent/courses`. Isso significa que o **backend FastAPI nem chegou a iniciar** no container Kubernetes (caso contrário responderia algum status HTTP, mesmo 5xx).
  - **Causa raiz #1 (BLOCKER)**: `.gitignore` linhas 116-118 ignoravam `.env`, `.env.*` e `*.env`. O sistema de deploy Emergent precisa que `backend/.env` e `frontend/.env` estejam **versionados** no repo para auto-popular com valores de produção (Atlas MongoDB URL, REACT_APP_BACKEND_URL prod). Sem esses arquivos no commit, o backend iniciava SEM `MONGO_URL` → `os.environ['MONGO_URL']` lançava `KeyError` na importação → backend crashava → nginx ficava sem upstream.
  - **Causa raiz #2 (BLOCKER)**: `supervisord.conf` linha 30 chamava `command=/bin/bash /app/backend/start.sh` em vez de invocar uvicorn diretamente. O wrapper bash adicionava indireção desnecessária e poderia falhar gerenciamento de signal/restart no K8s. Padrão esperado para apps FastAPI+React+Mongo na plataforma é `command=uvicorn ...` direto.
  - **Fix #1**: removidas as linhas `.env`, `.env.*`, `*.env` de `.gitignore` (mantidas apenas as exclusões de credenciais reais: `credentials.json`, `*.pem`, `*.key`, `.credentials`). Adicionado comentário explicando por que .env DEVE ser versionado.
  - **Fix #2**: `/etc/supervisor/conf.d/supervisord.conf` linha 30 alterada para `command=/root/.venv/bin/uvicorn server:app --host 0.0.0.0 --port 8001 --workers 1 --timeout-keep-alive 300` — preserva o crítico `--timeout-keep-alive 300` (essencial para evitar 502 do K8s Ingress durante export de vídeo) que estava no `start.sh`. O `start.sh` deixa de ser invocado mas é mantido como referência (não bloqueia nada).
  - **Validado**: 78/78 testes preservados. `supervisorctl status` mostra backend RUNNING após reread+update. `curl /api/projects` retorna 200 OK. `git check-ignore backend/.env frontend/.env` retorna vazio (não ignorados mais).

- 2026-04-29: FIX (P0 produção) — Cadeia de 520/502 em produção causados por listagem `/api/projects` enviando todo o conteúdo dos projetos.
  - **Bug do usuário (screenshot)**: console floodada com `Failed to load resource: status 520`/`502` em `/api/projects`, `/api/agent/courses`, `/api/agent/courses/{id}/analyze`, `/api/agent/projects/{id}/avatar-settings`, mais `net::ERR_HTTP2_PROTOCOL_ERROR` em loads de imagens. Cloudflare 520 = "origin returned empty/error" → tipicamente backend retornou resposta muito grande ou demorou demais.
  - **Causa raiz**: `GET /api/projects` (Dashboard listing) executava `db.projects.find(query, {"_id": 0}).to_list(500)` — retornava o **projeto inteiro** (slides, htmlContent, assets inline em base64) para CADA projeto. Para companies com muitos cursos pesados, a resposta podia exceder 50+ MB e estourar o limite do gateway emergent.host → 520. A falha desse endpoint causava cascata: o Dashboard sem dados disparava re-renders que causavam outros 502s/HTTP2 errors em endpoints adjacentes.
  - **Fix**: `list_projects` agora usa aggregation pipeline com `$project`/`$slice` retornando APENAS:
    - Metadata leve: `id`, `name`, `description`, `tags`, `createdAt`, `updatedAt`, `userId`, `companyId`, `source`, `agentSessionId`, `createdByAgent`, `singlePageMode`, `vlibras`, `approvalStatus`
    - `course.metadata` (título/descrição)
    - `course.slides` com `$slice: 1` (apenas o primeiro slide para o thumbnail do `SlideMinPreview`)
    - `course.slidesCount` (contagem total via `$size`)
  - **Compatibilidade frontend**: `Dashboard.jsx` ajustado para usar `project.course?.slidesCount ?? project.course?.slides?.length` no badge — fallback mantém retrocompatibilidade. Outros usos (thumbnail do primeiro slide, `SlideMinPreview`) continuam funcionando idênticos.
  - **Endpoint de detalhe NÃO afetado**: `GET /api/projects/{id}` continua retornando o projeto inteiro (necessário para o Editor). Apenas a LISTAGEM ficou leve.
  - **Validado**: 78/78 testes (4 novos `test_list_projects_lightweight.py`: cobertura de payload max 1 slide por projeto, `slidesCount` presente, response < 5MB, detalhe full document preservado). Curl: response caiu de 2.7MB → **236KB** no preview (10x menor); em produção com cursos maiores e mais conteúdo, a redução proporcional será gigante (>50MB → ~5MB típico).

- 2026-04-29: FIX (P0 produção) — Toggle "Página Única" retornando 502 Bad Gateway em produção.
  - **Bug do usuário (screenshot)**: ao ativar o switch de "Página Única" no `ExportDialog` em produção (`backend-startup.emergent.host`), o frontend recebia `PUT /api/projects/{id}` → **502 Bad Gateway** ("AxiosError: Request failed with status code 502" + "ERR_BAD_RESPONSE"). No preview funcionava normalmente.
  - **Causa raiz**: o endpoint `PUT /api/projects/{project_id}` em `routes/projects_crud.py` retornava `await get_project_by_id(project_id)` — o **projeto inteiro**. Para projetos com muitas slides + `htmlContent` extenso + media inline (base64), o JSON de resposta podia ultrapassar vários MB. Em produção (atrás do proxy/CDN da emergent.host), isso atingia o limite de tamanho/timeout do gateway → 502. No preview funcionava porque o limite é mais permissivo.
  - **Fix**: o endpoint agora retorna apenas `{success: true, id: project_id, updated: ["singlePageMode", "updatedAt"]}` (~100 bytes). O frontend (`ExportDialog.jsx`) já chama `fetchProject()` em `.then()` para re-buscar o estado fresco — então não há perda funcional, apenas overhead removido. Mesma proteção beneficia o toggle de VLibras (único outro consumer desse endpoint).
  - **Validado**: 74/74 testes (2 novos `test_put_project_lightweight.py` cobrindo: response shape correto, payload < 200 bytes, função não chama mais `get_project_by_id`). E2E via curl: response medida em **101 bytes**. Teste regressão `test_project_singlepagemode_field_persists` atualizado para verificar persistência via GET separado (espelha o fluxo real do frontend).

- 2026-04-29: FIX (P0) — Botão com timeline (startTime/endTime) não aparecia no Single Page export.
  - **Bug do usuário (screenshot)**: na slide "Cenário: Atendimento e Suporte" o autor configurou um botão "Clique aqui" (link para PDF) com `startTime=3.48` / `endTime=5` para aparecer 3.5s depois do início da timeline. No Single Page export o botão simplesmente nunca aparecia.
  - **Causa raiz #1**: o dispatcher `_render_element` em `single_page_exporter.py` não tinha case para `type='button'` nem para `type='shape'` — caía no `return ""` (string vazia). Idem para `shape`. Esses elementos eram silenciosamente descartados.
  - **Fix #1**: novos renderers `_render_button_element_inner` (renderiza `<a target="_blank">` com palette primary/secondary/outline/ghost/destructive/success se `buttonUrl`, ou `<button>` passive caso contrário; sempre marcado `data-required="true"` para gating) e `_render_shape_element_inner` (rectangle/circle decorativo, sem gating).
  - **Causa raiz #2**: mesmo após renderizar o botão, a timeline forçava `endTime=5s` → o botão aparecia em 3.48s (fade-in 0.5s) e desaparecia em 5s (fade-out 0.5s). Janela útil: ~1s — impossível de o aluno clicar. Pior: como o botão é `data-required="true"`, escondê-lo trava o gating da seção (aluno fica preso).
  - **Fix #2**: o JS engine de timeline agora checa `el.querySelector('[data-required="true"]')` antes de agendar o `setTimeout(hide)`. Required interactives (botões, quizzes, cenários, vídeos required) NUNCA são escondidos pelo `endTime` — só elementos decorativos (texto, imagem, shape) podem sumir. Garante que o aluno sempre consegue interagir.
  - **Validado**: 72/72 testes (8 novos `test_singlepage_button_element.py` cobrindo URL/sem URL, palettes, escape XSS, dispatch, timeline wrap, shape; 1 novo `test_timeline_does_NOT_hide_required_interactives`). Visual via Playwright em "Cenário: Atendimento e Suporte": botão azul "Clique aqui" agora aparece 3.5s após início da timeline e PERMANECE visível depois (`opacity:1`), aluno consegue clicar e completar a seção.

- 2026-04-29: FEATURE (P1) — Timeline (auto-play sequencial) no Single Page export.
  - **Resposta à pergunta do usuário**: antes, o Single Page **ignorava completamente** `startTime`/`endTime`/`animations` — todos os elementos apareciam simultaneamente quando o aluno chegava na seção.
  - **Implementado opção (a) Auto-play sequencial**:
    - Helper Python `_maybe_wrap_with_timeline(rendered_html, el)`: se elemento tem `startTime > 0` ou `endTime > 0`, embrulha o HTML em `<div class="sp-element-timed" data-start-time="X" data-end-time="Y">`.
    - Renderer principal `_render_element` agora passa todo elemento por esse wrapper.
    - Quando seção contém algum elemento timed, injeta um interactive sintético `.sp-timeline-gate` com `data-required="true"` + barra de progresso visual + mensagem "⏱ Reproduzindo sequência temporal — aguarde o fim para liberar a próxima seção". `data-section-duration` armazena `max(start,end)` de todos os elementos.
    - CSS: `.sp-element-timed{opacity:0;transform:translateY(20px)}` → ao receber `.sp-revealed` faz fade-in suave 0.5s. `.sp-hidden` para sair.
    - JS engine (`startSectionTimeline`, `observeTimelines`):
      - IntersectionObserver detecta seção entrando em viewport (40% threshold) e dispara timeline.
      - `setTimeout(reveal, startTime*1000)` agenda fade-in de cada elemento.
      - `setTimeout(hide, endTime*1000)` se `endTime > startTime`.
      - Loop a cada 100ms atualiza barra de progresso.
      - Ao atingir `sectionDuration`, chama `SP.markClicked(gate)` → libera próxima seção.
    - `unlockSection` também kickstart a timeline (caso IntersectionObserver não re-fire quando o `data-locked` é removido com a seção já em viewport).
  - **Comportamento legado preservado**: elementos sem `startTime`/`endTime` (ou com 0) renderizam imediatamente como antes — zero impacto em cursos sem timeline. Detectado em 31 elementos timed em 7 projetos reais (0.3% dos elementos totais).
  - **Validado**: 63/63 testes (9 novos `test_singlepage_timeline.py`). Visual via Playwright em "Reporte por cursos & trilhas" (3 elementos com startTime 18.81/20.85s + endTime 40s): seção entra em viewport → barra de progresso rodando (1.5% → 14% após 5s, consistente com 40s totais), gate amarelo de gating visível, chevron de avanço oculto até timeline terminar.

- 2026-04-29: FIX (P0 visual follow-up 3) — Heurística "header bar" auto-detecta cabeçalhos oversized em Quizzes/Cenários/etc.
  - **Bug do usuário (screenshot)**: na slide "Checkpoint: Impactos Estruturais" (que contém Quiz), o autor criou um elemento HTML cabeçalho gradient com texto "QUIZ - CULTURA DE ATUALIZAÇÃO..." mas dimensionou para `h=700` (para cobrir a área do slide canvas no editor). No Single Page, isso renderizava como um bloco gigante violeta-rosa de ~700px com o texto perdido no meio. Mesmo problema afetava Cenários, abertura de seções, etc.
  - **Causa**: o fix anterior usava `el.height` do banco. Quando o autor oversize'a um header (700px), respeitamos a altura — mas o conteúdo é estruturalmente um header thin.
  - **Fix**: novo helper `_looks_like_header_bar(html)` aplica heurística em 3 etapas — só dispara se TODAS forem verdadeiras:
    1. Plain text < 200 chars (após strip de tags) — header bars são curtos
    2. `align-items:center` em algum estilo (típico de header flex)
    3. **Sem** tags hierárquicas: `<h1>-<h6>`, `<p>`, `<ul>`, `<ol>`, `<li>`, `<table>` — esses indicam body content
  - Quando a heurística retorna True, força `h = 60` independente do `el.height` autoral. Aplica naturalmente o left-justify override (já existente para `h<100`).
  - **Por que safe?**: o filtro de tags hierárquicas garante que body content com h2/p/ul (ex: "O Conceito de Recálculo Automático" com h=700) NÃO é detectado como header — preserva 700px. Texto longo (>200 chars) também escapa da heurística.
  - **Validado**: 54/54 testes (3 novos: `test_oversized_header_detected_and_capped_to_60`, `test_real_body_content_NOT_detected_as_header`, `test_header_with_long_text_NOT_capped`). Visual via Playwright em "Checkpoint: Impactos Estruturais": iframe header agora mostra `w=838 h=60` com texto "QUIZ - CULTURA DE ATUALIZAÇÃO E IMPACTOS ESTRUTURAIS" alinhado à esquerda e visível na íntegra. Antes era um bloco de 700px.

- 2026-04-29: FIX (P0 visual follow-up 2) — Texto cortado em headers thin (60px) por causa de `margin-left:auto` autoral.
  - **Bug do usuário (screenshot)**: o texto "Cultura de Atualização e Impactos Estruturais" aparecia como "Cultura de Atualização e Impactos Estrutur..." — cortado pela direita. Causa: o HTML autoral usava `margin-left:auto` em um `<span>` para alinhar à direita do **slide canvas original**, mas o iframe Single Page é mais estreito que esse canvas, então o texto estourava o lado direito. Como agora temos `overflow:hidden` (do fix anterior), o estouro = corte invisível.
  - **Fix**: para iframes thin (`0 < h < 100`, tipicamente headers de 60px), `_render_html_element_inner` agora injeta CSS adicional que:
    - `body>div, body { justify-content:flex-start !important; text-align:left !important }` (força flex-row a iniciar à esquerda)
    - `[style*="margin-left:auto"], [style*="margin-left: auto"] { margin-left:0 !important }` (neutraliza inline `margin-left:auto`)
    - `span,div,p { white-space:nowrap; overflow:visible }` (texto não quebra em multi-linha dentro do header thin)
  - **Por que só thin?**: o reset agressivo de `margin-left:auto` quebraria layouts intencionais (e.g. paginação justificada à direita, badges). Aplicar só para `h < 100` preserva intenção autoral em conteúdos médios/grandes.
  - **Validado**: 51/51 testes (2 novos: `test_thin_header_left_justify_override` confirma override em h=60, `test_normal_height_iframe_does_NOT_left_align_override` confirma que h=400 NÃO recebe override). Visual via Playwright em "Gestão de Progresso": header gradient agora mostra "Cultura de Atualização e Impactos Estruturais" **completo**, alinhado à esquerda, sem corte.

- 2026-04-29: FIX (P0 visual follow-up) — Iframes thin (60px) ainda mostravam scrollbar dentro do iframe.
  - **Bug**: depois do fix de altura autoral, o iframe respeitava 60px corretamente, mas o `<body>` dentro do iframe tinha `margin:8px` default do navegador. Conteúdo `height:100%` + 8px de margem extrapolava os 60px → scrollbar horizontal/vertical apareciam consumindo metade do espaço útil.
  - **Fix**: `_render_html_element_inner` agora prepende `<style>html,body{margin:0;padding:0;height:100%;overflow:hidden;box-sizing:border-box}*{box-sizing:border-box}</style>` antes do conteúdo do usuário (apenas para iframes com global styles, base64 payload). Reset universal sem perturbar o conteúdo autoral.
  - **Validado**: 49/49 testes (1 novo `test_iframe_reset_css_injected_to_kill_scrollbars`). Visual via Playwright em "Gestão de Progresso" — header gradient agora aparece como **uma linha limpa de 60px sem scrollbar**.

- 2026-04-29: FIX (P0 visual) — Iframes HTML do tipo "header" não respeitavam altura autoral, virando blocos gigantes no Single Page export.
  - **Bug do usuário (screenshot)**: o usuário criou um elemento HTML de **50px** de altura (barra horizontal de gradient violeta-rosa) no editor para servir de cabeçalho da slide. No export Single Page, essa mesma barra renderizava como um **bloco de ~700px** sem nenhum motivo, ocupando toda a viewport e empurrando o conteúdo real para baixo.
  - **Causa raiz**: `_render_html_element_inner` em `single_page_exporter.py` (linha 290) tinha `style="...min-height:540px..."` **hardcoded** para TODOS os iframes, ignorando completamente `el.get("height")` salvo no documento do elemento (que vai de 8px a 864px nos projetos reais).
  - **Fix**: agora a função lê `el.height` e gera `height:Npx` (não `min-height`) com clamping seguro:
    - `height >= 60` → usa o valor literal (até teto de 720px para evitar scrolls gigantes).
    - `0 < height < 60` → eleva para 60px (visibilidade/clicabilidade mínima).
    - `height <= 0` ou ausente/inválido → fallback `min-height:540px` (comportamento original).
  - **Validado**: 79/79 testes (7 novos `test_singlepage_html_iframe_height.py` cobrindo: thin header 60px, clamp UP de tiny→60, clamp DOWN de 1080→720, height normal pass-through, fallback quando ausente/zero/inválido). Visual confirmado via Playwright em "Gestão de Progresso" (slide "O Conceito de Recálculo Automático"): iframe header bounding box `w=838 h=60` — exatamente uma linha de cabeçalho. Outros iframes do mesmo projeto: 60px (3 headers), 700px (4 corpos), 720px (1 clamped do 1080).

- 2026-04-29: FEATURE (P1) — Botão "🤖 Pedir explicação detalhada ao Tutor IA" no Quiz após resposta errada (Single Page + Tradicional).
  - **Bug do usuário**: a integração Tutor IA + Cenários estava completa, mas o aluno errar no Quiz NÃO oferecia ajuda do tutor — gap de paridade pedagógica.
  - **Fix Single Page**: dentro do callback de submit do quiz (em `single_page_exporter.py` `_JS`), após calcular `isCorrect` por questão, se `!isCorrect && window.AiTutor`: cria botão `.sp-quiz-tutor` violeta (gradient) anexado ao `<fieldset>`. Click → abre o tutor + pré-preenche prompt contextual: "Em um quiz, a pergunta foi: '...'. Eu respondi: '...' (errei). A resposta correta era: '...'. A explicação curta diz: '...'. Pode me explicar de forma mais detalhada por que minha resposta está incorreta e o raciocínio para chegar na resposta certa?". Suporta `q.options` como string OU `{text, correct}` object.
  - **Fix Tradicional**: `quiz-controller.js` ganhou função pública `QuizController.askTutor(elementId, questionId)` exposta no return. Botão renderizado no `renderQuestion → showingFeedback` quando `!wasCorrect && window.AiTutor`. Mesma lógica de prompt usando `question.alternatives` (estrutura do quiz tradicional).
  - **Decisão UX**: NÃO foi adicionado botão "💡 Pedir dica" ANTES do submit do quiz — isso seria essencialmente "me dê a resposta" (fraude pedagógica). Diferente dos cenários que são reflexivos/CYOA, o quiz é avaliativo: ajuda só faz sentido após erro.
  - **Toggle opcional**: respeita admin `settings.tutor.enabled`. Sem tutor → botão simplesmente não renderiza (conditional `window.AiTutor`).
  - **Validado**: 72/72 testes (2 novos: `test_quiz_wrong_answer_offers_tutor_explanation` + `test_traditional_quiz_controller_has_tutor_button`). Visual via Playwright em curso "Como Combater o Assédio" (15 questões): aluno marca tudo errado → 13 botões violetas de "Pedir explicação detalhada ao Tutor IA" aparecem (apenas nas erradas, as 2 corretas não), click abre painel do tutor com prompt completo serializado (pergunta + minha resposta + correta + explicação curta).

- 2026-04-29: FIX (P0 visual) — FAB do Tutor IA colidia com o chevron de avanço no Single Page export.
  - **Bug do usuário (screenshot)**: o FAB violeta do Tutor IA (`.tutor-fab`, `right:24px`) caía exatamente sobre o chevron amarelo `.sp-next-btn` (também `right:18px`), tornando impossível clicar no avanço sem clicar acidentalmente no tutor.
  - **Fix**: dentro do bloco `tutor_style` em `_BUILD_PAGE` (só injetado quando `tutor_config.enabled=true`), adicionada CSS override que move o FAB para o canto inferior **esquerdo** em Single Page: `.tutor-fab{left:24px !important;right:auto !important}` + mesmo para `.tutor-panel`. Mobile (≤480px) usa `left:16px` e o painel ocupa fullscreen.
  - **Por que dentro do tutor_style e não no CSS principal?**: cursos exportados sem tutor não devem ter referências a `.tutor-fab` no DOM/CSS (mantém o output limpo + faz os testes de "tutor desabilitado" continuarem válidos).
  - **Validado**: 52/52 testes (2 novos: `test_tutor_fab_position_override_when_enabled` + `test_tutor_position_override_NOT_present_when_disabled`). Visual via Playwright: FAB x=24, NEXT x=1846 — sem colisão.

- 2026-04-29: FEATURE (P1) — Integração do Tutor IA dentro dos Cenários de Aprendizagem (Single Page + Tradicional).
  - **Bug do usuário**: cenários CYOA no export Single Page não tinham conexão com o Tutor IA. Mesmo o widget de tutor (FAB+chat) sequer era carregado no Single Page (parâmetro `tutor_config` existia em `generate_single_page_html` mas era ignorado).
  - **Fix — Etapa 1: Tutor IA wired no Single Page**:
    - `_BUILD_PAGE` agora aceita `tutor_config` e, quando `enabled=true`, injeta inline `tutor.css` (`<style data-tutor-css="1">`), `tutor.js` (engine) + `window.TUTOR_CONFIG = {...}` + `AiTutor.init(...)` em DOMContentLoaded. Força `cssInlined=true` para o widget não tentar buscar `styles/tutor.css` (que não existe no Single Page standalone).
    - `routes/export.py` (rota HTML) já carregava `tutor_settings` do admin → agora repassa para `generate_single_page_html(tutor_config=tutor_settings)`. Mesma lógica para SCORM.
  - **Fix — Etapa 2: Botão "💡 Pedir dica" em cada nó do cenário (Single Page)**:
    - JS engine de cenário (`renderNode → choices`) renderiza condicionalmente `<button class="sp-scenario-hint">` se `window.AiTutor` existe.
    - Click → abre o tutor (`AiTutor.toggle()`) e pré-preenche o input com prompt contextual: título do cenário, título do nó, narrativa truncada (400 chars), opções enumeradas. Termina com `(não me dê a resposta direta)` — preserva o aprendizado pedagógico.
  - **Fix — Etapa 3: Botão proativo "🤖 Quer entender melhor?" após escolha sub-ótima**:
    - `showFeedback(choice)` injeta `<button class="sp-scenario-rescue">` somente quando `!choice.is_optimal && window.AiTutor`.
    - Helper `wireRescueBtn(choice)` chamado nos 2 caminhos (próximo nó existe + ending fallback).
    - Click → abre tutor e pré-preenche prompt explicando o erro: "escolhi X, sistema disse que não é a melhor escolha, feedback foi Y, pode me ajudar a entender por que essa decisão é problemática e quais princípios eu deveria considerar para escolher melhor?".
  - **Fix — Etapa 4: Mesma integração no export Tradicional**:
    - `scenario-controller.js` ganhou função pública `askTutor(elementId, mode, nodeId, choiceId)` (modo `hint` ou `rescue`).
    - Botão "💡 Pedir dica" adicionado em `renderNode` após as choices.
    - Botão "🤖 Quer entender melhor?" em `renderFeedback` quando `!choice.is_optimal`.
  - **Toggle opcional**: integração inteira respeita o admin toggle `settings.tutor.enabled`. Quando o admin desativa o tutor: (1) `tutor_settings` retorna `None` em `routes/export.py`, (2) engine `tutor.js` não é injetado, (3) os botões hint/rescue dependem de `window.AiTutor` (conditional), então simplesmente NÃO renderizam — sem código quebrado, sem UI fantasma.
  - **Validado**: 68/68 testes (9 novos `test_singlepage_tutor_in_scenarios.py` cobrindo: tutor inline quando enabled, NÃO injetado quando disabled/None, botão hint condicional em window.AiTutor, botão rescue só em sub-ótimas, prompt serializado com contexto do nó, traditional scenario-controller também tem os botões + askTutor exposto). Visual confirmado via Playwright em projeto "Slides manuais" (cenário "A Jornada da Universidade Corporativa Digital"): botão "💡 Pedir dica do Tutor IA" aparece, click abre painel do tutor com input pré-preenchido com prompt contextual completo do nó "O Desafio Inicial: Digitalizando a UC".

- 2026-04-28: FIX (P0) — Gamificação não disparava em Single Page export (HTML + SCORM).
  - **Causa raiz**: `routes/export.py` carregava `gamification_settings` mas só passava para o exporter SCORM tradicional. O SCORM single-page e o HTML single-page recebiam os dados mas NUNCA os repassavam para `generate_single_page_html()` ou `export_single_page_scorm_package()`. O `gamification.js` engine + `Gamification.init()` simplesmente não eram injetados no HTML resultante. Resultado: toggles "Mostrar após Quiz", "Mostrar após Cenário", "Resumo Final" e badges configurados no painel de Gamificação ficavam invisíveis ao aluno.
  - **Fix**:
    - `generate_single_page_html()` ganhou parâmetro `gamification_config: Optional[dict]`. Quando enabled=true, injeta inline o conteúdo de `services/export_assets/gamification.js` + `window.GAMIFICATION_CONFIG = {...}` + `Gamification.init(...)` em DOMContentLoaded.
    - 3 hooks adicionados ao JS runtime do single page (com feature-detection `if (window.Gamification)`):
      1. `onQuizComplete(pct, total, correct)` chamado depois do submit do quiz (`SP.markClicked` no fim de `submit.click()`).
      2. `onScenarioComplete(pct, scenarioTitle)` chamado nos 2 caminhos de fim de cenário (ending node oficial + fallback sem next_node_id). Título capturado via `.sp-scenario-title` (classe nova adicionada ao `<h3>` do scenario intro).
      3. `onCourseComplete()` chamado em `SP.advance()` quando alcança end-card (junto com `scormMarkComplete`).
    - `export_single_page_scorm_package()` repassa `gamification_config` para o gerador HTML.
    - `routes/export.py` (rota HTML single-page) agora carrega o config (mesmo fallback `DEFAULT_BADGES`/`DEFAULT_QUIZ_FEEDBACK`/`DEFAULT_SCENARIO_FEEDBACK` do SCORM) e passa para o gerador.
    - `routes/export.py` (rota SCORM single-page) passa `gamification_config=gamification_settings` que já era carregado.
  - **Validado**: 59/59 testes (8 novos `test_singlepage_gamification.py` cobrindo: engine inline quando enabled, hooks presentes mesmo sem engine, NÃO injetado quando disabled/None, SCORM ZIP contém engine, badges JSON serializado). Visual confirmado via Playwright em "Imagens_WideScreen": 
    - `Gamification.onQuizComplete(100, 5, 5)` → modal "🎉 Excelente! 100%" + 2 badges (Mestre dos Quizzes + Perfeição Total).
    - `Gamification.onScenarioComplete(85, "...")` → modal de feedback do cenário.
    - `Gamification.onCourseComplete()` → modal "🎓 Curso Concluído!" + badge "Curso Concluído".

- 2026-04-28: FIX (P0 visual) — Avatares HeyGen com fundo transparente no Single Page export.
  - **Causa raiz**: `_render_video_element_inner` aplicava `class="sp-video sp-interactive"` para QUALQUER vídeo, independente da origem. CSS `.sp-video video { background:#000 }` + `.sp-interactive { background:#fef9c3 }` (card amarelo) faziam o avatar HeyGen aparecer dentro de uma caixa amarela com fundo preto — destoando do fundo do slide. A função `_render_avatar_element_inner` (criada com tratamento transparente) era código morto: nenhum projeto tem `type=avatar` — todos os HeyGens entram como `type=video` com `src` apontando para `heygen.ai`.
  - **Fix**:
    - Novo helper `_is_heygen_avatar_url(url)` detecta URLs contendo `heygen` (case-insensitive).
    - `_render_video_element_inner` agora roteia URLs HeyGen para `<div class="sp-avatar-wrap">` (sem classe `sp-interactive`, com `background:transparent` inline + CSS dedicada `.sp-avatar-wrap video{background:transparent !important}`).
    - Vídeos NÃO-HeyGen (YouTube, MP4 customizados, etc.) mantêm o card amarelo `.sp-video sp-interactive` original — o gating pedagógico continua funcionando.
    - Seletor de gating mudou de `.sp-interactive[data-required="true"]` para `[data-required="true"]` — assim o `.sp-avatar-wrap` (que NÃO usa `sp-interactive`) ainda bloqueia o avanço da seção até o usuário reproduzir o vídeo. `markPlayed` e `data-completed="true"` continuam funcionando em ambos os casos.
    - CSS adicional para `.sp-avatar-wrap[data-completed="true"]::after` exibe checkmark verde quando avatar é assistido (mesmo padrão visual do `.sp-interactive`).
  - **Validado**: 51/51 testes (5 novos `test_singlepage_avatar_transparency.py` cobrindo: detecção HeyGen, render como avatar-wrap, fallback para vídeos não-HeyGen, CSS transparency presente no export, gating selector relaxado). Visual confirmado via Playwright em projeto real "Imagens_WideScreen" (5 avatares HeyGen): `wrap bg: rgba(0,0,0,0)`, `video bg: rgba(0,0,0,0)`, avatar misturando perfeitamente com slide background image laranja.

- 2026-04-28: FEATURE — Cenários de Aprendizagem agora rodam de forma interativa no Página Única.
  - **Bug do usuário**: cenários (gerados pelo "Criador de Cenários de Aprendizagem" via IA) só mostravam título/descrição/personagens com botão genérico "Marcar como concluído". A estrutura rica de `nodes[]` com `choices[]`, `feedback`, `is_optimal`, `points`, `next_node_id` (Choose Your Own Adventure educacional) era ignorada.
  - **Fix**:
    - `_render_scenario_element_inner` serializa `nodes`, `choices`, `feedback`, `is_optimal`, `points`, `next_node_id`, `is_ending`, `ending_type`, `score`, `character_speaking` em `data-scenario` (HTML-escaped JSON).
    - Renderização inicial mostra título + descrição + contexto + personagens + botão **"▶ Iniciar Cenário Interativo"**.
    - Novo `SP.startScenario(scenarioEl)` no JS runtime: navega o grafo de nós, renderiza narrativa + character_speaking + choices clicáveis numeradas, processa feedback colorido (verde para `is_optimal`, vermelho para sub-óptimas), aplica points, e segue `next_node_id`. Ao chegar em `is_ending`, mostra banner final colorido (verde/vermelho/azul conforme `ending_type`) com score `(pts/maxPts %)` e botão para liberar próxima seção.
    - Cenários SEM `nodes` mantêm fallback "Marcar como concluído ✓".
    - Score do cenário entra no `quizScores` interno e é reportado via SCORM `cmi.core.score` agregado.
  - **Bug colateral corrigido**: aspas simples literais dentro do JS template (`closest('.sp-scenario')`) quebravam parsing. Trocado por `&quot;` HTML-encoded (browser decodifica antes do parse).
  - **Validado**: 40/40 testes (5 novos `test_scenario_interactive.py`). Visual confirmado via Playwright em curso real "Liderança de Impacto" — 3 cenários rodando, choices clicáveis, feedback exibido com pontos, navegação entre nós funcionando.


  - **Decisão do usuário**: o canvas absoluto preservava layout pixel-perfect do editor, mas ficou inconsistente para Página Única (que é vertical-scroll, não slide-by-slide). Preferência foi voltar ao look A4 com elementos empilhados.
  - **Mantido**: bg per-slide com auto `_is_dark_color` (texto auto-claro em fundos escuros), feedback colorido nos quizzes, charset utf-8 nos iframes, botão "✓ Concluí" para iframes sandbox, render rico de scenarios (título + contexto + personagens), normalização de quiz options.
  - **Constraints novos para evitar elementos gigantes**:
    - `.sp-video, .sp-audio { max-width: 720px; margin: 0 auto }` — vídeo/áudio centralizado e limitado a 720px de largura
    - `.sp-video video { max-height: 480px }` — vídeo cabe sem dominar a tela
    - `.sp-image img { max-height: 540px }` — imagens grandes do editor agora são limitadas
    - `.sp-section-body > * { max-width: 880px }` — todos os blocos respeitam largura máxima legível
    - Elementos `avatar` com `videoUrl` viram player; com `imageUrl` vira figure de até 320px
  - **Validado**: 40/40 testes (1 novo `test_video_element_has_max_width_constraint`).


  - **Bug 1 (mojibake)**: iframes sandbox geravam URL `data:text/html;base64,...` sem declarar charset. Browsers caem em Latin-1 por default → `Inspeção` virava `InspeÃ§Ã£o`, `✅` virava `âœ…`, etc. **Fix**: `data:text/html;charset=utf-8;base64,...` + `<meta charset="utf-8">` injetado no início do htmlContent quando ausente.
  - **Bug 2 (texto branco em card branco)**: o editor permite ao autor definir `color: #fff` em textos de slides com fundo escuro. No Página Única, eu colocava o `slide.background` na `<section>` (apenas margens externas) e mantinha o card sempre branco → textos brancos do editor ficavam invisíveis sobre o card. **Fix**: a cor `slide.background` agora é aplicada ao **`.sp-section-inner`** (o card central), não na `<section>`. Função utilitária `_is_dark_color()` (luminância WCAG) adiciona classe `sp-dark` quando o BG é escuro, que troca cor padrão de texto para `#f1f5f9` e título para `#fde047` (amarelo). Slides claros mantêm o look A4 branco padrão.
  - **Validado**: 39/39 testes (1 novo `test_iframe_data_uri_declares_utf8_charset_for_accents`). Visual confirmado em 2 viewports — capa NR35 escura com texto amarelo/branco perfeitamente legível, slides claros mantêm card branco, todos os acentos `á è ã í` e emojis `✅ ❌ 🔎` renderizam corretamente.


  - **Quiz visual feedback** após submit: cada opção muda de cor — **verde** marca a correta com badge "✓ Correta"; **vermelho** marca a opção errada do aluno com "✗ Sua resposta". Explicações exibidas em caixa azul "💡 Explicação" abaixo de cada questão. Banner final: 🎉 verde se ≥80%, vermelho se <80%.
  - **Backgrounds per-slide**: cada `<section>` recebe `style="background-color"` ou `background-image` da slide individual (`slide.background` + `slide.backgroundImage`). Antes só o primeiro slide.backgroundImage era usado como BG global.
  - **Painel interativo iframe**: botão explícito "✓ Concluí o simulador" abaixo de cada iframe sandbox (clicks dentro do iframe não fazem bubbling).
  - **Quiz JSON escape**: `data-questions` com `"` + `html.escape(quote=True)` para suportar apóstrofes nas perguntas.
  - **Validado**: 38/38 testes (3 novos `test_singlepage_bg_and_quiz_feedback.py`).

- 2026-04-28: FIX (P0 BUG VISUAL) — Página Única descentralizada (body=960px) por vazamento de CSS.
  - **Causa**: Simuladores/scenarios injetam `<style>body{display:flex;width:960px}` que vazava para o body do curso single-page.
  - **Fix**: `_render_html_element` detecta `<style>/<script>/<body>/<html>/<head>` e renderiza em iframe sandbox isolado. `.sp-section-inner` com `margin: 0 auto` e `max-width: 1080-1180px`. Interativos com borda amarela 3px + box-shadow pulsante + badges grandes destacados.


  - **Causa raiz**: Os simuladores/scenarios (campo `htmlContent`) trazem `<style>body{display:flex;width:960px;height:540px;...}</style>` próprio. Como o renderer single-page injetava esses HTMLs DIRETAMENTE no DOM da página, os 7+ blocos `<style>` faziam **vazamento de CSS global** — o `<body>` do curso herdava `display:flex; width:960px`, encolhendo tudo para a esquerda.
  - **Fix**: (1) `_render_html_element` detecta tags globais (`<style>`, `<script>`, `<body>`, `<html>`, `<head>`) no `htmlContent` e renderiza em `<iframe sandbox>` via data-URI; (2) `.sp-section-inner` com `margin: 0 auto` (mais resiliente que flex parent); (3) interativos com borda amarela 3px + box-shadow pulsante + badge "▶ ASSISTA/CLIQUE PARA LIBERAR" muito visível; (4) max-width aumentado para 1080-1180px; (5) title centralizado.
  - **Validado** em 1920px e 1280px via Playwright: card centralizado (370px e 100px de espaço respectivamente). 30/30 testes.

- 2026-04-28: FIX (P0 BUG INFRA) — Erro 500 ao exportar SCORM Página Única (No space left on device).
  - **Causa raiz**: GridFS `exports.chunks` acumulou 4.65 GB de exports antigos (165 arquivos de 24h+). Disco em 100%.
  - **Fix**: limpeza imediata via mongosh `compact` (4.3 GB liberados) + nova função `cleanup_old_gridfs_exports(24h)` chamada em background a cada export para prevenir recorrência.

- 2026-04-28: FIX (P0 BUG) — SCORM Página Única rejeitado por LMS estritos (Canvas/Blackboard/SCORM Cloud).
  - **Causa raiz**: Identifier com hífens, `scorm-api.js` na raiz (não em `scripts/`), title sem escape de aspas/apóstrofo.
  - **Fix**: identifier sanitizado (hífens → underscore), `scripts/scorm-api.js` (convenção do tradicional), title escapa `& < > " '`.


  - **Causa raiz**: ZIP single-page tinha 3 problemas estruturais que o LMS tradicional aceita mas LMS estritos rejeitam:
    1. **`identifier="SCORM_SP_<uuid>"`** com hífens — alguns LMS exigem XML NCName estrito (`[A-Za-z_][A-Za-z0-9._]*`)
    2. **`scorm-api.js` na raiz** ao invés de `scripts/scorm-api.js` (convenção do exporter tradicional, esperada por LMS antigos)
    3. **Title sem escape de aspas/apóstrofo** (`&quot;`/`&apos;`) — quebra o XML em projetos com nomes contendo `"` ou `'`
  - **Fix**:
    1. `safe_identifier = "SCORM_SP_" + re.sub(r"[^A-Za-z0-9_]", "_", project_id)` — substitui hífens por underscore
    2. `scorm-api.js` movido para `scripts/scorm-api.js`; `<script src>` no HTML ajustado
    3. Title escapa `&`, `<`, `>`, `"`, `'` para `&amp;`/`&lt;`/`&gt;`/`&quot;`/`&apos;`
  - **Validado**: 43/43 testes (9 estruturais novos `test_scorm_singlepage_structure.py` + 6 E2E + 5 single-page HTML + 5 retry + 8 async + 10 element units). Estrutura agora alinha-se ao tradicional que o LMS aceita.

- 2026-04-28: FIX (P0 BUG) — Toggle "Página Única" não persistia.
  - **Causa raiz**: `ExportDialog.jsx` usava `fetch()` direto que NÃO passa pelo `axios.interceptors` que injeta `Authorization: Bearer`. PUT retornava 401/403, `fetchProject()` falhava silenciosamente, toggle voltava ao default.
  - **Fix**: trocado `fetch()` por `axios.put()` em ambos os toggles (Página Única + VLibras).

- 2026-04-28: FIX (P0 BUG) — Erro 500 ao exportar SCORM em projetos com `fontSize: "24px"` (string com unidade CSS).
  - **Causa raiz**: `ElementStyle.fontSize` declarado como `Optional[float]` rejeitava strings tipo `"24px"`.
  - **Fix**: `parse_numeric_with_unit` (`@field_validator(mode='before')`) aceita CSS units.

- 2026-04-28: FEATURE (P1) — Modo "Página Única" para SCORM 1.2 (Fase 2 de 2).
  - **Causa raiz**: O endpoint `/api/course/{id}/export-scorm` (e o auto-save do editor via `PUT /api/projects/{id}/slides/{id}/elements/{id}`) parseava o documento via `Project(**project_doc)`. O `ElementStyle.fontSize` era declarado como `Optional[float]` mas o frontend enviava strings tipo `"24px"`, `"1.5rem"` (CSS-style values), causando `pydantic_core._pydantic_core.ValidationError: Input should be a valid number`. Erros 500 em cascata: ProjectContext.jsx mostrava "AxiosError" no console F12, e o usuário não conseguia exportar.
  - **Fix**: estendido `ElementStyle.parse_numeric_with_unit` (`@field_validator(mode='before')`) para `fontSize`, `strokeWidth`, `borderRadius` — extrai o número via regex `^\s*([+-]?[\d.]+)` e descarta a unidade. Resolve o problema na RAIZ (todos os endpoints que parseiam Project agora aceitam strings com unidade).
  - **Refactor preventivo**: `/export-scorm` agora coleta `question_ids` direto do dict cru (sem precisar parsear Project) e só constrói `Project(**project_doc)` no caminho legacy slide-by-slide. O caminho single-page nunca usa Project Pydantic — usa o dict puro.
  - **Validado**: 10/10 testes em `test_element_style_units.py` (fontSize px/rem/pt/negativo/empty/invalid + ElementUpdate + full Project parse com o cenário exato do bug). Curl E2E confirmou os 3 cenários funcionando no projeto NR35 (id `6e5e065d-22f0-4322-b35b-8aa7ca70f05f`) que tinha o bug: SCORM single-page ✓, SCORM tradicional ✓, HTML single-page ✓.
  - **Bônus**: corrigido bug pré-existente onde o tradicional SCORM crashava na mesma condição.

- 2026-04-28: FEATURE (P1) — Modo "Página Única" para SCORM 1.2 (Fase 2 de 2).
  - Novo módulo `services/scorm_single_page_exporter.py`: empacota o HTML single-page (Fase 1) num ZIP SCORM 1.2 com manifest + 4 XSDs + scorm-api.js.
  - **`scorm-api.js`** (bridge para LMS): `findAPI` walker até 500 levels; expõe `window.SCORM` com init, setLocation, saveSuspend, getSuspend, recordInteraction, setScore, complete, commit, finish.
  - **JS runtime atualizado**: `scorm_mode=true` injeta hooks que disparam em pontos chave:
    - **Avanço de seção** → `cmi.core.lesson_location` + `cmi.suspend_data` (JSON com unlocked + completed + quizScores + currentIndex) + `LMSCommit`
    - **Quiz respondido** → `cmi.interactions.{n}.id/type/student_response/result/description/time` + `cmi.core.score.raw/max/min` (running pct)
    - **End-card alcançado** → `cmi.core.lesson_status="passed"` se todos clicáveis OK + quizzes ≥80%, senão `"completed"`
    - **beforeunload** → `LMSCommit + LMSFinish`
  - **Resume**: ao carregar, lê `cmi.suspend_data`, restaura unlocked sections + completed interactives + quiz scores + scrolla para `lesson_location`.
  - **Endpoint `/api/course/{id}/export-scorm`** aceita `{singlePage: bool}` no body, sobrescreve `project.singlePageMode`. Retorna `{mode, downloadUrl, jobId}`.
  - **Frontend**: `ProjectContext.exportScorm({singlePage})` + `useEditorExport.handleExport` lê `currentProject.singlePageMode`. Toast indica modo.
  - **Bug corrigido durante implementação**: `SP.advance()` chamava `unlockSection()` ANTES de atualizar `state.currentIndex`, fazendo o SCORM salvar a localização ANTIGA. Reordenado: `state.currentIndex = nextIdx` PRIMEIRO. Regressão coberta por `test_e2e_lms_initialize_and_lesson_status`.
  - **Robustez**: `_cleanup_old_exports` agora aplica DUPLA política — idade (24h) + cap de tamanho total (5GB) — para evitar disco cheio em produção.
  - **Validado**: 15/15 testes (9 API + 6 E2E real-browser com mock LMS) iteration_114. 23/23 testes single-page total (HTML + SCORM + apply-improvements).

- 2026-04-28: FEATURE (P0) — Modo "Página Única" (scroll vertical / scrollytelling) para export HTML.
  - Inspirado em Articulate Rise: header preto fixo + título à direita + hambúrguer à esquerda + barra de progresso amarela; cards brancos A4 sobre fundo azul-rede; botão amarelo redondo no canto inferior direito que SÓ aparece quando todos os elementos clicáveis da seção atual foram concluídos (gating pedagógico).
  - **Backend** (`services/single_page_exporter.py` 741 linhas): renderer auto-contido (HTML+CSS+JS); detecta interativos (audio onplay, video onplay, html-com-onclick, quiz, scenario, simulator); cada slide vira `<section data-locked="true">` com unlock progressivo; drawer linear-estrito.
  - **Endpoint**: `POST /api/course/{id}/export-html` aceita body `{singlePage: bool}` que sobrescreve `project.singlePageMode`. Retorna `{mode, filename}`.
  - **Preview inline**: `GET /api/exports/{filename}?preview=1` agora serve `text/html` sem `Content-Disposition: attachment`.
  - **Project model**: `singlePageMode: bool = False` + `ProjectUpdate.singlePageMode`.
  - **Frontend**: novo Switch controlado `single-page-toggle` no `ExportDialog`; `useEditorExport.handleExportHTML` envia `{singlePage}`.
  - **Validado**: 19/19 testes (5 baseline + 14 extended) iteration_113.
  - **Próxima fase (P1)**: SCORM 1.2 single-page com `cmi.completion_status` e `cmi.location` resume.

- 2026-04-28: FIX (P0) — Conclusão do refactor async de POST /api/agent/courses/{project_id}/apply-improvements (timeout 502). Removidas 340 linhas de código órfão (SyntaxError). Endpoint retorna 202 + applyJobId; novo GET /apply-status/{job_id}; worker daemon com event loop dedicado; idempotência (mesmo jobId em clique duplo); preview preservado em falha; TTL index 24h em apply_jobs. Frontend faz polling 3s c/ progress bar violet→fuchsia. 13/13 testes passando (iteration_112).


  - PROBLEMA: aplicar melhorias do Agente IA executava sincronamente (Leonardo + Gemini + cenarios + avatares = 1-5min) e batia em timeout de 60s do Nginx, retornando 502 Bad Gateway. Refactor anterior havia comecado a converter para background mas foi interrompido mid-edit, deixando 340 linhas de codigo orfao com SyntaxError ('await outside async function' linha 3298). Backend so estava de pe porque uvicorn iniciou antes do save corrompido.
  - FIX BACKEND:
    - Removido codigo orfao (linhas 3288-3626) de routes/agent.py
    - Endpoint POST /apply-improvements agora retorna 202 imediatamente com {status: 'processing', applyJobId, startedAt} em <2s
    - Novo endpoint GET /api/agent/courses/{project_id}/apply-status/{job_id} para polling do progresso
    - Worker em thread daemon com event loop proprio + AsyncIOMotorClient dedicado executa _run_apply_improvements_bg (atualiza apply_jobs collection com progresso 0-100% + mensagem por etapa: snapshot → AI → slides → cenarios → Leonardo → Gemini → avatares)
    - Helper functions extraidas: _process_scenarios, _process_leonardo_images, _process_gemini_images, _attach_image_to_slide, _collect_avatar_scenes
    - Idempotencia: clicar Aplicar 2x retorna o MESMO applyJobId (busca processing job em andamento)
    - Retry-safe: preview so e deletado ao concluir com sucesso (preserva no MongoDB se algum passo falhar)
    - TTL index em apply_jobs.createdAtDate (auto-delete jobs apos 24h)
    - Index secundario em apply_jobs (projectId, status) para acelerar lookup de idempotencia
  - FIX FRONTEND:
    - handleConfirmImprovements (Agent.jsx) agora faz polling em /apply-status a cada 3s (max 10min)
    - Trata 401/403/404 como terminal (evita loop infinito em token expirado)
    - Novo estado applyProgress: {progress, message} renderizado como barra de progresso violet→fuchsia em PreviewPanel
    - Mensagem de chat enriquecida com counts de scenarios, Leonardo, Gemini, avatares
  - Validado: 13/13 testes (5 retry + 8 novos async-flow) iteration_112. Curl E2E confirmou POST <30ms, GET status retorna progresso ate done com canUndo=true.


  - PROBLEMA: a regra anterior obrigava `imagem_premium` (Leonardo, custo alto) para todo slide textual. O usuario reportou que nem sempre vale a pena pagar Leonardo — para a maioria dos slides uma imagem ilustrativa simples e mais barata ja resolve.
  - BACKEND: novo tipo `imagem_simples` (gerado via Gemini Nano Banana, parte do Emergent LLM Key — custo BAIXO). O prompt da IA agora prioriza `imagem_simples` para slides textuais comuns (>350 chars sem imagem) e reserva `imagem_premium` apenas para slides estrategicos (capa, abertura de modulo, conteudo emblematico).
  - Novo helper compartilhado /app/backend/services/gemini_image.py para gerar imagens via Gemini Nano Banana (extraido para reuso entre /api/ai/generate-image manual e o pipeline de improvements).
  - Pipeline de aplicacao em /app/backend/routes/agent.py agora processa AMBOS os tipos: campo `_leonardoImage` -> Leonardo, campo `_geminiImage` -> Gemini. Cada imagem gerada e persistida no MongoDB via store_asset_async, inserida no slide com layout duas colunas e auto-salva na galeria.
  - FRONTEND: novo chip de filtro "Imagem (econômica)" + cor pink dedicada. Toggle inline "↑ Trocar por premium" / "↓ Trocar por econômica" em cada sugestao de imagem permite ao usuario decidir caso-a-caso. Badge agora mostra "Gemini Nano Banana · Econômica" ou "Leonardo AI · Premium". setTypeOverrides permite trocar simples↔premium sem perder o `imagePrompt`.
- 2026-04-27: FEATURE - Filtros visuais por categoria nas sugestoes de melhoria.
- 2026-04-25: P2 - RBAC + refatoracao agent.py
  - SECURITY: 11 endpoints de /api/agent/courses/{id}/* e /api/agent/projects/{id}/* agora exigem `require_auth + load_authorized_project`. Antes: anonimo podia chamar /analyze, /preview-improvements, /apply-improvements, /undo-improvements, /heygen-status, /generate-narration, /narration-status, /avatar-settings GET+PUT, /avatar-generation-status. Agora: anonimo -> 401, cross-company -> 404. Validado por 43 novos testes em test_agent_rbac_p2.py.
  - REFACTOR: extraidas 5 rotas de approval (get_approval_queue, submit_improvements_for_approval, approve_improvement, reject_improvement, clear_stuck_caches) de routes/agent.py para novo routes/agent_approvals.py (446 linhas focadas no fluxo aprovador/company_admin -> aprovacao). agent.py reduziu de 4099 -> 3753 linhas (-346). Lazy import de `_apply_ai_result_to_slides` evita ciclo. server.py registra novo router.
  - TOTAL: 119/119 testes RBAC + retry passing (43 novos + 76 regressao). iteration_111. Zero regressao.
- 2026-04-24: FEATURE - Dashboard de "Saude das Integracoes" no Admin (super_admin only). Nova aba `Integracoes` com ping em tempo real para MongoDB, Emergent LLM, Leonardo AI, HeyGen, ElevenLabs, Resend e ConvertAPI. Cards mostram status (OK/Erro/Nao configurado), latencia em ms e saldo/creditos disponiveis quando aplicavel (Leonardo tokens, ElevenLabs chars, HeyGen quota, ConvertAPI segundos). Cache de 60s server-side para economizar chamadas; auto-refresh a cada 60s no frontend; botao "Atualizar agora" que invalida o cache via query param. Backend: novo /api/admin/integrations-health em routes/health.py (403 para non-super, checks em paralelo via asyncio.gather). Frontend: /app/frontend/src/pages/IntegrationsHealthPanel.jsx. Validado: todos os 7 services retornam OK no preview, RBAC 401/403/200 funcionando.
- 2026-04-24: FEATURE - Endpoint /api/health adicionado em routes/health.py. Retorna `{"status":"ok"}` em <5ms sem tocar MongoDB ou qualquer integracao externa. Pronto para uso como K8s readinessProbe/livenessProbe — evita que o orquestrador roteie trafego para pods que ainda estao terminando o cold-start. Complementa os /health, /healthz, /ready existentes (sem prefix /api).
- 2026-04-24: FIX (DEPLOYMENT) - Startup do backend produzia janela de ~40s onde nginx retornava 502 "Connection refused" apos cada deploy. Root cause: 2 handlers de `@app.on_event("startup")` estavam awaitando operacoes MongoDB que demoram no Atlas (especialmente `create_index` + aggregate de deduplicacao + sequential update_many na migracao de roles). Fix: movidos `startup_create_indexes` e `startup_migrate_roles` para `asyncio.create_task` (pattern ja usado em migrate_urls, admin_check, ppt_recovery, asset_sync). Startup local caiu de 4-6s para <10ms. Em producao (Atlas) a janela de 502s desaparece pois uvicorn aceita conexoes imediatamente e as migrations rodam em background sem bloquear o HTTP server. Validado: 76/76 testes RBAC + retry passing.
- 2026-04-24: FIX - Geracao de imagens Leonardo AI no preview. Root cause: `LEONARDO_API_KEY` no `/app/backend/.env` do preview estava com valor invalido (`ai-tutor-platform-12` — um pedaco do hostname). Leonardo retornava HTTP 500 `"Invalid response from authorization hook"`. NAO foi causado pelos refactors RBAC recentes (leonardo.py / .env nao foram tocados). Correcao: (1) criada nova chave `SCORMIFY-preview` na conta Leonardo do usuario; (2) chave atualizada apenas no .env do preview (producao mantem sua propria chave, independente); (3) adicionado logging detalhado do body de erro em `services/leonardo_ai.py` + deteccao do erro de auth com mensagem clara em pt-BR para diagnosticar problemas futuros mais rapido. Tambem corrigido `AttributeError: 'str' object has no attribute 'get'` em `agent.py:2888` adicionando `isinstance(x, dict)` em 4 loops de `updatedSlides`/`newSlides` para evitar crash 500 quando a IA retorna itens malformados. Validado E2E: geracao Leonardo concluida com URL da imagem retornada.
- 2026-04-24: FIX (P1 BUG) - "Erro ao aplicar melhorias" no Agente IA em producao. Root cause: o cache `improvement_previews` era deletado IMEDIATAMENTE apos ser lido em apply-improvements (linha 2780 do agente). Se o passo seguinte de aplicacao falhasse (Leonardo AI, scenario gen, avatar scene, etc), o preview ja nao existia mais e o retry do usuario resultava em 400 "Preview expired or not found". Fix: mover o `delete_one` para DEPOIS de todo o trabalho critico concluir com sucesso (antes do `return`). Se qualquer passo falhar, o preview permanece e o usuario pode reclicar "Confirmar e Aplicar" sem refazer a analise da IA. Tambem adicionado try/except com traceback em `apply_course_improvements` e `_apply_ai_result_to_slides` para surfacer a causa real de falhas futuras no log em vez de 500 opaco. Validado por /app/backend/tests/test_apply_improvements_retry.py (3 casos) + teste E2E manual com aiResult malformado provando que o preview fica preservado pos-falha.
- 2026-04-24: REFACTOR - Quebrado routes/projects.py (1502 linhas monoliticas) em 6 modulos focados:
  - routes/projects_common.py (199 linhas) - helpers compartilhados: can_access_project, load_authorized_project, process_ppt_upload
  - routes/projects_crud.py (651 linhas) - Project CRUD, Course get/save, Job status, PPT upload (init/chunk/complete/legacy), apply-design-template, fix-simulators
  - routes/projects_slides.py (273 linhas) - Slide CRUD + duplicate + reorder + normalize-dimensions + element CRUD
  - routes/projects_media.py (117 linhas) - upload de media com otimizacao de imagem
  - routes/projects_audio.py (250 linhas) - audio per-slide + global audio + volume + trim
  - routes/projects_annotations.py (86 linhas) - annotations CRUD
  Total: 1576 linhas em 6 arquivos (vs 1502 monolito). server.py registra os 5 novos routers. Zero impacto no contrato (todas as 176 rotas OpenAPI preservadas). Validado: 73/73 RBAC + 11/11 code-checks passing.
- 2026-04-24: REFACTOR - Consolidado o guard RBAC duplicado em 28 handlers de routes/projects.py numa helper unica `_load_authorized_project(project_id, user)`. Antes: 4 linhas repetidas por handler (28 x 4 = 112 linhas duplicadas com potencial de esquecer uma das checagens, como aconteceu em iteration_109). Agora: 1 linha por handler, impossivel esquecer a checagem de companyId. projects.py reduzido de 1622 -> 1502 linhas. Validado: 73/73 testes RBAC passing (test_rbac_subresources.py + test_rbac_projects_multitenancy.py).
- 2026-04-24: FIX (P0 SECURITY) - Multi-tenancy RBAC hardening no /api/projects e /api/agent/courses. Antes: Company Admin via TODOS os cursos (bug reportado pelo usuário) e 25+ endpoints de sub-recursos (slides/elements/media/audio/annotations) NAO tinham auth — qualquer request anonimo podia mutar cursos de qualquer empresa. Agora: require_auth + _can_access_project aplicado em 28 handlers (list_projects, get_project, create_project, update/delete_project, get_course, save_course, slides CRUD + duplicate + reorder + normalize_dimensions, elements CRUD, upload_media, global_audio CRUD + volume, slide_audio CRUD + volume + timing, annotations CRUD, apply_design_template, fix_simulators, PPT upload init/legacy, agent_list_courses). 53 projetos orfaos sem companyId foram migrados para company_didaxis001 via scripts/backfill_project_companies.py. Validado: super_admin ve tudo, users so veem cursos da propria empresa, acesso cross-company retorna 404. 73/73 testes RBAC passing (iteration_110, test_rbac_subresources.py + test_rbac_projects_multitenancy.py).
- 2026-04-24: REFACTOR - Rotas de PDF extraidas de routes/agent.py para novo routes/pdf_import.py. agent.py reduzido de 4842 -> 4067 linhas (-16%). Movidas: upload-chunk, pdf-preview (GET/POST), repair-pdf-images, generate-faithful-course, faithful-status + helpers (_PDF_EXTRACTION_TASKS, _background_pdf_extraction, _background_faithful_render, _page_hint_from_filename). Mesmos paths, mesmo contrato. Testado 100% backend (12/12 iteration_107) - 5 endpoints PDF + smoke tests de auth/projects/agent.
- 2026-04-24: FEATURE - "Remover Fundo" no Editor. Novo dialog RemoveBackgroundDialog com color-key 100% em browser (canvas): auto-deteccao da cor de fundo nos 4 cantos, eye-dropper pick, tolerancia + suavidade (feathering), upload do PNG transparente resultante via /api/projects/{id}/media. Botao aparece no painel de propriedades quando elemento tipo "image" esta selecionado.
- 2026-04-23: FEATURE - Modo Fiel (PDF → Slides): cada pagina do PDF vira 1 slide preservando layout/cores/imagens/logos originais. Pula IA e LLM completamente. Estrategia final apos varias iteracoes de performance:
  - Upload em chunks de 4MB (bypass limite Cloudflare)
  - Extracao automatica de imagens DESABILITADA (inconstante em producao com Tesseract + 520 timeouts)
  - PDF salvo em GridFS imediatamente, frontend mostra CTA "Gerar em Modo Fiel" como caminho primario
  - Render em 1280x546 / DPI 110 / JPEG quality 80 (resolucao adequada, ~4x mais rapido que config original)
  - Background thread com event loop proprio + cliente Motor dedicado (nao compete com uvicorn)
  - `nice +10` na thread de renderizacao (OS prioriza event loop HTTP)
  - Cooldown 300ms entre paginas (cede CPU ao scheduler)
  - Endpoint `/faithful-status` com timeout MongoDB 5s e fallback soft (progress=-1)
  - Frontend tolerante a 520/502 transient durante polling (nao aborta)
  - Resultado: 45 paginas renderizam em ~20s em producao com pod 250m CPU, zero timeouts
- 2026-04-23: FEATURE - Preview Editorial de imagens extraidas de PDF (legado — ainda funciona, mas Modo Fiel e o caminho recomendado).
- 2026-04-23: FEATURE - Importação de PDF com OCR (modo normal — agora opcional via API se algum cliente precisar).
- 2026-04-22: BUGFIX - Imagens Leonardo AI sumindo em produção (persistência no MongoDB + remoção de fallback CDN expirado).
- 2026-04-22: BUGFIX - CORS Tutor IA para LMS externos (ASGI wrapper com reflect-origin).
- 2026-04-22: DEPLOY FIX - Removidas seções duplicadas em `.gitignore` bloqueando `.env`.
- 2026-03-29: FIX - Avatar scene HeyGen generation simplified.
- 2026-03-29: FIX - Manual HeyGen creation WebM fallback no longer blocks on voice incompatibility — gracefully falls back to v2
- 2026-03-29: REFACTOR - Editor.jsx reduced from ~3892 to ~2064 lines (47% reduction). 14 dialogs extracted to /pages/Editor/dialogs/
- 2026-03-29: FEATURE - Custom badge image upload for gamification (GamificationPanel + /api/gamification/upload-badge-image)
- 2026-03-28: CHANGE - HeyGen avatar videos now request transparent background (WebM) with fallback to standard
- 2026-03-28: CHANGE - Avatar scenes now use HeyGen voices (not ElevenLabs). Voice selector fetches from /api/heygen/voices. Default fallback is PT-BR
- 2026-03-28: BUGFIX - HeyGen voice ID mismatch (ElevenLabs ID passed to HeyGen). Now uses HeyGen native TTS
- 2026-03-28: BUGFIX - avatar-settings 404 on projects without avatarSceneSettings
- 2026-03-28: Avatar & Voice Selectors - HeyGen avatar + HeyGen voice dropdowns
- 2026-03-28: Inline script editor with char counter, background editor, position selector
- 2026-03-28: Avatar Scene Type Switcher + visual mockup preview
- 2026-03-28: Avatar Scene Suggestions feature + auto-generation on apply
- 2026-03-27: E2E Video Export verified (client-side html2canvas + MediaRecorder)

## Recent Fixes & Features
- 2026-03-29: FIX - Production 500 error on /api/auth/me resolved. Root cause: .gitignore was blocking .env files from deployment. Fixed .gitignore, .env files now tracked in git. Auth flow fully tested (11/11 backend tests pass, frontend login flow verified).
- 2026-03-30: FEATURE - Avatar & Voice Preview in Agent IA "Configurações de Avatar". Replaced dropdown selectors with visual avatar grid (thumbnails, 4 columns), large preview card with "Ver Animado" video toggle, voice list with play buttons for audio preview, and selected voice preview card with "Selecionada" badge. All tested 100% (iteration_90).
- 2026-03-30: FEATURE - "Testar Combinação" button generates a mini HeyGen test video with the selected avatar + voice combination. Backend POST /api/heygen/test-combination endpoint + frontend player with status polling. Tested 100% backend (5/5) + frontend (iteration_91).
- 2026-04-02: FEATURE - Integrated real scenario generation service into AI Agent improvements. When AI suggests 'scenario' type improvements, the system now: 1) Extracts scenarioConfig (theme, objectives, audience, complexity), 2) Calls generate_scenario_with_ai (same as manual "Criador de Cenários") to generate the real scenario tree with nodes/choices/endings, 3) Saves to db.scenarios collection, 4) Creates proper slide with type="scenario" element. All new improvement types (scenario, visual_summary, reinforcement) now fully integrated. Tested 100% frontend + 92% backend (iteration_98).
- 2026-03-30: FEATURE - Agent IA now analyzes ALL courses (imported PPT + agent-created). Expanded GET /api/agent/courses to return all 51 projects with 'source' field. CourseListPanel has filter tabs (Todos/Agente/Importados), visual badges (violet=Agente, green=Importado), distinct icons (Brain/Upload). Imported course analysis suggests simulators, jogos, avatares, narração. Tested 100% (iteration_92).
- 2026-03-30: FIX - Agent courses endpoint only showing agent-created courses in production. Root cause: fetching full documents caused timeout. Fixed with MongoDB aggregation pipeline ($project + $size). Response in 0.2s.
- 2026-03-30: FEATURE - Enhanced 'Alterar Texto' dialog: now includes Fonte (20 font options with preview text) and Tamanho do Texto (15 sizes) alongside Cor. Empty fields preserve current values. Preview shows 3 slides with applied styles. Tested 100% (iteration_94).
- 2026-03-31: FIX (P0) - 401 Unauthorized in Agent subcomponents in production. Added authHeaders() to ALL fetch calls in 5 files: GeneratedPanel.jsx, CoursePanels.jsx, ConfigPanel.jsx, MediaConfigPanel.jsx, StoryboardPanel.jsx. Tested 100% backend (9/9) + frontend (iteration_95).
- 2026-04-02: FIX (P0) - Production image persistence fix. Root cause: `store_asset_sync` created a NEW pymongo MongoClient for every image, blocking the async event loop and causing silent timeouts in production. Fix: Created `store_asset_async(db, ...)` that reuses the existing motor connection pool. Replaced ALL sync calls in async contexts (ai_agent.py: 4 calls, agent.py routes: 3 calls, projects.py routes: 3 calls, export.py: 1 call). Only startup scripts and PPT parser (sync thread) still use sync version. Also fixed a hidden daemon thread in agent.py bg upload. Verified 450 assets in MongoDB.
- 2026-04-02: FEATURE - AI Agent "Gerar Curso" progress panel. Added GeneratingProgressPanel component showing: animated progress bar with %, phase timeline (init/slides/images/save), image generation sub-progress (X/Y), elapsed timer, summary stats (slides/images/time), helpful tip. Chat messages now have visual indicators (spinner for progress, checkmark for success, alert for errors). Tested 100% (iteration_96).
- 2026-04-02: FEATURE - Expanded AI Agent improvement types. Added 3 new types: Cenário Interativo (interactive decision scenarios with branching choices), Resumo Visual (visual summaries - infographics, mind maps, timelines, process diagrams), Reforço de Aprendizagem (flashcards, "Sabia que?" boxes, practical tips, case studies). Backend prompts include pedagogical principles: less text + more engagement. Frontend shows colored badges (cyan=scenario, amber=visual_summary, rose=reinforcement). SlideTypeSwitcher updated. Tested 100% (iteration_97).
- 2026-04-06: FEATURE - Admin Panel: Excluir permanentemente usuários e empresas (hard delete), alterar senha ao editar usuário, trocar role editor ↔ company_admin. Modal de edição mostra campo de senha com placeholder 'Deixe vazio para não alterar'. Delete de empresa remove todos seus usuários. Testado 100% backend (12/12) + frontend (iteration_99).

- 2026-04-06: FEATURE - Storyboard text editing + Aprovador role + Approval queue.
  - StoryboardPanel: inline editing for slide titles, content elements, and narration scripts.
  - Typo fix: "Proximo" -> "Proxima" on slide navigation button.
  - New `aprovador` role: can login, auto-redirected to approval queue on /agent page.
  - Approval workflow: Submit for Approval -> Aprovador reviews/edits/approves -> Super Admin resumes.
  - Backend endpoints: submit-for-approval, approve-storyboard, reject-storyboard, resume-from-approval, update-storyboard-text, approval-queue.
  - Admin panel: Aprovador option in role dropdown when creating/editing users.
  - Agent page: 3-column ModeSelector with "Fila de Aprovacao" card (amber themed).
  - ApprovalQueuePanel: full review UI with editable fields, approve/reject buttons.
  - Tested 100% backend (14/14) + frontend (iteration_100).

- 2026-04-06: FIX - Approval workflow now requires selecting a target company.
  - submit-for-approval requires `targetCompanyId` in request body.
  - Aprovador ONLY sees sessions targeted to their company.
  - Company selector dialog opens when clicking "Enviar para Aprovacao" in StoryboardPanel.
  - Super Admin sees all sessions in the queue.

- 2026-04-06: FIX - Super Admin can now resume approved sessions directly into the Storyboard wizard.
  - Clicking "Retomar" in the Fila de Aprovação loads the full session (storyboard, config, structure) into create mode at step 4.
  - Super Admin can then proceed to Media Config and complete generation.

- 2026-04-07: FIX - Images not persisting after FORK (re-occurrence).
  - Root cause: after fork, local files are lost and startup only did LOCAL→MongoDB (not MongoDB→LOCAL).
  - Added proactive asset RESTORATION at startup: restores ALL project assets and audio files from MongoDB to disk.
  - Fixed `serve_global_asset` base64 bug (wrote string instead of bytes, causing corrupt files).
  - Made `serve_asset` and `serve_global_asset` stream directly from memory if disk write fails.
  - Added `POST /api/admin/restore-assets` endpoint for manual force-restoration.
  - Tested: 97 assets auto-restored on startup, per-request fallback serves correctly (200 OK).

- 2026-04-06: FEATURE - Tutor IA Dashboard (Analytics).
  - Tutor chat now logs all questions to `tutor_logs` collection with projectId, companyId, courseTopic.
  - GET /api/admin/tutor-dashboard: aggregated analytics by course and company.
  - GET /api/admin/tutor-dashboard/course/{id}: detailed view with top questions and recent logs.
  - Super Admin sees all data; Company Admin sees only their company's courses.
  - Frontend TutorDashboard component with summary cards, company breakdown, search, course detail drill-down.
  - New "Dashboard Tutor" tab in Admin panel.
  - Tested 100% backend (12/12) + frontend verified (iteration_101).

- 2026-04-07: FIX (P0) - MongoDB Atlas timeout storm during deploy.
  - Root cause: `startup_persist_local_assets` called `store_asset_sync` per asset, creating a NEW MongoClient (TLS handshake + auth) for EACH of 596+ assets. Also `startup_restore_assets_from_mongodb` loaded ALL base64 data at once, timing out on Atlas.
  - Fix: Merged both startup tasks into single `startup_asset_sync` that uses ONE MongoClient. Phase 1 RESTORE: fetches lightweight filename index first, then loads data only for missing files individually. Phase 2 PERSIST: uses same client to write new local files to MongoDB. Increased all Atlas timeouts to 60s (connection) / 120s (socket). Updated `store_asset_sync`, `retrieve_asset_sync`, and `restore_project_assets_sync` timeouts. Also increased main AsyncIOMotorClient timeouts.
  - Verified: 3 deleted test files auto-restored on startup, per-request MongoDB fallback returns 200.

- 2026-04-08: FEATURE - Enviar Melhorias para Aprovacao (Improvement Approval Workflow).
  - PreviewPanel: novo botao "Enviar para Aprovacao" com dialog de selecao de empresa (ao lado de "Confirmar e Aplicar").
  - Visual HTML Preview: conteudo HTML e renderizado em iframes sandboxed (visual) ao inves de codigo-fonte.
  - Backend endpoints: POST submit-improvements-for-approval, approve (auto-aplica melhorias), reject.
  - Approval Queue unificada: retorna storyboards + melhorias combinados com campo _type.
  - ApprovalQueuePanel: diferencia items por tipo (badge Storyboard/Melhorias), renderiza HTML visual, botoes aprovar/devolver.
  - Testado 100% backend (15/15) + frontend (iteration_102).

- 2026-04-08: FEATURE - Sistema de Balanceamento de Recursos Pedagogicos.
  - ConfigPanel: Novo card "Recursos Pedagogicos" com 4 niveis de interatividade (Baixa/Media/Alta/Maxima).
  - 8 tipos de recursos toggleaveis: Quiz, Jogos Educativos, Cenarios de Desafio, Infograficos Interativos, Flashcards Animados, Linhas do Tempo, Estudos de Caso, Cenas com Avatar.
  - Barra de distribuicao visual mostrando % aproximada de cada recurso.
  - Backend: generate_structure envia instrucoes explicitas de distribuicao na prompt (ex: "De 20 slides, gere EXATAMENTE: 9 conteudo, 2 quiz, 3 simulador...").
  - 4 novos tipos de slide (infographic, flashcard, timeline, case_study) processados como HTML interativo em iframe.
  - Testado 100% backend (13/13) + frontend (iteration_103).

- 2026-04-08: FIX (P0) - 504 Gateway Timeout em producao nos endpoints /analyze e /generate-structure.
  - Root cause: Endpoints sincronos aguardavam resposta da IA (10-30s), excedendo timeout de 60s do proxy Kubernetes.
  - Fix: Convertidos para processamento assincrono com polling (mesmo padrao do generate-storyboard).
    - POST /analyze -> retorna imediatamente {"status":"processing"}, processa em thread, step muda para "analyzed"
    - POST /generate-structure -> retorna imediatamente {"status":"processing"}, step muda para "structured"
    - POST /courses/{id}/analyze -> usa analysis_cache collection, retorna "processing" e poll via POST
    - Frontend atualizado com pollSessionStep() que checa a cada 3s ate max 3 minutos
  - Testado: /analyze 193ms, /generate-structure 142ms, polling confirma resultados em <5s.

- 2026-04-14: FEATURE - Leonardo AI Integration (Editor + Agent).
  - Backend: 3 new endpoints - POST /api/leonardo/generate (starts image generation via Leonardo Phoenix 1.0), GET /api/leonardo/status/{id} (polls completion), POST /api/leonardo/save-to-project (downloads and saves to project assets + auto-saves to AI Image Gallery).
  - Service: leonardo_ai.py with generate_image, poll_generation, generate_and_wait, download_image_to_disk.
  - Editor: Leonardo AI button in toolbar (Wand2 icon, violet gradient). Opens dialog with LeonardoPanel - prompt textarea, 6 style presets (Automatico, Cinematico, Ilustracao, Fotografia, Arte Digital, 3D), generate button, results grid with "Usar no Curso" button that adds image directly to current slide.
  - Agent: Leonardo AI as media type option in MediaConfigPanel. When creating a course, slides configured as "Leonardo AI" will use Leonardo API instead of Gemini for image generation. Custom prompt per slide supported.
  - Gallery Integration: All Leonardo images are auto-saved to the AI Image Gallery (image_gallery collection) with "leonardo:" prefix in keywords. Works in Editor save-to-project, Agent course generation, and Agent apply-media-config flows.
  - Tested 100% backend (12/12) + frontend (iteration_104). Gallery auto-save verified via curl (13->14 images).

- 2026-04-14: FEATURE - Leonardo AI nas Melhorias do Agent IA.
  - Novo tipo de melhoria "imagem_premium": a IA sugere imagens profissionais Leonardo AI para slides que precisam de impacto visual (capa, abertura de modulo, conteudo-chave).
  - Cada sugestao inclui imagePrompt (ingles, detalhado) e imageStyle (CINEMATIC, PHOTOGRAPHY, etc.).
  - Ao aplicar melhorias, slides com _leonardoImage sao processados automaticamente: gera imagem via Leonardo, salva no projeto, insere como elemento, redimensiona layout para duas colunas.
  - Imagens geradas sao auto-salvas na Galeria de Imagens IA.
  - Frontend: badge fuchsia "Imagem Premium" com icone ImagePlus, exibe prompt e estilo sugerido.
  - Type Switcher atualizado com opcao "Imagem Premium (Leonardo)".
- 2026-04-15: FEATURE - Custos Leonardo AI no Relatorio de Uso.
  - Testado 100% backend (7/7) + frontend (iteration_105).

- 2026-04-15: FIX (P0) - PPT Upload quebrado apos deploy em producao.
  - Causa raiz: O estado do upload chunked (jobs dict) era armazenado APENAS em memoria. Quando o servidor reinicia (deploy), o estado e perdido e o chunk endpoint retorna 404.
  - Fix Backend: Upload metadata agora persistido em MongoDB (collection ppt_uploads). Endpoints /chunk e /complete recuperam estado do MongoDB se nao encontrado em memoria. Timeouts aumentados para Atlas.
  - Fix Frontend: Upload chunked agora tem retry automatico (ate 2x). Se chunk falha com 404/410, reinicia o upload do zero. Mensagem de erro clara ao usuario.
  - Tambem melhorado: Avatar BG persistence com retry + timeouts maiores para Atlas.
  - Testado: Upload init → restart servidor → chunk aceito com sucesso (recuperado do MongoDB).
  - Cost Estimate: POST /api/agent/sessions/{id}/cost-estimate agora retorna leonardoImages, costs.leonardo ($0.036/imagem), models.leonardo.
  - Usage Logs: usage_logs inclui leonardoImages nos detalhes e leonardoGeneration no estimatedCost.
  - Admin Reports: GET /api/admin/reports retorna totalLeonardoImages por empresa.
  - Frontend CostEstimateCard: badge fuchsia "Leonardo AI", grid dinamica (3 ou 4 colunas), coluna de custo Leonardo com estilo fuchsia, rodape inclui "+ Leonardo AI".
  - Frontend Admin: card Leonardo AI com icone Sparkles no relatorio de uso quando totalLeonardoImages > 0.
  - Testado 100% backend (5/5) + frontend (iteration_106).
  - Frontend Admin: Card "Leonardo AI - Uso de Imagens" com gradiente fuchsia/violet no topo do relatorio. Mostra: imagens geradas, pendentes, custo USD/BRL, modelo, custo por imagem.


## Upcoming Tasks (Prioritized)
- P1: Email Notifications (Approval workflow + Tutor IA alerts)
- P1: SCORM 2004 & xAPI Export
- P1: Dashboard for analytics & scoring
- P1: Course version history
- P2: Cleanup legacy video_exporter.py backend code
