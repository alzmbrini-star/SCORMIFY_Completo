# PRD - Course Authoring Agent (Scormfy)

## Problem Statement
Build an advanced Instructional Design AI Agent that generates SCORM-compliant courses from content (PDF, PPT, DOC, or text). The application includes an AI agent pipeline, a full slide editor, and export capabilities.

## Architecture
- **Frontend**: React 18 + Tailwind CSS + Shadcn/UI
- **Backend**: FastAPI + Motor (async MongoDB)
- **Database**: MongoDB
- **Integrations**: OpenAI GPT-4o, Google Gemini 2.5 Flash & Nano Banana, ElevenLabs TTS, HeyGen Avatar Video, ConvertAPI, VLibras

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

### AI Tutor
- Embedded chat widget in exported SCORM and HTML courses
- Uses Gemini 3 Flash for contextual Q&A
- Answers ONLY based on course content
- Slide-aware context

### Interactive Scenario Creator (NEW - Mar 11, 2026)
- AI-powered generation of decision-tree learning scenarios using Gemini 2.5 Flash
- Complete CRUD API for scenarios (create, read, update, delete, regenerate)
- ScenarioCreator dialog with configurable inputs: theme, objectives, audience, complexity, industry, duration
- **Font size control** in ElementProperties panel (same pattern as Quiz: 12px-28px selector)
- Interactive ScenarioPlayer component with font-size-aware rendering:
  - Decision tree navigation with choices (A, B, C...)
  - Character-driven narratives
  - Adaptive feedback after each choice (optimal/non-optimal)
  - Points accumulation
  - Multiple endings (good, neutral, bad) with score
  - Restart capability
- Integrated as a slide element type ('scenario') in the editor
- Renders in SlideCanvas (editor), CoursePreview, and SplitPreview
- Full export support in SCORM and HTML packages (scenario-controller.js with fontSize support)

### Accessibility
- VLibras Brazilian Sign Language integration

## File Structure
```
frontend/src/
├── components/
│   ├── scenario/
│   │   ├── ScenarioCreator.jsx    (AI generation dialog)
│   │   └── ScenarioPlayer.jsx     (interactive decision tree player)
│   ├── quiz/
│   │   ├── QuizGenerator.jsx
│   │   └── QuizPlayer.jsx
│   └── editor/
│       ├── SlideCanvas.jsx         (scenario element rendering)
│       ├── CoursePreview.jsx        (scenario player in preview)
│       └── SplitPreview.jsx         (scenario player in split)
├── pages/
│   ├── Dashboard.jsx
│   ├── Editor.jsx                  (scenario button + handler)
│   └── Agent.jsx

backend/
├── routes/
│   ├── scenarios.py               (CRUD + AI generation endpoints)
│   ├── admin.py
│   └── export.py
├── services/
│   ├── scenario_service.py        (Gemini AI generation logic)
│   ├── scorm_exporter.py          (scenario support added)
│   ├── html_exporter.py           (ScenarioController JS added)
│   └── export_assets/
│       ├── scenario-controller.js (decision tree player for exports)
│       ├── player.js              (scenario case added)
│       └── player_template.html   (scenario script tag added)
├── models.py                      (type='scenario', scenarioData field)
└── server.py                      (scenarios router registered)
```

## Known Issues
- HeyGen Video Generation: Blocked by user's API credits being 0 (external)

## Backlog
### P0
- Scenario Creator Phase 4 enhancements: advanced analytics, scoring dashboard
- SCORM 2004 & xAPI Export implementation
### P1
- Further Editor.jsx dialog extraction (~1200 lines)
- Scenario collaborative mode (multiple learners)
### P2
- Advanced AI Tutor interactivity features
- Gamification elements (badges, leaderboard)
### Cancelled
- Synthesia Integration (user decided cost was too high)

## Credentials
- Admin: admin@scormify.com / admin123
