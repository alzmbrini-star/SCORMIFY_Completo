# PRD - Course Authoring Tool (Scormfy)

## Original Problem Statement
Build a full-featured course authoring tool with AI-powered course generation, SCORM export, VLibras accessibility, and multimedia integration.

## Architecture
- **Frontend**: React + Tailwind + Shadcn/UI
- **Backend**: FastAPI + MongoDB
- **AI**: OpenAI GPT-5.2 (text), GPT Image 1 (images) via Emergent LLM Key
- **Integrations**: ElevenLabs TTS, Google Gemini, HeyGen, ConvertAPI, VLibras

## What's Been Implemented

### Core Features (Complete)
- Full course editor, SCORM 1.2 export, HTML export, TTS, AI scripts, HeyGen avatars, PPT import, quiz system, AI Tutor, mobile player

### VLibras Integration (Complete)
- CORS Proxy for both VLibras domains, XHR monkey-patch in exports

### AI Agent - Phase 1 MVP (Complete)
- Content upload -> AI analysis -> structure -> storyboard -> course generation
- Background tasks with polling, chat with agent

### AI Agent - Phase 2: Editing & Templates (Complete - 2026-03-02)
- 6 Visual Templates, Course Editing with AI analysis + improvements
- Mode Selector: "Criar Novo Curso" vs "Editar Curso Existente"

### Visual Improvements (Complete - 2026-03-02)
- 6 Professional Color Palettes, two-column layouts, header bars, styled typography
- Title slides with module trail, quiz slides with indicators, summary slides

### Per-Slide Media Configuration (Complete - 2026-03-02)
- **New "Midia" step** (step 5) between Storyboard and Generate in create flow
- **5 media types per content slide**:
  - **Imagem IA**: Photorealistic images via GPT Image 1 (contextual prompts based on slide content)
  - **YouTube**: Embed YouTube videos (supports watch, short, and embed URL formats)
  - **Vimeo**: Embed Vimeo videos
  - **Avatar HeyGen**: Full avatar video generation (see below)
  - **Sem midia**: Text-only, full-width layout
- **Quick-apply buttons**: "Todas: Imagem IA" and "Todas: Sem midia"
- **Media summary**: Shows count per type with credit usage warning for AI images

### Content Depth Enhancement (Complete - 2026-03-02)
- AI prompts generate 100+ words per content slide with structured HTML
- Summary slides have 400+ words of comprehensive review

### Functional Scormfy Quizzes (Complete - 2026-03-02)
- Agent creates `type: 'quiz'` elements with quizConfig and questionIds
- Questions saved to MongoDB with alternatives, correctIndex, explanation

### Full HeyGen Avatar Integration (Complete - 2026-03-02)
- **Avatar Picker**: Grid of HeyGen avatars with preview images in media config step
- **Voice Picker**: Portuguese voice selection with preview audio playback
- **Auto-Generation**: When course is generated, HeyGen videos are triggered in background
- **Status Tracking**: Generated panel auto-polls video status every 15s
- **Slide Updates**: Completed videos automatically replace processing placeholders
- **Backend**: Background task triggers HeyGen API, stores video_id mappings, status endpoint
- **Endpoint**: `GET /api/agent/projects/{id}/heygen-status` - polls all pending videos

### Bug Fixes (Complete - 2026-03-02)
- LIBRAS/VLibras toggle in export modal fixed with Shadcn Switch

## API Endpoints (Agent)
- `POST /api/agent/sessions` - Create session
- `POST /api/agent/sessions/{id}/upload` - Upload content
- `POST /api/agent/sessions/{id}/analyze` - AI analysis
- `POST /api/agent/sessions/{id}/configure` - Set config
- `POST /api/agent/sessions/{id}/generate-structure` - Generate structure (optional templateId)
- `POST /api/agent/sessions/{id}/generate-storyboard` - Background storyboard gen
- `POST /api/agent/sessions/{id}/media-config` - Save per-slide media config with heygen settings
- `POST /api/agent/sessions/{id}/generate-course` - Generate project with media + HeyGen background
- `POST /api/agent/sessions/{id}/chat` - Chat with agent
- `GET /api/agent/templates` - List templates
- `GET /api/agent/courses` - List agent-created courses
- `GET /api/agent/projects/{id}/heygen-status` - Check HeyGen video status
- `POST /api/agent/courses/{id}/analyze` - AI course analysis
- `POST /api/agent/courses/{id}/apply-improvements` - Apply improvements

## Key Files
- `backend/server.py` - Main server with all API routes
- `backend/services/ai_agent.py` - AI agent: visual generation, media config, templates, editing, heygen
- `frontend/src/pages/Agent.jsx` - Agent page: mode selector, 7-step create flow, edit flow

## Prioritized Backlog
### P1
- Platform Improvement Suggestions (agent self-analysis)
### P2
- Enhanced Content Input (PDF, DOCX, links)
- ElevenLabs narration auto-generation per slide
### P3
- Refactor server.py into routers, Jinja2 for HTML templates
- SCORM 2004 export
