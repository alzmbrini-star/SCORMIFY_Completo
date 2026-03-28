# PRD - Scormify: AI Course Authoring Platform

## Original Problem Statement
Build a full-featured AI course authoring platform with an "Intelligent Active Learning Scenario Creator" and AI Agent for course generation/modification. Core focus on stable, production-ready exports (SCORM, HTML, Video/MP4) without server crashes or timeouts.

## Core Features (Implemented)
- **AI Scenario Creator**: Interactive branching scenarios with choices, feedback, and scoring
- **AI Agent**: Course creation from storyboard with media generation
- **AI HTML Generator**: Generate interactive HTML+JS content via prompt in the Editor (Gemini)
- **AI Simulator/Game Generation**: Agent creates interactive HTML+JS simulators per module
- **AI Improvements Preview & Undo**: Before/after comparison before applying AI suggestions
- **AI Avatar Scene Suggestions**: Agent suggests avatar scenes during course analysis with:
  - Narration script, background description, avatar position
  - Auto-generation of background image (Gemini), ElevenLabs narration, HeyGen avatar video on apply
  - Per-course configurable avatar scene limit
  - Violet-themed UI cards for avatar suggestions with script preview
  - Real-time generation progress polling (background, audio, video status)
- **SCORM 1.2 Export**: Full SCORM package generation with completion tracking
- **HTML Standalone Export**: Self-contained HTML courses
- **Video Export (MP4/WebM)**: 100% Client-side video generation using html2canvas + Canvas API + MediaRecorder
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
    ├── src/pages/Agent/components/CoursePanels.jsx (CourseReviewPanel, EditResultPanel, PreviewPanel, StatusBadge)
    ├── src/components/ (editor/, scenario/, ui/)
    ├── src/utils/ (clientVideoExport.js)
    └── src/contexts/ (AuthContext, ProjectContext)
```

## Key API Endpoints
- `GET /api/agent/projects/{id}/avatar-settings` - Get avatar scene settings per project
- `PUT /api/agent/projects/{id}/avatar-settings` - Update avatar scene settings (maxScenes, defaultAvatarId, defaultVoiceId)
- `GET /api/agent/projects/{id}/avatar-generation-status` - Poll avatar scene generation progress
- `POST /api/agent/courses/{id}/analyze` - Analyze course (now includes avatar_scene type improvements)
- `POST /api/agent/courses/{id}/apply-improvements` - Apply improvements (returns avatarScenesTriggered)
- `GET /api/course/{id}/slides-data` - JSON slide data for client-side rendering
- `GET /api/proxy-video?url=...` - StreamingResponse proxy for HeyGen/external videos
- `GET /api/audio/{filename}` - ElevenLabs TTS audio files

## Credentials
- Admin: admin@scormify.com / admin123

## 3rd Party Integrations
- Google Gemini (via Emergent LLM Key) - Text + Image generation (Nano Banana)
- OpenAI GPT-4o (via Emergent LLM Key)
- HeyGen - Avatar videos (user API key)
- ElevenLabs - Audio narration (user API key)
- ConvertAPI - PPT import (user API key)

## Completed
- 2026-03-28: Avatar Scene Suggestions feature - AI Agent suggests avatar scenes during analysis, auto-triggers generation on apply
- 2026-03-28: Avatar Settings per-course (maxScenes, defaultAvatarId, defaultVoiceId)
- 2026-03-28: Avatar generation progress polling with StatusBadge component
- 2026-03-28: Violet-themed UI for avatar scene improvements in CourseReviewPanel
- 2026-03-27: E2E Video Export verified: 17/17 backend tests, all frontend flows working
- 2026-03-27: Client-side video export (html2canvas + MediaRecorder + AudioContext)
- 2026-03-27: Fixed legacy audio 'url' vs 'src' format handling

## Upcoming Tasks (Prioritized)
- P1: SCORM 2004 & xAPI Export
- P1: Dashboard for analytics & scoring
- P1: Course version history
- P2: Custom badge image uploads for gamification
- P2: Cleanup legacy video_exporter.py backend code
- P2: Refactor Editor.jsx (~3700 lines) - extract dialogs to components
