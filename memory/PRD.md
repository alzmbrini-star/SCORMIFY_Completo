# PRD - Course Authoring Tool (Scormfy)

## Original Problem Statement
Build a full-featured course authoring tool with AI-powered course generation, SCORM export, VLibras accessibility, and multimedia integration.

## Architecture
- **Frontend**: React + Tailwind + Shadcn/UI
- **Backend**: FastAPI + MongoDB
- **AI**: Gemini 3 Flash (text), Gemini Nano Banana (images) via Emergent LLM Key
- **Integrations**: ElevenLabs TTS, HeyGen Avatars, ConvertAPI, VLibras

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
- Mode Selector: "Criar Novo Curso" vs "Editar Curso Existente"
- Platform & Course Improvement Suggestions with AI self-analysis

### Visual Improvements (Complete)
- 6 Professional Color Palettes, two-column layouts, header bars, styled typography

### Per-Slide Media Configuration (Complete)
- 8 media types: AI Image, YouTube, Vimeo, HeyGen Avatar, Flipbook, HTML, Button, No Media
- Quick-apply buttons, media summary

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

### Global Text Styling (Complete - 2026-03-03)
- **Global Text Color**: Color picker in Agent Media Config, bulk action in Editor
- **Global Font Size**: Size scale control (P=80%, N=100%, G=120%, GG=140%) in Agent Media Config. Applies to new courses during generation and existing courses via "Aplicar Alterações". Preview shows scaled text with selected color.

### Text Entrance Animations (Complete)
- 8 animation types: Fade In, Slide In (4 directions), Zoom In, Typewriter, Bounce
- Configurable globally in Agent and per-element in Editor

### Apply Media Changes to Existing Project (Complete)
- "Editar Mídia" button in Editor -> Agent Media Config -> "Aplicar Alterações ao Projeto"
- Updates backgrounds, text colors, font sizes, animations, narration without regenerating

### Dashboard Improvements (Complete - 2026-03-03)
- **Course Grid View**: Agent courses shown in visual grid (3 columns) with colored gradient cards
- **Slide Mini-Preview Thumbnails**: Dashboard project cards show CSS-based mini-preview of first slide (background, title, accent bar) for courses without PPT thumbnails

### Deployment Fixes (Complete - 2026-03-03)
- Added MongoDB connection timeouts (serverSelectionTimeoutMS=10000, connectTimeoutMS=10000) to all Motor and PyMongo clients
- Protected all startup events with try/except for graceful failure
- Fixed truncated shutdown event handler
- Applied timeouts to asset_store.py sync MongoClient instances

## Key API Endpoints (Agent)
- `POST /api/agent/sessions` - Create session
- `POST /api/agent/sessions/{id}/upload` - Upload content
- `POST /api/agent/sessions/{id}/analyze` - AI analysis
- `POST /api/agent/sessions/{id}/configure` - Set config
- `POST /api/agent/sessions/{id}/generate-structure` - Generate structure
- `POST /api/agent/sessions/{id}/generate-storyboard` - Background storyboard gen
- `POST /api/agent/sessions/{id}/media-config` - Save per-slide media config (incl. globalFontSize)
- `POST /api/agent/sessions/{id}/generate-course` - Generate project
- `POST /api/agent/sessions/{id}/apply-media-changes` - Apply changes to existing project
- `POST /api/agent/sessions/{id}/generate-slide-narration` - Generate narration scripts
- `GET /api/agent/sessions/by-project/{id}` - Get session for project editing

## Key Files
- `backend/server.py` - Main server (~5350 lines)
- `backend/services/ai_agent.py` - AI agent logic (~1480 lines)
- `frontend/src/pages/Agent.jsx` - Agent page (~2825 lines)
- `frontend/src/pages/Editor.jsx` - Course editor
- `frontend/src/pages/Dashboard.jsx` - Project dashboard

## Prioritized Backlog
### P1
- User-requested features (ask user for next priority)
### P2
- Advanced Interactivity: Per-course "Tutor IA"
### P3
- Refactor server.py into routers
- Refactor Editor.jsx into smaller components
- Refactor Agent.jsx MediaConfigPanel into sub-components
- Jinja2 for HTML templates
- SCORM 2004 export
