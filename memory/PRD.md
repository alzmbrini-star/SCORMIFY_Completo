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

### 2026-02-13
- **Split Preview - Preview Integrado ao Editor** (IMPLEMENTED AND TESTED)
  - **Feature**: Botão "Visualizar" agora abre um painel lateral de preview em vez de modal fullscreen
  - **Split-view**: Editor à esquerda + Preview em tempo real à direita
  - **Sidebar colapsável**: Painel de slides à esquerda recolhe automaticamente (mostra apenas números) quando o preview está ativo
  - **Navegação sincronizada**: Trocar slide no editor atualiza o preview e vice-versa
  - **Controles**: Play/Pause timeline, navegação prev/next, mini sidebar com thumbnails
  - **Expandir para fullscreen**: Botão para abrir o CoursePreview em tela cheia
  - **Files Created**: `/app/frontend/src/components/editor/SplitPreview.jsx`
  - **Files Modified**: `/app/frontend/src/pages/Editor.jsx` (import, state, layout condicional)

### 2026-02-12
- **CORREÇÃO P0: Imagens RTF Quebradas Após Fork** (FIXED AND TESTED)
  - **Problema**: URLs absolutas de imagens eram salvas no MongoDB. Após fork, o domínio muda e as imagens quebravam.
  - **Correção**: `htmlUtils.js` (stripDomainFromAssetUrls/resolveAssetUrls), `Editor.jsx` (strip on save, resolve on edit), `SlideCanvas.jsx` (improved resolveHtmlContentUrls), `server.py` (auto-migration on startup)
  - **Testes**: 100% backend (10/10), 100% frontend (16/16 unit tests)

- **CORREÇÃO: Botão "Iniciar Quiz" no SCORM Não Funcionava** (FIXED AND TESTED)
  - **Causa Raiz**: Erro de escape em Python triple-quoted string no `scorm_exporter.py`. `\'` era consumido como escape Python, gerando `''` (aspas duplas) em vez de `\''` (aspas escapadas) no JavaScript. Resultado: `QuizController` falhava ao carregar com "Unexpected string" syntax error.
  - **Correção**: Alterado `\'` para `\\'` em 6 pontos do `QUIZ_CONTROLLER_JS` (selectAnswer, prevQuestion, nextQuestion, showResults, confirmAnswer, restartQuiz)
  - **Testes**: Verificado com node --check (syntax OK), Playwright E2E (quiz start, answer selection, confirmation, navigation)

### 2026-02-11
- **MELHORIA: Dimensões dos Slides para Mobile (21:9)**
  - Novos projetos e imports de PPT agora usam proporção 21:9 (1920x820) em vez de 16:9 (1536x864)
  - Slides no formato 21:9 preenchem melhor a tela de celulares em modo landscape
  - Projetos existentes mantêm suas dimensões originais (não são afetados)
  
- **CORREÇÃO: Escala de Slides em Mobile Landscape**
  - Implementado posicionamento `position: fixed` para o container do slide
  - Slide agora ignora restrições do parent container em mobile landscape
  - O slide ocupa a largura máxima disponível sem barras pretas
  
- **CORREÇÃO: Fundo Transparente para Textos** (COMPLETED)
  - Checkbox "Transparent" disponível no painel de propriedades para elementos de texto
  - CSS do SCORM exporter ajustado para aplicar background via JS inline
  - Suporte adicionado ao HTML exporter também

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

### Drag/Resize Element Bug (404/520 Errors) - FIXED (Feb 12, 2026)
- **Issue**: Erros 404 e 520 apareciam ao arrastar ou redimensionar elementos no SlideCanvas
- **Root Cause**: 
  1. A função `onUpdateElement` estava sendo chamada em CADA movimento do mouse durante o arraste
  2. Isso gerava centenas de requisições HTTP simultâneas, causando sobrecarga do servidor
  3. Erros 404/520 ocorriam devido ao rate limiting ou timeout das conexões
- **Fix Applied**:
  1. Criado estado local `localElementUpdates` para atualização otimista durante drag/resize
  2. `handleMouseMove` agora atualiza apenas o estado local (UI imediata, sem chamadas de API)
  3. `handleMouseUp` faz UMA ÚNICA chamada de API quando o mouse é solto
  4. `displayElement` combina dados do elemento com atualizações locais para renderização
  5. Estado local é limpo após salvamento bem-sucedido
- **Files Modified**:
  - `/app/frontend/src/components/editor/SlideCanvas.jsx`:
    - Linha 103: Adicionado estado `localElementUpdates`
    - Linhas 186-277: `handleMouseMove` usa `setLocalElementUpdates` em vez de `onUpdateElement`
    - Linhas 279-323: `handleMouseUp` faz chamada de API e limpa estado local
    - Linhas 472-480: `displayElement` combina elemento com atualizações locais
- **Technical Details**:
  - **Antes**: API call em cada evento mousemove (centenas de requisições durante um arraste)
  - **Depois**: Uma única API call no mouseup (performance otimizada)
- **Status**: FIXED AND TESTED (100% dos testes passaram)
- **Verification**: 
  - Arrastado elemento 100px em 20 movimentos → apenas 1 PUT request
  - Redimensionado elemento 50px em 10 movimentos → apenas 1 PUT request
  - Zero erros 404/520 no console durante operações

## Prioritized Backlog

### P0 (Critical)
- All implemented ✓

### P1 (High Priority)
- [ ] PPT animation extraction and playback
- [x] Drag & drop slide reordering (DONE)
- [x] Timeline synchronization (DONE)
- [x] Refatorar código duplicado sanitizeHtmlForDisplay (DONE - Feb 12, 2026)
- [x] Renomear cursos/projetos (DONE - Feb 12, 2026)
- [x] Tamanho de fonte ajustável no Quiz (DONE - Feb 12, 2026)
- [x] Centralizar CSS de RTF em arquivo compartilhado (DONE - Feb 12, 2026)
- [x] Element copy/paste (DONE - Feb 12, 2026)
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

### HTML Export Video Transparency Fix - IMPLEMENTED (Feb 5, 2026)
- **Issue**: Vídeos WebM com fundo transparente (HeyGen avatars) apareciam com fundo preto na exportação HTML
- **Root Cause**: CSS `.video-element` tinha `background: #000` que sobrepunha a transparência do vídeo
- **Fix Applied**:
  1. CSS `.video-element` alterado para `background: transparent`
  2. CSS `.video-element video` adicionado `background-color: transparent !important`
  3. JavaScript: vídeos WebM recebem style inline `background:transparent !important`
  4. Removido `border-radius` e `overflow:hidden` que causavam artefatos
- **File Modified**:
  - `/app/backend/services/html_exporter.py` (linhas ~458-480 CSS, linhas ~1040-1050 JS)
- **Status**: IMPLEMENTED
- **Note**: Vídeos WebM da HeyGen gerados com `transparent_background: true` agora exibem fundo transparente corretamente

### HTML Export Timeline Fix - IMPLEMENTED (Feb 5, 2026)
- **Issue**: A timeline não funcionava na exportação HTML - elementos não apareciam/desapareciam baseado em startTime/endTime
- **Root Cause**: O exportador HTML não tinha implementação de timeline
- **Fix Applied**:
  1. Adicionada variável `timelineTimers` para armazenar timers
  2. Adicionada variável `slideDuration` para calcular a duração total do slide
  3. Elementos com `startTime > 0` iniciam ocultos (`display:none`)
  4. Timers JavaScript agendam `fadeIn` quando `startTime` é atingido
  5. Timers JavaScript agendam `fadeOut` quando `endTime` é atingido
  6. Adicionado suporte a timeline para annotations também
  7. Adicionadas keyframes CSS `fadeIn` e `fadeOut` com animações suaves
  8. Timers são limpos ao trocar de slide
- **File Modified**:
  - `/app/backend/services/html_exporter.py`
    - Linhas ~860: variável `timelineTimers` e `isPresentationMode`
    - Linhas ~718-726: keyframes CSS fadeIn/fadeOut
    - Linhas ~990-1020: lógica de startTime/endTime na renderização de elementos
    - Linhas ~1160-1230: setup de timers para elementos e annotations
- **Status**: IMPLEMENTED
- **Note**: Elementos e anotações agora aparecem/desaparecem conforme configurado na timeline

### PPT Animations Extraction & Playback - IMPLEMENTED (Feb 6, 2026)
- **Feature**: Extrair animações originais do PowerPoint e reproduzi-las na exportação HTML
- **Implementation**:
  1. **Backend - Extração** (`/app/backend/services/ppt_parser.py`):
     - Nova função `extract_animations()` que analisa o XML de timing do slide
     - Detecta tipos de animação: entrance, exit, emphasis, motion
     - Extrai propriedades: effect, trigger, duration, delay, easing
     - Mapeia efeitos PPT para nomes padronizados (fade, fly, zoom, bounce, etc.)
     - Animações são anexadas aos elementos via `element.animations`
  2. **Frontend - Playback** (`/app/backend/services/html_exporter.py`):
     - 23 novas keyframes CSS para efeitos PPT (ppt-appear, ppt-fade, ppt-fly-*, ppt-zoom, ppt-bounce, ppt-spin, ppt-swivel, ppt-wipe-*, etc.)
     - Lógica JavaScript para processar animações por elemento
     - Suporte a triggers: afterPrevious, withPrevious (onClick não implementado)
     - Animações de entrada, saída e ênfase funcionando
- **Status**: IMPLEMENTED
- **Note**: Animações são extraídas do PPTX e reproduzidas automaticamente na exportação HTML

### SmartArt Extraction - IMPLEMENTED (Feb 6, 2026)
- **Feature**: Detectar e extrair gráficos SmartArt do PowerPoint
- **Implementation**:
  1. **Backend** (`/app/backend/services/ppt_parser.py`):
     - Nova função `extract_smartart()` que detecta elementos SmartArt via namespace dgm
     - Extrai imagem embutida do SmartArt (quando disponível)
     - Extrai texto do SmartArt para acessibilidade
     - Converte EMF/WMF para PNG quando possível
     - SmartArt é salvo como tipo de elemento `smartart`
  2. **Frontend** (`/app/backend/services/html_exporter.py`):
     - Renderização de SmartArt como imagem com texto alt para acessibilidade
- **Status**: IMPLEMENTED
- **Note**: SmartArt complexo é renderizado como imagem; texto é preservado para search/accessibility


### Text Wrapping para Imagens no Editor RTF - IMPLEMENTED (Feb 6, 2026)
- **Feature**: Contorno de texto ao redor de imagens com 4 modos de posicionamento
- **Implementation**:
  1. **Em linha** (`rtf-image-inline`): Imagem segue o fluxo normal do texto
  2. **Centralizada** (`rtf-image-center`): Imagem centralizada com texto acima/abaixo
  3. **Flutuar Esquerda** (`rtf-image-float-left`): `float: left`, texto flui à direita
  4. **Flutuar Direita** (`rtf-image-float-right`): `float: right`, texto flui à esquerda
- **UI Improvements**:
  - Popover redesenhado com ícones visuais representando cada modo
  - Botões "Flutuar" destacados em cyan para indicar wrapping
  - Descrições explicativas abaixo dos botões
- **CSS Properties Applied**:
  - Float: `float: left/right`, `clear: left/right`
  - Margins: `margin: 0 16px 12px 0` (left) / `margin: 0 0 12px 16px` (right)
  - Max-width: 45% para imagens flutuantes, 80% para centralizadas
  - `shape-outside: margin-box` para contorno suave
- **Files Modified**:
  - `/app/frontend/src/components/RichTextEditor.jsx`:
    - Função `addImage(alignment)` atualizada para aceitar 4 modos
    - CSS classes adicionadas para cada tipo de posicionamento
    - Popover UI redesenhado com grid 2x2
- **Test IDs Added**:
  - `rtf-image-btn`: Botão de inserir imagem
  - `rtf-image-url-input`: Campo de URL
  - `rtf-image-inline-btn`: Botão Em linha
  - `rtf-image-center-btn`: Botão Centralizada
  - `rtf-image-float-left-btn`: Botão Flutuar Esquerda
  - `rtf-image-float-right-btn`: Botão Flutuar Direita
- **Status**: IMPLEMENTED AND TESTED (100% success rate)
- **Verification**: Testing agent confirmou todos os 18 testes passando


### Redimensionamento e Exclusão de Imagens no RTF - IMPLEMENTED (Feb 6, 2026)
- **Feature**: Controles visuais para editar imagens diretamente no editor RTF
- **Implementation**:
  1. **Seleção de Imagem**: Clicar na imagem adiciona classe `selected-image` com borda cyan
  2. **Botão Excluir**: Botão vermelho (Trash2 icon) no canto superior direito remove a imagem
  3. **Handle Redimensionar**: Handle cyan (Maximize2 icon) no canto inferior direito permite arrastar para redimensionar
  4. **Handle Mover**: Para imagens flutuantes, handle cinza (Move icon) no centro superior permite arrastar posição
  5. **Desmarcar**: Clicar fora da imagem remove seleção e esconde controles
- **UI Controls**:
  - Botão excluir: `bg-red-500`, círculo 7x7px, `-3px offset`
  - Handle redimensionar: `bg-cyan-500`, quadrado 5x5px, cursor `nwse-resize`
  - Handle mover: `bg-slate-600`, círculo 7x7px, cursor `move`
- **Aspect Ratio**: Redimensionamento mantém proporção original da imagem
- **State Management**:
  - `selectedImage`: Referência ao elemento img selecionado
  - `imageControlsPosition`: Posição calculada dos controles overlay
  - `isResizing`: Flag durante operação de resize
- **Test IDs Added**:
  - `rtf-image-delete-btn`: Botão de excluir
  - `rtf-image-resize-handle`: Handle de redimensionar
  - `rtf-image-move-handle`: Handle de mover (para floating images)
- **Files Modified**:
  - `/app/frontend/src/components/RichTextEditor.jsx`:
    - Função `deleteSelectedImage()` para remover imagens
    - useEffect para calcular posição dos controles
    - Image Controls Overlay UI com botões e handles
- **Status**: IMPLEMENTED AND TESTED (100% success rate)
- **Verification**: Testing agent confirmou 11 testes passando incluindo resize com aspect ratio mantido


### Correção do Text Wrapping no SlideCanvas - FIX (Feb 6, 2026)
- **Issue:** O float das imagens não estava sendo aplicado no SlideCanvas iframe, causando discrepância entre o editor RTF e a visualização do slide
- **Root Cause:** Os CSS inline do HTML salvo tinham muitas propriedades Tailwind que conflitavam com os estilos de float. A especificidade CSS do iframe era insuficiente.
- **Fix Applied:**
  1. Aumentada especificidade CSS com seletores múltiplos (`body img.rtf-image-float-right`)
  2. Adicionado `!important` em todas as propriedades relevantes (float, clear, display, margin)
  3. Removido `overflow: hidden` do container que bloqueava o fluxo de texto
  4. Adicionado `overflow: visible` em elementos de texto (p, div, span, etc.)
- **Files Modified:**
  - `/app/frontend/src/components/editor/SlideCanvas.jsx`: CSS do srcDoc do iframe atualizado
- **Status**: FIXED AND VERIFIED
- **Verification**: Screenshot visual confirmou que o texto agora contorna a imagem corretamente no slide


## Quiz Generator Feature - IMPLEMENTED (Feb 07, 2026)

### Overview
Complete Quiz Generator feature for creating interactive quizzes within SCORM courses. Supports AI-powered question generation, manual question creation, and full SCORM integration for score reporting.

### Features Implemented
1. **Question Types**: Multiple Choice and True/False
2. **AI Question Generation**: Uses OpenAI GPT via Emergent LLM Key
3. **Document Import**: Parse .doc/.docx files for question generation context
4. **Question Bank**: Store, view, select, and delete questions (with scroll support)
5. **Quiz Configuration**:
   - Custom title
   - Number of questions to display
   - Shuffle questions and alternatives
   - Show/hide feedback
   - Passing score (0-100%)
6. **Interactive Quiz Player**: 
   - Progress bar and question counter
   - Answer selection with visual feedback (grid 2x2 layout)
   - Correct/Incorrect feedback with explanations
   - Final score screen (0-10 scale) - compact layout
   - Restart quiz option
7. **SCORM Integration**:
   - Quiz score reported to LMS (cmi.core.score.raw)
   - Completion status based on passing score (cmi.core.lesson_status)
   - Compact UI optimized for SCORM player windows
   - Thin scrollbar matching RTF content style

### Backend Endpoints (server.py)
- `GET /api/questions` - List questions (filter by project_id, tag)
- `GET /api/questions/{id}` - Get single question
- `POST /api/questions` - Create manual question
- `PUT /api/questions/{id}` - Update question
- `DELETE /api/questions/{id}` - Delete question
- `POST /api/questions/generate` - Generate questions with AI
- `POST /api/questions/parse-doc` - Parse .doc file for text extraction
- `POST /api/quiz/submit` - Submit quiz answers and get score
- `GET /api/quiz/attempts/{project_id}` - Get quiz attempts

### Database Models (models.py)
- `QuizQuestion`: Question with alternatives, type, explanation
- `QuizAlternative`: Individual answer option with correct flag
- `QuizConfig`: Quiz settings (title, count, shuffle, feedback, passing score)
- `QuizAttempt`: Record of user quiz attempt with answers and score

### Frontend Components
- `/app/frontend/src/components/quiz/QuizGenerator.jsx` - Dialog for creating quizzes
- `/app/frontend/src/components/quiz/QuizPlayer.jsx` - Interactive quiz player
- Editor integration: Toolbar button (HelpCircle icon)
- SlideCanvas: Quiz element rendering
- CoursePreview: Embedded QuizPlayer

### SCORM Export Support (scorm_exporter.py)
- QuizController.js included in SCORM package
- Quiz questions stored in course.json
- Score reporting via SCORM API
- Compact responsive UI for LMS players
- Thin scrollbar styling matching RTF content

### Quiz UI Refinements (Feb 07, 2026)
- **Compact Layout**: Reduced padding and font sizes for better fit
- **Header**: Question type badge inline with counter (e.g., "Quiz | Múltipla | 1/5")
- **Alternatives**: Grid 2x2 layout with smaller circles (20px)
- **Feedback Box**: Compact with 11px explanation text
- **Results Screen**: Fully visible without scrolling
- **Scrollbar**: Thin 4px scrollbar matching RTF style

## Additional Improvements (Feb 07, 2026)

### Project Name Sync with Course Title
- When creating a new project manually, the course title now uses the project name
- When updating project name, course metadata title is also updated
- Fixes "Untitled Course" issue for manually created projects

### HeyGen Video Autoplay Fix in HTML Export (Feb 07, 2026)
- **Issue**: HeyGen videos (.webm) were not playing in exported HTML packages - appeared as static images
- **Root Cause**: HTML exporter was missing the autoplay logic present in SCORM exporter
- **Fix Applied**:
  1. Added auto-play code for local videos when slide becomes active (`renderSlide` function)
  2. Videos are now programmatically played with `.play()` when slide loads
  3. Added fallback to muted autoplay if browser blocks unmuted autoplay
  4. Added `loadedmetadata` event listener for videos that haven't loaded yet
  5. Videos are paused and reset when navigating away from a slide
- **Files Modified**:
  - `/app/backend/services/html_exporter.py` - Added video autoplay and pause logic
- **Status**: FIXED AND TESTED
- **Verification**: Video plays correctly when slide loads and when returning to slide after navigation

### Quiz Not Loading in HTML Export (Feb 07, 2026)
- **Issue**: Quiz displayed "Nenhuma questão encontrada" (No questions found) in HTML export
- **Root Cause**: QuizController.init() was being called with `course` variable which was private inside Player module scope, instead of `courseData` which is global
- **Fix Applied**:
  - Changed QuizController initialization from `course` to `courseData`
  - Added console logging for debugging quiz initialization
- **Files Modified**:
  - `/app/backend/services/html_exporter.py` - Fixed variable scope in QuizController initialization
- **Status**: FIXED AND TESTED
- **Verification**: Quiz with 15 questions loads and displays correctly in HTML export
- **Note**: If a quiz shows "Nenhuma questão encontrada", check if the referenced question IDs exist in the question bank - questions may have been deleted

### AI Image Generation in RTF Editor (Feb 09, 2026)
- **Feature**: Users can now generate images with AI directly inside the Rich Text Editor
- **Integration**: OpenAI GPT Image 1 via Emergent LLM Key
- **How it works**:
  1. User clicks the cyan image+sparkles button in RTF toolbar
  2. Enters a description of the desired image
  3. AI generates the image and inserts it in the document
- **Files Modified**:
  - `/app/backend/server.py` - Added `/api/ai/generate-image` endpoint
  - `/app/frontend/src/components/RichTextEditor.jsx` - Added AI image generation UI
  - `/app/frontend/src/pages/Editor.jsx` - Added `generateImageWithAI` function
- **Status**: IMPLEMENTED AND TESTED

### Fullscreen Button Visual Fix (Feb 09, 2026)
- **Issue**: O botão Fullscreen atualizava corretamente as dimensões, mas os elementos não preenchiam visualmente toda a área do slide
- **Root Cause**: Quando `objectFit: 'cover'` era aplicado, os elementos (Quiz, HTML, Video) mantinham bordas arredondadas e badges visuais
- **Fix Applied**:
  1. Quiz Element: Removido `rounded-lg` e `border-2 border-cyan-500/30` quando `objectFit === 'cover'`
  2. HTML Element: Removido `rounded` class quando `objectFit === 'cover'`
  3. Video Element: Escondidos badges de indicador (YouTube/Vimeo) e play hint quando `objectFit === 'cover'`
  4. Quiz/HTML/Video: Escondidos badges de seleção quando em fullscreen
- **Files Modified**:
  - `/app/frontend/src/components/editor/SlideCanvas.jsx`:
    - Linha 836: Quiz element conditional styling
    - Linha 647: HTML element conditional styling  
    - Linhas 586, 595: Video element badge visibility
- **Status**: FIXED AND TESTED (100% success rate - 11/11 tests passed)
- **Verification**: Testing agent confirmou que todos os tipos de elementos (Quiz, HTML, Video, Image) agora preenchem visualmente toda a área quando Fullscreen é aplicado

### AI Image Generation Text Preservation Bug Fix (Feb 09, 2026)
- **Issue**: Quando o usuário gerava uma imagem com IA no Rich Text Editor, o texto existente era perdido/substituído pela imagem
- **Root Cause**: O código usava `document.execCommand('insertHTML')` que, após o editor perder foco durante a geração (15-20s), substituía todo o conteúdo em vez de inserir no cursor
- **Fix Applied**: Modificado `handleAIImageGenerate` para concatenar a imagem ao conteúdo existente em vez de usar execCommand
- **Files Modified**:
  - `/app/frontend/src/components/RichTextEditor.jsx` - linhas 435-460
- **Before**: `document.execCommand('insertHTML', false, imgHtml)` substituía todo o conteúdo
- **After**: `editorRef.current.innerHTML = currentContent + imgHtml` preserva o conteúdo e adiciona a imagem no final
- **Status**: FIXED AND TESTED
- **Verification**: Teste confirmou que conteúdo de 89526 chars foi preservado, aumentando para 89872 chars após adicionar imagem

### AI Image Optimization (Feb 09, 2026)
- **Issue**: Imagens geradas pela IA estavam muito pesadas (~1.6MB) causando carregamento lento
- **Fix Applied**:
  1. Conversão de PNG para JPEG com qualidade 80%
  2. Redimensionamento para máximo 1200px no lado maior
  3. Otimização com Pillow
- **Files Modified**:
  - `/app/backend/server.py` - endpoint `/api/ai/generate-image`
- **Results**: Redução de ~96% no tamanho (1622KB → 68KB)
- **Status**: FIXED AND TESTED

### Fullscreen Visual Fix for HTML Elements (Feb 09, 2026)
- **Issue**: Elementos HTML com Fullscreen não preenchiam visualmente toda a área no Visualizador/HTML/SCORM
- **Root Cause**: Imagens dentro do HTML tinham estilos inline (max-width: 80%, width fixo) que impediam o preenchimento
- **Fix Applied**: CSS com `!important` que sobrescreve estilos inline quando `objectFit === 'cover'`
- **Files Modified**:
  - `/app/frontend/src/components/editor/CoursePreview.jsx`
  - `/app/backend/services/html_exporter.py`
  - `/app/backend/services/scorm_exporter.py`
- **Status**: FIXED AND TESTED

### Mobile RTF/HTML Content Fix - IMPLEMENTED (Feb 11, 2026)
- **Issue**: Imagens no conteúdo RTF transbordavam para fora do slide no mobile
- **Fix Applied**: 
  - Todas as imagens no mobile agora têm `float: none`, `display: block`, `max-width: 90%`
  - Imagens ficam centralizadas (`margin: 12px auto`)
  - Body com `overflow-x: hidden` para impedir scroll horizontal
  - Fontes ajustadas para melhor legibilidade (body 16px, parágrafos 15px)
- **Files Modified**: `/app/backend/services/scorm_exporter.py` - CSS mobileCSS dentro do iframe RTF
- **Status**: IMPLEMENTED AND TESTED

### Mobile Quiz Font Size Improvement - IMPLEMENTED (Feb 11, 2026)
- **Issue**: Fonte do quiz muito pequena no mobile, dificultando leitura das alternativas e feedback
- **Fix Applied**: Aumentado tamanhos de fonte para mobile:
  - Container base: 20px
  - Alternativas: 18px com padding 16px 18px
  - Feedback: 18px
  - Botões: 18px
- **Files Modified**: `/app/backend/services/scorm_exporter.py` - CSS do quiz-player-container
- **Status**: IMPLEMENTED AND TESTED

### Transparent Background for Text Elements - COMPLETED (Feb 11, 2026)
- **Feature**: Opção para tornar o fundo de elementos de texto transparente
- **Implementation**:
  1. **Editor UI** (Editor.jsx): Checkbox "Transparent" no painel de propriedades para elementos de texto
  2. **Canvas Rendering** (SlideCanvas.jsx): Renderização condicional do fundo baseado em `style.transparentBackground`
  3. **SCORM Export** (scorm_exporter.py): 
     - CSS atualizado para não ter fundo padrão na classe `.text-element`
     - JavaScript aplica fundo inline: transparente, customizado, ou default (rgba(255,255,255,0.9))
  4. **HTML Export** (html_exporter.py): Mesma lógica aplicada para elementos de texto
- **Files Modified**:
  - `/app/backend/services/scorm_exporter.py` - CSS e JS para transparência
  - `/app/backend/services/html_exporter.py` - Suporte a `transparentBackground`
- **Status**: COMPLETED AND TESTED
- **Verification**: Checkbox visível e funcional no painel de propriedades

### Mobile Swipe Navigation + Side Buttons - IMPLEMENTED (Feb 11, 2026)
- **Feature**: Nova navegação mobile com botões laterais e conteúdo maximizado
- **Implementation**:
  1. **Barra inferior removida no mobile** - Controles desktop escondidos em telas < 1024px ou dispositivos touch
  2. **Botões de navegação nas laterais**:
     - Botão **‹** no canto esquerdo - slide anterior
     - Botão **›** no canto direito - próximo slide
     - Semitransparentes com efeito blur, ficam desativados nos extremos
  3. **Botão de menu ☰** no canto superior esquerdo - abre sidebar de navegação
  4. **Contador de slides** na parte inferior central (ex: "3 / 16")
  5. **Swipe navigation** continua funcionando
  6. **Detecção de mobile melhorada**:
     - CSS media query `@media (max-width: 1024px)`
     - JavaScript detecta user-agent + touch + tamanho e adiciona classe `mobile-mode`
- **Files Modified**:
  - `/app/backend/services/scorm_exporter.py`:
    - Função `initMobileMode()` para detecção via JS
    - CSS para `.mobile-nav-btn`, `.mobile-slide-counter`, `.mobile-menu-btn`
    - CSS para `body.mobile-mode` como fallback
    - HTML com botões de navegação mobile
    - Função `updateProgress()` atualiza contador mobile
- **Status**: IMPLEMENTED AND TESTED
- **User Verification**: Confirmado funcionando em dispositivo mobile real

## Roadmap / Backlog

### P0 - Critical (Next)
- [x] SCORM Mobile: Forçar landscape com overlay "Rotacione seu dispositivo" (FIXED - Feb 12, 2026)
- [x] SCORM Mobile Landscape: Pinch-to-zoom + Scroll vertical habilitados (FIXED - Feb 12, 2026)
- [x] SCORM Mobile Landscape: Reflow de elementos - texto e vídeo empilhados sem sobreposição (FIXED - Feb 12, 2026)
- [x] Refatoração SCORM Exporter: CSS/JS extraídos para arquivos separados (4163→377 linhas) (DONE - Feb 13, 2026)
- [x] Split Preview: Preview integrado ao Editor em painel lateral (DONE - Feb 13, 2026)

### P1 - High Priority
- Quiz analytics dashboard (view attempts, scores per question)
- Bulk question import from CSV/Excel
- Question categories/tags management UI

### P2 - Medium Priority
- Fill-in-the-blank question type
- Matching question type
- Question difficulty levels
- Time limit per question
- Quiz retake restrictions

### AI-Generated Images Export Persistence - FIXED (Feb 10, 2026)
- **Issue**: Imagens geradas por IA no RTF não eram incluídas nas exportações HTML/SCORM, ficando inacessíveis quando o curso era hospedado em um LMS
- **Root Cause**: O `htmlContent` do Rich Text Editor continha URLs apontando para `/api/assets/{filename}` que não eram processadas durante a exportação
- **Fix Applied**:
  1. **HTML Export**: Nova função `process_html_content_images()` que escaneia todas as tags `<img>` dentro do `htmlContent` e converte as URLs para data URIs base64
  2. **SCORM Export**: 
     - Copia imagens da pasta `/storage/assets/` (onde ficam as imagens AI) para o pacote
     - Converte URLs `/api/assets/{id}` para caminhos relativos `assets/{id}` no `htmlContent`
- **Files Modified**:
  - `/app/backend/services/html_exporter.py`:
    - Nova função `process_html_content_images()` para processar imagens dentro do HTML
    - Chamada durante processamento de elementos HTML
  - `/app/backend/services/scorm_exporter.py`:
    - Cópia de assets globais para o pacote SCORM
    - Processamento de URLs no `htmlContent`
- **Status**: FIXED AND TESTED
- **Verification**: Exportação HTML mostra imagens como data URIs; SCORM inclui arquivos de imagem e usa caminhos relativos

### AI Image Preview Feature - IMPLEMENTED (Feb 10, 2026)
- **Feature**: Prévia de imagens AI geradas antes de inserir no documento
- **Implementation**:
  1. Usuário digita o prompt da imagem
  2. IA gera a imagem e mostra preview
  3. Opções disponíveis:
     - **"✓ Usar esta"** → insere no documento (botão verde)
     - **"↻ Regenerar"** → gera nova imagem com o mesmo prompt (botão cyan outline)
     - **"✎ Editar prompt"** → volta para o campo de edição do prompt
     - **"Cancelar"** → fecha sem inserir
- **UI States**:
  - `prompt`: Campo de texto para descrever a imagem + botão "Gerar Imagem"
  - `preview`: Imagem gerada + botões de ação
- **Files Modified**:
  - `/app/frontend/src/components/RichTextEditor.jsx`:
    - Novos estados: `aiImagePreview`, `aiImageStep`
    - Novas funções: `handleInsertAIImage`, `handleRegenerateAIImage`, `handleEditAIImagePrompt`, `handleCancelAIImage`
    - Popover atualizado com layout de preview
- **Test IDs Added**:
  - `ai-image-prompt-input`: Campo de texto do prompt
  - `ai-image-generate-btn`: Botão de gerar
  - `ai-image-preview`: Imagem de preview
  - `ai-image-use-btn`: Botão "Usar esta"
  - `ai-image-regenerate-btn`: Botão "Regenerar"
  - `ai-image-edit-btn`: Botão "Editar prompt"
- **Status**: IMPLEMENTED AND TESTED

### ElevenLabs Text-to-Speech Integration - IMPLEMENTED (Feb 11, 2026)
- **Feature**: Text-to-Speech with 21 professional voices using ElevenLabs API
- **Languages Supported**: Portuguese (Brazil), English, Spanish via eleven_multilingual_v2 model
- **Voice Types**: 13 male voices, 7 female voices with gender filtering
- **Endpoints Added**:
  - `GET /api/elevenlabs/voices` - List all voices with optional gender filter
  - `POST /api/elevenlabs/generate-speech` - Generate audio from text
  - `GET /api/audio/{filename}` - Serve generated audio files
- **Frontend Features**:
  - TTS button in Editor toolbar (Volume2 icon)
  - Dialog with voice selection grid
  - Gender filter dropdown (Todos/Masculino/Feminino)
  - Text input area for narration
  - Audio preview player
  - "Adicionar ao Slide" button to attach audio to current slide
- **Status**: IMPLEMENTED AND TESTED (100% backend, 95% frontend)
- **Files Modified**:
  - `/app/backend/server.py` - Added ElevenLabs endpoints
  - `/app/backend/.env` - Added ELEVENLABS_API_KEY
  - `/app/frontend/src/pages/Editor.jsx` - Added TTS states, functions, and Dialog

### RTF Content Overflow Bug - FIXED (Feb 11, 2026)
- **Issue**: Texto e imagens inseridas via URL em elementos RTF ultrapassavam os limites do elemento no preview e nas exportações SCORM/HTML
- **Root Cause**: 
  1. CSS regra para elementos de texto precisava permitir overflow para que o layout com float funcionasse corretamente
  2. Imagens com largura definida em pixels (via style="width:XXXpx") não respeitavam `max-width:100%`
- **Fix Applied**:
  1. Mantido `overflow:visible!important` em elementos de texto (p, div, span, h1-h6, etc.) para permitir que o texto flua corretamente ao redor de imagens flutuantes
  2. Nova regra CSS `img[style*="width"]{max-width:100%!important;width:auto!important;height:auto!important}` força imagens com width inline a respeitar limites
  3. Regra universal `*{max-width:100%!important}` adicionada para garantir que nenhum elemento ultrapasse o container
- **Important**: NÃO usar `overflow:hidden` em elementos de texto internos pois quebra o layout de float com imagens
- **Files Modified**:
  - `/app/backend/services/scorm_exporter.py` - CSS do iframe HTML
  - `/app/backend/services/html_exporter.py` - CSS do iframe HTML
  - `/app/frontend/src/components/editor/CoursePreview.jsx` - CSS do Visualizador
- **Status**: FIXED AND TESTED - Layout com imagem flutuante e texto funcionando corretamente

### SlideCanvas Visual Consistency - FIXED (Feb 12, 2026)
- **Issue**: O layout de elementos RTF no SlideCanvas (editor) era muito diferente do resultado final (CoursePreview, SCORM, HTML exports). Imagens com float não mostravam o texto fluindo corretamente - imagens apareciam muito grandes ocupando toda a largura.
- **Root Cause**: As imagens tinham estilos inline com largura fixa em pixels (ex: `width: 302.385px`) que sobrescreviam o `max-width: 45%` do CSS.
- **Fix Applied**:
  1. Modificado CSS no SlideCanvas para usar `width: 45% !important` ao invés de apenas `max-width: 45%` - isso força a largura mesmo quando há estilos inline
  2. Adicionado `object-fit: contain` para manter proporção da imagem
  3. Adicionado seletores adicionais para classes RTF (`img.rtf-image-float-left`, `img[class*="float-left"]`)
  4. Aplicado mesma correção em CoursePreview, SCORM exporter e HTML exporter
- **Files Modified**:
  - `/app/frontend/src/components/editor/SlideCanvas.jsx` - CSS do iframe HTML
  - `/app/frontend/src/components/editor/CoursePreview.jsx` - CSS do iframe HTML
  - `/app/backend/services/scorm_exporter.py` - CSS do iframe HTML
  - `/app/backend/services/html_exporter.py` - CSS do iframe HTML
- **Status**: FIXED AND TESTED - Imagens flutuantes agora mostram com ~45% da largura e texto flui corretamente ao lado


### Login "Body Stream Already Read" Error Fix - FIXED (Feb 11, 2026)
- **Issue**: Ao fazer login, usuários recebiam erro "Failed to execute 'json' on 'Response': body stream already read"
- **Root Cause**: Em casos de erro, o código tentava ler o response.json() duas vezes quando o parse JSON falhava
- **Fix Applied**: 
  1. Adicionado `response.clone()` antes de tentar ler o body para ter uma cópia de backup
  2. Se o parse JSON falhar, usa o clone para tentar obter o texto do erro
  3. Aplicado em funções `login()` e `processGoogleAuth()` no AuthContext
- **Files Modified**:
  - `/app/frontend/src/contexts/AuthContext.jsx` - funções login() e processGoogleAuth()
- **Status**: FIXED AND TESTED


### RTF Save Data Loss Bug - FIXED (Feb 12, 2026)
- **Issue**: Ao editar texto RTF e clicar em "Salvar Alterações", aparecia "Falha ao salvar texto" e ao fechar o editor, o conteúdo era apagado
- **Root Cause**: 
  1. `handleAddRichTextToSlide` usava `currentSlide.id` que poderia ser null/stale se o slide mudasse durante a edição
  2. `updateElement` e `addElement` no ProjectContext retornavam silenciosamente `undefined` quando `currentProject` era null
  3. O handler `onOpenChange` do Dialog limpava o conteúdo ao fechar, mesmo quando o save falhava
  4. Se o elemento HTML fosse deletado (por qualquer razão) enquanto o RTF editor referenciava seu ID, o PUT retornava 404
- **Fix Applied**:
  1. Adicionado estado `editingHtmlSlideId` para armazenar o ID do slide na abertura do editor
  2. `handleAddRichTextToSlide` agora usa `editingHtmlSlideId` (armazenado) em vez de `currentSlide.id` (dinâmico)
  3. `updateElement`/`addElement` agora lançam erros quando params obrigatórios estão faltando
  4. **Pré-verificação de existência**: Antes de chamar `updateElement`, verifica se o elemento ainda existe no estado local. Se foi deletado, cria um novo via `addElement` automaticamente
  5. Mensagens de erro mais detalhadas com informação do backend
- **Files Modified**:
  - `/app/frontend/src/pages/Editor.jsx` - handleAddRichTextToSlide (verificação de existência + auto-create), handleEditHtmlElement, dialog onOpenChange
  - `/app/frontend/src/contexts/ProjectContext.jsx` - updateElement, addElement (validação robusta)
- **Status**: FIXED AND TESTED (100% backend 13/13 + frontend all flows)
- **Verification**: Testing agent confirmou: edição, criação, e cenário de elemento deletado todos funcionam sem erros 404


### RTF Image Not Showing on Slide Canvas - FIXED (Feb 12, 2026)
- **Issue**: Imagens criadas no RTF editor não apareciam no Slide Canvas. O texto era cortado e a imagem flutuante era invisível.
- **Root Cause**: 
  1. O iframe do SlideCanvas usava dimensões fixas em pixels (width: ${element.width}px, height: ${element.height}px) no body CSS. Quando o canvas escalava visualmente o elemento, o conteúdo interno continuava na resolução nativa, resultando em corte (overflow: hidden). A imagem, posicionada à direita via float, ficava fora da área visível.
  2. O contentEditable do RTF editor herdava variáveis CSS Tailwind da página (--tw-*), adicionando ~69KB de lixo ao HTML salvo. Isso também interferia na renderização.
- **Fix Applied**:
  1. Alterado body CSS do iframe de pixels fixos para `width: 100%; height: 100%` - conteúdo agora reflui dentro do tamanho real do iframe no canvas
  2. Adicionada função `sanitizeHtmlForDisplay` que remove variáveis --tw-*, outline-style/outline-width de artefatos do editor
  3. Aplicada sanitização em 4 pontos: SlideCanvas (display), Editor (save), CoursePreview (preview), e exportadores SCORM/HTML
  4. Redução de conteúdo de 75KB para 6KB por elemento HTML
- **Files Modified**:
  - `/app/frontend/src/components/editor/SlideCanvas.jsx` - body CSS width:100%, sanitizeHtmlForDisplay function
  - `/app/frontend/src/pages/Editor.jsx` - sanitizeHtmlContent applied on save
  - `/app/frontend/src/components/editor/CoursePreview.jsx` - sanitization in processHtmlContent
  - `/app/backend/services/scorm_exporter.py` - sanitization before export
  - `/app/backend/services/html_exporter.py` - sanitization in process_html_content_images
- **Status**: FIXED AND TESTED (100% backend + frontend, testing agent iteration_19)


### SCORM player.js Double-Brace Artifact Fix (Feb 13, 2026)
- **Issue**: O arquivo `player.js` extraído para `export_assets/` continha artefatos `{{` e `}}` (escape de Python f-string) em vez de `{` e `}` na seção de decodificação Base64
- **Root Cause**: Durante a refatoração que extraiu o JS de strings Python f-string para arquivos externos, os double-braces `{{` não foram convertidos de volta para single-braces `{`
- **Fix Applied**: Substituído `{{` por `{` e `}}` por `}` nas linhas 1149-1160 do `player.js` (seção de decodificação Base64 do htmlContent)
- **Files Modified**: `/app/backend/services/export_assets/player.js`
- **Status**: FIXED AND TESTED
- **Note**: Embora `{{` seja sintaticamente válido em JavaScript (cria block scope aninhado), era um artefato que deveria ser limpo

### HTML Export Video Investigation (Feb 13, 2026)
- **Context**: O agente anterior reportou que vídeos estavam faltando na exportação HTML após a refatoração
- **Investigation**: Testados múltiplos projetos (Demo SCORMIFY videos, Ferramenta de Criação, Universidade-Corporativa-Didaxis)
- **Result**: Vídeos (YouTube, HeyGen/WebM) estão renderizando corretamente em todos os projetos testados
- **Vimeo Note**: O projeto "Universidade-Corporativa-Didaxis" tem um vídeo Vimeo que mostra "Player error" - isso é um erro do lado do Vimeo (vídeo privado/restrito), não do nosso código
- **Preview Route**: Adicionado parâmetro `?preview=1` ao endpoint `/api/exports/{filename}` para servir HTML inline sem forçar download

### Backend Export Route Enhancement (Feb 13, 2026)
- **Feature**: Parâmetro `?preview=1` no endpoint GET `/api/exports/{filename}`
- **Purpose**: Permite visualizar arquivos HTML exportados diretamente no navegador sem forçar download
- **Implementation**: Quando `preview=1` é passado para arquivos `.html`, o `Content-Disposition: attachment` é omitido
- **Files Modified**: `/app/backend/server.py`
- **Status**: IMPLEMENTED



### P3 - Future Enhancements
- Question bank sharing between projects
- Question import from QTI format
- Adaptive quizzes based on performance
- Gamification (badges, leaderboards)

