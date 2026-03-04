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

### Admin Reports Tab (Complete - 2026-03-04)
- **New "Relatórios" Tab**: Added to Admin panel showing usage statistics by company
- **Access Control**:
  - Super Admin: sees all companies + orphan projects
  - Company Admin: sees only their own company
- **Stats Displayed**:
  - Total courses created
  - Total slides generated
  - AI images generated
  - Narrations generated
  - Cost in USD and BRL (R$)
- **Course Details**: Name, editor, creation date
- **Editors List**: All editors in the company
- **Usage Logging**: New `usage_logs` collection tracks AI usage during course generation
- **Files Modified**:
  - `backend/server.py`: Added `GET /api/admin/reports` endpoint, usage logging in course generation
  - `frontend/src/pages/Admin.jsx`: Added Reports tab with expandable company cards

### AI Image Persistence Fix (Complete - 2026-03-04)
- **Problem**: AI-generated images (backgrounds and slide images) were being lost in production due to ephemeral filesystem
- **Solution**: Images are now automatically persisted to MongoDB's `project_assets` collection
- **Files Modified**:
  - `backend/server.py`: `agent_generate_bg_image` now persists bg images to MongoDB
  - `backend/services/ai_agent.py`: `_fetch_stock_image` and `_fetch_picsum_image` now persist images to MongoDB
  - `backend/server.py`: Startup task now also persists `bg_temp` folder images
- **Fallback**: The `serve_asset` endpoint already had MongoDB fallback for when local files are missing
- **Affected Image Types**:
  - Background images (`/api/projects/bg_temp/assets/bg_ai_*.png`)
  - AI-generated slide images (`/api/projects/{id}/assets/ai_img_*.png`)
  - Stock images from Picsum (`/api/projects/{id}/assets/stock_*.jpg`)

### Role-Based Access Control for AI Agent (Complete - 2026-03-04)
- **Permission System**: `agentAccess` permission in `company.permissions` controls access to AI Agent
- **Super Admin Access**: Super Admins always have full access regardless of company permissions
- **Company Permissions UI**: Checkbox "Agente IA" in Admin panel for each company under "Permissões de API"
- **Frontend Protection**: 
  - Dashboard: "Agente IA" button only visible if `hasPermission('agentAccess')` or `isSuperAdmin`
  - Agent Page: Redirects to "/" with error toast if user lacks permission
- **Backend Protection**: 
  - New `require_agent_access` dependency in `routes/auth.py`
  - All `/api/agent/*` endpoints protected with 403 response for unauthorized users
  - New `GET /api/agent/check-access` endpoint for frontend permission checking
- **Default Behavior**: New companies created with `agentAccess: false`

## Key API Endpoints (Agent)
- `GET /api/agent/check-access` - Check if current user has AI Agent access
- `POST /api/agent/sessions` - Create session (protected)
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
- `backend/server.py` - Main server (~5500 lines) - **NEEDS REFACTORING**
- `backend/routes/auth.py` - Auth routes incl. `require_agent_access`
- `backend/routes/companies.py` - Company CRUD with `agentAccess` permission
- `backend/services/ai_agent.py` - AI agent logic (~1480 lines)
- `frontend/src/pages/Agent.jsx` - Agent page (~2900 lines) - **NEEDS REFACTORING**
- `frontend/src/pages/Editor.jsx` - Course editor - **NEEDS REFACTORING**
- `frontend/src/pages/Dashboard.jsx` - Project dashboard (has `hasAgentAccess` check)
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
