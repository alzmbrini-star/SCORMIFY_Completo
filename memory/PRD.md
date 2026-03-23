# PRD - Scormify: AI Course Authoring Platform

## Original Problem Statement
Build a full-featured AI course authoring platform with an "Intelligent Active Learning Scenario Creator" and AI Agent for course generation/modification.

## Core Features (Implemented)
- **AI Scenario Creator**: Interactive branching scenarios with choices, feedback, and scoring
- **AI Agent**: Course creation from storyboard with media generation
- **SCORM 1.2 Export**: Full SCORM package generation with completion tracking
- **HTML Standalone Export**: Self-contained HTML courses
- **Gamification System**: Configurable badges and feedback per-project
- **PPT Import**: Convert PowerPoint to course (requires ConvertAPI)
- **VLibras**: Brazilian Sign Language accessibility widget
- **AI Tutor**: AI-powered tutor with configurable backend URL

## Architecture
```
/app
├── backend (FastAPI + MongoDB)
│   ├── server.py (main app, startup tasks)
│   ├── routes/ (agent, export, auth, projects, gamification, admin)
│   ├── services/ (ai_agent, scorm_exporter, html_exporter, asset_store)
│   └── services/export_assets/ (player.js, scenario-controller.js, quiz-controller.js, scorm-api.js)
└── frontend (React)
    ├── src/pages/ (Dashboard, Editor, Agent, Admin, Login)
    ├── src/components/ (editor/, scenario/, ui/)
    └── src/contexts/ (AuthContext, ProjectContext)
```

## Key Technical Decisions
- **Scenario Scoring**: Based on % of "ideal decisions" (not points)
- **SCORM Completion**: Event-driven via CoursePlayer.onScenarioComplete/onQuizComplete
- **Image Generation**: Parallel (5 concurrent) using asyncio.gather with semaphore
- **MongoDB Atlas Support**: Increased timeouts (30s server/connect, 60s socket), retryWrites/retryReads
- **Asset Persistence**: Batch queries on startup instead of individual find_one per asset

## Credentials
- Admin: admin@scormify.com / admin123

## 3rd Party Integrations
- Google Gemini (via Emergent LLM Key) - AI generation
- OpenAI GPT-4o (via Emergent LLM Key)
- HeyGen - Avatar videos (BLOCKED - user credits insufficient)
- ElevenLabs - Audio narration (requires user API key)
- ConvertAPI - PPT import (EXPIRED trial - user needs new key)
- VLibras - Brazilian Sign Language accessibility
