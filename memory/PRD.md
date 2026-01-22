# Scormify - PPT to SCORM Converter

## Original Problem Statement
Criar um aplicativo web que converte arquivos PPT/PPTX para pacotes SCORM 1.2 com fidelidade visual, editor de slides, timeline de animações/áudio, e exportação compatível com LMS.

## Architecture
- **Frontend**: React + Tailwind CSS + Shadcn/UI
- **Backend**: FastAPI (Python)
- **Database**: MongoDB
- **File Storage**: Local filesystem (/app/backend/storage)

## User Personas
1. **Instructional Designers** - Create e-learning content from existing PPT presentations
2. **Training Managers** - Need SCORM packages for LMS deployment
3. **Content Creators** - Build interactive courses with multimedia

## Core Requirements
- [x] PPT/PPTX file upload and parsing
- [x] Slide editor with canvas
- [x] Text, shape, image, video elements
- [x] Timeline for animations
- [x] Audio recording (Web Audio API)
- [x] YouTube/Vimeo embedding
- [x] Global soundtrack support
- [x] Slide CRUD (create, duplicate, delete, reorder)
- [x] Annotation tools (freehand drawing)
- [x] SCORM 1.2 export with valid manifest
- [x] Dark/Light theme toggle

## What's Been Implemented (January 2026)

### Backend (server.py)
- Project CRUD API endpoints
- PPT parsing with python-pptx
- Slide/Element management
- Media upload (images, audio)
- SCORM 1.2 package generation
- Valid imsmanifest.xml with namespaces
- XSD schema files

### Frontend
- Dashboard with project list
- Editor with:
  - Left sidebar: Slide thumbnails with context menu
  - Main canvas: Interactive elements
  - Right sidebar: Properties panel, Layers, Media
  - Toolbar: Text, Shape, Image, Video, Annotations, Recording
  - Timeline: Element tracks and playhead
- Theme toggle (dark/light)
- Export dialog with download

## Prioritized Backlog

### P0 (Critical)
- All implemented ✓

### P1 (High Priority)
- [ ] PPT animation extraction and playback
- [ ] Drag & drop slide reordering
- [ ] Element copy/paste
- [ ] Undo/redo history

### P2 (Medium Priority)
- [ ] PPT SmartArt rendering
- [ ] WordArt support
- [ ] Chart rendering
- [ ] Multiple audio tracks per slide
- [ ] Animation timeline editor

### P3 (Future)
- [ ] Collaborative editing
- [ ] Template library
- [ ] Asset library
- [ ] Preview mode
- [ ] SCORM 2004 support

## Next Tasks
1. Implement drag & drop slide reordering
2. Add undo/redo functionality
3. Improve PPT animation extraction
4. Add element copy/paste shortcuts
5. Implement preview mode

## Tech Stack
- React 18
- FastAPI
- MongoDB
- python-pptx
- Tailwind CSS
- Shadcn/UI
- Lucide Icons
