# Scormify - PPT to SCORM Converter

## Original Problem Statement
Criar um aplicativo web que converte arquivos PPT/PPTX para pacotes SCORM 1.2 com fidelidade visual, editor de slides, timeline de animações/áudio, e exportação compatível com LMS.

## Architecture
- **Frontend**: React + Tailwind CSS + Shadcn/UI
- **Backend**: FastAPI (Python)
- **Database**: MongoDB
- **File Storage**: Local filesystem (/app/backend/storage)
- **PPT Conversion**: LibreOffice (headless) + pdf2image

## User Personas
1. **Instructional Designers** - Create e-learning content from existing PPT presentations
2. **Training Managers** - Need SCORM packages for LMS deployment
3. **Content Creators** - Build interactive courses with multimedia

## Core Requirements
- [x] PPT/PPTX file upload and parsing (via LibreOffice)
- [x] High-fidelity slide rendering (slides as PNG images)
- [x] Slide editor with canvas
- [x] Text, shape, image, video elements (overlay on slide images)
- [x] Video resize and move functionality
- [x] Timeline for animations
- [x] Audio recording (Web Audio API)
- [x] Audio upload (slide-specific or global soundtrack)
- [x] YouTube/Vimeo embedding
- [x] Global soundtrack support
- [x] Slide CRUD (create, duplicate, delete, reorder)
- [x] Annotation tools (freehand drawing)
- [x] SCORM 1.2 export with valid manifest
- [x] Dark/Light theme toggle
- [x] Project management (dashboard, delete)

## What's Been Implemented

### Backend (server.py)
- Project CRUD API endpoints
- PPT parsing via LibreOffice + pdf2image pipeline
- Slide/Element management
- Media upload (images, audio, video)
- **Audio Upload**: Slide-specific and global audio endpoints
- SCORM 1.2 package generation
- Valid imsmanifest.xml with namespaces
- XSD schema files

### Frontend
- Dashboard with project list and delete functionality
- Editor with:
  - Left sidebar: Slide thumbnails with context menu
  - Main canvas: Interactive elements overlay on slide images
  - Right sidebar: Properties panel, Layers, Media tab
  - Toolbar: Text, Shape, Image, Video, Annotations, Recording
  - Timeline: Element tracks and playhead
- **Audio Upload Dialog**: Choose between "Slide Atual" or "Todos os Slides"
- **Video Element Controls**: Resize handles, move functionality, delete button
- Theme toggle (dark/light)
- Export dialog with download

## Recent Bug Fixes (January 2026)

### Audio Upload Bug - FIXED
- **Issue**: Audio upload was not working
- **Root Cause**: Missing Dialog component in Editor.jsx for audio target selection
- **Fix Applied**: 
  1. Added Audio Upload Dialog with options "Slide Atual" and "Todos os Slides"
  2. Backend adjusted to receive audio_type via Form() instead of query parameter
- **Status**: CONFIRMED FIXED (verified by testing agent)

### Video Resize/Move Bug - FIXED
- **Issue**: Video elements were difficult to resize and move because the iframe captured all mouse events
- **Root Cause**: The YouTube/Vimeo iframe was intercepting all click/drag events
- **Fix Applied**:
  1. Added transparent overlay on video elements to capture mouse events
  2. Set `pointer-events: none` on iframe/video elements
  3. Enlarged resize handles for easier grabbing (4x4 corners, 8x3/3x8 edges)
  4. Added hover effects on resize handles
  5. Added visual indicators (YouTube/Vimeo badge, "Double-click to play" hint)
- **Status**: FIXED AND TESTED

### SCORM Export Positioning Bug - FIXED
- **Issue**: Images and videos in SCORM export had fixed size and position instead of respecting editor values
- **Root Cause**: 
  1. CSS `.image-element` had `width: 100%; height: 100%` directly on the img tag, overriding inline styles
  2. The `createElementNode` function was creating img tags directly instead of wrapping in a container div
- **Fix Applied**:
  1. Changed image rendering to use a container div with inline position/size, containing an img with 100% dimensions
  2. Ensured all position values use fallback defaults: `(element.x || 0)`
  3. Added `+1` to zIndex to prevent overlap with background
- **Status**: FIXED AND TESTED
- **Verification**: Exported SCORM shows correct inline styles: `left:500px;top:200px;width:310px;height:165px`

### Multiple Slides Blank in SCORM Export - FIXED
- **Issue**: Only the first slide had background image, all other slides were blank in SCORM export
- **Root Cause**: 
  1. The `poppler-utils` package (pdftoppm) was not installed
  2. The fallback method using `libreoffice --convert-to png` only generates ONE image for the entire presentation
  3. When pdf2image library tried to use pdftoppm, it failed silently and fell back to the single-image method
- **Fix Applied**:
  1. Installed `poppler-utils` package: `sudo apt-get install poppler-utils`
  2. Improved `convert_pptx_to_images_fallback()` function to use pdftoppm directly if pdf2image fails
  3. Added proper file renaming from pdftoppm output (slide-1.png, slide-2.png) to our format (slide_001.png, slide_002.png)
- **Status**: FIXED AND TESTED
- **Note**: Projects created before this fix need to be re-imported to regenerate all slide images

### Element Position/Size Not Persisting in SCORM Export - FIXED
- **Issue**: Video/image elements were not being exported with the correct size and position as shown in the Canvas editor
- **Root Cause**: 
  1. The `handleMouseUp` function in `SlideCanvas.jsx` was not explicitly saving the final position after drag/resize
  2. During rapid mouse movements, some position updates might be lost due to async operations
- **Fix Applied**:
  1. Added `pendingUpdateRef` to track the last known position during drag/resize operations
  2. Modified `handleMouseUp` to explicitly save the final position with `await onUpdateElement()`
  3. Added logging to confirm the final position is saved
- **Status**: FIXED AND TESTED
- **Verification**: 
  - Video resized to 1100x550 in editor
  - Exported SCORM shows: `style="left:0px; top:0px; width:1100px; height:550px"`
  - Coverage: 85.9% width, 76.4% height of slide

## Prioritized Backlog

### P0 (Critical)
- All implemented ✓

### P1 (High Priority)
- [ ] PPT animation extraction and playback
- [ ] Drag & drop slide reordering
- [ ] Element copy/paste
- [ ] Undo/redo history
- [ ] Gravação de áudio pelo microfone (melhorias)

### P2 (Medium Priority)
- [ ] PPT SmartArt rendering
- [ ] WordArt support
- [ ] Chart rendering
- [ ] Multiple audio tracks per slide
- [ ] Animation timeline editor
- [ ] SCORM tracking avançado (cmi.core.lesson_status, cmi.core.total_time)

### P3 (Future)
- [ ] Collaborative editing
- [ ] Template library
- [ ] Asset library
- [ ] Preview mode
- [ ] SCORM 2004 support

## Key API Endpoints

### Projects
- `GET /api/projects` - List all projects
- `POST /api/projects` - Create project
- `GET /api/projects/{id}` - Get project
- `PUT /api/projects/{id}` - Update project
- `DELETE /api/projects/{id}` - Delete project

### PPT Processing
- `POST /api/ppt/upload` - Upload and process PPT file
- `GET /api/job/{id}` - Check job status

### Slides
- `POST /api/projects/{id}/slides` - Add slide
- `PUT /api/projects/{id}/slides/{slide_id}` - Update slide
- `DELETE /api/projects/{id}/slides/{slide_id}` - Delete slide
- `POST /api/projects/{id}/slides/{slide_id}/duplicate` - Duplicate slide
- `POST /api/projects/{id}/slides/reorder` - Reorder slides

### Audio
- `POST /api/projects/{id}/slides/{slide_id}/audio` - Upload slide audio
- `POST /api/projects/{id}/global-audio` - Set global soundtrack

### Export
- `POST /api/course/{id}/export-scorm` - Export SCORM package
- `GET /api/exports/{filename}` - Download SCORM package

## Tech Stack
- React 18
- FastAPI
- MongoDB
- LibreOffice (headless)
- pdf2image / poppler-utils
- Tailwind CSS
- Shadcn/UI
- Lucide Icons

## Important Notes
- LibreOffice must be installed for PPT conversion (`sudo apt-get install libreoffice poppler-utils`)
- Slides are rendered as PNG images for high fidelity
- Editable elements are overlaid on top of slide images
- Asset URLs differ between editor (absolute) and SCORM package (relative)
- Video elements use transparent overlay to allow manipulation while preventing iframe event capture
