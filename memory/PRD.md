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

## Credentials
- Admin: admin@scormify.com / admin123

## 3rd Party Integrations
- Google Gemini (via Emergent LLM Key) - Text + Image generation (Nano Banana)
- OpenAI GPT-4o (via Emergent LLM Key)
- HeyGen - Avatar videos + voice TTS (user API key)
- ElevenLabs - Audio narration for regular slides only (user API key)
- ConvertAPI - PPT import (user API key)

## Code Architecture
```
/app
├── backend
│   ├── routes
│   │   ├── agent.py            # AI agent endpoints, HeyGen/ElevenLabs orchestration
│   │   ├── heygen.py           # Core HeyGen endpoints
│   │   ├── gamification.py     # Gamification + badge image upload
│   ├── services
│   │   ├── ai_agent.py         # AI prompting logic for storyboards
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

## Upcoming Tasks (Prioritized)
- P1: SCORM 2004 & xAPI Export
- P1: Dashboard for analytics & scoring
- P1: Course version history
- P2: Cleanup legacy video_exporter.py backend code
