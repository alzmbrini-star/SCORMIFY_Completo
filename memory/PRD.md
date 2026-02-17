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
- **BUGFIX P0: Vídeos HeyGen com fundo transparente apareciam com fundo preto** (FIXED)
  - Causa raiz: FFmpeg não decodificava canal alpha de VP9 WebM sem `-c:v libvpx-vp9` explícito
  - Correção: Detecta vídeos com alpha (`has_alpha` flag), usa decoder `libvpx-vp9` + `format=yuva420p` + `overlay format=auto`
  - Verificado: Cantos transparentes do avatar agora mostram slide por baixo (RGB match confirmado)

- **BUGFIX P0: FFmpeg não encontrado após fork** (FIXED)
  - Caminhos absolutos: `/usr/bin/ffmpeg`, `/usr/bin/ffprobe`, `/root/.venv/bin/yt-dlp`

### 2026-02-14
- **FEATURE P0: Exportação de Vídeo (MP4/WebM)** (IMPLEMENTED AND TESTED)

### 2026-02-13
- **FEATURE P0: Narração IA + Vision/OCR** (IMPLEMENTED AND TESTED)

## Key Files
- `backend/server.py` - Server principal
- `backend/services/video_exporter.py` - Exportação de vídeo com alpha transparency
- `frontend/src/pages/Editor.jsx` - Editor

## Backlog
- Refatorar `html_exporter.py` para templates externos
- Quiz readability mobile
