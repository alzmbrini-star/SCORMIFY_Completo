# Changelog

## 2026-03-25 (Current Session)

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
