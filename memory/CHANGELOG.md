# Scormfy - Changelog

## 2026-03-05

### Backend Refactoring (Major)
- `server.py` reduced from 5740 → 318 lines (95% reduction)
- Created 14 modular route files in `routes/` directory
- Testing agent validated 23/23 endpoints + all frontend pages

### Smart Edit Mode
- Detects which slides were modified when editing media of existing project
- Cost estimate reflects only changed slides (not entire course)
- Backend `apply-media-changes` endpoint accepts `changedSlides` parameter
- Only applies changes to specified slide indices

### Global Background Control
- New "Fundo Global" section with "Todos os Slides" badge
- Applies same background (solid, gradient, image, AI image) to all slides at once
- Placed above per-slide list for easy access

### Bug Fixes
- MongoDB supervisor config restored (was removed in previous session)
- "Aplicar Alterações" button: Fixed narrationVoiceId restoration from session  
- Editor slide thumbnails: Fixed background image rendering + HTML font-size
- Added `useMemo` import for changed slide calculation
- Added `StreamingResponse`, `Request`, `BackgroundTasks` imports to route modules
