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

## Architecture
- **Frontend:** React (port 3000)
- **Backend:** FastAPI (port 8001)
- **Database:** MongoDB
- **Proxy:** Nginx (port 80) managed by deployment orchestrator

## 3rd Party Integrations
- ElevenLabs (TTS)
- HeyGen (avatar video)
- Google Gemini via Emergent LLM Key (AI script generation)
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
- **Tested:** Export → delete local file → download succeeds via GridFS restore

## Audio Upload Fix (Feb 2026)
- **Root cause:** After container restart/deploy, local project directories (`storage/projects/{id}/assets/`) don't exist. Audio upload, media upload, and global audio endpoints tried to write files without creating the directory first → 500 error
- **Fix:** Added `file_path.parent.mkdir(parents=True, exist_ok=True)` before file write in 3 endpoints: `upload_media`, `upload_slide_audio`, `set_global_audio`
- **Tested:** Deleted local assets dir, uploaded audio → HTTP 200 success

## Backend Startup Optimization (Feb 2026)
- **Root cause:** Heavy module-level imports (PIL, python-pptx, scorm_exporter, html_exporter, video_exporter, system_deps) were loaded at server boot time, causing ~35 second startup delay in production containers
- **Fix:** Converted all heavy imports to lazy imports (loaded inside functions on first use). Moved `ensure_system_dependencies()` to a background startup task
- **Result:** Startup time reduced from ~35 seconds to ~1.2 seconds. Health check responds almost instantly
- **Tested:** Backend restarts in ~1.2s, health check OK, SCORM export OK, image upload with PIL optimization OK

## Backlog
- **P2:** Refactor `backend/src/exporters/html_exporter.py` to use external templates for HTML, CSS, JS
