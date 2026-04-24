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
