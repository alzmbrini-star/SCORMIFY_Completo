# Changelog

## 2026-03-25 (Current Session)

### Bug Fix: AI-Generated HTML Breaking Editor CSS
- **Root Cause**: AI-generated HTML contains full `<!DOCTYPE html>` documents with global CSS styles. When embedded inside another `<html>` wrapper in the iframe's `srcDoc`, the nested HTML structures conflicted, causing CSS to leak/override the dark theme.
- **Fix**: Added detection in all iframe renderers (SlideCanvas, CoursePreview, SplitPreview, player.js, html_exporter.py) to check if content is a full HTML document (`<!DOCTYPE html>` or `<html>`). Full documents are rendered directly as srcDoc without wrapping.
- **Applied in**: 
  - `frontend/src/components/editor/SlideCanvas.jsx`
  - `frontend/src/components/editor/CoursePreview.jsx`
  - `frontend/src/components/editor/SplitPreview.jsx`
  - `backend/services/export_assets/player.js`
  - `backend/services/html_exporter.py`
- **Status**: Tested ✅ — dark theme restored, HTML elements render correctly

### Feature: AI-Powered HTML Generation in Editor
- **What**: Added "Gerar com IA" tab in HTML dialog with prompt, preview, and code editor
- **Backend**: `POST /api/generate-html` using Gemini (gemini-3-flash-preview)
- **Status**: Tested ✅ (iteration_78)

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
