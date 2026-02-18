# Scormify - PPT to SCORM Converter

## Original Problem Statement
Criar um aplicativo web que converte PPT/PPTX para SCORM 1.2 com editor de slides, timeline, áudio e exportação.

## Architecture
- **Frontend**: React + Tailwind + Shadcn/UI
- **Backend**: FastAPI (Python)
- **Database**: MongoDB
- **Dependencies**: FFmpeg, yt-dlp, Pillow
- **Third-Party**: HeyGen (avatares), ElevenLabs (TTS), Gemini 3 Flash Vision (narração IA com OCR)

## Changelog

### 2026-02-17 (Latest)
- **FEATURE P0: Leitura OCR no diálogo HeyGen** (IMPLEMENTED AND TESTED)
  - HeyGen agora tem 3 tabs: "Digitar" (manual), "Ler Slide" (OCR/Vision), "Tema Livre" (tema livre)
  - Tab "Ler Slide" usa Gemini Vision para ler conteúdo do slide e gerar 3 opções de script
  - Reutiliza endpoint `generate-narration` existente
  - Seletor de estilo (Educativo/Conversacional/Formal/Amigável)
  - Ao clicar numa opção, preenche textarea e volta para tab "Digitar"
  - **Testado**: 100% backend + frontend (iteration_25)

- **BUGFIX P0: HeyGen fundo preto na exportação de vídeo** (FIXED)
  - Decoder VP9 alpha explícito com `-c:v libvpx-vp9`

- **BUGFIX P0: FFmpeg não encontrado após fork** (FIXED)
  - Caminhos absolutos para ffmpeg/ffprobe/yt-dlp

### 2026-02-14
- **FEATURE P0: Exportação de Vídeo (MP4/WebM)** (IMPLEMENTED AND TESTED)

### 2026-02-13
- **FEATURE P0: Narração IA + Vision/OCR no TTS** (IMPLEMENTED AND TESTED)

## Key Files
- `backend/server.py` - Server principal
- `backend/services/video_exporter.py` - Exportação de vídeo
- `frontend/src/pages/Editor.jsx` - Editor com TTS + HeyGen + IA

## Backlog
- Refatorar `html_exporter.py` para templates externos
- Quiz readability mobile
