# Scormify - Product Requirements Document

## Original Problem Statement
Course editor application for creating and exporting SCORM-compliant courses. Features include:
- Side-by-side preview panel in editor
- Mobile-responsive exported courses
- AI-powered narration generation (Gemini)
- AI script generation for HeyGen avatars
- Video export (MP4/WebM)
- Multi-tenant authentication system

## Architecture

### Tech Stack
- **Frontend:** React + TailwindCSS + Shadcn/UI
- **Backend:** FastAPI (Python)
- **Database:** MongoDB (Atlas in production)
- **Integrations:** ElevenLabs (TTS), HeyGen (Avatars), Gemini (AI), moviepy/ffmpeg (Video)

### Key Files
- `backend/server.py` - Main API server with CORS, video export, auth routes
- `backend/routes/auth.py` - Authentication endpoints with datetime serialization
- `backend/src/exporters/video_exporter.py` - Video export logic
- `backend/src/exporters/html_exporter.py` - HTML/SCORM export
- `frontend/src/contexts/AuthContext.jsx` - Auth state management
- `frontend/src/pages/Editor/Editor.jsx` - Main editor with AI narration UI

## Completed Features

### 2026-02-19
- [x] Fixed deployment issues preventing login in production
  - `load_dotenv(override=False)` to respect Kubernetes env vars
  - Datetime serialization for JSON responses
  - Auto-creation of super admin on startup
  - Dynamic CORS for `.emergent.host` domain
  - Fixed "Response body already used" bug in frontend

### Previous Sessions
- [x] AI Narration Generation with Gemini Vision (OCR support)
- [x] AI Script Generation for HeyGen avatars
- [x] Video Export (MP4/WebM) with ffmpeg
- [x] HeyGen avatar transparency, aspect ratio, and audio sync fixes
- [x] Mobile layout fixes for exported courses
- [x] System dependencies auto-check (non-blocking)

## Backlog

### P2 - Code Quality
- [ ] Refactor `html_exporter.py` to use external templates instead of inline strings

### P3 - Enhancements
- [ ] Password recovery via email
- [ ] User management dashboard improvements

## Credentials
- **Admin Login:** admin@scormify.com / admin123

## API Endpoints
- `POST /api/auth/login` - Email/password login
- `POST /api/auth/google` - Google OAuth
- `GET /api/auth/me` - Get current user
- `GET /api/auth/debug-db` - Database connectivity check
- `POST /api/projects/{id}/export-video` - Video export
- `POST /api/projects/{id}/slides/{slide_id}/generate-narration` - AI narration
