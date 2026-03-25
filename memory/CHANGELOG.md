# Changelog

## 2026-03-25 (Current Session - Fork 2, continued)

### Bug Fix: AI Tutor 404 in Production SCORM Exports
- **Root Cause**: `_get_external_url()` in `export.py` read `BASE_URL` from `.env` which had the PREVIEW URL. In production, the Kubernetes ingress proxy changes the URL. The function wasn't aware of the actual external-facing URL.
- **Fix**: Modified `_get_external_url()` to accept an optional `Request` parameter. New priority order: `X-Forwarded-Host` + `X-Forwarded-Proto` (from K8s ingress) > `Referer` > `BASE_URL` from .env > `REACT_APP_BACKEND_URL` from .env. All 4 callers in export.py now pass the request object.
- **Key insight**: The K8s proxy replaces `Origin` header with internal cluster URL, but preserves `X-Forwarded-Host` with the external URL.
- **Applied in**: `backend/routes/export.py` (function + 4 call sites)
- **Status**: Tested — SCORM/HTML exports use correct external URL ✅ (iteration_77)

### CRITICAL Bug Fix: Missing Route Registrations (Companies, Users, etc.)
- **Root Cause**: 8 route modules never registered in server.py
- **Fix**: Added all 8 missing route imports and include_router() calls
- **Applied in**: `backend/server.py`
- **Status**: Tested ✅ (iteration_76)

### Bug Fix: AI Tutor URL priority in SCORM export
- **Fix**: Changed priority from DB settings > env to env > DB settings
- **Status**: ✅ (iteration_75)

### Feature: Fix Simulators UI Button
- Added "Ferramentas" dropdown menu to Editor header
- **Status**: ✅ (iteration_75)

## 2026-03-24 (Previous Sessions - see previous changelog entries)
- SCORM completion fix, HTML scenario fix, deployment fix
- Background images export fix, login fix, [object Object] fix
- Before/After Preview + Undo, AI improvements layout fix
- Gamification system, AI Agent scenario fix
