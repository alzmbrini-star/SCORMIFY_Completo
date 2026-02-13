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

### 2026-02-13 (Latest)
- **BUGFIX P0: Sobreposição de Elementos + Centralização no Mobile Export** (FIXED AND TESTED)
  - **Problema 1 (Overlap)**: `optimizeForMobile()` forçava elementos quiz/html a cobrir 100% do slide, sobrepondo outros elementos.
  - **Problema 2 (Desalinhamento)**: `transform-origin: center center` com `transform: scale()` não reduzia o layout box, causando desalinhamento com flexbox centering.
  - **Correção**: 
    - Removida `optimizeForMobile()` e código morto de reflow do `player.js` e `player.css`
    - Alterado `transform-origin` de `center center` para `0 0` em ambos os players
    - Adicionadas margens negativas (`marginRight`, `marginBottom`) para sincronizar layout box com tamanho visual
    - Flexbox centering agora funciona corretamente em qualquer orientação
  - **Files Modified**: `player.js`, `player.css`, `html_exporter.py`
  - **Testado**: SCORM + HTML export com slides multi-elemento em portrait e landscape - centralizado e sem sobreposição

- **Layout 50/50 Lado a Lado - Editor + Preview** (IMPLEMENTED)
- **Split Preview - Preview Integrado ao Editor** (IMPLEMENTED AND TESTED)

### 2026-02-12
- **CORREÇÃO P0: Imagens RTF Quebradas Após Fork** (FIXED AND TESTED)

## Key Files
- `backend/services/export_assets/player.js` - Player SCORM (scaling + navegação)
- `backend/services/export_assets/player.css` - Estilos do player SCORM
- `backend/services/html_exporter.py` - Gerador HTML standalone
- `backend/services/scorm_exporter.py` - Gerador pacote SCORM
- `frontend/src/pages/Editor.jsx` - Editor principal

## Backlog
- Refatorar `html_exporter.py` para usar templates externos (manutenibilidade)
- Quiz readability improvements on very small mobile screens
