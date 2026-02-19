# Scormify - Product Requirements Document

## Original Problem Statement
Course editor application for creating and exporting SCORM-compliant courses with:
- Side-by-side preview panel in editor
- Mobile-responsive exported courses
- AI-powered narration generation (Gemini)
- AI script generation for HeyGen avatars
- Video export (MP4/WebM)
- Multi-tenant authentication system
- High-fidelity PPT import (LibreOffice local or ConvertAPI cloud)

## Architecture

### Tech Stack
- **Frontend:** React + TailwindCSS + Shadcn/UI
- **Backend:** FastAPI (Python)
- **Database:** MongoDB (Atlas in production)
- **Integrations:** 
  - ElevenLabs (TTS)
  - HeyGen (Avatars)
  - Gemini (AI narration)
  - ConvertAPI (PPT to PNG conversion)
  - moviepy/ffmpeg (Video export)

### Key Files
- `backend/server.py` - Main API server with CORS, video export, auth routes
- `backend/routes/auth.py` - Authentication with datetime serialization
- `backend/services/ppt_image_parser.py` - PPT import with ConvertAPI integration
- `backend/src/exporters/video_exporter.py` - Video export logic
- `frontend/src/contexts/AuthContext.jsx` - Auth state management
- `frontend/src/pages/Editor/Editor.jsx` - Main editor with AI narration UI

## Completed Features

### 2026-02-19 (Current Session)
- [x] Fixed deployment login issues (datetime serialization, super admin auto-creation)
- [x] Added CORS support for `.emergent.host` production domain
- [x] Integrated ConvertAPI for high-fidelity PPT import without LibreOffice
- [x] Fixed slide ordering in ConvertAPI conversion (use native API order)
- [x] Fixed `load_dotenv(override=False)` for Kubernetes compatibility

### Previous Sessions
- [x] AI Narration Generation with Gemini Vision (OCR support)
- [x] AI Script Generation for HeyGen avatars
- [x] Video Export (MP4/WebM) with ffmpeg
- [x] HeyGen avatar transparency, aspect ratio, and audio sync fixes
- [x] Mobile layout fixes for exported courses
- [x] System dependencies auto-check (non-blocking)

## PPT Import Flow
```
PPT Upload
    ├─ 1st: Try LibreOffice (if available locally)
    ├─ 2nd: Try ConvertAPI (cloud, high fidelity) ✅
    └─ 3rd: Python-only parser (fallback, lower fidelity)
```

## Backlog

### P2 - Code Quality
- [ ] Refactor `html_exporter.py` to use external templates

### P3 - Enhancements
- [ ] Password recovery via email
- [ ] Support for Google Slides / Keynote import
- [ ] User management dashboard improvements

## Credentials
- **Admin Login:** admin@scormify.com / admin123
- **ConvertAPI:** Configured in backend/.env

## API Endpoints
- `POST /api/auth/login` - Email/password login
- `POST /api/auth/google` - Google OAuth
- `GET /api/auth/me` - Get current user
- `POST /api/ppt/upload` - Upload and parse PPT file
- `POST /api/projects/{id}/export-video` - Video export
- `POST /api/projects/{id}/slides/{slide_id}/generate-narration` - AI narration
