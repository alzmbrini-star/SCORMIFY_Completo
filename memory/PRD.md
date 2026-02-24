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

## Audio Timeline Fix v2 + Slide Progress Bar (Feb 2026)
- **Audio fix reforçado:** Reescrita completa do `playSlideAudio` com 3 modos:
  1. **Timeline mode:** Quando algum áudio tem `startTime > 0`, agenda via `setTimeout` no tempo correto
  2. **Sequential mode:** Quando múltiplos áudios sem `startTime`, encadeia via evento `ended`
  3. **Single mode:** Áudio único toca imediatamente
  - Adicionado logging `[Audio]` para debug no console do browser
  - Sort por `startTime` antes de processar
- **Barra de progresso do slide:** 
  - Barra fina (4px, 6px ao hover) na base do slide mostrando progresso temporal
  - Baseada na `duration` do slide via `setInterval(50ms)`
  - Ao completar 100%: muda para verde com pulso luminoso (2x), indicando que as animações finalizaram
  - Posicionada absolutamente dentro do `#slide-wrapper`, z-index 500
- **Tested:** 21/21 tests passed (iteration_32)

## PPT Text Visibility Fix (Feb 2026)
- **Root cause:** 3 problemas que tornavam textos de PPT invisíveis no SCORM:
  1. **Cor branca sobre branco:** Body CSS tem `color:#fff`, textos importados de PPT não possuem `fontColor`, resultando em texto branco sobre fundo branco
  2. **`visible:false`:** Elementos de PPT import têm `visible:false` e o player os pulava inteiramente
  3. **`opacity:0`:** Elementos de PPT import têm `style.opacity:0`, tornando-os permanentemente invisíveis
- **Fix:**
  1. Adicionado `color: #000000` como padrão para text e shape elements (alinhado com o editor)
  2. Removido o skip de `visible===false` — elementos agora são sempre renderizados
  3. `applyElementStyles` agora só aplica opacity quando `> 0`
- **Tested:** 16/16 tests passed (iteration_33)

## Backend Startup Optimization v2 (Feb 2026)
- **Root cause:** `emergentintegrations.llm.chat` (imports `litellm`, `grpcio`, `google-genai`, `openai`) era importado no nível do módulo (linhas 1835 e 1906), causando startup lento (~155s em produção ARM64)
- **Fix:** Convertido para lazy imports dentro das funções `generate_ai_script` e `generate_slide_narration`
- **Result:** Startup time reduzido de 2.71s para 0.43s localmente (6x mais rápido). Em produção ARM64, deve reduzir de ~155s para poucos segundos.
- **Tested:** Deployment agent check PASS. Health endpoint responde em <0.5s.

## Audio Timeline Fix v3 — Timer Initialization Bug (Feb 2026)
- **Root cause:** `window.audioTimelineTimers` nunca era inicializado como `[]` porque `stopAllSlideAudios` só o criava dentro de `if (window.audioTimelineTimers)` — que falhava na primeira chamada (undefined). Os `.push()` falhavam silenciosamente, e os callbacks dos `setTimeout` retornavam sem tocar.
- **Fix:** Adicionado `window.audioTimelineTimers = []` explicitamente no início de `playSlideAudio`, ANTES de qualquer código que use o array.
- **Browser test:** Confirmou `timers: 3` (antes era `undefined`) e `[Audio] Playing audio 1 at 0 s` (antes não aparecia).
- **Tested:** 16/16 tests passed (iteration_34)

## Slide Thumbnail Previews (Feb 2026)
- **Root cause:** Slide thumbnails in the editor's left sidebar were blank/white when slides were manually created (no backgroundImage from PPT import). Only showed a centered slide number.
- **Fix:** Created `SlideThumbnailContent` component that renders a miniature version of all slide elements (text, images, shapes, video placeholders, buttons, HTML, quiz) at their original pixel positions. A parent container with CSS `transform: scale()` (dynamically calculated via `ResizeObserver`) scales the 960x540 canvas down to fit the thumbnail.
- **Elements supported:** text (with font/color/size), image (with asset URL resolution), shape (fill, stroke, border-radius), video (play icon placeholder), button (gradient/outline styles), HTML (label), quiz (label)
- **Tested:** 13/13 tests passed (iteration_35). Verified across 3 projects: PPT-imported slides, manually-created slides, mixed content.

## Deployment Health Check Fix v3 (Feb 2026)
- **Root cause:** 3 issues preventing successful deployment:
  1. **Frontend health check disabled:** `ENABLE_HEALTH_CHECK=false` in frontend/.env. When nginx routes `/health` to the frontend (port 3000), the dev server returned React's index.html instead of a JSON health response. The deployment's health probe received HTML and treated it as unhealthy.
  2. **emergent-health.conf removed:** `fix_nginx_modules.sh` deleted `/etc/nginx/conf.d/emergent-health.conf`, the deployment orchestrator's own health check config file.
  3. **.env files blocked by .gitignore:** Lines `*.env` and `*.env.*` in `.gitignore` prevented .env files from being included in the repo, causing deployment failures when the container couldn't find required environment configuration.
- **Fix:**
  1. Set `ENABLE_HEALTH_CHECK=true` in `frontend/.env` — the CRA dev server now serves JSON health endpoints at `/health`, `/health/ready`, `/health/live`, `/health/simple`
  2. Removed the `rm -f emergent-health.conf` line from `fix_nginx_modules.sh` — deployment's health conf is preserved
  3. Removed `*.env` and `*.env.*` entries from `.gitignore`
- **Result:** Health check at `/health` now returns `{"status":"healthy"}` from both frontend (port 3000) and backend (port 8001). Deployment orchestrator's health config is preserved.

## Backlog
- **P2:** Refactor `backend/src/exporters/html_exporter.py` to use external templates for HTML, CSS, JS
- **P2:** Refactor `backend/server.py` into multiple APIRouter files
