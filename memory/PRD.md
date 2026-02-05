# Scormify - PPT to SCORM Converter

## Original Problem Statement
Criar um aplicativo web que converte arquivos PPT/PPTX para pacotes SCORM 1.2 com fidelidade visual, editor de slides, timeline de animações/áudio, e exportação compatível com LMS.

## Architecture
- **Frontend**: React + Tailwind CSS + Shadcn/UI
- **Backend**: FastAPI (Python)
- **Database**: MongoDB
- **File Storage**: Local filesystem (/app/backend/storage)
- **PPT Conversion**: LibreOffice (headless) + pdf2image
- **Third-Party Integrations**: HeyGen API (avatares de IA), Emergent LLM Key (geração de scripts)

## Changelog (Recent Updates)

### 2025-02-02
- **CORREÇÃO: Timeout HeyGen** - Aumentado o tempo limite de polling de 5 para 15 minutos
  - Adicionado contador de tempo decorrido na interface
  - Melhorado feedback visual com barra de progresso animada
  - Mensagens mais claras sobre tempo de espera (2-10 minutos)
  - Dica dinâmica após 2 minutos de espera
  - Limpeza adequada do timer quando o diálogo é fechado

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

## Recent Fixes (February 4, 2026)

### Image Insertion Dimensioning Fix
- **Issue**: Imagens inseridas usavam dimensões percentuais ('100%', '100%') que quebravam drag/resize
- **Root Cause**: Strings percentuais não eram compatíveis com o sistema de manipulação de elementos
- **Fix Applied**: Imagens agora usam dimensões em pixels (960x540) para cobrir o slide
- **Files Modified**: `/app/frontend/src/pages/Editor.jsx` - handleImageUpload function
- **Status**: FIXED

### Fullscreen Multiple Videos Fix
- **Issue**: Sair do fullscreen em um vídeo reiniciava todos os outros vídeos no slide
- **Root Cause**: O evento de resize após fullscreen causava re-render do slide inteiro
- **Fix Applied**: 
  1. Adicionada função `restoreAllVideoStates()` para restaurar estados de todos os vídeos
  2. Extendido tempo de proteção de re-render para 3 segundos após sair do fullscreen
  3. Adicionado logging para debug
- **Files Modified**: `/app/backend/services/scorm_exporter.py` - handleFullscreenChange function
- **Status**: FIXED (requires export to apply)

### Mobile Orientation Overlay Fix
- **Issue**: A overlay de orientação mobile não aparecia em dispositivos móveis no modo retrato
- **Root Cause**: Detecção via JavaScript não funcionava corretamente em iframes de LMS
- **Fix Applied**: Adicionadas media queries CSS que forçam a exibição da overlay em modo retrato
  - `@media screen and (orientation: portrait) and (max-width: 900px)`
  - `@media screen and (max-aspect-ratio: 4/5) and (max-width: 900px)`
- **Files Modified**: `/app/backend/services/scorm_exporter.py` - CSS styles
- **Status**: FIXED (requires user testing on real mobile device)

### Annotation Pointer Alignment
- **Status**: CONFIRMED FIXED by user (Feb 4, 2026)

### Course Preview Mode - IMPLEMENTED (Feb 4, 2026)
- **Feature**: Preview the course directly in the editor before exporting SCORM
- **Implementation**:
  1. Full-screen preview modal with dark theme
  2. Slide navigation (prev/next buttons, keyboard arrows, sidebar thumbnails)
  3. Sidebar menu with all slides, thumbnails, and progress indicators
  4. Timeline playback with play/pause controls
  5. Volume control for global and slide audio
  6. Fullscreen mode support
  7. Element visibility based on timeline settings
  8. Annotations rendering with all shapes (freehand, arrow, circle, rectangle)
  9. Support for all element types (text, image, shape, video, button, HTML, flipbook)
- **Files Created**:
  - `/app/frontend/src/components/editor/CoursePreview.jsx`
- **Files Modified**:
  - `/app/frontend/src/pages/Editor.jsx` - Added preview button and state
- **Status**: IMPLEMENTED AND TESTED

### HeyGen Integration Improvements - IMPLEMENTED (Feb 4, 2026)
- **Feature 1**: Credit balance check before video generation
  - New endpoint: `GET /api/heygen/credits` - Returns remaining quota
  - UI shows credits in dialog header with visual indicator (green/red)
  - Prevents video generation if no credits available
- **Feature 2**: Webhook support for video completion notifications
  - New endpoint: `POST /api/heygen/webhook` - Receives HeyGen callbacks
  - New endpoint: `GET /api/heygen/webhook-url` - Returns webhook URL and setup instructions
  - Automatically updates video status in database when webhook received
- **Files Modified**:
  - `/app/backend/server.py` - Added 3 new endpoints
  - `/app/frontend/src/pages/Editor.jsx` - Added credits display and validation
- **Status**: IMPLEMENTED

### Slide Dimension Normalization - IMPLEMENTED (Feb 4, 2026)
- **Feature**: Normalize all slides to consistent dimensions
  - New endpoint: `POST /api/projects/{id}/normalize-dimensions`
  - Scales element positions and sizes proportionally
  - New slides inherit dimensions from first slide
- **Files Modified**:
  - `/app/backend/server.py` - Added normalization endpoint
  - `/app/backend/models.py` - Added width/height to SlideCreate
  - `/app/frontend/src/contexts/ProjectContext.jsx` - Inherit dimensions on addSlide
- **Status**: IMPLEMENTED

### HTML Export Desktop Blank Screen Fix - FIXED (Feb 4, 2026)
- **Issue**: O player HTML exportado aparecia em branco no desktop após adicionar recurso de "auto fullscreen" para mobile landscape
- **Root Cause**: 
  1. O media query CSS `@media screen and (orientation: landscape) and (max-width: 1024px)` era muito amplo e afetava janelas de desktop redimensionadas
  2. O endpoint `serve_export` retornava `application/zip` para todos os arquivos, forçando download do HTML
- **Fix Applied**:
  1. Modificados os media queries CSS para detectar apenas dispositivos móveis reais:
     - Adicionado `max-height: 450px` (telas móveis em landscape têm altura limitada)
     - Adicionado `max-width: 950px` (mais restritivo)
     - Adicionado `pointer: coarse` para detectar dispositivos touch
  2. Atualizada função `isMobileLandscape()` em JavaScript para usar detecção mais precisa
  3. Corrigido `FileResponse` para retornar `text/html` para arquivos HTML e `application/zip` para ZIPs
- **Files Modified**:
  - `/app/backend/services/html_exporter.py` - CSS media queries (linhas 311-357) e função isMobileLandscape()
  - `/app/backend/server.py` - Endpoint serve_export (linha 1147)
- **Status**: FIXED AND TESTED (100% success rate)
- **Verification**: Player HTML funciona corretamente em viewports 1920x800 e 1024x768

### HTML Export JSON Parsing Fix - FIXED (Feb 4, 2026)
- **Issue**: Alguns projetos exportados como HTML mostravam slide em branco (1/1) mesmo tendo múltiplos slides
- **Root Cause**: 
  1. Elementos com `htmlContent` (código HTML embutido) continham caracteres especiais (quebras de linha, aspas, `</script>`) que quebravam o JSON embutido no HTML
  2. O JSON ficava inválido e o player não conseguia ler os slides
- **Fix Applied**:
  1. Adicionado encoding Base64 para campos `htmlContent` durante a exportação
  2. O conteúdo HTML é prefixado com `__B64__:` para identificação
  3. Adicionada decodificação automática no JavaScript do player usando `atob()`
  4. Mantido escape de `</script>` para segurança adicional
- **Files Modified**:
  - `/app/backend/services/html_exporter.py` - Função `generate_html_template()` (linhas 203-220)
  - `/app/backend/services/html_exporter.py` - Renderização de elementos HTML (linhas 1048-1060)
- **Status**: FIXED AND TESTED
- **Verification**: Projeto "Ferramenta de Criação de Rapid Learning" com 11 slides agora exporta e renderiza corretamente

### HeyGen Integration Improvements - IMPLEMENTED (Feb 5, 2026)
- **Feature**: Melhorias na integração com HeyGen para geração de vídeos com avatar
- **Improvements Applied**:
  1. **Cache de Créditos**: Créditos são cacheados por 60 segundos para evitar chamadas repetidas à API lenta da HeyGen
  2. **Loading Separado**: O carregamento de créditos agora é separado do carregamento de avatares/vozes, não bloqueando a UI
  3. **Server-Sent Events (SSE)**: Implementado endpoint SSE para receber atualizações em tempo real do webhook
  4. **Webhook Melhorado**: Webhook agora notifica subscribers SSE quando um vídeo é concluído
  5. **Fallback para Polling**: Se SSE falhar, o sistema automaticamente volta ao polling tradicional
- **Files Modified**:
  - `/app/backend/server.py`:
    - Adicionado cache para créditos (linhas 72-80)
    - Adicionado sistema de subscribers SSE (linha 81)
    - Atualizado endpoint `/api/heygen/credits` para usar cache
    - Atualizado endpoint `/api/heygen/webhook` para notificar SSE subscribers
    - Novo endpoint `/api/heygen/video-events/{video_id}` para SSE
  - `/app/frontend/src/pages/Editor.jsx`:
    - Adicionado estado `heygenCreditsLoading` separado
    - Atualizado `loadHeygenData()` para carregar créditos separadamente
    - Atualizado `pollHeygenVideoStatus()` para usar SSE com fallback para polling
    - UI atualizada para mostrar "Verificando créditos..." durante loading
- **Status**: IMPLEMENTED AND TESTED
- **Verification**: Dialog do HeyGen carrega instantaneamente com avatares/vozes, créditos são exibidos assim que disponíveis

### Webhook Configuration Helper - AVAILABLE
- **Endpoint**: `GET /api/heygen/webhook-url`
- **Returns**: URL do webhook e instruções para configurar no dashboard da HeyGen
- **Note**: O usuário precisa configurar o webhook no dashboard da HeyGen para receber notificações em tempo real

### HeyGen Avatar and Voice Filters - IMPLEMENTED (Feb 5, 2026)
- **Feature**: Filtros avançados para avatares e vozes no diálogo HeyGen
- **Improvements Applied**:
  1. **Filtro de Gênero para Avatares**: Dropdown para filtrar por Masculino/Feminino/Todos
  2. **Mais Avatares**: Limite aumentado de 100 para 200 avatares
  3. **Indicador Visual de Gênero**: Símbolo ♂/♀ no canto de cada avatar
  4. **Filtro de Idioma para Vozes**: Dropdown com bandeirinhas (🇧🇷🇵🇹🇺🇸🇬🇧🇪🇸🇫🇷🇩🇪🇮🇹)
  5. **Filtro de Gênero para Vozes**: Dropdown separado para gênero
  6. **Contador de Itens**: Mostra quantidade de avatares/vozes disponíveis
  7. **Bandeira na Lista de Vozes**: Cada voz mostra bandeira do país + indicador de gênero
- **Files Modified**:
  - `/app/backend/server.py`:
    - Endpoint `/api/heygen/avatars` - Adicionado parâmetro `gender` e retorna `available_genders`
    - Endpoint `/api/heygen/voices` - Adicionado parâmetros `language` e `gender`, retorna `available_languages` e `available_genders` com bandeirinhas
    - Lógica para detectar PT-BR vs PT-PT pelo nome da voz (ex: "Sofia Brazil")
  - `/app/frontend/src/pages/Editor.jsx`:
    - Novos estados: `heygenAvatarGenderFilter`, `heygenVoiceLanguageFilter`, `heygenVoiceGenderFilter`, `heygenAvailableGenders`, `heygenAvailableLanguages`
    - Novas funções: `reloadHeygenAvatars()`, `reloadHeygenVoices()`
    - UI atualizada com dropdowns de filtro e contadores
- **Status**: IMPLEMENTED AND TESTED
- **Verification**: Filtros funcionando - 689 avatares femininos, 49 vozes em português com bandeiras

### Rich Text Editor with AI Generation - IMPLEMENTED (Feb 5, 2026)
- **Feature**: Editor de texto rico com geração de conteúdo por IA (GPT-4o)
- **Capabilities**:
  1. **Geração de Texto com IA**: Botão "Gerar com IA" abre prompt para descrever o conteúdo desejado
  2. **Formatação Avançada**: Títulos (H1, H2, H3), Negrito, Itálico, Sublinhado, Riscado
  3. **Alinhamento**: Esquerda, Centro, Direita, Justificado
  4. **Listas**: Com bullets e numeradas
  5. **Inserção de Mídia**: Links, Imagens, Tabelas
  6. **Undo/Redo**: Histórico de alterações
  7. **Texto em Português**: IA configurada para gerar conteúdo em PT-BR
- **API Endpoint**: `POST /api/ai/generate-text`
  - Request: `{ "prompt": "string", "context": "string?", "format": "html" }`
  - Response: `{ "success": true, "content": "<html>..." }`
- **Files Created/Modified**:
  - `/app/frontend/src/components/RichTextEditor.jsx` - Componente do editor RTF
  - `/app/backend/server.py` - Endpoint `/api/ai/generate-text` usando emergentintegrations com GPT-4o
  - `/app/frontend/src/pages/Editor.jsx` - Integração do editor no fluxo de criação de slides
- **Dependencies**:
  - Backend: `emergentintegrations` (instalado)
  - Frontend: ContentEditable nativo (sem dependências externas pesadas)
- **Status**: IMPLEMENTED AND TESTED
- **Verification**: Geração de texto formatado funcionando com títulos, listas e negrito

### Rich Text Editor Improvements - IMPLEMENTED (Feb 5, 2026)
- **Feature 1: Enhanced Table Formatting**
  - Configuração de tabela com seletor de linhas/colunas
  - Preview visual da grade antes de inserir
  - Header com gradiente escuro (#475569 → #334155)
  - Borda cyan abaixo do header (border-bottom: 2px solid #22d3ee)
  - Linhas alternadas (zebra striping: #1e293b e #1a2433)
  - Bordas arredondadas (border-radius: 8px)
  - Sombra elegante (box-shadow)
  - Classe CSS: `rtf-table`
  
- **Feature 2: Image Resize Functionality**
  - Seleção de imagem ao clicar (adiciona classe `selected-image`)
  - Borda cyan e box-shadow na imagem selecionada
  - Cursor de redimensionamento (nwse-resize)
  - Arrasto no canto inferior direito (zona de 20px)
  - Preservação do aspect ratio durante redimensionamento
  
- **Files Modified**:
  - `/app/frontend/src/components/RichTextEditor.jsx` - Componente completo reescrito com:
    - Estado para configuração de tabela (tableRows, tableCols)
    - Estados para seleção/redimensionamento de imagem
    - Handlers para clique, seleção e arrasto
    - CSS avançado para tabelas e imagens
- **Status**: IMPLEMENTED AND TESTED
- **Verification**: Testing agent confirmou 100% de sucesso em todos os testes frontend

### Floating Image Feature - IMPLEMENTED (Feb 5, 2026)
- **Feature**: Capacidade de inserir imagens flutuantes ao lado do texto e movimentá-las arrastando
- **Implementation**:
  1. **Popover de imagem atualizado** com duas opções:
     - "Em linha" - imagem segue o fluxo do texto (comportamento padrão)
     - "Flutuante" - posição livre, pode ser arrastada
  2. **Imagens flutuantes** usam CSS class `floating-image` com:
     - `position: absolute`
     - `cursor: move`
     - `box-shadow` para efeito visual
     - Posição inicial: left: 20px, top: 20px
  3. **Funcionalidade de arraste**:
     - Clique na imagem para selecionar
     - Arraste para mover para qualquer posição
     - Posição salva no atributo style
- **Files Modified**:
  - `/app/frontend/src/components/RichTextEditor.jsx`:
    - `addImage(floating)` - Parâmetro para modo flutuante
    - `handleDragStart()` - Captura posição inicial
    - Effect para mouse move/up durante arraste
    - CSS styles para `.floating-image` e `.floating-image.selected-image`
- **Status**: IMPLEMENTED AND TESTED
- **Verification**: Testing agent confirmou drag de left:20px/top:20px para left:100px/top:60px

### Font and Color Selectors + Transparent Background - IMPLEMENTED (Feb 5, 2026)
- **Feature 1: Fundo Transparente**
  - CSS rules para `.rich-text-editor` e todos os filhos com `background-color: transparent !important`
  - Permite que o texto destaque com a cor do slide
  
- **Feature 2: Seletor de Fonte**
  - 10 fontes disponíveis: Arial, Helvetica, Verdana, Tahoma, Trebuchet MS, Georgia, Times New Roman, Courier New, Impact, Comic Sans MS
  - Cada fonte exibida no seu próprio estilo na lista
  - Aplicação via `document.execCommand('fontName')`
  
- **Feature 3: Seletor de Cor**
  - 20 cores predefinidas em grade 5x4
  - Cores incluem: branco, preto, primárias, secundárias, e tons modernos (#22d3ee, #a855f7, #ec4899, etc)
  - Color picker nativo do navegador para cor personalizada
  - Campo HEX para entrada manual (#FFFFFF)
  - Indicador de cor atual ao lado do ícone de paleta
  
- **Files Modified**:
  - `/app/frontend/src/components/RichTextEditor.jsx`:
    - FONTS array com 10 fontes
    - COLORS array com 20 cores
    - applyFont() e applyColor() functions
    - CSS styles para fundo transparente
- **Status**: IMPLEMENTED AND TESTED
- **Verification**: Testing agent confirmou todas as funcionalidades (17 testes passaram)

### Font Size Selector + Transparent Background Fix - IMPLEMENTED (Feb 5, 2026)
- **Feature 1: Seletor de Tamanho de Fonte**
  - 7 tamanhos disponíveis: 10px, 12px, 14px, 16px, 18px, 24px, 36px
  - Botão mostra tamanho atual na toolbar
  - Usa `document.execCommand('fontSize')` com valores 1-7
  
- **Feature 2: Correção do Fundo Transparente**
  - Removido `bg-white` do container do elemento HTML no SlideCanvas
  - iframe srcDoc envolve conteúdo em HTML completo com CSS:
    - `body { background: transparent !important; }`
    - `* { background: transparent !important; }`
  - Texto agora aparece diretamente sobre o fundo do slide
  
- **Files Modified**:
  - `/app/frontend/src/components/RichTextEditor.jsx`:
    - FONT_SIZES array com 7 tamanhos
    - applyFontSize() function
    - Popover UI para seleção de tamanho
  - `/app/frontend/src/components/editor/SlideCanvas.jsx`:
    - iframe srcDoc com CSS de fundo transparente
    - Container div com background: transparent
- **Status**: IMPLEMENTED AND TESTED
- **Verification**: Testing agent confirmou fundo transparente e tamanhos funcionando (12 testes passaram)

### HTML Export UTF-8 Encoding Fix - IMPLEMENTED (Feb 5, 2026)
- **Issue**: Caracteres acentuados (ç, ã, é, á, etc) apareciam corrompidos na exportação HTML
- **Root Cause**: `atob()` em JavaScript decodifica base64 para string binária, não UTF-8
- **Fix Applied**:
  - Substituído `atob(htmlContent.substring(8))` por:
    ```javascript
    var binaryString = atob(htmlContent.substring(8));
    var bytes = new Uint8Array(binaryString.length);
    for (var i = 0; i < binaryString.length; i++) {
      bytes[i] = binaryString.charCodeAt(i);
    }
    htmlContent = new TextDecoder('utf-8').decode(bytes);
    ```
- **File Modified**:
  - `/app/backend/services/html_exporter.py` (linha ~1050-1065)
- **Status**: IMPLEMENTED
- **Verification**: Caracteres como "utilização", "navegação", "áreas", "decisões" agora aparecem corretamente

### SCORM Export Transparent Background + UTF-8 Fix - IMPLEMENTED (Feb 5, 2026)
- **Issues Fixed**:
  1. Fundo branco nos elementos HTML no SCORM export
  2. Caracteres acentuados corrompidos na exportação SCORM
  
- **Fixes Applied**:
  1. CSS `.html-element { background: white; }` → `background: transparent;`
  2. CSS `.html-element iframe` adicionado `background: transparent;`
  3. JavaScript: srcdoc envolve conteúdo em HTML completo com CSS transparente
  4. JavaScript: Decodificação base64 com `TextDecoder('utf-8')` para UTF-8 correto
  
- **File Modified**:
  - `/app/backend/services/scorm_exporter.py`
    - Linhas ~838-865: Novo case 'html' com decodificação UTF-8 e wrapping HTML
    - Linhas ~1764-1775: CSS com fundo transparente
- **Status**: IMPLEMENTED
- **Verification**: Exportar SCORM novamente para verificar fundo transparente e acentos corretos

### Video Library (Biblioteca de Vídeos) - IMPLEMENTED (Feb 5, 2026)
- **Feature**: Permite recuperar, reutilizar e excluir vídeos HeyGen gerados anteriormente
- **Implementation**:
  1. **Backend**:
     - Endpoint `GET /api/heygen/videos` atualizado para incluir mais campos (script, avatar_id, voice_id, project_id)
     - Novo endpoint `GET /api/heygen/videos/{video_id}/refresh` para atualizar status de vídeo pendente
     - Novo endpoint `DELETE /api/heygen/videos/{video_id}` para excluir vídeos da biblioteca
     - `POST /api/heygen/generate-video` agora aceita `project_id` opcional
  2. **Frontend**:
     - Novo botão "📹 Biblioteca de Vídeos" (Film icon) na toolbar do editor
     - Diálogo mostrando todos os vídeos gerados com:
       - Thumbnail com overlay de duração
       - Título do vídeo
       - Status badge (Concluído/Processando/Falhou/Pendente)
       - Data e hora de criação
       - Preview do script usado
       - Preview de vídeo no hover (para vídeos completos)
     - Botão "Adicionar" para adicionar vídeos completos ao slide atual
     - Botão "Atualizar" para verificar status de vídeos em processamento
     - Botão "Excluir" (vermelho) para remover vídeos indesejados da biblioteca
     - Botão "Atualizar Lista" para recarregar lista
- **Files Modified**:
  - `/app/backend/server.py`:
    - `HeyGenVideoRequest` - adicionado campo `project_id`
    - `list_heygen_videos` - expandido com mais campos e filtro por projeto
    - `refresh_heygen_video_status` - novo endpoint para atualizar status
    - `delete_heygen_video` - novo endpoint para excluir vídeos
  - `/app/frontend/src/pages/Editor.jsx`:
    - Estados: `showVideoLibrary`, `videoLibraryItems`, `videoLibraryLoading`, `refreshingVideoId`
    - Funções: `loadVideoLibrary`, `refreshVideoStatus`, `handleAddLibraryVideoToSlide`, `handleDeleteLibraryVideo`, `handleOpenVideoLibrary`, `formatDuration`, `formatDateTime`, `getStatusBadge`
    - UI: Botão na toolbar (data-testid="video-library-btn"), Diálogo completo com botões Adicionar/Excluir
- **Status**: IMPLEMENTED AND TESTED (100% success rate)
- **Verification**: Testing agent e testes manuais confirmaram todas as funcionalidades funcionando corretamente
