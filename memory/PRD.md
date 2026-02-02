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
- [x] Annotation tools (arrow, circle, rectangle, freehand) - **FULLY WORKING**
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

### Annotation Tools Bug - FIXED (Jan 22, 2026)
- **Issue**: Annotation tools (setas, círculos, retângulos) desapareciam após serem desenhadas
- **Root Cause**: A condição `annotationPoints.length > 2` no `handleMouseUp` exigia mais de 2 pontos, mas formas como seta, círculo e retângulo usam apenas 2 pontos (início e fim)
- **Fix Applied**:
  1. Alterado condição para `annotationPoints.length >= minPoints` onde `minPoints` é 3 para freehand e 2 para shapes
  2. Adicionado suporte completo para renderização de arrow, circle, rectangle na exportação SCORM (scorm_exporter.py)
  3. Definido `includeInExport: true` como padrão e aumentado `strokeWidth` para 3
- **Files Modified**:
  - `/app/frontend/src/components/editor/SlideCanvas.jsx` - handleMouseUp (linhas 224-236)
  - `/app/backend/services/scorm_exporter.py` - renderAnnotation function (expandido para todos os tipos)
- **Status**: FIXED AND TESTED (8/8 testes passando)
- **Verification**: Anotações agora persistem após desenho, são salvas no banco e aparecem na exportação SCORM

### Audio Management Features - ADDED
- **New Features**: 
  1. Remove global audio (trilha sonora)
  2. Remove slide audio (individual)
  3. Volume control for global soundtrack (0-100%)
  4. Volume control for slide audio (0-100%)
- **Backend Endpoints Added**:
  - `DELETE /api/projects/{id}/global-audio` - Remove global audio
  - `PUT /api/projects/{id}/global-audio/volume` - Update global volume
  - `DELETE /api/projects/{id}/slides/{slide_id}/audio/{audio_id}` - Remove slide audio
  - `PUT /api/projects/{id}/slides/{slide_id}/audio/{audio_id}/volume` - Update slide audio volume
- **Frontend Updates**:
  - Volume sliders in Media tab
  - "Reduza para não sobrepor a narração" hint for global audio
  - Delete buttons for each audio item
- **Status**: IMPLEMENTED AND TESTED

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

### Image Position/Size Not Correct in SCORM Export - FIXED
- **Issue**: Images appeared at different sizes in SCORM export compared to Canvas editor
- **Root Cause**: 
  1. The SCORM player container used fixed dimensions from the first slide only
  2. Different slides can have different dimensions (e.g., 1280x720 vs 960x540)
  3. When elements were positioned for a 960x540 slide but rendered in a 1280x720 container, they appeared proportionally smaller
- **Fix Applied**:
  1. Modified `renderSlide()` function in `scorm_exporter.py` to dynamically adjust container dimensions
  2. Added: `container.style.width = slideWidth + 'px'` and `container.style.height = slideHeight + 'px'`
  3. Container now matches each slide's actual dimensions
- **Status**: FIXED AND TESTED
- **Verification**: 
  - Image resized to 920x500 (95.8% x 92.6% coverage) 
  - SCORM export shows correct: `style="left:20px; top:20px; width:920px; height:500px"`

### Timeline Synchronization Feature - IMPLEMENTED (Jan 23, 2026)
- **Issue**: A Timeline era apenas um placeholder visual sem funcionalidade real
- **Solution Implemented**:
  1. Adicionados campos `startTime` e `endTime` ao modelo `SlideElement` no backend
  2. Criada sincronização entre Timeline e SlideCanvas - elementos aparecem/desaparecem baseado no tempo
  3. Implementado arrasto de clipes na timeline para ajustar tempos
  4. Adicionados handles de início/fim para ajuste preciso
  5. Playhead se move durante reprodução
  6. Controles de Play/Pause/Reset funcionando
  7. Highlight visual no clipe ativo (ring cyan)
  8. Tooltips com informação de tempo em cada clipe
  9. Persistência dos valores no MongoDB
- **Files Modified**:
  - `/app/backend/models.py` - Adicionados campos startTime/endTime ao SlideElement e ElementUpdate
  - `/app/frontend/src/components/editor/Timeline.jsx` - Reescrito com funcionalidade completa
  - `/app/frontend/src/components/editor/SlideCanvas.jsx` - Filtro de elementos por tempo
  - `/app/frontend/src/pages/Editor.jsx` - Estado compartilhado de timeline
- **Status**: IMPLEMENTED AND TESTED

### HeyGen Avatar Video Integration - IMPLEMENTED (Feb 2, 2026)
- **Feature**: Generate AI avatar videos with lip-sync from text scripts
- **Implementation**:
  1. Backend endpoints for HeyGen API (avatars, voices, video generation, status)
  2. Frontend dialog with avatar grid, voice selector, script editor
  3. Progress indicator during video generation
  4. Video preview and add-to-slide functionality
  5. Portuguese voices filter (49 voices available)
- **API Key**: Configured in backend/.env (user provided)
- **Endpoints Added**:
  - `GET /api/heygen/avatars` - Lists 100 avatars with previews
  - `GET /api/heygen/voices` - Lists voices filtered by language
  - `POST /api/heygen/generate-video` - Starts video generation
  - `GET /api/heygen/video-status/{id}` - Polls generation status
- **Files Modified**:
  - `/app/backend/server.py` - Added HeyGen API routes
  - `/app/backend/.env` - Added HEYGEN_API_KEY
  - `/app/frontend/src/pages/Editor.jsx` - Added avatar button and dialog
- **Status**: IMPLEMENTED

### New Elements: Button, HTML, Flipbook - IMPLEMENTED (Jan 30, 2026)
- **Feature**: Added 3 new element types to slides
- **Implementation**:
  1. **Button Element** (🔗): Configurable link buttons with text, URL, icon, 4 styles (primary/secondary/outline/ghost), new tab option
  2. **HTML Element** (`</>`): Custom HTML/CSS/JS code rendered in isolated iframe
  3. **Flipbook Element** (📖): Support for external URLs (FlipHTML5, Issuu), PDF, or multiple images with navigation
- **Editor**: New toolbar buttons + configuration dialogs for each type
- **SCORM Export**: Full support with styled buttons and embedded content
- **Files Modified**:
  - `/app/backend/models.py` - Added buttonText, buttonUrl, buttonIcon, buttonStyle, htmlContent, flipbookType, flipbookUrl, flipbookPages fields
  - `/app/frontend/src/pages/Editor.jsx` - Added 3 dialogs and toolbar buttons
  - `/app/frontend/src/components/editor/SlideCanvas.jsx` - Render logic for new elements
  - `/app/backend/services/scorm_exporter.py` - SCORM export with CSS styles
- **Status**: IMPLEMENTED AND TESTED

### SCORM Sidebar Navigation - IMPLEMENTED (Jan 29, 2026)
- **Feature**: Added slide navigation sidebar menu for students
- **Implementation**:
  1. Hamburger menu button (☰) in controls bar
  2. Slide-out sidebar with all slides listed
  3. Thumbnail preview for each slide using background image
  4. Status indicators: ✓ Completed | ● Current | ○ Pending
  5. Direct navigation by clicking any slide
  6. Auto-scroll to keep current slide visible
  7. Smooth open/close animation
  8. Translated buttons to Portuguese (Anterior/Próximo)
- **Files Modified**:
  - `/app/backend/services/scorm_exporter.py` - Added sidebar HTML, CSS, and JS functions
- **Status**: IMPLEMENTED

### SCORM Volume Control - IMPLEMENTED (Jan 29, 2026)
- **Issue**: Volume button in exported SCORM was not functional (icon only, no action)
- **Fix Applied**:
  1. Added `toggleVolumeSlider()` function to show/hide volume slider popup
  2. Added `setVolume(value)` function to adjust volume (0-100%)
  3. Added `toggleMute()` function for mute/unmute
  4. Added CSS styles for volume slider popup with gradient thumb
  5. Volume control affects both global audio and slide-specific audios
  6. Dynamic icon changes: 🔊 (high) → 🔉 (medium) → 🔇 (muted)
- **Files Modified**:
  - `/app/backend/services/scorm_exporter.py` - Added volume control functions and UI
- **Status**: IMPLEMENTED AND TESTED

### Element Delete Bug (404 Error) - FIXED (Jan 25, 2026)
- **Issue**: Users reported "Request failed with status code 404" when trying to delete images
- **Root Cause**: 
  1. Elements with `visible: false` were not being rendered in the canvas, making them impossible to select and delete
  2. Elements with `opacity: 0.0` in their style were completely invisible
  3. The filter condition `if (el.visible === false) return false` was hiding elements during editing
- **Fix Applied**:
  1. Modified `SlideCanvas.jsx` to show all elements during editing (only filter by visibility during timeline playback)
  2. Hidden elements (`visible: false`) now render with 30% minimum opacity and yellow dashed border
  3. Added validation and logging in `deleteElement` function in `ProjectContext.jsx`
  4. Added error handling in `Editor.jsx` for undefined `currentSlide.id`
  5. Elements now use `scale` factor for proper responsive positioning
- **Files Modified**:
  - `/app/frontend/src/components/editor/SlideCanvas.jsx` - Element visibility filter, opacity handling
  - `/app/frontend/src/contexts/ProjectContext.jsx` - Added ID validation and console logging
  - `/app/frontend/src/pages/Editor.jsx` - Added validation for delete/update operations
- **Status**: FIXED AND TESTED
- **Verification**: Elements can now be selected and deleted without 404 errors

## Prioritized Backlog

### P0 (Critical)
- All implemented ✓

### P1 (High Priority)
- [ ] PPT animation extraction and playback
- [x] Drag & drop slide reordering (DONE)
- [x] Timeline synchronization (DONE)
- [ ] Element copy/paste
- [ ] Undo/redo history
- [ ] Gravação de áudio pelo microfone (melhorias)

### P2 (Medium Priority)
- [ ] PPT SmartArt rendering
- [ ] WordArt support
- [ ] Chart rendering
- [ ] Multiple audio tracks per slide
- [x] Animation timeline editor (DONE - Timeline now functional)
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
