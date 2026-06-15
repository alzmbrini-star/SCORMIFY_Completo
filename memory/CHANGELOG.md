# Changelog


## 2026-02-XX (Bugfix: Whiteboard APNG ficava em loop infinito)

### Sintoma
- Vídeos de Whiteboard com fundo transparente (APNG) reiniciavam sozinhos toda vez que terminavam de escrever o texto. Esperado: tocar até o fim e parar congelado no quadro final.

### Causa
- `whiteboard_renderer.py:_write_apng_via_ffmpeg` chamava `ffmpeg ... -plays 0` (que no APNG significa "loop infinito"). O chunk `acTL` da PNG saía com `num_plays=0`.

### Correção
- **Renderer**: trocado para `-plays 1` (toca uma única vez).
- **Migração dos arquivos existentes**: script utilitário em `/tmp/fix_apng_loop.py` patcheia o chunk `acTL` in-place (reescreve apenas `num_plays` + CRC32) em todos os APNGs já em `/app/backend/storage/whiteboard/*.png`. Muito mais rápido que re-encode (ms vs minutos por arquivo). Aplicado em 7 APNGs existentes.

### Como verificar
- Recarregue um curso com slide whiteboard APNG → o vídeo escreve o texto e fica parado no quadro final, sem reiniciar.



## 2026-02-XX (Bugfix: SCORM Export quebrando slides com Whiteboard)

### P0 fix: Vídeo/APNG do Whiteboard não embarcava no pacote SCORM
- **Sintoma**: Ao exportar um curso SCORM Multi-página, slides contendo um vídeo de Whiteboard (Hand Writer) apareciam como tela vermelha com ícone de imagem quebrada no canto. Outros slides funcionavam normalmente.
- **Causa raiz**: O `scorm_exporter.py` só tratava URLs `/assets/...` e URLs externas `http(s)://...`. O renderer de Whiteboard gera URLs relativas `/api/whiteboard/file/wb_*.mp4` (vídeo) ou `/api/whiteboard/file/wb_*.png` (APNG transparente). Essas URLs caíam no fallthrough, ficavam intactas no `course.json` exportado e não resolviam quando o pacote era aberto offline.
- **Correção** (`/app/backend/services/scorm_exporter.py`, ~linha 548): novo branch que detecta `/api/whiteboard/file/` no `element.src`, localiza o arquivo em `STORAGE_DIR/whiteboard/`, copia para `package/assets/` e reescreve o `src` para `assets/{nome}`. Funciona tanto para MP4 (`type=video`) quanto APNG (`type=image` + `isAnimatedPng=true`).
- **Teste**: novo `tests/test_scorm_whiteboard_asset.py` valida copy + rewrite para MP4 e APNG usando arquivos reais já presentes em `storage/whiteboard/`. Passa em verde.
- **Impacto**: usuário precisa **Redeploy to Production** para que a correção apareça no link público.



## 2026-02-XX (Whiteboard: Negrito + Sublinhado + Alinhamento + Listas)

### Feature: Set completo de formatação RTF
- **Backend renderer**: chars agora é `list[dict]` com `{ch, x, y, color, bold, underline}`. Parser HTML estendido para extrair:
  - **Negrito** via `<b>`, `<strong>`, `font-weight:bold|600+`
  - **Sublinhado** via `<u>`, `text-decoration:underline`
  - **Alinhamento** via `text-align:left|center|right` no bloco ancestral (consumido por linha-fonte, não por linha-quebrada)
  - **Listas** `<ul><li>...</li></ul>` — cada `<li>` vira uma linha começando com "• "
- **Render**:
  - **Bold** simulado por **dilatação 1-px do alpha** no `_make_glyph_image` (sem variante bold nas fontes manuscritas; dilatação fica visualmente como "mais pressão no marcador"). Cache de glifo é mantido — bold é aplicado no composite.
  - **Underline** desenhado por `ImageDraw.line` abaixo da baseline (offset 0.92×altura, thickness ≈ altura/28) em segmentos contíguos. Segmento cresce progressivamente conforme a caneta avança (sublinhado também "anima" junto da escrita).
  - **Alinhamento** aplicado por **linha-fonte** (parágrafo HTML) — cada wrap subline herda a alignment do parágrafo. X inicial calculado de `MARGIN_X + (max_w − line_w) / 2` para centro e `MARGIN_X + max_w − line_w` para direita.
- **Frontend** (`WhiteboardDialog.jsx`):
  - Segunda linha de toolbar com botões **B / U / ⇤ / ⇔ / ⇥ / •** (Bold, Underline, AlignLeft, AlignCenter, AlignRight, BulletList).
  - Cada botão usa `document.execCommand` (`bold`, `underline`, `justifyLeft/Center/Right`, `insertUnorderedList`) com `styleWithCSS=true` para gerar HTML semanticamente compatível com o parser do backend.
  - Detecção de payload expandida — envia `textHtml` se houver QUALQUER formatação (cor, bold, underline, alinhamento, ou lista).
- **Skip nesta iteração**: Itálico (Caveat/Marker não têm itálico nativo; faking via skew CSS ficaria visualmente ruim). Listas numeradas. Identação multi-nível. Tamanho por trecho.
- **Verificação visual**: HTML de teste com Título centralizado + negrito, Normal + sublinhado, 2 itens com bullet, e "Direita" alinhada à direita — todos os 4 features renderizaram corretamente no MP4.



## 2026-02-XX (Whiteboard: Cor da tinta + editor RTF mini)

### Feature: Color picker global + RTF inline para colorir trechos
- **Backend renderer** (`whiteboard_renderer.py`):
  - Estrutura de `chars` virou 4-tupla `(char, x, y, color)` (era 3-tupla). Cada caractere carrega sua própria cor RGB.
  - Nova função `_parse_html_to_runs` (HTMLParser stdlib) extrai inline `<span style="color:#XXX">` e `<font color="#XXX">` em sequências de `(char, color)`.
  - Novo `_parse_color` aceita `#RRGGBB`, `#RGB`, `rgb(r,g,b)`.
  - `_make_glyph_image` recebe cor: recolore o RGB do glifo mantendo o alpha (que preserva antialiasing). Cache de glifo continua keyed por char (cor aplicada no composite).
  - `_layout` aceita `default_color` e `text_html` opcionais; quando `text_html` está presente, faz parsing das runs e mapeia cada char para sua cor.
  - `render_whiteboard_video` aceita `ink_color` e `text_html` params; renderiza cada char com sua cor exata.
- **Backend route** (`whiteboard.py`): novos campos `inkColor` (hex/rgb) e `textHtml` (HTML max 8000 chars). Validados e passados ao renderer.
- **Frontend** (`WhiteboardDialog.jsx`):
  - **Editor mini-RTF**: substituí o Textarea por um `<div contentEditable>` com toolbar de cores. Paleta de 10 cores (alto contraste contra branco) + input `<input type="color">` para cor customizada + botão "Limpar" (`removeFormat`).
  - **Cor padrão das letras**: input color picker no rodapé do editor que define `inkColor` para todo o texto não-colorido.
  - **Comportamento de seleção**: usa `document.execCommand('foreColor', ...)` com `styleWithCSS=true` para envolver a seleção em `<span style="color:#XXX">`.
  - **Paste sanitization**: paste externo é convertido para plain text (`insertText`) para evitar HTML/CSS sujo de outros apps.
  - **Sync bidirecional**: `text` (plain) e `textHtml` (rich) sincronizados via `onInput`/`onBlur`. Quando IA preenche texto, o useEffect atualiza o contentEditable preservando o cursor.
  - **Payload smart**: só envia `textHtml` se detectou pelo menos uma tag de cor inline — caso contrário envia só `text` + `inkColor` global (payloads menores).
- **Verificação**:
  - ✅ Global red (#E11D48): "Vermelho!" todo na cor escolhida.
  - ✅ Mixed HTML: "Normal `VERMELHO` e `azul`" — cada palavra na sua cor exata, com a caneta tracejando o esqueleto em qualquer cor.
- **Skip nesta iteração**: variação de tamanho por trecho (exigiria reflow de layout para mixed font sizes — bem mais complexo). Documentado como backlog.



## 2026-02-XX (Whiteboard: Gerador de texto com IA — GPT-4o)

### Feature: Texto do whiteboard gerado por IA com contexto do slide
- **Botão "Gerar com IA"** no `WhiteboardDialog`: expande um painel violeta com um campo opcional de instrução livre e um botão "Gerar texto agora". O texto retornado preenche o textarea principal.
- **Híbrido** (slide + prompt):
  - Extrai automaticamente do slide: `title`, conteúdo de `elements` (texto/HTML, com tags strippadas), `narration`, `notes`, `extractedText` (PPT).
  - Instrução livre opcional do autor (ex: "tom motivacional", "incluir data X"). Pode ser deixada vazia se o contexto do slide é suficiente.
- **Modelo**: GPT-4o via Emergent LLM Key (`emergentintegrations.llm.chat.LlmChat`), seguindo o padrão já usado em `density_suggester.py`.
- **Post-processing**:
  - Remove aspas/backticks envolventes que o modelo às vezes adiciona.
  - Converte `\n` literal (que GPT às vezes emite como 2 chars) em quebra real, respeitada pelo renderer.
  - Hard-cap em `maxChars` (default 280, range 80..600) com elipse no fim.
  - Strip por linha + colapso de linhas vazias.
- **Endpoint**: `POST /api/whiteboard/generate-text` — payload `{userPrompt?, projectId?, slideId?, maxChars}` → `{text, charsUsed}`.
- **Validação**: 400 se nem userPrompt nem slide content estão presentes (evita "geração no escuro").
- **Aplicado em**: `routes/whiteboard.py` (endpoint + extrator de contexto), `pages/Editor/dialogs/WhiteboardDialog.jsx` (UI expansível com Wand2 icon).



## 2026-02-XX (Whiteboard: Fundo transparente + multi-fontes + tamanhos grandes)

### Feature: Fundo transparente via APNG animado
- **Motivação**: usuário queria sobrepor o vídeo do whiteboard no background do slide sem fundo branco.
- **Investigação de codec**: WebM VP9-alpha e VP8-alpha foram testados primeiro (parecem suportados via `-pix_fmt yuva420p`), mas tanto o `imageio_ffmpeg` bundled quanto o `ffmpeg` 5.1 do sistema **silenciosamente strippam o canal alpha** durante o encode. O output sempre saía como yuv420p mesmo com a flag `alpha_mode=1`.
- **Solução**: usamos **APNG (Animated PNG)** para outputs transparentes. APNG preserva alpha losslessly e tem suporte nativo em todos os browsers modernos via `<img>`. Trade-off: arquivos ~10x maiores que MP4 (3.4s = ~1.6MB), aceitável para animações curtas (recomendado <300 chars/slide).
- **Pipeline**: quando `transparent=True`, frames RGBA são pipeados diretamente para `ffmpeg -c:v apng -f apng -plays 0 -pred mixed` via stdin. Compositing testado sobre fundo colorido: 100% transparente, sem halos.
- **Binding ao slide**: APNG transparente é injetado como `element.type = "image"` (com `isAnimatedPng: true`) em vez de `"video"`, pois browsers renderizam APNG via `<img>` automaticamente. MP4 opaco continua como `"video"`.

### Feature: 7 fontes manuscritas + tamanhos até 240px
- **Fontes empacotadas** (todas OFL/Apache, baixadas do repositório oficial Google Fonts):
  - Caveat (manuscrita, default)
  - Architects Daughter (arquiteto)
  - Indie Flower (arredondada)
  - Patrick Hand (limpa)
  - Permanent Marker (marcador grosso)
  - Shadows Into Light (fina)
  - Kalam (caligráfica)
- **Catalog API**: `GET /api/whiteboard/fonts` retorna fontes presentes no disco com label e style hint.
- **Tamanhos**: `fontSize` agora aceita 40..240 (era 40..140), com presets na UI: Pequeno (64), Médio (96), Grande (140), Maior (180), Enorme (220), além de input numérico livre.
- **UI nova** (`WhiteboardDialog.jsx`):
  - Dropdown de fonte (fetched de `/api/whiteboard/fonts`)
  - Combinação preset + input numérico para tamanho
  - Toggle "Fundo transparente" com explicação do trade-off
  - Preview do resultado em `<img>` (APNG) ou `<video>` (MP4) com xadrez de fundo para visualizar transparência

### Files
- `services/whiteboard_renderer.py`: FONT_CATALOG, `_resolve_font_path`, `list_available_fonts`, `_write_apng_via_ffmpeg`, suporte transparent no `_render_frame_writing`.
- `routes/whiteboard.py`: fontFamily/transparent params, /fonts endpoint, binding APNG como image element, serve .png com mime image/apng.
- `assets/whiteboard/fonts/*.ttf`: 7 fontes empacotadas (~1.3MB total).
- `pages/Editor/dialogs/WhiteboardDialog.jsx`: UI completa.



## 2026-02-XX (Whiteboard: Caneta minimalista + escrita coluna-a-coluna)

### Feature: Asset de caneta minimalista (substitui mão cartunizada)
- **Asset**: `/app/backend/assets/whiteboard/_generate_hand.py` reescrito para gerar uma caneta minimalista (estilo fineliner) com nib, seção, barril, clip metálico e end cap. Mantida a convenção do tip em (0, 0) para compatibilidade com o renderer.
- **Output**: PNG 144×159 (`hand.png`), paleta restrita (preto/grafite/cinza metálico).
- **Renderer**: `hand_target_h` ajustado de 3.0× para 2.2× do `font_size` para proporção mais elegante. Offsets do tip ajustados para alinhamento preciso no traço.

### Bug fix: Caneta parecia "parada" no vídeo gerado
- **Root cause**: o `chars_per_second` default era 19 (~ritmo de digitação robótica). A 30 FPS isso dá só **1.58 frames por caractere**. Como o algoritmo usa ~14 sub-passos por letra para traçar o esqueleto, cada frame avançava ~9 sub-passos — o olho não captava movimento dentro de uma letra, parecia que a caneta pulava de letra em letra.
- **Fix #1 (backend)**: sub-passos por caractere agora são calculados em função de `FPS/cps` (clamp 6..24), garantindo aproximadamente 1 sub-passo por frame. Também adicionada duração mínima `total_substeps/FPS` para forçar ≥1 frame por sub-passo (slow-down automático se cps for muito alto).
- **Fix #2 (frontend)**: default reduzido de 19 → 6 cps (velocidade natural de manuscrita). Limites do input ajustados para 2..30 (era 4..40). Texto de ajuda reescrito.
- **Verificação**: gerei "O instrutor deve enfatizar" com título em cps=6. Grid de 16 frames mostra a caneta em posições nitidamente diferentes em cada frame, acompanhando o texto sendo escrito.
- **Aplicado em**: `services/whiteboard_renderer.py` (cálculo dinâmico de sub-passos + min duration), `pages/Editor/dialogs/WhiteboardDialog.jsx` (default + bounds + help text).


- **Problema da versão anterior**: a caneta usava varredura coluna-a-coluna com centroide vertical da tinta. Em letras com múltiplos traços (H, T, F), a caneta "ficava no vazio" entre os traços (média de duas regiões de tinta = espaço em branco).
- **Solução**: implementado **Zhang-Suen thinning em numpy puro** (sem scipy). Cada glifo é renderizado → binarizado → afinado em um esqueleto de 1 pixel → caminho do esqueleto é ordenado em "ordem de escrita":
### Feature: Animação de escrita seguindo o ESQUELETO da letra (Zhang-Suen)

  1. Componentes conectados ordenados pela esquerda-cima.
  2. Dentro de cada componente, começa do endpoint topo-esquerdo, anda buscando vizinhos com preferência por continuidade direcional.
- **Revelação por disco**: cada ponto do esqueleto "pinta" um disco de raio ≈ stroke-width na máscara de revelação — a tinta cresce naturalmente em volta da ponta da caneta, como tinta saindo do nib.
- **Caneta segue o esqueleto**: a posição da ponta a cada sub-passo é o ponto correspondente do caminho do esqueleto.
- **Resultado verificado**: para "H", a caneta desenha o vertical esquerdo, depois a travessa, depois o vertical direito — multi-stroke real. Para "o" cursivo, a caneta segue a curva continuamente.
- **Performance**: 44 chars em 2s de render, MP4 ~45 KB. Cache por glifo único garante reutilização para caracteres repetidos.
- **Sub-passos por caractere**: aumentados para `font_size/6` (clamp 8–20) para movimento mais suave.
- **Aplicado em**: `services/whiteboard_renderer.py` (Zhang-Suen + ordenação de path + reveal masks por disco).



## 2026-02-XX (Editor Chat: Brand Kit fix + logo size control)

### Bug fix: "Aplique o brand kit completo" só aplicava cores (sem logo, sem fonte)
- **Root cause**: o LLM mapeava a frase "brand kit completo" para `apply_brand_palette` em vez de `apply_brand_identity`, porque o System Prompt só tinha exemplos com "identidade visual completa" / "branding".
- **Fix**: adicionados exemplos explícitos ("aplique o brand kit", "kit da empresa", "kit completo da marca", "brand kit completo") apontando para `apply_brand_identity` em `routes/editor_chat.py`. Também adicionado padrão "logo grande/médio/pequeno" na descrição da op.

### Feature: Tamanho customizável do logo no Brand Kit
- **Modelo**: novo campo `logoSize` (int, default 96, range 32–320) em `BrandKit` + `BrandKitUpdate`.
- **Editor Chat**: op `apply_brand_identity` agora aceita `logoSize: int | "small" | "medium" | "large"`. Override em ordem: op-level > BrandKit-level > default(96).
- **Re-apply idempotente**: rodar o comando novamente com tamanho diferente agora SINCRONIZA o elemento `isBrandLogo` existente (atualiza width/height/posição/src) em vez de pular silenciosamente.
- **UI Super Admin**: `BrandLibraryDialog.jsx` ganhou seção "Tamanho do logo" com 3 presets (Pequeno=64, Médio=96, Grande=160) + input numérico personalizado (32–320 px).
- **Testes**: 8 testes pytest em `tests/test_editor_chat_logo_size.py` cobrem default size, preset overrides, clamping, idempotência e fallback sem logo URL.


## 2026-04-17 (Fork: AI Agent analyze_content Fix)

### CRITICAL Bug Fix: AI Agent Course Creation - `analyze_content` ImportError
- **Root Cause**: The `async def analyze_content()` function definition in `/app/backend/services/ai_agent.py` was accidentally placed INSIDE a prompt f-string instead of being a proper Python function declaration. This made the function invisible to Python imports, causing `ImportError: cannot import name 'analyze_content'` when the background analysis thread tried to execute.
- **Fix**: Moved the `async def analyze_content(...)` declaration to its correct position ABOVE the docstring and prompt string, restoring it as a proper top-level async function.
- **Applied in**: `services/ai_agent.py` (lines 121-125)
- **Status**: Tested - import verified, backend restarted clean

### Fix: Agent 404 Errors on Suggestions Polling + MongoDB Connection Leaks
- **Problem**: During AI course creation, the frontend polled `/api/agent/sessions/{id}/suggestions` indefinitely even on 404 errors, flooding the browser console. Backend background tasks (`_generate_improvement_suggestions`, `_generate_narrations`) each created their own MongoDB clients, risking Atlas M0 connection limit exhaustion.
- **Fix (Frontend)**: Added `res.ok` check in suggestions polling with max 5 retries before switching to error state. Prevents infinite 404 polling.
- **Fix (Backend)**: Replaced standalone `AsyncIOMotorClient()` creation in `_generate_improvement_suggestions` and `_generate_narrations` with the shared singleton `_get_bg_motor_db()` (maxPoolSize=3).
- **Applied in**: `GeneratedPanel.jsx` (polling logic), `agent.py` (background tasks)
- **Status**: Backend compiled, endpoint tested
- **Problem**: The Storyboard panel showed raw HTML tags (`<h1>`, `<p>`, `<strong>`) instead of rendered formatted content, making it hard for approvers to visualize the final slides.
- **Fix**: Added preview/edit toggle in `StoryboardPanel.jsx`. Default mode ("Visualizar") renders HTML content with proper prose styling. "Editar" mode shows original Textarea fields.
- **Applied in**: `frontend/src/pages/Agent/components/StoryboardPanel.jsx`
- **Status**: Implemented, lint clean



## 2026-03-27 (Fork: Video Export Production Fix)

### CRITICAL Bug Fix: Video Export 520 in Production (Event Loop Blocking)
- **Root Cause**: `create_slide_base_image()` (PIL/Pillow) and `get_media_duration()` (subprocess.run) were synchronous and blocked the FastAPI event loop for 2-3 seconds PER SLIDE. For a 14-slide course, this blocked the server for ~40 seconds total. Cloudflare's health checks couldn't reach the backend → returned **520 "Web server returned unknown error"**.
- **Fix**: Wrapped ALL blocking operations in `asyncio.to_thread()`:
  - `create_slide_base_image()` → runs in thread pool (PIL image creation)
  - Image padding operations → runs in thread pool  
  - `get_media_duration()` → runs in thread pool (ffprobe subprocess)
- **Result**: Event loop stays free during entire video processing. Poll response times: all < 0.7s (was 2-3s blocking per slide). Health checks respond in < 0.3s during video processing.
- **Applied in**: `services/video_exporter.py` (3 blocking operations wrapped in asyncio.to_thread)
- **Status**: Tested ✅ — 14-slide project processes while server handles all requests normally

### CRITICAL Bug Fix: Video Export 403 in Production (withCredentials conflict)
- **Root Cause**: The axios interceptor in `ProjectContext.jsx` set `withCredentials: true` on ALL requests. This sent Cloudflare cookies (`__cf_bm` bot management cookie) with every polling request. Cloudflare detected the automated polling pattern (every 3s with credentials) as bot activity and blocked with 403 Forbidden.
- **Fix**: Removed `withCredentials: true` from the global axios interceptor. Auth works via `Authorization: Bearer <token>` header from localStorage, cookies are unnecessary. Also changed `asyncio.ensure_future(create_job())` to `await create_job()` in the backend to guarantee job exists in MongoDB before the response is sent (prevents 404 in multi-worker deployments).
- **Applied in**: `frontend/src/contexts/ProjectContext.jsx` (axios interceptor), `backend/routes/export.py` (create_job await)
- **Status**: Tested ✅ — Login, dashboard, and video export all work without withCredentials

### CRITICAL Bug Fix: Video Export 502/504/Timeout in Production (P0 - RESOLVED)
- **Root Cause**: `POST /export-video` did heavy synchronous work BEFORE returning the jobId — importing `video_exporter` module (which downloads static-ffmpeg binaries ~50-100MB on first call), checking `is_ffmpeg_available()`, and fetching the project from MongoDB. In production, Cloudflare/Nginx proxy killed the connection after 30-60s timeout → 502/504.
- **Fix (Backend)**: Endpoint now returns jobId in **< 300ms** with ZERO heavy work. All validation (FFmpeg check, project fetch) moved to `asyncio.create_task(run_export())`. Job creation uses fire-and-forget `asyncio.ensure_future(create_job())`. Errors surface as job status "failed" instead of HTTP errors.
- **Fix (Frontend)**: `useEditorExport.js` now has: retry with exponential backoff on initial POST (3 attempts), tolerance for intermittent 502/504 during polling (up to 10 consecutive errors), 10-minute max polling timeout, and proper cleanup via `useRef`.
- **Applied in**: `routes/export.py` (export_video_endpoint), `frontend/src/pages/Editor/hooks/useEditorExport.js`
- **Status**: Tested ✅ (iteration_79) — 100% backend/frontend pass rate. POST: 0.24s, 10-slide export: ~40s.

---

## 2026-03-25 (Previous Session)

### CRITICAL Bug Fix: Video Export 502 in Production
- **Root Cause**: `run_ffmpeg()` used blocking `subprocess.run()` inside an async task. While FFmpeg processed 18 slides (30-60s), the entire asyncio event loop was blocked — the backend couldn't respond to ANY request, causing Cloudflare proxy to return 502.
- **Fix**: Created `run_ffmpeg_async()` using `asyncio.create_subprocess_exec()`. All FFmpeg/FFprobe calls in `export_video()` are now non-blocking. Backend responds to polling requests during video processing.
- **Also fixed**: Import of `video_exporter` wrapped in try/except (prevents backend crash if module fails), `_ensure_ffmpeg()` initialization wrapped in try/except, `static-ffmpeg` pip package as fallback (no root needed), startup event tries `static-ffmpeg` before `apt-get`
- **Applied in**: `services/video_exporter.py`, `routes/export.py`, `server.py`
- **Status**: Tested ✅ — backend responds HTTP 200 during all 18 slide processing

### Bug Fix: Video Export Job 404 in Production
- **Root Cause**: Job status was stored in-memory (`jobs` dict). In production, process restarts or multiple workers caused the job data to be lost, returning 404 on GET `/api/job/{jobId}`.
- **Fix**: Job data now persisted in **MongoDB** (`jobs` collection) with local cache for fast access. Jobs survive restarts, deploys, and multi-worker environments.
- **Applied in**: `routes/deps.py` (create_job, update_job, get_job), `routes/export.py`, `routes/projects.py`
- **Status**: Tested ✅ — job survives backend restart and is recoverable from MongoDB

### Bug Fix: SCORM Completion Not Triggering
- **Root Cause**: Completion logic required ALL scenarios to be completed in addition to quizzes. Scenarios are interactive branching exercises that users might skip or not complete fully, blocking SCORM "completed" status indefinitely.
- **Fix**: Changed completion rules in `player.js` to: Navigate to last slide + Complete all quizzes (if any). Scenarios are now optional (enrich learning but don't block completion).
- **Applied in**: `services/export_assets/player.js` (checkAndSetCompletion + finalCompletionCheck)
- **Status**: Tested ✅ — re-exported SCORM package contains updated logic

### Feature: AI Simulator/Game Generation in Course Creation
- **Modified**: `ai_agent.py` - Added `simulator` slide type to `generate_structure`, `generate_storyboard`, `generate_course_from_storyboard`, `generate_structure_from_template`
- **Modified**: `routes/agent.py` - Enhanced `_build_improved_elements` to handle HTML simulator elements, added `course_interactivity` category to improvement suggestions, enhanced `apply_course_improvements` prompt
- **What it does**: AI Agent now MANDATORY creates 1-2 interactive HTML+JS simulators per module (calculators, drag-and-drop, flashcards, memory games, quizzes, timelines, etc.)
- **Status**: Code deployed ✅ — needs user testing via course creation flow

### Video Export Fix: FFmpeg Persistence
- **Root Cause**: FFmpeg not available after fork/deploy because system packages are reset
- **Fix**: Triple-layer persistence:
  1. `start.sh` script installs FFmpeg before starting uvicorn (supervisor)
  2. FastAPI `startup_ensure_ffmpeg()` event auto-installs if missing
  3. `video_exporter.py` lazy-loads FFmpeg paths at runtime
- Added WebM media type to `serve_export` endpoint
- **Applied in**: `server.py`, `backend/start.sh`, `services/video_exporter.py`, `routes/export.py`
- **Status**: Tested ✅ (MP4: 54s/374KB, WebM: 54s/1.1MB)

### CRITICAL Bug Fix: AI Tutor CORS in Production (Recurring Issue #4)
- **Root Cause**: SCORM packages served from LMS domains (e.g., `didaxis.didaxis.com.br`) make cross-origin requests to the backend. Production proxy/infrastructure may strip CORS headers or not forward OPTIONS preflight to the app.
- **Fix**: Triple-layer CORS protection for `/api/tutor/chat`:
  1. Global `CORSMiddleware` with `allow_origins=["*"]` and fallback for empty env vars
  2. Custom `TutorCorsMiddleware` that explicitly handles OPTIONS and adds CORS headers for `/tutor/chat`
  3. Explicit CORS headers in `JSONResponse` at the route handler level
- **Applied in**: `server.py` (middleware), `routes/admin.py` (endpoint handlers)
- **Status**: Tested ✅ (preview) — User must **re-deploy and re-export SCORM** to test in production

### Bug Fix: Washed-Out Slide Thumbnails
- **Root Cause**: HTML element placeholders in thumbnails were empty transparent divs, hiding the actual slide content. AI-generated slides use HTML elements as main visual content covering the full area.
- **Fix**: Replaced empty placeholder with sandboxed `<iframe>` (`sandbox="allow-scripts"`, no `allow-same-origin`) that renders the actual HTML content safely without CSS leaking
- **Applied in**: `SlideThumbnailContent.jsx`
- **Status**: Verified ✅ — thumbnails now show full slide content (text, images, tables, buttons)

### CRITICAL Bug Fix: AI HTML CSS Leaking to Editor UI
- **Root Cause**: `SlideThumbnailContent.jsx` rendered HTML elements using `dangerouslySetInnerHTML` directly in the editor DOM (no iframe isolation). AI-generated HTML contains `<style>` tags with global CSS rules (e.g., `button { background: gradient(...) }`, `body { background: white }`) that cascade to ALL elements on the page, breaking toolbar icons, button visibility, and the dark theme.
- **Fix**: Replaced `dangerouslySetInnerHTML` with a safe placeholder (`</> HTML`) for HTML elements in thumbnails. Also removed `allow-same-origin` from all iframe sandboxes and added `contain: strict; isolation: isolate` on iframe containers.
- **Applied in**: `frontend/src/pages/Editor/components/SlideThumbnailContent.jsx`, `frontend/src/components/editor/SlideCanvas.jsx`, `CoursePreview.jsx`, `SplitPreview.jsx`, `Editor.jsx`
- **Status**: Tested ✅ — toolbar clean, dark theme restored, HTML renders correctly in iframe

### Feature: AI-Powered HTML Generation in Editor
- **What**: "Gerar com IA" tab in HTML dialog with prompt → preview → edit → insert
- **Backend**: `POST /api/generate-html` using Gemini
- **Status**: Tested ✅ (iteration_78)

### Bug Fix: Full HTML Documents Breaking iframe CSS
- **Fix**: Auto-detect `<!DOCTYPE html>` and render directly as srcDoc without wrapper
- **Applied in**: SlideCanvas, CoursePreview, SplitPreview, player.js, html_exporter.py
- **Status**: Tested ✅

### Bug Fix: AI Tutor 404 in Production SCORM Exports
- **Fix**: `_get_external_url()` now uses X-Forwarded headers from K8s proxy
- **Status**: Tested ✅ (iteration_77)

### CRITICAL Bug Fix: Missing Route Registrations
- **Fix**: Added 8 missing route modules to server.py
- **Status**: Tested ✅ (iteration_76)

## Previous Sessions
- SCORM completion, HTML scenario, deployment, background images, login fixes
- Before/After Preview + Undo, AI improvements layout fix
- Gamification, AI Agent scenario fix, Fix Simulators button
