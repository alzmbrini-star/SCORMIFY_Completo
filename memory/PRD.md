# PRD - Course Authoring Tool (Scormfy)

## Original Problem Statement
Build a full-featured course authoring tool with AI-powered course generation, SCORM export, VLibras accessibility, and multimedia integration.

## Architecture
- **Frontend**: React + Tailwind + Shadcn/UI
- **Backend**: FastAPI + MongoDB
- **AI**: OpenAI GPT-5.2 (text), GPT Image 1 (images) via Emergent LLM Key
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
- **Platform & Course Improvement Suggestions (2026-03-02)**: AI automatically analyzes each course creation process and generates 18 categorized suggestions (Platform UX/Features/Performance, Course Content/Design/Pedagogy). Shows in GeneratedPanel with collapsible UI, priority badges, and on-demand regeneration. Uses Gemini 3 Flash with GPT-4o fallback.
- 6 Visual Templates, Course Editing with AI analysis + improvements
- Mode Selector: "Criar Novo Curso" vs "Editar Curso Existente"

### Visual Improvements (Complete)
- 6 Professional Color Palettes, two-column layouts, header bars, styled typography

### Per-Slide Media Configuration (Complete)
- 5 media types: AI Image (GPT Image 1), YouTube, Vimeo, HeyGen Avatar, No Media
- Quick-apply buttons, media summary

### Content Depth Enhancement (Complete)
- AI generates 100+ words per content slide, 400+ words summary slides

### Functional Scormfy Quizzes (Complete)
- type='quiz' elements with quizConfig + questionIds linked to MongoDB questions

### Full HeyGen Avatar Integration (Complete - 2026-03-02)
- Avatar grid picker with preview images (1288+ avatars)
- Portuguese voice picker with audio preview (29+ voices)
- Background video generation after course creation
- Auto-polling status with slide auto-update
- **Avatar Preview**: "Testar Avatar + Voz" button generates short preview video before course generation

### Enhanced Content Input (Complete - 2026-03-02)
- **PDF**: Native extraction via PyPDF2 (fallback to ConvertAPI)
- **DOCX**: Native extraction via python-docx (including tables)
- **URL/Website**: Web scraping via httpx + BeautifulSoup (extracts article/main content)
- Upload panel redesigned with 3 columns: File Upload, Text Input, URL Input

### Automatic Narration - ElevenLabs (Complete - 2026-03-02)
- Toggle "Narração Automática" in course config step
- ElevenLabs voice picker with 21+ voices and audio preview
- Background TTS generation for all content slides after course creation
- Narration status polling in generated panel with per-slide progress
- Audio attached to slides as mp3 files accessible via editor
- Endpoint: POST /api/agent/projects/{id}/generate-narration
- Endpoint: GET /api/agent/projects/{id}/narration-status

### Bug Fixes (Complete)
- LIBRAS/VLibras toggle in export modal fixed with Shadcn Switch
- **Storyboard Polling Timeout Fix (2026-03-02)**: Polling timeout increased from 3min to 15min, progress indicator always visible, pre-check for existing storyboard, backend duplicate generation protection, final check on timeout expiry

### Features Implemented
- **Background Customization per Slide (2026-03-02)**: Users can customize slide backgrounds in the Media Config step with solid colors, gradients (2 colors + direction), uploaded images with opacity, or AI-generated images with opacity. Applies to all slide types (cover, content, quiz, summary). "Apply to All" and "Apply to Type" quick actions available.
- **Gemini Model Switch & Cost Optimization (2026-03-03)**: Replaced GPT-5.2 ($0.06/batch) with Gemini 3 Flash ($0.006/batch) for text generation. Replaced GPT Image 1 ($0.08/image) with Gemini Nano Banana ($0.02/image) for image generation. ~79% cost reduction. Added cost estimation endpoint and UI card showing breakdown before course generation, with savings comparison vs old GPT pricing. GPT-4o kept as fallback model.
- **Flipbook, HTML, Button Media Types (2026-03-03)**: Added 3 new media types in Agent Media Config: Flipbook (PDF upload or URL), HTML embed (custom code or URL/iframe), Button with external link (text, URL, color). All types generate corresponding slide elements during course generation. Edit Media button added to Editor header for returning to media configuration of existing courses.

## Key API Endpoints (Agent)
- `POST /api/agent/sessions` - Create session
- `POST /api/agent/sessions/{id}/upload` - Upload content (file, text, or URL)
- `POST /api/agent/sessions/{id}/analyze` - AI analysis
- `POST /api/agent/sessions/{id}/configure` - Set config (incl. narration settings)
- `POST /api/agent/sessions/{id}/generate-structure` - Generate structure
- `POST /api/agent/sessions/{id}/generate-storyboard` - Background storyboard gen
- `POST /api/agent/sessions/{id}/media-config` - Save per-slide media + heygen config
- `POST /api/agent/sessions/{id}/generate-course` - Generate project + HeyGen + narration
- `GET /api/agent/projects/{id}/heygen-status` - HeyGen video status
- `GET /api/agent/projects/{id}/narration-status` - Narration status
- `POST /api/agent/projects/{id}/generate-narration` - Trigger narration
- `GET /api/agent/templates` - List templates
- `GET /api/agent/courses` - List agent courses

## Key Files
- `backend/server.py` - Main server (~4700 lines)
- `backend/services/ai_agent.py` - AI agent logic (~1200 lines)
- `frontend/src/pages/Agent.jsx` - Agent page (~1730 lines)

## Prioritized Backlog
### P1
- Platform Improvement Suggestions (agent self-analysis)
### P3
- Refactor server.py into routers, ai_agent.py into modules
- Jinja2 for HTML templates
- SCORM 2004 export
