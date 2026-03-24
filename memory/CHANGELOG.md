# Changelog

## 2026-03-24 (Current Session - Fork 2)

### CRITICAL Bug Fix: Missing Route Registrations (Companies, Users, etc.)
- **Root Cause**: 8 route modules existed as files in `/app/backend/routes/` but were NEVER registered in `server.py` via `include_router()`. Missing: `companies`, `users`, `elevenlabs`, `gallery`, `heygen`, `questions`, `scenarios`, `vlibras`.
- **Impact**: All endpoints for these routes returned HTTP 404. Admin panel showed "Nenhuma empresa cadastrada" and no users because `/api/companies` and `/api/users` were unreachable.
- **Fix**: Added all 8 missing route imports and `include_router()` calls in `server.py`. Also called `set_db(db)` for `companies` and `users` routes (which use the `set_db` pattern).
- **Applied in**: `backend/server.py` (lines 123-147)
- **Status**: Tested with 13 backend tests + frontend UI verification — ALL PASSED ✅

### Bug Fix: AI Tutor URL Stale After Fork
- **Root Cause**: In `export.py`, SCORM export prioritized DB `apiUrl` over `_get_external_url()`.
- **Fix**: Changed priority to `_get_external_url() or settings_doc.get('apiUrl', '').strip()`.
- **Applied in**: `backend/routes/export.py`
- **Status**: Tested — correct URL in SCORM and HTML exports ✅

### Feature: Fix Simulators UI Button
- **What**: Added "Ferramentas" dropdown menu to Editor header with "Corrigir Simuladores" option.
- **Applied in**: `frontend/src/pages/Editor.jsx`
- **Status**: Tested ✅

## 2026-03-24 (Previous Session)

### Bug Fix: SCORM Completion Not Triggering
- **Fix**: Changed `Player` to `CoursePlayer` in scenario/quiz controllers
- **Status**: Tested ✅

### Bug Fix: HTML Export Scenarios Not Opening
- **Fix**: Replaced `data-scenario` attribute with `window.__scenarioDataMap`
- **Status**: Tested ✅

### Fix: Course Generation Timeout
- **Fix**: Parallel image generation with asyncio.Semaphore(5)
- **Status**: Deployed, needs user testing

### Fix: Production Deployment Failures
- **Fix**: Dynamic timeout detection for MongoDB Atlas
- **Status**: ✅

### Bug Fix: Background Images Lost in Export
- **Fix**: Changed CSS wildcard to specific selectors
- **Status**: ✅

### Bug Fix: Login "body stream already read" Error
- **Fix**: localStorage token fallback with global fetch interceptor
- **Status**: ✅

### Bug Fix: [object Object] in Slides
- **Fix**: Multi-layer type-checking on backend and frontend
- **Status**: ✅

### Feature: Before/After Preview + Undo for AI Improvements
- **Status**: ✅

### Feature: Static Simulator Fix Endpoint + UI Button
- **Status**: Backend + Frontend ✅

## Previous Session
- Gamification system, AI Agent scenario fix, asyncio fix, configurable backend URL
