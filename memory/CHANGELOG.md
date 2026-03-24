# Changelog

## 2026-03-24 (Current Session)

### Bug Fix: AI Tutor URL Stale After Fork
- **Root Cause**: In `export.py` line 154, SCORM export prioritized `settings_doc.get('apiUrl')` from MongoDB over `_get_external_url()`. If DB had an old URL from a previous fork, it would be used in exported courses.
- **Fix**: Changed priority to `_get_external_url() or settings_doc.get('apiUrl', '').strip()` — current environment URL always takes priority.
- **Applied in**: `backend/routes/export.py` (SCORM export). HTML export already used `_get_external_url()` correctly.
- **Status**: Tested with both SCORM and HTML exports — correct URL verified in course.json and HTML output ✅

### Feature: Fix Simulators UI Button
- **What**: Added "Ferramentas" dropdown menu to Editor header with "Corrigir Simuladores" option
- **How it works**: Calls `POST /api/projects/{project_id}/fix-simulators`, shows toast with result, reloads page if fixes were applied
- **Applied in**: `frontend/src/pages/Editor.jsx` — Added Wrench icon import, `fixingSimulators` state, `handleFixSimulators` handler, DropdownMenu component
- **Data test IDs**: `tools-menu-btn`, `fix-simulators-btn`
- **Status**: Tested — dropdown opens correctly, API called successfully ✅

## 2026-03-24 (Previous Session)

### Bug Fix: SCORM Completion Not Triggering
- **Root Cause**: `scenario-controller.js` and `quiz-controller.js` called `Player.onScenarioComplete()` but the object is named `CoursePlayer`
- **Fix**: Changed all references from `Player` to `CoursePlayer`
- **Status**: Tested with LMS simulator - WORKING ✅

### Bug Fix: HTML Export Scenarios Not Opening
- **Root Cause**: Scenario data stored in `data-scenario` HTML attribute. Portuguese text with single quotes broke the attribute parsing
- **Fix**: Replaced with `window.__scenarioDataMap` JavaScript object
- **Status**: Tested - WORKING ✅

### Fix: Course Generation Timeout (23 slides with images)
- **Fix**: Parallel generation with `asyncio.gather` + `asyncio.Semaphore(5)`
- **Status**: Code fix deployed, needs user testing

### Fix: Production Deployment Failures (MongoDB Atlas Timeouts)
- **Fix**: Dynamic timeout detection, increased to 30s server/connect, 60s socket
- **Status**: Backend starts cleanly ✅

### Deployment Fix: Backend Health Check Timeout
- **Fix**: Added `/api/health` and `/api/healthz` endpoints. Deferred heavy startup tasks.
- **Status**: Deployment agent verified PASS ✅

### Bug Fix: Background Images Lost in SCORM/HTML Export
- **Fix**: Changed CSS wildcard to specific selectors
- **Status**: Tested - ALL PASSED ✅

### Bug Fix: Button/Badge Colors Not Showing in Editor Canvas
- **Fix**: Changed CSS to `html, body, .content-wrapper { background: transparent !important; }`
- **Status**: Verified ✅

### Bug Fix: Login "body stream already read" Error + Token Fallback
- **Fix**: localStorage token fallback with global fetch interceptor
- **Status**: Login works even when cookies are blocked ✅

### Bug Fix: [object Object] in Slides After AI Improvements
- **Fix**: Multi-layer type-checking on backend and frontend
- **Status**: Tested - ALL PASSED ✅

### Feature: Before/After Preview + Undo for AI Improvements
- **Status**: Tested - ALL PASSED ✅

### Bug Fix: AI Improvements Breaking Slide Layout
- **Fix**: Incremental Y positioning, preserves non-text elements
- **Status**: Tested - ALL PASSED ✅

### Feature: Static Simulator Fix Endpoint
- **Endpoint**: POST /api/projects/{project_id}/fix-simulators
- **Status**: Backend tested, frontend button now implemented ✅

## Previous Session (Completed)
- Gamification system (badges, feedback)
- AI Agent scenario creation fix
- Asyncio event loop fix for scenario data saving
- Configurable Backend URL for exported packages
- Multiple frontend bug fixes
