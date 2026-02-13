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
- **BUGFIX P0: Sobreposição de Elementos no Mobile Export** (FIXED AND TESTED)
  - **Problema**: No player SCORM exportado, a função `optimizeForMobile()` forçava elementos quiz e html a ocupar o slide inteiro (position 0,0 com width/height do slide), causando sobreposição com outros elementos no mesmo slide (texto+vídeo, dois textos, duas imagens).
  - **Causa raiz**: `optimizeForMobile()` em `player.js` expandia `.quiz-element` e `.html-element` para cobrir 100% do slide em dispositivos mobile, destruindo o posicionamento original dos elementos.
  - **Correção**: 
    - Removida a função `optimizeForMobile()` do `player.js` (SCORM)
    - Removidas as chamadas `setTimeout(optimizeForMobile, 100)` e `setTimeout(updateSlideScale, 150)`
    - Removido código morto do modo reflow (bloco `if (false)` e cleanup associado)
    - Removidos CSS de reflow não utilizados do `player.css`
    - O `transform: scale()` no container já trata o redimensionamento proporcional corretamente
    - Fontes quiz continuam otimizadas via CSS media queries (sem alterar posições)
  - **Files Modified**: 
    - `backend/services/export_assets/player.js` (removido optimizeForMobile + dead reflow code)
    - `backend/services/export_assets/player.css` (removido CSS .mobile-landscape-reflow)
  - **Testado**: SCORM export com slides multi-elemento (html+video, grid de textos) - elementos posicionados corretamente sem sobreposição

- **Correção Mobile - SCORM/HTML Export Player** (IMPLEMENTED)
  - Removido modo reflow do player SCORM → usa scaling uniforme como desktop
  - Overlay de orientação agora é dispensável com botão "Continuar no modo retrato"
  - Scale mínimo reduzido para suportar portrait

- **Layout 50/50 Lado a Lado - Editor + Preview** (IMPLEMENTED)
  - Editor canvas e Preview panel alinhados lado a lado com divisão 50%/50%

- **Split Preview - Preview Integrado ao Editor** (IMPLEMENTED AND TESTED)
  - Botão "Visualizar" abre painel lateral de preview em vez de modal fullscreen

### 2026-02-12
- **CORREÇÃO P0: Imagens RTF Quebradas Após Fork** (FIXED AND TESTED)
  - URLs absolutas de imagens convertidas para relativas no save

## Key Files
- `backend/services/export_assets/player.js` - Player SCORM (scaling + navegação)
- `backend/services/export_assets/player.css` - Estilos do player SCORM
- `backend/services/html_exporter.py` - Gerador HTML standalone
- `backend/services/scorm_exporter.py` - Gerador pacote SCORM
- `frontend/src/pages/Editor.jsx` - Editor principal

## Backlog
- Refatorar `html_exporter.py` para usar templates externos (manutenibilidade)
- Quiz readability improvements on very small mobile screens
