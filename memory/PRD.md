# PRD - Course Authoring Agent (Scormfy)

## Problem Statement
Build an advanced Instructional Design AI Agent that generates SCORM-compliant courses from content (PDF, PPT, DOC, or text). The application includes an AI agent pipeline, a full slide editor, and export capabilities.

## Architecture
- **Frontend**: React 18 + Tailwind CSS + Shadcn/UI
- **Backend**: FastAPI + Motor (async MongoDB)
- **Database**: MongoDB
- **Integrations**: OpenAI GPT-4o, Google Gemini 3 Flash & Nano Banana, ElevenLabs TTS, HeyGen Avatar Video, ConvertAPI, VLibras

## Core Features (Implemented)
### Auth & Dashboard
- JWT auth with login/register
- Admin panel for user/key management
- Project dashboard with CRUD
- **Dashboard metrics panel** (total courses, slides, exports)

### AI Agent Pipeline
- Multi-step course creation wizard
- Course editing mode with AI-powered improvement suggestions
- Chat interface for real-time agent interaction

### Slide Editor
- Full WYSIWYG editor with drag & drop elements
- Rich text editor with AI generation
- Slide thumbnails with live preview
- Animation system, background images, layer management

### Media & Audio
- ElevenLabs TTS narration with voice selection
- Audio recording and upload
- Volume controls per audio track

### HeyGen Integration
- Single-slide avatar video generation
- PPT-to-Video multi-scene generation
- Video library management

### Export
- SCORM 1.2 package export (with AI Tutor)
- HTML standalone export (with AI Tutor)
- Video export (MP4)

### AI Tutor (NEW)
- Embedded chat widget in exported SCORM and HTML courses
- Uses Gemini 3 Flash for contextual Q&A
- Answers ONLY based on course content
- Message limit per session
- Suggested questions support
- Admin configurable (name, prompt, limits)

### Accessibility
- VLibras Brazilian Sign Language integration

## Recent Changes

### Mar 9, 2026 - Bug Fix: AI Tutor Fails in SCORM Export
- **Root Cause**: The `apiUrl` embedded in SCORM (and HTML) exports was derived from HTTP request headers (`Origin`, `x-forwarded-host`, `host`). In production, these headers contained internal Kubernetes cluster URLs (e.g., `scorm-tutor-qa.cluster-0.preview.emergentcf.cloud`) which are NOT accessible from outside the cluster. When users tested the SCORM package locally or in SCORM Cloud, the AI Tutor's `fetch()` call to this internal URL failed.
- **Fix (export.py)**: Changed URL detection to use `BASE_URL` env var (or `REACT_APP_BACKEND_URL` from frontend `.env`) as the **primary** source instead of request headers. This always resolves to the correct external-facing URL.
- **Fix (tutor.js)**: Improved error handling in the `fetch` catch block to show descriptive error messages including HTTP status codes, and log the `apiUrl` being used for easier debugging.
- **Also fixed**: Removed duplicated per-slide contexts code in HTML export section.
- **Verified**: SCORM export now embeds `https://scorm-tutor-qa.preview.emergentagent.com` (external URL) and tutor API calls succeed with `Origin: null`.

### Mar 9, 2026 - Bug Fixes: Timeline & Media Overlap
- **Timeline Slider Instability**: Fixed by adding local scrubbing state (`isScrubbing`/`scrubTime`) during drag with `onValueCommit` for parent state updates. Added `requestAnimationFrame` throttling to clip dragging to prevent excessive API calls.
- **Media Editing Image Overlap**: Fixed by tracking original global settings (`originalGlobalTextColor`, `originalGlobalFontSize`, `originalGlobalAnimation`, `originalDesignTemplate`) in Agent.jsx and comparing current vs original values in `hasGlobalChanges` instead of just checking existence. Also sends empty array `[]` instead of `null` when no slides changed.

### Mar 9, 2026 - Feature: Tutor IA Slide-Aware em Exportações
- **tutor.js**: Reescrito para ser slide-aware. Rastreia `currentSlideIndex`, mostra indicador do slide atual, envia contexto específico do slide com cada mensagem.
- **player.js**: Adicionadas chamadas `AiTutor.onSlideChange(currentSlide)` em `nextSlide`, `prevSlide`, e `goToSlide`.
- **scorm_exporter.py**: Gera array `slideContexts` com conteúdo de cada slide (texto, HTML, quiz, botões).
- **export.py**: Gera `slideContexts` para exportação HTML, fallback para `BASE_URL` na detecção de `apiUrl`.
- **html_exporter.py**: Chama `AiTutor.onSlideChange()` quando slides são renderizados.
- **tutor.css**: Adicionado estilo para indicador de slide no chat.

### Mar 9, 2026 - Bug Fix: Gallery Images Broken in Export
- **Root Cause**: SCORM and HTML exporters used current project ID to look up gallery images, but gallery images reference assets from OTHER projects (`/api/projects/OTHER_ID/assets/...`). The asset wasn't found because it doesn't belong to the current project.
- **Fix (scorm_exporter.py)**: Added a pre-scan of all slide elements to collect referenced project IDs, then copies their assets into the package. Also modified the embed logic to extract source project ID from URLs and search in the correct project's directory.
- **Fix (html_exporter.py)**: Modified image element processing and HTML content image processing to extract source project ID from gallery URLs and search in the correct directories + MongoDB.
- **Verified**: Export now shows `Embedded image as data URI from local file: ai_img_xxx.png` instead of `Could not find image anywhere`.
- **Root Cause**: `pre-start.sh` ran `fix_nginx_modules.sh` which replaced the deployment's nginx config with a preview proxy config that forwards `location /` to `localhost:3000` (React dev server). In deployment, there is NO dev server - frontend is pre-built static files. This caused all health checks to timeout.
- **Fix**: Modified `fix_nginx_modules.sh` to detect deployment mode (checks for `asset-manifest.json` and `static/` directory in `/usr/share/nginx/html/`). In deployment mode, serves static files with `try_files`. In preview mode, proxies to dev server on port 3000.
- **Also fixed**: Cleaned up `.gitignore` - removed broken `-e ` entries and duplicate/redundant patterns.

### Mar 7, 2026 - Dashboard Metrics & AI Tutor
- Added `GET /api/dashboard/metrics` endpoint (totalCourses, totalSlides, totalExports)
- Added export logging to `export_logs` collection
- Added metrics cards to Dashboard UI (3 cards with icons)
- Integrated AI Tutor into HTML export (was SCORM-only before)
- Added `_generate_tutor_block()` to html_exporter.py
- Fixed tutor.js to support CSS inlining for HTML exports

### Mar 7, 2026 - Frontend Refactoring
- Editor.jsx: 5709 -> 3639 lines (36% reduction)
- Agent.jsx: 3593 -> 1024 lines (71% reduction)

## File Structure
```
frontend/src/pages/
├── Dashboard.jsx           (metrics + project list)
├── Editor.jsx              (3639 lines - orchestrator)
├── Editor/
│   ├── utils.js
│   ├── hooks/              (5 hooks)
│   └── components/         (5 components)
├── Agent.jsx               (1024 lines - orchestrator)
└── Agent/
    └── components/         (5 panels)

backend/
├── routes/
│   ├── admin.py            (tutor settings + chat + metrics)
│   └── export.py           (SCORM/HTML/Video + export logging)
├── services/
│   ├── scorm_exporter.py   (tutor integration)
│   ├── html_exporter.py    (tutor integration added)
│   └── export_assets/
│       ├── tutor.js        (chat widget)
│       └── tutor.css       (chat styles)
```

## Known Issues
- HeyGen Video Generation: Blocked by user's API credits being 0 (external)

## Backlog
### P0
- SCORM 2004 & xAPI Export implementation
### P1
- Further Editor.jsx dialog extraction (~1200 lines)
### P2
- Advanced AI Tutor interactivity features
### Cancelled
- Synthesia Integration (user decided cost was too high)

## Credentials
- Admin: admin@scormify.com / admin123
