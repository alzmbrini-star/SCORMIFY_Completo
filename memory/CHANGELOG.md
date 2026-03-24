# Changelog

## 2026-03-23 (Current Session)

### Bug Fix: SCORM Completion Not Triggering
- **Root Cause**: `scenario-controller.js` and `quiz-controller.js` called `Player.onScenarioComplete()` but the object is named `CoursePlayer`
- **Fix**: Changed all references from `Player` to `CoursePlayer`
- **Additional**: Removed `visitedLastSlide` requirement - course marks complete as soon as all interactive elements are done
- **Additional**: SCORM API now sends both "completed" AND "passed" for max LMS compatibility
- **Additional**: Added `finalCompletionCheck` on `beforeunload` as safety net
- **Additional**: Scenario score now sent to SCORM via `ScormAPI.setScore()`
- **Status**: Tested with LMS simulator - WORKING ✅

### Bug Fix: HTML Export Scenarios Not Opening
- **Root Cause**: Scenario data stored in `data-scenario` HTML attribute. Portuguese text with single quotes broke the attribute parsing, silently failing `JSON.parse`
- **Fix**: Replaced with `window.__scenarioDataMap` JavaScript object - no HTML attribute escaping needed
- **Additional**: HTML ScenarioController scoring updated from points to ideal decisions
- **Additional**: VLibras now gracefully skipped on `file://` protocol
- **Additional**: AI Tutor skipped on `file://` protocol  
- **Status**: Tested - WORKING ✅

### Fix: Course Generation Timeout (23 slides with images)
- **Root Cause**: AI images generated sequentially (one by one). 23 images × ~10s = ~4 minutes just for images
- **Fix**: Parallel generation with `asyncio.gather` + `asyncio.Semaphore(5)` - max 5 concurrent
- **Additional**: Frontend polling timeout increased from 10 min to 30 min
- **Additional**: Progress messages show "Gerando imagens IA: 3/23..." 
- **Additional**: Early project save (status "generating") preserves images on failure
- **Status**: Code fix deployed, needs user testing

### Fix: Production Deployment Failures (MongoDB Atlas Timeouts)
- **Root Cause**: All MongoDB client instances used 10s timeout, insufficient for Atlas latency
- **Fix**: Dynamic timeout detection (`is_atlas` flag), increased to 30s server/connect, 60s socket
- **Additional**: Asset persistence uses batch query instead of individual `find_one` per asset
- **Additional**: Added `retryWrites=True, retryReads=True` for Atlas resilience
- **Additional**: Fixed URL migration `TypeError: expected string, got dict` for htmlContent
- **Status**: Backend starts cleanly ✅

### Bug Fix: Background Images Lost in SCORM/HTML Export (2026-03-24)
- **Root Cause**: CSS `*{background:transparent!important}` in player.js (SCORM) and html_exporter.py (HTML) overrode ALL inline backgrounds, including images embedded as CSS `url()` in htmlContent
- **Fix**: Changed wildcard to `*{box-sizing:border-box!important;max-width:100%!important}` — only `body` keeps `background:transparent!important`
- **Applied in**: player.js (line 1325), html_exporter.py (line 2017)
- **Status**: Tested with 8 tests including SCORM ZIP content verification - ALL PASSED ✅

### Bug Fix: Button/Badge Colors Not Showing in Editor Canvas (2026-03-24)
- **Root Cause**: CSS rule `* { background: transparent !important; }` in iframe forced ALL elements transparent, overriding inline background-color on buttons/badges
- **Fix**: Changed to `html, body, .content-wrapper { background: transparent !important; }` — only container backgrounds are transparent, content elements keep their styling
- **Applied in**: SlideCanvas.jsx, CoursePreview.jsx, SplitPreview.jsx
- **Status**: Verified via screenshot - badges and buttons now show colored backgrounds ✅

### Bug Fix: Login "body stream already read" Error + Token Fallback (2026-03-24)
- **Root Cause**: Fetch response body read twice when network fails. Also, auth relied ONLY on cookies.
- **Fix**: Added try/catch around response.text(), clear error messages. Added localStorage token fallback: login saves token, global fetch interceptor auto-includes `Authorization: Bearer` header for all `/api/` calls.
- **Applied in**: AuthContext.jsx (rewritten), index.js (fetch interceptor), ProjectContext.jsx (axios interceptor)
- **Status**: Login works even when cookies are blocked ✅

### Bug Fix: [object Object] in Slides After AI Improvements (2026-03-23)
- **Root Cause**: AI sometimes returns `content` as dict/object instead of HTML string. Saved directly to `htmlContent`, rendered as `[object Object]` in frontend.
- **Fix (Backend)**: `_build_improved_elements` now type-checks and converts dict/list/None content to string. `_apply_ai_result_to_slides` validates all fields. `GET /api/projects/{id}` auto-sanitizes corrupt data.
- **Fix (Frontend)**: `resolveHtmlContentUrls`, `processHtmlContent` in SlideCanvas, CoursePreview, SplitPreview return empty string for non-string content.
- **Status**: Tested with 22 tests - ALL PASSED ✅

### Feature: Before/After Preview + Undo for AI Improvements (2026-03-23)
- **Preview**: New `/preview-improvements` endpoint calls AI and returns before/after comparison WITHOUT saving changes
- **Cached AI Result**: Preview caches AI response; apply uses cache via `previewId` (no duplicate AI call)
- **Undo**: Snapshot saved to `course_snapshots` collection before applying; `/undo-improvements` restores it
- **Frontend**: New `PreviewPanel` component with side-by-side before/after comparison (ANTES/DEPOIS)
- **Edit Flow**: 4 steps now: Selecionar → Análise → Preview → Resultado (was 3)
- **Cancel**: User can cancel preview and return to analysis to adjust selections
- **Status**: Tested with 13 tests (backend + frontend) - ALL PASSED ✅

### Bug Fix: AI Improvements Breaking Slide Layout (2026-03-23)
- **Root Cause**: `agent_apply_improvements` in `backend/routes/agent.py` placed ALL elements at `y: 40`, causing overlap. Also wiped non-text elements (images, scenarios, quizzes).
- **Fix**: Incremental Y positioning (`current_y = 80`, `current_y += elem_height + 20`). Preserves header bars (y=0, height<=60), non-text elements, and existing images/scenarios/quizzes.
- **Additional**: Improved AI prompt in `ai_agent.py` to request single combined HTML element per slide.
- **Status**: Tested with 22 tests (unit + integration) - ALL PASSED ✅

## Previous Session (Completed)
- Gamification system (badges, feedback)
- AI Agent scenario creation fix (type: "scenario" instead of text)
- Asyncio event loop fix for scenario data saving
- Configurable Backend URL for exported packages
- Multiple frontend bug fixes
