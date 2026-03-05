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
- **Global Font Size**: Size scale control (P=80%, N=100%, G=120%, GG=140%) in Agent Media Config

### Text Entrance Animations (Complete)
- 8 animation types: Fade In, Slide In (4 directions), Zoom In, Typewriter, Bounce

### Apply Media Changes to Existing Project (Complete)
- "Editar Mídia" button in Editor -> Agent Media Config -> "Aplicar Alterações ao Projeto"

### Dashboard Improvements (Complete - 2026-03-03)
- Course Grid View, Slide Mini-Preview Thumbnails

### Admin Reports Tab (Complete - 2026-03-04)
- Usage statistics by company, AI credit tracking, role-based access

### AI Image Persistence Fix (Complete - 2026-03-04)
- Images persisted to MongoDB to survive ephemeral storage restarts

### Role-Based Access Control for AI Agent (Complete - 2026-03-04)
- Permission system with `agentAccess` in company permissions

### Bug Fixes (2026-03-05)
- **MongoDB Supervisor**: Re-added MongoDB to supervisor config (was removed in previous session)
- **"Aplicar Alterações" button disabled silently**: Fixed narrationVoiceId not restored from session when editing media, added feedback message when button is disabled
- **Editor Slide Thumbnails broken**: Fixed background images using CSS instead of `<img>` tag, removed double font-size reduction for HTML content, applied proper opacity

## Key API Endpoints (Agent)
- `GET /api/agent/check-access` - Check user permission for AI Agent
- `POST /api/agent/sessions` - Create session (protected)
- `POST /api/agent/sessions/{id}/upload` - Upload content
- `POST /api/agent/sessions/{id}/analyze` - AI analysis
- `POST /api/agent/sessions/{id}/configure` - Set config
- `POST /api/agent/sessions/{id}/generate-structure` - Generate structure
- `POST /api/agent/sessions/{id}/generate-storyboard` - Background storyboard gen
- `POST /api/agent/sessions/{id}/media-config` - Save per-slide media config
- `POST /api/agent/sessions/{id}/generate-course` - Generate project
- `POST /api/agent/sessions/{id}/apply-media-changes` - Apply changes to existing project
- `GET /api/admin/reports` - Admin reports data

## Key Files
- `backend/server.py` - Main server (~5740 lines) - **NEEDS REFACTORING**
- `backend/routes/auth.py` - Auth routes incl. `require_agent_access`
- `backend/routes/companies.py` - Company CRUD with `agentAccess` permission
- `backend/services/ai_agent.py` - AI agent logic (~1480 lines)
- `frontend/src/pages/Agent.jsx` - Agent page (~2920 lines) - **NEEDS REFACTORING**
- `frontend/src/pages/Editor.jsx` - Course editor (~4943 lines) - **NEEDS REFACTORING**
- `frontend/src/pages/Dashboard.jsx` - Project dashboard
- `frontend/src/contexts/AuthContext.jsx` - Auth context with `hasPermission` helper

## Prioritized Backlog
### P1 - URGENT
- **Refactor `server.py`**: Split into `/backend/routes/` using FastAPI APIRouter
- **Refactor `Editor.jsx`**: Break into smaller components and hooks
- **Refactor `Agent.jsx`**: Break MediaConfigPanel into sub-components
### P2
- Advanced Interactivity: Per-course "Tutor IA"
- User-requested features
### P3
- Jinja2 for HTML templates
- SCORM 2004 export
- Professional Layout Templates (design tokens, colors, fonts)
