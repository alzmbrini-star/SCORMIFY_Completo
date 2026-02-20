# Scormify - PRD (Product Requirements Document)

## Problem Statement
Scormify is a course authoring tool with React frontend and FastAPI backend. It supports AI-powered narration (Gemini), video export, SCORM/HTML exports, and PPT import via ConvertAPI.

## Core Requirements
- **[DONE]** Fix login and deployment issues
- **[DONE]** PPT import in production via ConvertAPI (LibreOffice not available)
- **[DONE]** Fix SCORM export missing images for ConvertAPI-imported projects
- **[DONE]** Fix projects not appearing after login (P0 bug)
- **[DONE]** Persistent asset storage in MongoDB for ephemeral production environments
- **[DONE]** Embed images as base64 data URIs in SCORM exports (eliminate file dependency)
- **[DONE]** Root `/health` endpoint for Kubernetes health checks
- **[DONE]** Non-blocking startup asset persistence (background thread)
- **[DONE]** Fix SCORM export 520 error in production (asyncio.to_thread + None safety)
- **[DONE]** Prevent disk exhaustion from accumulated exports (24h cleanup policy)
- **[DONE]** Fix SCORM completion (LMSFinish) sent before quiz ends - now uses courseHasQuiz flag to defer completion to QuizController
- **[PENDING USER VERIFICATION]** SCORM export visual regressions (stretched images, transparent backgrounds)

## Architecture
- Frontend: React (port 3000)
- Backend: FastAPI (port 8001)
- Database: MongoDB (persistent)
- Storage: Local filesystem + MongoDB backup (project_assets collection)
- 3rd Party: ConvertAPI (PPT), ElevenLabs (TTS), HeyGen (video), Google Gemini (AI)

## What's Been Implemented

### Session - Feb 20, 2026
1. **SCORM Export 520 Error Fix (P0)**
   - `export_scorm_package` now runs via `asyncio.to_thread()` - prevents event loop blocking
   - Video download timeout reduced 120s → 25s (under Cloudflare's ~30s limit)
   - Full defensive None checks on all slide/element/audio fields
   - Correct URL parsing: strips project_id prefix from asset filenames
   - `SlideElement.type`, `SlideAudio.src/filename`, `GlobalAudio.src/filename`, `Slide.width/height` made `Optional` in models.py to survive legacy data from MongoDB without Pydantic ValidationError
   - Export cleanup: `_cleanup_old_exports()` deletes files older than 24h after each export

### Session - Feb 19, 2026
1. **MongoDB Asset Persistence** (`services/asset_store.py`)
   - Assets stored in MongoDB `project_assets` collection as base64
   - Automatic backup during PPT import, media upload, audio upload
   - Restore on SCORM export when local files missing
   - Startup migration of existing local assets to MongoDB (background thread)

2. **Base64 Data URI Embedding in SCORM** (`services/scorm_exporter.py`)
   - Background images embedded directly as `data:image/png;base64,...` in course.json
   - Element images also embedded as data URIs
   - Eliminates dependency on separate image files in SCORM package

3. **Deployment Fixes**
   - Root `/health` endpoint for Kubernetes health checks
   - Non-blocking startup (background thread for asset persistence)

### Previous Sessions
- Production login & stability fixes
- ConvertAPI integration for PPT import
- Slide ordering fix for ConvertAPI
- SCORM visual regression fixes (objectFit, background transparency)
- Super admin auto-creation on startup

## Prioritized Backlog
- **P1**: User verification of SCORM export visual quality in production
- **P2**: Refactor `html_exporter.py` to use external templates
- **P2**: File cleanup/directory restructuring

## Key Files
- `backend/services/asset_store.py` - MongoDB asset persistence
- `backend/services/scorm_exporter.py` - SCORM export with base64 data URI embedding + None safety
- `backend/services/html_exporter.py` - HTML export with MongoDB fallback
- `backend/services/ppt_image_parser.py` - ConvertAPI + MongoDB storage
- `backend/server.py` - API endpoints, startup hooks, health check, export cleanup
- `backend/models.py` - Pydantic models with Optional fields for legacy data safety
- `frontend/src/contexts/ProjectContext.jsx` - axios withCredentials fix

## Testing
- Test Report: `/app/test_reports/iteration_27.json` - 18/18 pass rate (100%)
- Test Project: NR01 (57d237b2-3636-4ea8-a306-bede62e4fe23) - 3 ConvertAPI slides
- All None-field edge cases now pass (200 OK instead of 500/520)
