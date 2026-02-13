# Scormify - PPT to SCORM Converter

## Original Problem Statement
Criar um aplicativo web que converte arquivos PPT/PPTX para pacotes SCORM 1.2 com fidelidade visual, editor de slides, timeline de animações/áudio, e exportação compatível com LMS.

## Architecture
- **Frontend**: React + Tailwind CSS + Shadcn/UI
- **Backend**: FastAPI (Python)
- **Database**: MongoDB
- **File Storage**: Local filesystem (/app/backend/storage)
- **PPT Conversion**: LibreOffice (headless) + pdf2image
- **Third-Party Integrations**: HeyGen API (avatares de IA), ElevenLabs (TTS), Emergent LLM Key (Gemini 3 Flash Vision - narração IA com OCR, GPT-4o - scripts)

## Changelog (Recent Updates)

### 2026-02-13 (Latest)
- **FEATURE P0: Geração de Narração com IA + Vision/OCR** (IMPLEMENTED AND TESTED)
  - Backend: `POST /api/projects/{project_id}/slides/{slide_id}/generate-narration`
  - Usa **Gemini 3 Flash multimodal** (`gemini-3-flash-preview`) via Emergent LLM Key
  - **Vision/OCR**: Lê imagens dos slides (backgroundImage de PPTs importados + image elements) via FileContent
  - Extrai texto de elementos text/html diretamente
  - Retorna 3 opções de narração contextual baseadas no conteúdo real do slide
  - Suporta 4 estilos: Educativo, Conversacional, Formal, Amigável
  - Frontend: Botão "Gerar com IA" no diálogo TTS com seletor de estilo
  - **Testado**: Backend 10/10, Frontend 100% verificado (iteration_22 + iteration_23)

- **BUGFIX P0: Sobreposição + Centralização no Mobile Export** (FIXED AND TESTED)

### 2026-02-12
- **CORREÇÃO P0: Imagens RTF Quebradas Após Fork** (FIXED AND TESTED)

## Key Files
- `backend/server.py` - Server com endpoint narração IA (vision + text)
- `backend/services/export_assets/player.js` - Player SCORM
- `backend/services/html_exporter.py` - Gerador HTML standalone
- `frontend/src/pages/Editor.jsx` - Editor com TTS + IA

## Backlog
- Refatorar `html_exporter.py` para usar templates externos
- Quiz readability improvements on very small mobile screens
