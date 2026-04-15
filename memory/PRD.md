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

## Code Architecture
```
/app
├── backend
│   ├── routes
│   │   ├── agent.py            # AI agent endpoints, HeyGen/ElevenLabs orchestration
│   │   ├── heygen.py           # Core HeyGen endpoints
│   │   ├── leonardo.py         # Leonardo AI image generation endpoints
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
- 2026-03-29: FIX - Avatar scene HeyGen generation simplified: WebM transparent first, v2 standard fallback (removed unreliable background-image-URL strategy that caused HeyGen processing failures in production)
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
