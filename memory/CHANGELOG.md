# Changelog

## 2026-03-25 (Current Session)

### CRITICAL Bug Fix: Video Export 502 in Production
- **Root Cause**: `run_ffmpeg()` used blocking `subprocess.run()` inside an async task. While FFmpeg processed 18 slides (30-60s), the entire asyncio event loop was blocked — the backend couldn't respond to ANY request, causing Cloudflare proxy to return 502.
- **Fix**: Created `run_ffmpeg_async()` using `asyncio.create_subprocess_exec()`. All FFmpeg/FFprobe calls in `export_video()` are now non-blocking. Backend responds to polling requests during video processing.
- **Also fixed**: Import of `video_exporter` wrapped in try/except (prevents backend crash if module fails), `_ensure_ffmpeg()` initialization wrapped in try/except, `static-ffmpeg` pip package as fallback (no root needed), startup event tries `static-ffmpeg` before `apt-get`
- **Applied in**: `services/video_exporter.py`, `routes/export.py`, `server.py`
- **Status**: Tested ✅ — backend responds HTTP 200 during all 18 slide processing

### Bug Fix: Video Export Job 404 in Production
- **Root Cause**: Job status was stored in-memory (`jobs` dict). In production, process restarts or multiple workers caused the job data to be lost, returning 404 on GET `/api/job/{jobId}`.
- **Fix**: Job data now persisted in **MongoDB** (`jobs` collection) with local cache for fast access. Jobs survive restarts, deploys, and multi-worker environments.
- **Applied in**: `routes/deps.py` (create_job, update_job, get_job), `routes/export.py`, `routes/projects.py`
- **Status**: Tested ✅ — job survives backend restart and is recoverable from MongoDB

### Bug Fix: SCORM Completion Not Triggering
- **Root Cause**: Completion logic required ALL scenarios to be completed in addition to quizzes. Scenarios are interactive branching exercises that users might skip or not complete fully, blocking SCORM "completed" status indefinitely.
- **Fix**: Changed completion rules in `player.js` to: Navigate to last slide + Complete all quizzes (if any). Scenarios are now optional (enrich learning but don't block completion).
- **Applied in**: `services/export_assets/player.js` (checkAndSetCompletion + finalCompletionCheck)
- **Status**: Tested ✅ — re-exported SCORM package contains updated logic

### Feature: AI Simulator/Game Generation in Course Creation
- **Modified**: `ai_agent.py` - Added `simulator` slide type to `generate_structure`, `generate_storyboard`, `generate_course_from_storyboard`, `generate_structure_from_template`
- **Modified**: `routes/agent.py` - Enhanced `_build_improved_elements` to handle HTML simulator elements, added `course_interactivity` category to improvement suggestions, enhanced `apply_course_improvements` prompt
- **What it does**: AI Agent now MANDATORY creates 1-2 interactive HTML+JS simulators per module (calculators, drag-and-drop, flashcards, memory games, quizzes, timelines, etc.)
- **Status**: Code deployed ✅ — needs user testing via course creation flow

### Video Export Fix: FFmpeg Persistence
- **Root Cause**: FFmpeg not available after fork/deploy because system packages are reset
- **Fix**: Triple-layer persistence:
  1. `start.sh` script installs FFmpeg before starting uvicorn (supervisor)
  2. FastAPI `startup_ensure_ffmpeg()` event auto-installs if missing
  3. `video_exporter.py` lazy-loads FFmpeg paths at runtime
- Added WebM media type to `serve_export` endpoint
- **Applied in**: `server.py`, `backend/start.sh`, `services/video_exporter.py`, `routes/export.py`
- **Status**: Tested ✅ (MP4: 54s/374KB, WebM: 54s/1.1MB)

### CRITICAL Bug Fix: AI Tutor CORS in Production (Recurring Issue #4)
- **Root Cause**: SCORM packages served from LMS domains (e.g., `didaxis.didaxis.com.br`) make cross-origin requests to the backend. Production proxy/infrastructure may strip CORS headers or not forward OPTIONS preflight to the app.
- **Fix**: Triple-layer CORS protection for `/api/tutor/chat`:
  1. Global `CORSMiddleware` with `allow_origins=["*"]` and fallback for empty env vars
  2. Custom `TutorCorsMiddleware` that explicitly handles OPTIONS and adds CORS headers for `/tutor/chat`
  3. Explicit CORS headers in `JSONResponse` at the route handler level
- **Applied in**: `server.py` (middleware), `routes/admin.py` (endpoint handlers)
- **Status**: Tested ✅ (preview) — User must **re-deploy and re-export SCORM** to test in production

### Bug Fix: Washed-Out Slide Thumbnails
- **Root Cause**: HTML element placeholders in thumbnails were empty transparent divs, hiding the actual slide content. AI-generated slides use HTML elements as main visual content covering the full area.
- **Fix**: Replaced empty placeholder with sandboxed `<iframe>` (`sandbox="allow-scripts"`, no `allow-same-origin`) that renders the actual HTML content safely without CSS leaking
- **Applied in**: `SlideThumbnailContent.jsx`
- **Status**: Verified ✅ — thumbnails now show full slide content (text, images, tables, buttons)

### CRITICAL Bug Fix: AI HTML CSS Leaking to Editor UI
- **Root Cause**: `SlideThumbnailContent.jsx` rendered HTML elements using `dangerouslySetInnerHTML` directly in the editor DOM (no iframe isolation). AI-generated HTML contains `<style>` tags with global CSS rules (e.g., `button { background: gradient(...) }`, `body { background: white }`) that cascade to ALL elements on the page, breaking toolbar icons, button visibility, and the dark theme.
- **Fix**: Replaced `dangerouslySetInnerHTML` with a safe placeholder (`</> HTML`) for HTML elements in thumbnails. Also removed `allow-same-origin` from all iframe sandboxes and added `contain: strict; isolation: isolate` on iframe containers.
- **Applied in**: `frontend/src/pages/Editor/components/SlideThumbnailContent.jsx`, `frontend/src/components/editor/SlideCanvas.jsx`, `CoursePreview.jsx`, `SplitPreview.jsx`, `Editor.jsx`
- **Status**: Tested ✅ — toolbar clean, dark theme restored, HTML renders correctly in iframe

### Feature: AI-Powered HTML Generation in Editor
- **What**: "Gerar com IA" tab in HTML dialog with prompt → preview → edit → insert
- **Backend**: `POST /api/generate-html` using Gemini
- **Status**: Tested ✅ (iteration_78)

### Bug Fix: Full HTML Documents Breaking iframe CSS
- **Fix**: Auto-detect `<!DOCTYPE html>` and render directly as srcDoc without wrapper
- **Applied in**: SlideCanvas, CoursePreview, SplitPreview, player.js, html_exporter.py
- **Status**: Tested ✅

### Bug Fix: AI Tutor 404 in Production SCORM Exports
- **Fix**: `_get_external_url()` now uses X-Forwarded headers from K8s proxy
- **Status**: Tested ✅ (iteration_77)

### CRITICAL Bug Fix: Missing Route Registrations
- **Fix**: Added 8 missing route modules to server.py
- **Status**: Tested ✅ (iteration_76)

## Previous Sessions
- SCORM completion, HTML scenario, deployment, background images, login fixes
- Before/After Preview + Undo, AI improvements layout fix
- Gamification, AI Agent scenario fix, Fix Simulators button
