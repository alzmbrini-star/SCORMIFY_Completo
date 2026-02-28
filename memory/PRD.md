# PRD - Course Authoring Tool (Scormfy)

## Original Problem Statement
Build a full-featured course authoring tool that allows users to create interactive courses, export them to SCORM/HTML format, and include accessibility features like VLibras (Brazilian Sign Language) translation.

## Core Requirements
- Course creation with slides, elements, and multimedia
- SCORM 1.2 and standalone HTML export
- Text-to-Speech (ElevenLabs integration)
- AI content generation (Google Gemini)
- VLibras LIBRAS accessibility
- HeyGen avatar video generation
- PowerPoint import (ConvertAPI)
- Quiz/assessment support
- AI Tutor integration
- Mobile responsive course player

## Architecture
- **Frontend**: React + Tailwind + Shadcn/UI
- **Backend**: FastAPI + MongoDB
- **Integrations**: ElevenLabs TTS, Google Gemini, HeyGen, ConvertAPI, VLibras

## What's Been Implemented

### Core Features (Complete)
- Full course editor with drag-and-drop elements
- SCORM 1.2 export with quiz support
- Standalone HTML export
- Text-to-Speech via ElevenLabs
- AI script generation via Gemini
- HeyGen avatar video generation
- PowerPoint import via ConvertAPI
- Quiz/assessment system
- AI Tutor for exported courses
- Mobile-responsive course player

### VLibras Integration (Improved - 2026-02-28)
- **CORS Proxy**: Backend proxy at `/api/vlibras-proxy/` handles BOTH VLibras domains:
  - `dicionario2.vlibras.gov.br` (sign dictionary/bundles)
  - `traducao2.vlibras.gov.br` (translation API)
- **XHR Monkey-Patch**: Exported SCORM/HTML packages inject JavaScript that intercepts XMLHttpRequest to both VLibras domains and routes through the proxy
- **Auto-initialization**: VLibras widget auto-opens and begins translating on page load
- **Player Integration**: `translateWithVLibras()` called on slide navigation when `librasScript` field has content
- **Auto-fill Feature**: "Script LIBRAS" field auto-populates from TTS narration text
- **Manual Extract**: Button to extract text from slide elements into LIBRAS script field

### Known Limitation: VLibras Server IP Blocking
The Brazilian government VLibras servers (`dicionario2.vlibras.gov.br` and `traducao2.vlibras.gov.br`) block requests from cloud/data center IPs (AWS, GCP, etc.) returning HTTP 403. This means:
- **On cloud-hosted servers**: VLibras falls back to fingerspelling (spelling out words letter by letter) instead of proper sign language animations
- **On residential/educational IPs**: Full sign language animations should work
- **The avatar IS active and animated** (fingerspelling works), no longer static
- This is a government infrastructure limitation, not a bug in our code

## Prioritized Backlog

### P0 (Resolved)
- ~~VLibras avatar static in exports~~ → Fixed: proxy now handles both domains, URL detection corrected, avatar active with fingerspelling fallback

### P2
- Refactor `scorm_exporter.py` and `html_exporter.py` to use Jinja2 templates
- Refactor monolithic `server.py` into separate router files

### P3
- AI agent for automatic course generation from source documents

## Key API Endpoints
- `GET /api/vlibras-proxy/dicionario2/{path}` - Proxy for VLibras dictionary
- `POST /api/vlibras-proxy/traducao2/{path}` - Proxy for VLibras translation
- `GET /api/vlibras-proxy-test` - Test page for VLibras proxy
- `POST /api/course/{id}/export-scorm` - SCORM export
- `POST /api/course/{id}/export-html` - HTML export

## Key Files
- `backend/server.py` - Main server with VLibras proxy endpoints
- `backend/services/scorm_exporter.py` - SCORM export with VLibras injection
- `backend/services/html_exporter.py` - HTML export with VLibras injection
- `backend/services/export_assets/player.js` - Course player with VLibras translation logic
- `frontend/src/pages/Editor/Editor.jsx` - Editor with LIBRAS script auto-fill
