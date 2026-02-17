# Scormify - PPT to SCORM Converter

## Original Problem Statement
Criar um aplicativo web que converte PPT/PPTX para SCORM 1.2 com editor de slides, timeline, áudio e exportação.

## Architecture
- **Frontend**: React + Tailwind + Shadcn/UI
- **Backend**: FastAPI (Python)
- **Database**: MongoDB
- **Dependencies**: FFmpeg (/usr/bin/ffmpeg), yt-dlp, Pillow
- **Third-Party**: HeyGen (avatares), ElevenLabs (TTS), Gemini 3 Flash (narração IA)

## Changelog

### 2026-02-17 (Latest)
- **BUGFIX P0: Exportação de vídeo WebM/MP4 falhava** (FIXED AND TESTED)
  - Causa raiz: `ffmpeg` e `ffprobe` não estavam no PATH do processo backend após fork
  - Correção: Usar caminhos absolutos `/usr/bin/ffmpeg` e `/usr/bin/ffprobe` no video_exporter.py
  - Também corrigido: yt-dlp usando caminho absoluto `/root/.venv/bin/yt-dlp`
  - Testado: WebM (4.3MB, 75s) e MP4 ambos exportam corretamente

### 2026-02-14
- **FEATURE P0: Exportação de Vídeo (MP4/WebM)** (IMPLEMENTED AND TESTED)

### 2026-02-13
- **FEATURE P0: Narração IA + Vision/OCR** (IMPLEMENTED AND TESTED)
- **BUGFIX: htmlContent não era lido** (FIXED)

## Key Files
- `backend/server.py` - Server principal
- `backend/services/video_exporter.py` - Serviço de exportação de vídeo (usa caminhos absolutos para ffmpeg)
- `frontend/src/pages/Editor.jsx` - Editor

## Backlog
- Refatorar `html_exporter.py` para templates externos
- Quiz readability mobile
