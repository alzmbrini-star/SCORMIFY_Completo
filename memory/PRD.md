# Scormify - PPT to SCORM Converter

## Original Problem Statement
Criar um aplicativo web que converte arquivos PPT/PPTX para pacotes SCORM 1.2 com fidelidade visual, editor de slides, timeline de animações/áudio, e exportação compatível com LMS.

## Architecture
- **Frontend**: React + Tailwind CSS + Shadcn/UI
- **Backend**: FastAPI (Python)
- **Database**: MongoDB
- **File Storage**: Local filesystem (/app/backend/storage)
- **PPT Conversion**: LibreOffice (headless) + pdf2image
- **Third-Party Integrations**: HeyGen API (avatares de IA), ElevenLabs (TTS), Emergent LLM Key (Gemini 3 Flash - narração IA, GPT-4o - scripts)

## Changelog (Recent Updates)

### 2026-02-13 (Latest)
- **FEATURE P0: Geração de Narração com IA** (IMPLEMENTED AND TESTED)
  - Backend: `POST /api/projects/{project_id}/slides/{slide_id}/generate-narration`
  - Usa Gemini 3 Flash (`gemini-3-flash-preview`) via Emergent LLM Key
  - Analisa conteúdo do slide (textos, imagens, quiz) para gerar narração contextual
  - Retorna 3 opções de texto para o usuário escolher
  - Suporta 4 estilos: Educativo, Conversacional, Formal, Amigável
  - Frontend: Botão "Gerar com IA" no diálogo TTS com seletor de estilo
  - Opções exibidas em cards clicáveis; seleção preenche campo de texto TTS
  - **Testado**: Backend 10/10 testes, Frontend todos elementos verificados funcionais

- **BUGFIX P0: Sobreposição de Elementos + Centralização no Mobile Export** (FIXED AND TESTED)
  - Removida `optimizeForMobile()` e código morto de reflow
  - Alterado `transform-origin` para `0 0` com margens negativas
  - **Files Modified**: `player.js`, `player.css`, `html_exporter.py`

- **Layout 50/50 Lado a Lado - Editor + Preview** (IMPLEMENTED)
- **Split Preview - Preview Integrado ao Editor** (IMPLEMENTED AND TESTED)

### 2026-02-12
- **CORREÇÃO P0: Imagens RTF Quebradas Após Fork** (FIXED AND TESTED)

## Key Files
- `backend/server.py` - Server principal com endpoint de narração IA (line ~1657)
- `backend/services/export_assets/player.js` - Player SCORM
- `backend/services/export_assets/player.css` - Estilos do player SCORM
- `backend/services/html_exporter.py` - Gerador HTML standalone
- `backend/services/scorm_exporter.py` - Gerador pacote SCORM
- `frontend/src/pages/Editor.jsx` - Editor principal com diálogo TTS + IA

## Backlog
- Refatorar `html_exporter.py` para usar templates externos (manutenibilidade)
- Quiz readability improvements on very small mobile screens
