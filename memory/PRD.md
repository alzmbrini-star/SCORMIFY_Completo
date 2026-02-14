# Scormify - PPT to SCORM Converter

## Original Problem Statement
Criar um aplicativo web que converte PPT/PPTX para SCORM 1.2 com editor de slides, timeline, áudio e exportação.

## Architecture
- **Frontend**: React + Tailwind + Shadcn/UI
- **Backend**: FastAPI (Python)
- **Database**: MongoDB
- **Third-Party**: HeyGen (avatares), ElevenLabs (TTS), Gemini 3 Flash (narração IA), FFmpeg (vídeo), yt-dlp (YouTube/Vimeo)

## Changelog

### 2026-02-14 (Latest)
- **FEATURE P0: Exportação de Vídeo (MP4/WebM)** (IMPLEMENTED AND TESTED)
  - Backend: `POST /api/course/{project_id}/export-video` - async job com progresso
  - Composição: background + image elements + text + vídeos HeyGen/YouTube/Vimeo
  - Duração automática: vídeo overlay > áudio narração > padrão configurável
  - Quiz ignorado, YouTube/Vimeo incluídos via yt-dlp
  - Pillow para composição de imagens, FFmpeg para encoding
  - Frontend: Botões MP4/WebM no diálogo de exportação com barra de progresso
  - **Testado**: 100% backend + frontend (iteration_24)

### 2026-02-13
- **FEATURE P0: Narração IA + Vision/OCR** (IMPLEMENTED AND TESTED)
- **BUGFIX: htmlContent não era lido** (FIXED)
- **BUGFIX: Sobreposição + Centralização Mobile** (FIXED)

## Key Files
- `backend/server.py` - Server principal
- `backend/services/video_exporter.py` - Serviço de exportação de vídeo
- `frontend/src/pages/Editor.jsx` - Editor com exportação

## Backlog
- Refatorar `html_exporter.py` para templates externos
- Quiz readability mobile
