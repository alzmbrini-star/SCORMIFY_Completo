# PRD - Course Authoring Tool

## Original Problem Statement
Application is a React/FastAPI course authoring tool with features including SCORM export, PPT import, AI-powered script generation, TTS (ElevenLabs), and avatar video generation (HeyGen).

## Core Requirements
- **[DONE]** Fix all login and deployment-related issues
- **[DONE]** Implement PPT import for production environment
- **[DONE]** Resolve all SCORM and HTML export regressions
- **[DONE]** Ensure all core functionalities are stable in production
- **[DONE]** Achieve stable production deployment (Nginx startup conflict resolved)
- **[DONE]** Ensure projects are visible and accessible after login
- **[DONE]** AI Tutor feature (Gemini-powered, admin-configurable, SCORM-embedded)
- **[DONE]** Fix AI Tutor keyboard blocking in SCORM exports

## Architecture
- **Frontend:** React (port 3000)
- **Backend:** FastAPI (port 8001)
- **Database:** MongoDB
- **Proxy:** Nginx (port 80) managed by deployment orchestrator

## 3rd Party Integrations
- ElevenLabs (TTS)
- HeyGen (avatar video)
- Google Gemini via Emergent LLM Key (AI script generation + AI Tutor)
- ConvertAPI (PPT conversion, user API key)

## What's Been Implemented
- SCORM export hardened against None values
- SCORM quiz completion logic fixed (waits for quiz before LMSFinish)
- FastAPI non-blocking startup (health check responds immediately)
- Automated export file cleanup (background task)
- Nginx config patcher script (`fix_nginx_modules.sh`) - patches configs without starting Nginx
- Deployment orchestrator compatibility ensured

## Deployment Fix (Feb 2026)
- **Root cause:** `fix_nginx_modules.sh` STEP 4 was executing `nginx` / `nginx -s reload` commands, creating a port 80 conflict with the deployment orchestrator's own Nginx startup
- **Fix:** Removed all nginx start/reload commands from the script. Now only patches config files and validates with `nginx -t`
- **Deployment agent check:** All checks passed

## Export Persistence Fix (Feb 2026)
- **Root cause:** Export files (SCORM, HTML, video) stored only on ephemeral local disk. Container restarts/deploys wipe the files, causing "File not found" on download
- **Fix:** Added MongoDB GridFS persistence layer. Files are saved to GridFS after generation. Download endpoint falls back to GridFS if the local file is missing, restoring it transparently
- **Tested:** Export -> delete local file -> download succeeds via GridFS restore

## Audio Upload Fix (Feb 2026)
- **Root cause:** After container restart/deploy, local project directories (`storage/projects/{id}/assets/`) don't exist. Audio upload, media upload, and global audio endpoints tried to write files without creating the directory first -> 500 error
- **Fix:** Added `file_path.parent.mkdir(parents=True, exist_ok=True)` before file write in 3 endpoints: `upload_media`, `upload_slide_audio`, `set_global_audio`
- **Tested:** Deleted local assets dir, uploaded audio -> HTTP 200 success

## Backend Startup Optimization (Feb 2026)
- **Root cause:** Heavy module-level imports (PIL, python-pptx, scorm_exporter, html_exporter, video_exporter, system_deps) were loaded at server boot time, causing ~35 second startup delay in production containers
- **Fix:** Converted all heavy imports to lazy imports (loaded inside functions on first use). Moved `ensure_system_dependencies()` to a background startup task
- **Result:** Startup time reduced from ~35 seconds to ~1.2 seconds. Health check responds almost instantly
- **Tested:** Backend restarts in ~1.2s, health check OK, SCORM export OK, image upload with PIL optimization OK

## Frontend API URL Fix (Feb 2026)
- **Root cause:** `REACT_APP_BACKEND_URL` in production was set to wrong domain
- **Fix:** Created `utils/apiUrl.js` utility that uses `window.location.origin` in the browser (always the correct domain). Replaced ALL `process.env.REACT_APP_BACKEND_URL` references across 10+ files
- **Tested:** Login, dashboard, project list all work correctly

## AI Tutor Feature (Feb 2026)
- **Backend:** `POST /api/tutor/chat` endpoint using Google Gemini (via Emergent LLM Key) with course context, conversation history, message limit enforcement. `GET/PUT /api/admin/tutor-settings` for global configuration
- **Admin Panel:** New "Tutor IA" tab with: enable/disable toggle, tutor name, message limit, custom system prompt, suggested questions management
- **SCORM Export:** Floating chat widget (tutor.js + tutor.css) embedded in packages. Course content automatically extracted as context. Backend API URL embedded for LMS callback
- **Features:** Session history, pre-defined question suggestions, message counter, mobile responsive, markdown formatting
- **Tested:** 100% pass rate (10 backend + 8 frontend tests)

## AI Tutor Keyboard Fix (Feb 2026)
- **Root cause:** SCORM player.js had a document-level `keydown` listener that captured Space, Enter, ArrowLeft/Right, Backspace, f/F for slide navigation. When typing in the tutor input, these events propagated up and blocked normal typing.
- **Fix (two layers):**
  1. `player.js`: Added guard to skip keyboard navigation when `e.target` is `input`, `textarea`, or `contentEditable`
  2. `tutor.js`: Added `e.stopPropagation()` on `keydown`, `keyup`, `keypress` events from the tutor input field
- **Note:** Existing already-exported SCORM packages are NOT affected. Users must re-export to get the fix.
- **Tested:** 9/9 tests passed (iteration_29)

## AI Tutor Context Fix (Feb 2026)
- **Root cause:** SCORM exporter extracted course context using `htmlContent` and `text` fields, but elements actually store text in the `content` field. Result: empty context sent to Gemini, making the tutor respond generically without referencing course material.
- **Fix:**
  1. `scorm_exporter.py`: Changed extraction to check `content` first, then `htmlContent`, then `text`. Also extracts `buttonText` and quiz titles.
  2. `server.py`: Improved system prompt to instruct Gemini to cite specific slides (e.g., "Conforme apresentado no Slide 3...").
  3. Increased slide limit from 30 to 50 for richer context.
- **Note:** Users must re-export SCORM packages to get the improved context.
- **Tested:** 12/12 tests passed (iteration_30). Tutor now responds with slide-specific citations.

## Backlog
- **P2:** Refactor `backend/src/exporters/html_exporter.py` to use external templates for HTML, CSS, JS
- **P2:** Refactor `backend/server.py` into multiple APIRouter files
