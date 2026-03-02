# PRD - Course Authoring Tool (Scormfy)

## Original Problem Statement
Build a full-featured course authoring tool that allows users to create interactive courses, export them to SCORM/HTML format, and include accessibility features like VLibras (Brazilian Sign Language) translation. Additionally, build an AI Instructional Design Agent that transforms raw content into complete courses.

## Core Requirements
- Course creation with slides, elements, and multimedia
- SCORM 1.2 and standalone HTML export
- Text-to-Speech (ElevenLabs integration)
- AI content generation (Google Gemini)
- VLibras LIBRAS accessibility
- HeyGen avatar video generation
- PowerPoint import (ConvertAPI)
- Quiz/assessment support
- AI Tutor integration
- Mobile responsive course player
- **AI Instructional Design Agent** (GPT-5.2)

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
- Quiz/assessment system
- AI Tutor for exported courses
- Mobile-responsive course player

### VLibras Integration (Improved - 2026-02-28)
- CORS Proxy handling both VLibras domains (dicionario2 + traducao2)
- XHR monkey-patch in exports intercepts both domains
- Avatar active with fingerspelling fallback

### AI Instructional Design Agent - Phase 1 MVP (2026-03-02)
**Backend** (`/app/backend/services/ai_agent.py`):
- Content analysis with GPT-5.2 (extracts topics, difficulty, duration, gaps)
- Course structure generation (modules, slides, objectives, competencies)
- Storyboard generation (batch processing to avoid timeouts, background task)
- Course creation from storyboard (generates Scormfy Project with slides, quizzes)
- Chat with agent for adjustments and questions

**API Endpoints**:
- `POST /api/agent/sessions` - Create session
- `POST /api/agent/sessions/{id}/upload` - Upload content (file or text)
- `POST /api/agent/sessions/{id}/analyze` - AI content analysis
- `POST /api/agent/sessions/{id}/configure` - Set course parameters
- `POST /api/agent/sessions/{id}/generate-structure` - Generate course structure (now accepts optional templateId)
- `POST /api/agent/sessions/{id}/generate-storyboard` - Generate storyboard (background task)
- `POST /api/agent/sessions/{id}/generate-course` - Generate Scormfy project (now marks createdByAgent)
- `POST /api/agent/sessions/{id}/chat` - Chat with agent
- `GET /api/agent/sessions/{id}` - Get session state (polling)

**Frontend** (`/app/frontend/src/pages/Agent.jsx`):
- Hybrid interface: chat panel + visual content panels
- 6-step wizard: Upload > Analyze > Configure > Structure > Storyboard > Generate
- File upload (PDF, PPT, DOC, TXT) with ConvertAPI text extraction
- Text paste input
- Real-time polling for background tasks
- Navigate directly to editor after course generation

**Tested**: 15/15 backend + frontend tests passed (iteration_1.json)

### AI Agent - Phase 2: Course Editing & Visual Templates (2026-03-02)
**Backend** (`/app/backend/server.py` + `/app/backend/services/ai_agent.py`):
- **Visual Templates**: 6 course templates (Onboarding, Compliance, Técnico, Soft Skills, Saúde e Segurança, Vendas)
  - Each template has default configuration (depth, duration, modules, interactivity, format)
  - Structure generation can use templates as base via `generate_structure_from_template()`
- **Course Editing**: AI-powered course analysis and improvement application
  - `analyze_existing_course()`: Evaluates course quality, identifies strengths, improvements, missing elements
  - `apply_course_improvements()`: Generates updated content for selected improvements, adds new slides
- Projects created by agent now marked with `createdByAgent: true` flag

**New API Endpoints**:
- `GET /api/agent/templates` - List 6 available course templates
- `GET /api/agent/courses` - List courses created by the AI agent (filtered by createdByAgent flag)
- `POST /api/agent/courses/{id}/analyze` - AI analysis of existing course with improvement suggestions
- `POST /api/agent/courses/{id}/apply-improvements` - Apply selected improvements to a course

**Frontend** (`/app/frontend/src/pages/Agent.jsx`):
- **Mode Selector**: Initial screen with "Criar Novo Curso" and "Editar Curso Existente" cards
- **Template Grid**: 6 template cards in config step with auto-config population on selection
- **Edit Mode**: 3-step flow (Select Course > Review Analysis > Apply Improvements)
  - Course list showing agent-created courses
  - Score card with overall quality assessment
  - Improvement suggestions with checkbox selection (priority, type, description)
  - Missing elements and suggested new slides display
  - Apply selected improvements button

**Tested**: 27/27 backend + frontend tests passed (iteration_43.json)

## Prioritized Backlog

### P1 - Platform Improvement Suggestions
- Agent analyzes its own process and suggests improvements for Scormfy platform

### P2 - Enhanced Content Input
- Accept PDF, DOCX, and website links as source content
- HeyGen avatar integration for welcome videos
- AI Tutor auto-configuration per course

### P2 - Refactoring
- Refactor exporters to use Jinja2 templates
- Refactor monolithic server.py into separate routers

### P3 - Future
- SCORM 2004 export support
- Auto-generate TTS narration for each slide via ElevenLabs
- Auto-generate quiz questions with AI
- Timeline/animation suggestions

## Key Files
- `backend/server.py` - Main server with all API endpoints
- `backend/services/ai_agent.py` - AI agent service (GPT-5.2) with templates & editing
- `backend/services/scorm_exporter.py` - SCORM export
- `backend/services/html_exporter.py` - HTML export
- `backend/services/export_assets/player.js` - Course player
- `frontend/src/pages/Agent.jsx` - AI Agent page (mode selector + create/edit flows)
- `frontend/src/pages/Editor.jsx` - Course editor
- `frontend/src/pages/Dashboard.jsx` - Project dashboard
- `frontend/src/App.js` - Routes
