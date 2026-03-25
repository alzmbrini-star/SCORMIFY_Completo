# PRD - Scormify: AI Course Authoring Platform

## Original Problem Statement
Build a full-featured AI course authoring platform with an "Intelligent Active Learning Scenario Creator" and AI Agent for course generation/modification.

## Core Features (Implemented)
- **AI Scenario Creator**: Interactive branching scenarios with choices, feedback, and scoring
- **AI Agent**: Course creation from storyboard with media generation
- **AI HTML Generator**: Generate interactive HTML+JS content via prompt in the Editor
- **AI Improvements Preview & Undo**: Before/after comparison before applying AI suggestions, with rollback capability
- **SCORM 1.2 Export**: Full SCORM package generation with completion tracking
- **HTML Standalone Export**: Self-contained HTML courses
- **Gamification System**: Configurable badges and feedback per-project
- **PPT Import**: Convert PowerPoint to course (requires ConvertAPI)
- **VLibras**: Brazilian Sign Language accessibility widget
- **AI Tutor**: AI-powered tutor embedded in exported courses
- **Fix Simulators**: Tool to detect and fix static simulators

## Architecture
```
/app
├── backend (FastAPI + MongoDB)
│   ├── server.py (ALL 15 routes registered)
│   ├── routes/ (admin, agent, ai_gen, auth, companies, deps, elevenlabs, export, gallery, gamification, heygen, projects, questions, scenarios, users, vlibras)
│   ├── services/ (ai_agent, scorm_exporter, html_exporter, asset_store)
│   └── services/export_assets/
└── frontend (React)
    ├── src/pages/ (Dashboard, Editor, Agent, Admin, Login)
    ├── src/components/ (editor/, scenario/, ui/)
    └── src/contexts/ (AuthContext, ProjectContext)
```

## Key API Endpoints
- `POST /api/generate-html` - AI HTML generation from prompt (Gemini)
- `POST /api/agent/courses/{id}/preview-improvements` - Preview AI suggestions
- `POST /api/agent/courses/{id}/undo-improvements` - Undo last improvement
- `POST /api/projects/{id}/fix-simulators` - Fix static simulators
- `POST /api/tutor/chat` - AI Tutor chat
- `POST /api/course/{id}/export-scorm` - SCORM export
- `POST /api/course/{id}/export-html` - HTML export

## Credentials
- Admin: admin@scormify.com / admin123

## 3rd Party Integrations
- Google Gemini (via Emergent LLM Key)
- OpenAI GPT-4o (via Emergent LLM Key)
- HeyGen - Avatar videos (BLOCKED)
- ElevenLabs - Audio narration
- ConvertAPI - PPT import (EXPIRED)
- VLibras - Brazilian Sign Language
