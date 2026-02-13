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
- **BUGFIX P0: Narração IA não lia conteúdo real dos slides** (FIXED)
  - Causa raiz: Backend só verificava campo `content` dos elementos, mas o editor RTF salva em `htmlContent`
  - Correção: Agora lê `content` E `htmlContent`, extrai imagens inline de htmlContent (src="/api/..."), e carrega assets globais (/api/assets/)
  - Testado: Slides "Sydney, Austrália", "Pontes de Sydney", "Terra de Contrastes" - IA agora referencia conteúdo específico

- **FEATURE P0: Geração de Narração com IA + Vision/OCR** (IMPLEMENTED AND TESTED)
  - Backend: `POST /api/projects/{project_id}/slides/{slide_id}/generate-narration`
  - Usa **Gemini 3 Flash multimodal** via Emergent LLM Key
  - Lê: backgroundImage (PPTs importados), image elements, htmlContent (RTF), imagens inline, text elements
  - Retorna 3 opções de narração contextual baseadas no conteúdo real do slide
  - 4 estilos: Educativo, Conversacional, Formal, Amigável

## Key Files
- `backend/server.py` - Server com endpoint narração IA (vision + text + htmlContent)
- `frontend/src/pages/Editor.jsx` - Editor com TTS + IA

## Backlog
- Refatorar `html_exporter.py` para usar templates externos
- Quiz readability improvements on very small mobile screens
