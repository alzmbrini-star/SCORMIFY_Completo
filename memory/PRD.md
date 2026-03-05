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
- **Testing**: 11/11 backend tests + all frontend features verified (100%)

## Prioritized Backlog
### P1 - URGENT
- **Refactor `Editor.jsx`** (~4943 lines): Break into smaller components and hooks
- **Refactor `Agent.jsx`** (~3200 lines): Break MediaConfigPanel into sub-components
### P2
- Advanced Interactivity: Per-course "Tutor IA"
### P3
- SCORM 2004 export
