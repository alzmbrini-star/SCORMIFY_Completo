# Changelog

## 2026-03-25 (Current Session)

### Feature: AI-Powered HTML Generation in Editor
- **What**: Added "Gerar com IA" tab in the HTML insert dialog (<> icon). Users can type a prompt describing what they want (quiz, timer, simulator, etc.) and the AI generates complete interactive HTML+CSS+JS.
- **Flow**: Prompt → Gerar HTML → Preview (iframe) + Editar Código → Inserir no Slide
- **Backend**: New `POST /api/generate-html` endpoint using Gemini (gemini-3-flash-preview) with specialized system prompt for web content generation
- **Frontend**: Dialog now has two tabs: "Colar HTML" (existing) + "Gerar com IA" (new). After generation, sub-tabs for Preview and Code Editor.
- **Applied in**: `backend/routes/agent.py` (GenerateHtmlRequest model + endpoint), `frontend/src/pages/Editor.jsx` (dialog rewrite with Tabs)
- **Status**: Tested ✅ (iteration_78, 100% backend + frontend)

### Bug Fix: AI Tutor 404 in Production SCORM Exports
- **Root Cause**: `_get_external_url()` wasn't using `X-Forwarded-Host` headers from K8s proxy
- **Fix**: Uses `X-Forwarded-Host` + `X-Forwarded-Proto` as primary URL source
- **Status**: Tested ✅ (iteration_77)

### CRITICAL Bug Fix: Missing Route Registrations
- **Root Cause**: 8 route modules never registered in server.py (companies, users, etc.)
- **Fix**: Added all missing imports and include_router() calls
- **Status**: Tested ✅ (iteration_76)

### Bug Fix: AI Tutor URL priority + Fix Simulators UI Button
- **Status**: Tested ✅ (iteration_75)

## Previous Sessions
- SCORM completion fix, HTML scenario fix, deployment fix
- Background images export fix, login fix, [object Object] fix
- Before/After Preview + Undo, AI improvements layout fix
- Gamification system, AI Agent scenario fix
