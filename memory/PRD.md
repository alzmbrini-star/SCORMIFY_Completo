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

### AI Agent Pipeline
- Multi-step course creation wizard (Upload -> Analyze -> Configure -> Structure -> Storyboard -> Media Config -> Generate)
- Course editing mode with AI-powered improvement suggestions
- Chat interface for real-time agent interaction
- Content analysis from PDF/PPT/DOC/URL/text

### Slide Editor
- Full WYSIWYG editor with drag & drop elements
- Element types: text, image, shape, video, button, HTML, flipbook, quiz
- Rich text editor with AI generation
- Slide thumbnails with live preview
- Layer management with drag reorder
- Animation system (entrance effects)
- Background images and gradients
- Element properties panel

### Media & Audio
- ElevenLabs TTS narration with voice selection
- Audio recording and upload
- Global and per-slide audio tracks
- Volume controls per audio track
- AI-generated narration scripts

### HeyGen Integration
- Single-slide avatar video generation
- PPT-to-Video multi-scene generation
- Avatar & voice selection with filters
- Video library management
- Script generation (manual, AI, OCR)

### Export
- SCORM 1.2 package export
- HTML standalone export
- Video export (MP4)

### Accessibility
- VLibras Brazilian Sign Language integration
- Per-slide LIBRAS scripts

## Recent Changes

### Feb 2026 - Frontend Refactoring (P1)
**Editor.jsx**: Reduced from 5709 to 3639 lines (36% reduction)
- Extracted 5 custom hooks: useHeygenIntegration, useEditorExport, useEditorTTS, useEditorAudio, useEditorAI
- Extracted 5 components: SortableSlideItem, SortableLayerItem, SlideThumbnailContent, ElementProperties, SlideProperties
- Created shared utils.js with helper functions

**Agent.jsx**: Reduced from 3593 to 1024 lines (71% reduction)
- Extracted 5 panel components: ConfigPanel, StoryboardPanel, MediaConfigPanel, GeneratedPanel, CoursePanels

## File Structure (Post-Refactoring)
```
frontend/src/pages/
├── Editor.jsx              (3639 lines - orchestrator)
├── Editor/
│   ├── utils.js            (shared helpers)
│   ├── hooks/
│   │   ├── useHeygenIntegration.js
│   │   ├── useEditorExport.js
│   │   ├── useEditorTTS.js
│   │   ├── useEditorAudio.js
│   │   └── useEditorAI.js
│   └── components/
│       ├── SortableSlideItem.jsx
│       ├── SortableLayerItem.jsx
│       ├── SlideThumbnailContent.jsx
│       ├── ElementProperties.jsx
│       └── SlideProperties.jsx
├── Agent.jsx               (1024 lines - orchestrator)
└── Agent/
    └── components/
        ├── ConfigPanel.jsx
        ├── StoryboardPanel.jsx
        ├── MediaConfigPanel.jsx
        ├── GeneratedPanel.jsx
        └── CoursePanels.jsx
```

## Known Issues
- **HeyGen Video Generation**: Blocked by user's HeyGen API credits being 0 (external issue)

## Backlog
### P0
- SCORM 2004 & xAPI Export implementation
### P2
- Advanced Interactivity: Per-course "Tutor IA"
- Further Editor.jsx dialog extraction (HeyGen Dialog, TTS Dialog, Video Library Dialog ~1200 lines)

## Credentials
- Admin: admin@scormify.com / admin123
