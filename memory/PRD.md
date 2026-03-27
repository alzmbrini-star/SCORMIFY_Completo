# PRD - Scormify: AI Course Authoring Platform

## Original Problem Statement
Build a full-featured AI course authoring platform with an "Intelligent Active Learning Scenario Creator" and AI Agent for course generation/modification. Core focus on stable, production-ready exports (SCORM, HTML, Video/MP4) without server crashes or timeouts.

## Core Features (Implemented)
- **AI Scenario Creator**: Interactive branching scenarios with choices, feedback, and scoring
- **AI Agent**: Course creation from storyboard with media generation
- **AI HTML Generator**: Generate interactive HTML+JS content via prompt in the Editor (Gemini)
- **AI Simulator/Game Generation**: Agent creates interactive HTML+JS simulators per module
- **AI Improvements Preview & Undo**: Before/after comparison before applying AI suggestions
- **SCORM 1.2 Export**: Full SCORM package generation with completion tracking
- **HTML Standalone Export**: Self-contained HTML courses
- **Video Export (MP4/WebM)**: 100% Client-side video generation using html2canvas + Canvas API + MediaRecorder with:
  - html2canvas for WYSIWYG slide rendering (replaced PIL backend images)
  - requestAnimationFrame continuous redraw (fixes black video bug)
  - HeyGen avatar video overlay with position/size mapping via streaming proxy
  - ElevenLabs audio capture via AudioContext + MediaStreamAudioDestination
  - MP4 (H.264+AAC) format for Windows compatibility
  - Legacy audio format support (both `url` and `src` fields)
  - Video proxy endpoint for CORS bypass (/api/proxy-video) with StreamingResponse
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
│   ├── services/ (ai_agent, scorm_exporter, html_exporter, video_exporter[legacy], asset_store)
│   └── services/export_assets/
└── frontend (React)
    ├── src/pages/ (Dashboard, Editor, Agent, Admin, Login)
    ├── src/pages/Editor/hooks/useEditorExport.js
    ├── src/components/ (editor/, scenario/, ui/)
    ├── src/utils/ (clientVideoExport.js - html2canvas+Canvas+MediaRecorder+HeyGen+Audio)
    └── src/contexts/ (AuthContext, ProjectContext)
```

## Key API Endpoints
- `GET /api/course/{id}/slides-data` - Returns lightweight JSON slide data for client-side html2canvas rendering
- `GET /api/proxy-video?url=...` - StreamingResponse proxy for HeyGen/external videos (CORS bypass)
- `GET /api/audio/{filename}` - Serves ElevenLabs TTS audio files
- `POST /api/generate-html` - AI HTML generation from prompt (Gemini)
- `POST /api/agent/courses/{id}/preview-improvements` - Preview AI suggestions
- `POST /api/agent/courses/{id}/undo-improvements` - Undo last improvement
- `POST /api/projects/{id}/fix-simulators` - Fix static simulators
- `POST /api/tutor/chat` - AI Tutor chat (CORS-enabled for LMS)
- `POST /api/course/{id}/export-scorm` - SCORM 1.2 export
- `POST /api/course/{id}/export-html` - HTML standalone export

## Credentials
- Admin: admin@scormify.com / admin123

## 3rd Party Integrations
- Google Gemini (via Emergent LLM Key)
- OpenAI GPT-4o (via Emergent LLM Key)
- HeyGen - Avatar videos (integrated in video export overlay)
- ElevenLabs - Audio narration
- ConvertAPI - PPT import

## Completed
- 2026-03-27: Fixed black video export: requestAnimationFrame continuous redraw + captureStream(30)
- 2026-03-27: Added HeyGen video overlay in client-side export with position/size mapping
- 2026-03-27: Added audio capture from HeyGen videos via AudioContext + MediaStreamDestination
- 2026-03-27: Created /api/proxy-video endpoint for CORS-safe video loading (StreamingResponse)
- 2026-03-27: Removed static_ffmpeg dependency (was causing 520 errors in production)
- 2026-03-27: Refactored companies.py and users.py DB connections
- 2026-03-27: Simplified video export UI: single "Gerar Video" button
- 2026-03-27: Switched to html2canvas for WYSIWYG slide rendering
- 2026-03-27: Switched from WebM/VP9 to MP4/H.264+AAC for Windows compatibility
- 2026-03-27: Fixed legacy audio 'url' vs 'src' data format handling
- 2026-03-27: E2E Video Export verified: 17/17 backend tests passed, all frontend flows working

## Known Issues
- HeyGen avatar generation: Blocked on API credits (video overlay in export works when URLs exist)
- Backend FFmpeg video export deprecated (K8s CPU limits) - legacy code kept inactive

## Upcoming Tasks (Prioritized)
- P1: SCORM 2004 & xAPI Export
- P1: Dashboard for analytics & scoring
- P1: Course version history
- P2: Custom badge image uploads for gamification
- P2: Cleanup legacy video_exporter.py backend code
- P2: Refactor Editor.jsx (~3700 lines) - extract dialogs to components
