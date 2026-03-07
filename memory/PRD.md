# PRD - Course Authoring Agent (Scormfy)

## Problem Statement
Build an advanced Instructional Design AI Agent that generates SCORM-compliant courses from content (PDF, PPT, DOC, or text). The application includes an AI agent pipeline, a full slide editor, and export capabilities.

## Architecture
- **Frontend**: React 18 + Tailwind CSS + Shadcn/UI
- **Backend**: FastAPI + Motor (async MongoDB)
- **Database**: MongoDB
- **Integrations**: OpenAI GPT-4o, Google Gemini 3 Flash & Nano Banana, ElevenLabs TTS, HeyGen Avatar Video, ConvertAPI, VLibras

## Core Features (Implemented)
### Auth & Dashboard
- JWT auth with login/register
- Admin panel for user/key management
- Project dashboard with CRUD
- **Dashboard metrics panel** (total courses, slides, exports)

### AI Agent Pipeline
- Multi-step course creation wizard
- Course editing mode with AI-powered improvement suggestions
- Chat interface for real-time agent interaction

### Slide Editor
- Full WYSIWYG editor with drag & drop elements
- Rich text editor with AI generation
- Slide thumbnails with live preview
- Animation system, background images, layer management

### Media & Audio
- ElevenLabs TTS narration with voice selection
- Audio recording and upload
- Volume controls per audio track

### HeyGen Integration
- Single-slide avatar video generation
- PPT-to-Video multi-scene generation
- Video library management

### Export
- SCORM 1.2 package export (with AI Tutor)
- HTML standalone export (with AI Tutor)
- Video export (MP4)

### AI Tutor (NEW)
- Embedded chat widget in exported SCORM and HTML courses
- Uses Gemini 3 Flash for contextual Q&A
- Answers ONLY based on course content
- Message limit per session
- Suggested questions support
- Admin configurable (name, prompt, limits)

### Accessibility
- VLibras Brazilian Sign Language integration

## Recent Changes

### Mar 7, 2026 - Dashboard Metrics & AI Tutor
- Added `GET /api/dashboard/metrics` endpoint (totalCourses, totalSlides, totalExports)
- Added export logging to `export_logs` collection
- Added metrics cards to Dashboard UI (3 cards with icons)
- Integrated AI Tutor into HTML export (was SCORM-only before)
- Added `_generate_tutor_block()` to html_exporter.py
- Fixed tutor.js to support CSS inlining for HTML exports

### Mar 7, 2026 - Frontend Refactoring
- Editor.jsx: 5709 -> 3639 lines (36% reduction)
- Agent.jsx: 3593 -> 1024 lines (71% reduction)

## File Structure
```
frontend/src/pages/
├── Dashboard.jsx           (metrics + project list)
├── Editor.jsx              (3639 lines - orchestrator)
├── Editor/
│   ├── utils.js
│   ├── hooks/              (5 hooks)
│   └── components/         (5 components)
├── Agent.jsx               (1024 lines - orchestrator)
└── Agent/
    └── components/         (5 panels)

backend/
├── routes/
│   ├── admin.py            (tutor settings + chat + metrics)
│   └── export.py           (SCORM/HTML/Video + export logging)
├── services/
│   ├── scorm_exporter.py   (tutor integration)
│   ├── html_exporter.py    (tutor integration added)
│   └── export_assets/
│       ├── tutor.js        (chat widget)
│       └── tutor.css       (chat styles)
```

## Known Issues
- HeyGen Video Generation: Blocked by user's API credits being 0 (external)

## Backlog
### P0
- SCORM 2004 & xAPI Export implementation
### P1
- Further Editor.jsx dialog extraction (~1200 lines)

## Credentials
- Admin: admin@scormify.com / admin123
