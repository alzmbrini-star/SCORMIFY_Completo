# PRD - Scormify: AI Course Authoring Platform

## Original Problem Statement
Build a full-featured AI course authoring platform with an "Intelligent Active Learning Scenario Creator" and AI Agent for course generation/modification.

## Core Features (Implemented)
- **AI Scenario Creator**: Interactive branching scenarios with choices, feedback, and scoring
- **AI Agent**: Course creation from storyboard with media generation
- **AI HTML Generator**: Generate interactive HTML+JS content via prompt in the Editor (Gemini)
- **AI Simulator/Game Generation**: Agent creates interactive HTML+JS simulators per module (calculators, flashcards, memory games, drag-and-drop, quizzes, timelines, etc.)
- **AI Improvements Preview & Undo**: Before/after comparison before applying AI suggestions, with rollback capability
- **SCORM 1.2 Export**: Full SCORM package generation with completion tracking
- **HTML Standalone Export**: Self-contained HTML courses
- **Video Export (WebM)**: Client-side video generation using Canvas API + MediaRecorder (browser-based, no server limits)
- **Gamification System**: Configurable badges and feedback per-project
- **PPT Import**: Convert PowerPoint to course (ConvertAPI - Active)
- **VLibras**: Brazilian Sign Language accessibility widget
- **AI Tutor**: AI-powered tutor embedded in exported courses (triple-layer CORS for cross-origin LMS access)
- **Fix Simulators**: Tool to detect and fix static simulators

## Architecture
```
/app
├── backend (FastAPI + MongoDB)
│   ├── server.py (ALL routes registered, TutorCorsMiddleware)
│   ├── start.sh (Startup script)
│   ├── routes/ (admin, agent, ai_gen, auth, companies, deps, elevenlabs, export, gallery, gamification, heygen, projects, questions, scenarios, users, vlibras)
│   ├── services/ (ai_agent, scorm_exporter, html_exporter, video_exporter, asset_store)
│   └── services/export_assets/
└── frontend (React)
    ├── src/pages/ (Dashboard, Editor, Agent, Admin, Login)
    ├── src/components/ (editor/, scenario/, ui/)
    ├── src/utils/ (clientVideoExport.js - Canvas+MediaRecorder video gen)
    └── src/contexts/ (AuthContext, ProjectContext)
```

## Key API Endpoints
- `POST /api/course/{id}/export-video-frames` - Returns slide images as base64 for client-side video generation
- `POST /api/generate-html` - AI HTML generation from prompt (Gemini)
- `POST /api/agent/courses/{id}/preview-improvements` - Preview AI suggestions
- `POST /api/agent/courses/{id}/undo-improvements` - Undo last improvement
- `POST /api/projects/{id}/fix-simulators` - Fix static simulators
- `POST /api/tutor/chat` - AI Tutor chat (CORS-enabled for LMS)
- `POST /api/course/{id}/export-scorm` - SCORM export
- `POST /api/course/{id}/export-html` - HTML export

## Credentials
- Admin: admin@scormify.com / admin123

## 3rd Party Integrations
- Google Gemini (via Emergent LLM Key)
- OpenAI GPT-4o (via Emergent LLM Key)
- HeyGen - Avatar videos (BLOCKED - no credits)
- ElevenLabs - Audio narration
- ConvertAPI - PPT import (Active)
- VLibras - Brazilian Sign Language

## Completed (2026-03-27)
- Client-side Video Export (Canvas + MediaRecorder) - fully tested, 100% pass rate
- Refactored companies.py and users.py DB connections to use routes.deps pattern
- Simplified video export UI: single "Gerar Video (WebM)" button with progress bar
- Fixed blob URL download handling in export dialog

## Known Issues
- HeyGen Video: Blocked (insufficient credits)
- Backend FFmpeg video export deprecated (K8s CPU limits)

## Upcoming Tasks (Prioritized)
- P1: SCORM 2004 & xAPI Export
- P1: Dashboard for analytics & scoring
- P1: Course version history
- P2: Custom badge image uploads for gamification
- P2: Cleanup legacy video_exporter.py backend code
- P2: Refactor Editor.jsx (~3700 lines) - extract dialogs to components

## Status: All P0 issues resolved. Client-side video export working.
