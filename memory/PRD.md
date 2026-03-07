# PRD - Course Authoring Tool (Scormfy)

## Original Problem Statement
Build a full-featured course authoring tool with AI-powered course generation, SCORM export, VLibras accessibility, and multimedia integration.

## Architecture
- **Frontend**: React + Tailwind + Shadcn/UI
- **Backend**: FastAPI + MongoDB
- **AI**: Gemini 3 Flash (text), Gemini Nano Banana (images) via Emergent LLM Key
- **Integrations**: ElevenLabs TTS, HeyGen Avatars, ConvertAPI, VLibras

## Backend Architecture (Refactored 2026-03-05)
```
backend/
├── server.py              # 318 lines - Thin orchestrator (FastAPI app, CORS, startup events)
├── routes/
│   ├── deps.py           # 93 lines - Shared dependencies (db, paths, helpers)
│   ├── auth.py           # 415 lines - Authentication (login, logout, me, change-password)
│   ├── companies.py      # 169 lines - Company CRUD
│   ├── users.py          # 278 lines - User management
│   ├── projects.py       # 985 lines - Project CRUD, slides, elements, media, audio, annotations
│   ├── export.py         # 431 lines - SCORM/HTML export, asset serving
│   ├── heygen.py         # 1031 lines - HeyGen avatar video integration
│   ├── ai_gen.py         # 263 lines - AI text/image generation
│   ├── questions.py      # 218 lines - Quiz questions CRUD and generation
│   ├── elevenlabs.py     # 195 lines - ElevenLabs TTS
│   ├── admin.py          # 184 lines - Admin reports, tutor settings, tutor chat
│   ├── agent.py          # 1687 lines - AI Instructional Design Agent
│   └── vlibras.py        # 134 lines - VLibras CORS proxy
├── services/
│   ├── ai_agent.py       # AI agent logic
│   ├── asset_store.py    # MongoDB asset persistence
│   └── ppt_image_parser.py
└── models.py
```

## What's Been Implemented

### Core Features (Complete)
- Full course editor, SCORM 1.2 export, HTML export, TTS, AI scripts, HeyGen avatars, PPT import, quiz system, AI Tutor, mobile player

### VLibras Integration (Complete)
- CORS Proxy for both VLibras domains, XHR monkey-patch in exports

### AI Agent - Phase 1 MVP (Complete)
- Content upload -> AI analysis -> structure -> storyboard -> course generation
- Background tasks with polling, chat with agent

### AI Agent - Phase 2: Editing & Templates (Complete)
- 6 Visual Templates, Course Editing with AI analysis + improvements
- Mode Selector, Platform & Course Improvement Suggestions

### Visual Improvements (Complete)
- 6 Professional Color Palettes, two-column layouts, header bars, styled typography

### Per-Slide Media Configuration (Complete)
- 8 media types: AI Image, YouTube, Vimeo, HeyGen Avatar, Flipbook, HTML, Button, No Media

### Content Depth Enhancement (Complete)
- AI generates 100+ words per content slide, 400+ words summary slides

### Functional Scormfy Quizzes (Complete)
- type='quiz' elements with quizConfig + questionIds linked to MongoDB questions

### Full HeyGen Avatar Integration (Complete)
- Avatar grid picker, Portuguese voice picker, background video generation, auto-polling

### Enhanced Content Input (Complete)
- PDF (PyPDF2), DOCX (python-docx), URL/Website (httpx + BeautifulSoup)

### Automatic Narration - ElevenLabs (Complete)
- Per-slide narration in Agent Media Config, AI-generated script options, voice picker

### Background Customization (Complete)
- Solid colors, gradients, uploaded images, AI-generated images per slide

### Cost Optimization (Complete)
- Gemini 3 Flash + Nano Banana (~79% cost reduction vs GPT), cost estimation UI

### Global Text Styling (Complete)
- Global Text Color, Global Font Size in Agent Media Config

### Text Entrance Animations (Complete)
- 8 animation types: Fade In, Slide In (4 dirs), Zoom In, Typewriter, Bounce

### Apply Media Changes to Existing Project (Complete)
- "Editar Mídia" button in Editor -> Agent Media Config -> "Aplicar Alterações ao Projeto"

### Dashboard Improvements (Complete)
- Course Grid View, Slide Mini-Preview Thumbnails

### Admin Reports Tab (Complete)
- Usage statistics by company, AI credit tracking, role-based access

### AI Image Persistence Fix (Complete)
- Images persisted to MongoDB to survive ephemeral storage restarts

### Role-Based Access Control for AI Agent (Complete)
- Permission system with `agentAccess` in company permissions

### Backend Refactoring (Complete - 2026-03-05)
- server.py: 5740 → 318 lines (95% reduction)
- 14 modular route files in routes/ directory
- Testing: 23/23 backend endpoints passed, all frontend pages verified

### Bug Fixes (2026-03-05)
- MongoDB Supervisor: Re-added MongoDB to supervisor config
- "Aplicar Alterações" button: Fixed narrationVoiceId restoration from session
- Editor Slide Thumbnails: Fixed background image rendering + HTML font-size

### P0 Bug Fix: AI Image Generation in Edit Media (Complete - 2026-03-05)
- **Root Cause**: `apply_media_changes` endpoint only handled backgrounds/animations/narration but never processed `mediaConfig` for image generation
- **Fix**: Added media processing logic to `apply_media_changes` in `backend/routes/agent.py`:
  - `ai_image`: Calls `_fetch_stock_image` from `services/ai_agent.py` to generate images via Gemini Nano Banana
  - `youtube`/`vimeo`: Creates video embed elements in slides
  - `none`: Removes image/video elements and expands text to full width
- **Additional Fix**: Handled MongoDB null values for storyboard using `or {}` pattern
- **Testing**: 12/12 backend tests passed (100%)

### P3: Professional Layout Templates + AI Image Gallery (Complete - 2026-03-05)
- **6 Design Templates**: Corporativo, Educacional, Minimalista, Tech & Inovação, Criativo Bold, Elegante Premium
  - Each with distinct palette, heading/body fonts, corner radius, header style
  - Template picker UI in ConfigPanel step 2 with gradient previews
  - `designTemplateId` saved in session config, passed to course generation
- **AI Image Gallery**: Company-wide shared library of generated images
  - New `image_gallery` MongoDB collection
  - CRUD API: GET/POST/DELETE `/api/gallery/images`
  - Per-company visibility (super_admin sees all)
  - Auto-save when AI images are generated via `_fetch_stock_image`
  - Gallery modal in MediaConfigPanel with search, preview, and selection
  - `gallery_image` media type reuses existing images (no generation cost)
- **Backend**: `backend/routes/gallery.py` (new), `backend/routes/agent.py`, `backend/services/ai_agent.py`
- **Frontend**: `frontend/src/pages/Agent.jsx` (ImageGalleryModal component, design template picker)
- **Testing**: 11/11 backend + all frontend (iteration_59), then 20/20 visual diff tests (iteration_60)
- **Visual Differentiation Fix (2026-03-05)**: Each template now generates visually distinct slides:
  - `_build_header_bar()`: 6 header styles (solid/rounded/minimal/neon/gradient/elegant)
  - Fonts applied in all HTML: headings use `fontHeading`, body uses `fontBody`
  - `cornerRadius` applied to image elements per template
  - Title slide dividers and module list badges vary per template style
- **Templates no Editor Manual + Editar Mídia (2026-03-05)**:
  - Editor: Botão "Aplicar Tema Visual" (Palette icon) na toolbar abre dialog com 6 templates
  - Endpoint: `POST /api/projects/{id}/apply-design-template` aplica tema a todos os slides existentes
  - MediaConfigPanel: Seletor de tema na tela "Editar Mídia" auto-preenche bgConfig com cores do template
  - `_apply_design_token_to_slide()`: helper que atualiza headers, fontes, backgrounds e corner radius
  - Testes: 13/13 backend + all frontend flows (iteration_61)
- **Bug Fix: Contraste de Texto nos Templates (2026-03-05)**:
  - Problema: texto claro em fundos claros ficava invisível após aplicar template
  - Correção: `_apply_design_token_to_slide` agora atualiza TODAS as cores de texto (branco em fundos escuros, escuro em fundos claros)
  - `_is_light_color()`: detecta luminância do fundo para escolher cor de texto adequada
  - Detecção inteligente de tipo de slide por keywords no título (capa, quiz, resumo)
  - Detecção de header bars tolerante (width >= 1700)
  - Testes: 17/17 backend, 0 problemas de contraste em todos os 6 templates (iteration_62)

### P0: Per-Slide Narration Control & Cost Estimation (Complete - 2026-03-05)
- **Feature**: Per-slide narration toggle on Storyboard screen (step 4)
  - Global enable/disable narration toggle
  - Per-slide checkboxes to control which slides get narration
  - ElevenLabs voice selector with preview playback
  - Select all / Deselect all buttons
  - Character count per slide and total
  - Cost estimation based on ElevenLabs Starter plan ($5/30,000 chars)
  - Monthly quota usage percentage with progress bar
  - Narration config saved to session before proceeding to media config
- **Backend**: New endpoint `POST /api/agent/sessions/{id}/save-narration-config`
  - Saves `narrationSlides` map, `narrationVoiceId`, `narrationEnabled` to session config
  - Updated `cost-estimate` endpoint to calculate narration cost from storyboard character counts
  - Updated `generate-course` to respect per-slide narration toggles (`narrationSlides` map)
- **Frontend**: Rewritten `StoryboardPanel` component in `Agent.jsx`
- **Testing**: 15/15 backend tests passed (iteration_63)

### Bug Fix: Narration & Suggestions Background Tasks (Complete - 2026-03-05)
- **Root Cause**: `_generate_narrations` and `_generate_improvement_suggestions` were async functions using the global `db` Motor client which was bound to the main event loop, but they ran in background threads with separate event loops via `asyncio.run()`. Also `aiofiles` was not imported inside the narration function.
- **Fix**: Both functions now create their own Motor client (`AsyncIOMotorClient`) inside the function body, matching the pattern used by `_sync_generate_course`. Added explicit `import aiofiles` inside `_generate_narrations`.
- **Result**: 10/10 narrations generated successfully for test project. 0 failures.

### Bug Fix: HeyGen Credits & Narration Generation (Complete - 2026-03-06)
- **Bug 1**: `/api/heygen/credits` returning 500 - Missing `datetime` and `timezone` imports in `heygen.py`
- **Bug 2**: `/api/projects/{id}/slides/{id}/generate-narration` returning 500 - Missing `get_project_by_id` import in `heygen.py`
- **Bug 3**: HeyGen credits showing 0 for subscription plans - Fixed to read `data.details.plan_credit` from HeyGen API
- **Fix**: Added imports, updated credits parsing to use `plan_credit` for subscription plans
- **Result**: Credits display restored (399 créditos), OCR narration and video generation working

### Feature: Slides para Vídeo com Avatar (HeyGen) (Complete - 2026-03-07)
- **Feature**: Convert course slides to avatar-narrated videos via HeyGen API
  - One video per slide with slide image as background + avatar overlay (PiP)
  - AI-generated narration scripts via Gemini 3 Flash Vision (with slide image OCR)
  - Editable scripts per slide with character count
  - Enable/disable slides individually via checkboxes
  - Avatar and voice selection (reusing existing HeyGen integration)
  - Batch video generation with progress polling
  - HeyGen credits display
- **Backend endpoints**:
  - `POST /api/heygen/generate-all-slide-scripts?project_id={id}` - Generate AI scripts for all slides
  - `POST /api/heygen/generate-slide-video` - Generate video for single slide
  - `POST /api/heygen/generate-batch-slide-videos` - Batch video generation
  - `GET /api/heygen/batch-status/{batch_id}` - Poll batch status
- **Frontend**: New "Slides para Vídeo com Avatar" dialog accessible from Editor toolbar (Presentation icon)
- **Testing**: 17/17 backend tests passed, frontend verified (iteration_64)

## Prioritized Backlog
### P1 - URGENT
- **Refactor `Editor.jsx`** (~4943 lines): Break into smaller components and hooks
- **Refactor `Agent.jsx`** (~3400 lines): Break MediaConfigPanel into sub-components
### P2
- Advanced Interactivity: Per-course "Tutor IA"
### P3
- SCORM 2004 export
