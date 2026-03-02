# PRD - Course Authoring Tool (Scormfy)

## Original Problem Statement
Build a full-featured course authoring tool that allows users to create interactive courses, export them to SCORM/HTML format, and include accessibility features like VLibras (Brazilian Sign Language) translation. Additionally, build an AI Instructional Design Agent that transforms raw content into complete courses.

## Architecture
- **Frontend**: React + Tailwind + Shadcn/UI
- **Backend**: FastAPI + MongoDB
- **AI**: OpenAI GPT-5.2 via Emergent LLM Key (emergentintegrations)
- **Integrations**: ElevenLabs TTS, Google Gemini, HeyGen, ConvertAPI, VLibras

## What's Been Implemented

### Core Features (Complete)
- Full course editor with drag-and-drop elements
- SCORM 1.2 export with quiz support
- Standalone HTML export
- Text-to-Speech via ElevenLabs
- AI script generation via Gemini
- HeyGen avatar video generation
- PowerPoint import via ConvertAPI
- Quiz/assessment system, AI Tutor, mobile-responsive player

### VLibras Integration (Complete)
- CORS Proxy handling both VLibras domains (dicionario2 + traducao2)
- XHR monkey-patch in exports

### AI Instructional Design Agent - Phase 1 MVP (Complete)
- Full end-to-end flow: content upload → AI analysis → structure → storyboard → course generation
- Background task processing for storyboard with frontend polling
- Chat with agent

### AI Agent - Phase 2: Course Editing & Visual Templates (Complete - 2026-03-02)
- **Visual Templates**: 6 course templates (Onboarding, Compliance, Técnico, Soft Skills, Saúde e Segurança, Vendas)
- **Course Editing**: AI-powered analysis + improvement suggestions + selective application
- **Mode Selector**: "Criar Novo Curso" vs "Editar Curso Existente"
- Tested: 27/27 tests (iteration_43.json)

### Visual Improvements for Generated Courses (Complete - 2026-03-02)
- **6 Professional Color Palettes**: Emerald, violet, blue, green, red, amber - selected based on course title hash
- **Professional Backgrounds**: Dark primary for title/quiz/summary slides, light contentBg for content slides
- **Two-Column Layout**: Content slides have text (left 55%) + stock image (right 35%)
- **Header Bars**: Colored accent bars at top of each slide with module name
- **Stock Images**: Auto-downloaded from picsum.photos, saved to project assets for SCORM compatibility
- **Styled HTML Elements**: Professional typography with proper font sizes, colors, spacing
- **Title Slide Enhancements**: Accent bar, large centered title, subtitle, "Trilha do Curso" module trail
- **Quiz Slides**: Dark background with "Hora de Praticar!" indicator and question preview cards
- **Summary Slides**: Dark background with styled key takeaways
- Tested: 20/20 backend + 100% frontend (iteration_44.json)

## API Endpoints (Agent-specific)
- `POST /api/agent/sessions` - Create session
- `POST /api/agent/sessions/{id}/upload` - Upload content
- `POST /api/agent/sessions/{id}/analyze` - AI analysis
- `POST /api/agent/sessions/{id}/configure` - Set config
- `POST /api/agent/sessions/{id}/generate-structure` - Generate structure (accepts optional templateId)
- `POST /api/agent/sessions/{id}/generate-storyboard` - Background storyboard gen
- `POST /api/agent/sessions/{id}/generate-course` - Generate Scormfy project
- `POST /api/agent/sessions/{id}/chat` - Chat with agent
- `GET /api/agent/templates` - List 6 templates
- `GET /api/agent/courses` - List agent-created courses
- `POST /api/agent/courses/{id}/analyze` - AI course analysis
- `POST /api/agent/courses/{id}/apply-improvements` - Apply improvements

## Key Files
- `backend/server.py` - Main server with all API routes
- `backend/services/ai_agent.py` - AI agent service with visual generation, templates, editing
- `frontend/src/pages/Agent.jsx` - Agent page (mode selector + create/edit flows)
- `frontend/src/pages/Editor.jsx` - Course editor

## Prioritized Backlog
### P1
- Platform Improvement Suggestions (agent self-analysis)
### P2
- Enhanced Content Input (PDF, DOCX, links)
- HeyGen avatar + ElevenLabs narration integration
- AI Tutor auto-config per course
- Topic-relevant image search (replace picsum with keyword-based search API)
### P3
- Refactor server.py into routers, use Jinja2 for HTML templates
- SCORM 2004 export
