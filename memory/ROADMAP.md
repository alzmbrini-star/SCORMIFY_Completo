# Roadmap

## P0 - Critical
- [x] SCORM completion fix
- [x] HTML export scenario fix
- [x] Production deployment fix
- [x] Image generation timeout fix
- [x] AI improvements layout fix
- [x] Before/After Preview + Undo
- [x] AI Tutor URL fix
- [x] Fix Simulators UI button
- [x] **Missing route registrations fix** (companies, users, elevenlabs, gallery, heygen, questions, scenarios, vlibras)
- [x] **AI Tutor CORS fix** (triple-layer CORS for production cross-origin access)
- [x] **Video Export Production Fix**: POST returns instantly, all heavy work in background (2026-03-27)
- [x] **PPT Import populating Presenter Notes** (2026-02): body text now falls back into `slide.notes` when PPT has no presenter notes; `extractedText` field declared on `Slide` model
- [ ] **User verification**: Image generation with 23+ slides
- [x] **Production OOM 502/520 on Whiteboard** (2026-07-11) — render agora roda em SUBPROCESSO isolado (`whiteboard_worker.py`): OOM mata só o filho, job falha graciosamente, backend segue vivo; memória 100% devolvida ao SO; saída reduzida para 1280x720 (~2.25x menos buffers ffmpeg, override via `WHITEBOARD_OUTPUT_HEIGHT`); x264 `-preset veryfast -threads 2`. **Usuário precisa RE-DEPLOYAR.**
- [ ] **Production OOM 502/520 on HTML export** — mesma causa raiz (limite de memória do pod). Candidato a receber o mesmo padrão de isolamento em subprocesso do Whiteboard. SCORM continua funcionando normal.

## P1 - High Priority
- [ ] SCORM 2004 & xAPI Export (detailed performance data to LMS)
- [ ] Advanced scenario analytics & scoring dashboard
- [ ] Course version history

## P2 - Medium Priority
- [ ] Custom images for gamification badges
- [x] ConvertAPI key renewal (PPT import restored - credits renewed)

## P3 - Backlog
- [ ] Collaborative scenarios (multiple learners)
- [ ] Advanced AI Tutor interactivity
- [ ] HeyGen video generation (blocked on user API credits)

## Refactoring
- [ ] Extract dialogs from Editor.jsx (~3700 lines)
- [ ] Organize route files and models
