# PRD - Scormify: AI Course Authoring Platform

## Original Problem Statement
Build a full-featured AI course authoring platform with an "Intelligent Active Learning Scenario Creator" and AI Agent for course generation/modification.

## Core Features (Implemented)
- **AI Scenario Creator**: Interactive branching scenarios with choices, feedback, and scoring
- **AI Agent**: Course creation from storyboard with media generation
- **AI HTML Generator**: Generate interactive HTML+JS content via prompt in the Editor (Gemini)
- **AI Simulator/Game Generation**: Agent creates interactive HTML+JS simulators per module
- **AI Improvements Preview & Undo**: Before/after comparison before applying AI suggestions
- **SCORM 1.2 Export**: Full SCORM package generation with completion tracking
- **HTML Standalone Export**: Self-contained HTML courses
- **Video Export (WebM)**: Client-side video generation using Canvas API + MediaRecorder with:
  - requestAnimationFrame continuous redraw (fixes black video bug)
  - HeyGen avatar video overlay with position/size mapping
  - Audio capture from HeyGen videos via AudioContext
  - Video proxy endpoint for CORS bypass (/api/proxy-video)
- **Gamification System**: Configurable badges and feedback per-project
- **PPT Import**: Convert PowerPoint to course (ConvertAPI)
- **VLibras**: Brazilian Sign Language accessibility widget
- **AI Tutor**: AI-powered tutor embedded in exported courses
- **Fix Simulators**: Tool to detect and fix static simulators

## Architecture
```
/app
├── backend (FastAPI + MongoDB)
│   ├── server.py
│   ├── routes/ (admin, agent, ai_gen, auth, companies, deps, elevenlabs, export, gallery, gamification, heygen, projects, questions, scenarios, users, vlibras)
│   ├── services/ (ai_agent, scorm_exporter, html_exporter, video_exporter, asset_store)
│   └── services/export_assets/
└── frontend (React)
    ├── src/pages/ (Dashboard, Editor, Agent, Admin, Login)
    ├── src/components/ (editor/, scenario/, ui/)
    ├── src/utils/ (clientVideoExport.js - Canvas+MediaRecorder+HeyGen overlay)
    └── src/contexts/ (AuthContext, ProjectContext)
```

## Key API Endpoints
- `POST /api/course/{id}/export-video-frames` - Returns slide images as base64 + videoElements metadata
- `GET /api/proxy-video?url=...` - Proxies HeyGen/external videos for CORS bypass
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
- HeyGen - Avatar videos (integrated in video export overlay)
- ElevenLabs - Audio narration
- ConvertAPI - PPT import

## Completed (2026-03-27)
- Fixed black video export: requestAnimationFrame continuous redraw + captureStream(30)
- Added HeyGen video overlay in client-side export with position/size mapping
- Added audio capture from HeyGen videos via AudioContext + MediaStreamDestination
- Created /api/proxy-video endpoint for CORS-safe video loading
- Backend returns videoElements metadata in export-video-frames response
- Removed static_ffmpeg dependency (was causing 520 errors in production)
- Removed startup_ensure_ffmpeg event handler
- Refactored companies.py and users.py DB connections to use routes.deps pattern
- Simplified video export UI: single "Gerar Video (WebM)" button
- Fixed blob URL download handling in export dialog

## Known Issues
- HeyGen avatar generation: Blocked on API credits (video overlay in export works)
- Backend FFmpeg video export deprecated (K8s CPU limits)

## Upcoming Tasks (Prioritized)
- P1: SCORM 2004 & xAPI Export
- P1: Dashboard for analytics & scoring
- P1: Course version history
- P2: Custom badge image uploads for gamification
- P2: Cleanup legacy video_exporter.py backend code
- P2: Refactor Editor.jsx (~3700 lines) - extract dialogs to components
