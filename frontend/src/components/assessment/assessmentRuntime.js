// Serialized into the assessment document; do not reference module scope.
export function assessmentRuntime(resolveVideoLink) {
  const data = JSON.parse(document.getElementById('assessment-data').textContent);
  const questions = data.questions || [];
  const root = document.getElementById('app');
  const answers = new Map();
  const submitted = new Map();
  let index = 0;
  let selectedCard = null;
  const labels = { single_choice: 'Escolha simples', multiple_choice: 'Múltipla seleção', ordering: 'Ordenar etapas', categorization: 'Arrastar e soltar' };
  function node(tag, cls, text, parent) {
    const el = document.createElement(tag); el.className = cls || '';
    if (text !== undefined) el.textContent = text;
    if (parent) parent.appendChild(el); return el;
  }
  function button(text, cls, action, parent, disabled = false) {
    const el = node('button', cls, text, parent); el.type = 'button'; el.disabled = disabled; el.onclick = action; return el;
  }
  function value(q) {
    if (!answers.has(q.id)) {
      answers.set(q.id, q.type === 'categorization' ? {} : q.type === 'ordering' ? q.items.map(x => x.id).reverse() : []);
    }
    return answers.get(q.id);
  }
  function ready(q) {
    const a = value(q);
    return q.type === 'categorization' ? q.items.every(x => a[x.id]) : a.length > 0;
  }
  function correct(q, a) {
    if (q.type === 'ordering') return JSON.stringify(a) === JSON.stringify(q.correctOrder);
    if (q.type === 'categorization') return q.items.every(x => a[x.id] === x.correctTarget);
    return JSON.stringify([...a].sort()) === JSON.stringify(q.options.filter(x => x.isCorrect).map(x => x.id).sort());
  }
  function navigate(next) {
    if (next < 0 || next >= questions.length) return;
    if (data.allowSkip === false && questions.slice(0, next).some(q => !submitted.has(q.id))) return;
    index = next; selectedCard = null; render();
  }
  function finish() {
    if (data.allowSkip === false && submitted.size < questions.length) return;
    if (submitted.size < questions.length && !window.confirm('Há questões sem resposta confirmada. Deseja finalizar?')) return;
    let total = 0, points = 0;
    questions.forEach(q => { total += q.points || 1; if (submitted.has(q.id) && correct(q, submitted.get(q.id))) points += q.points || 1; });
    // Exported players expose an initialized SCORM API in the parent chain.
    // Record this assessment's score without completing the surrounding course.
    try {
      let owner = window;
      for (let depth = 0; depth < 8; depth++) {
        const api = owner.API || owner.API_1484_11;
        if (api) {
          const modern = !owner.API;
          const set = (key, val) => modern ? api.SetValue(key, String(val)) : api.LMSSetValue(key, String(val));
          const prefix = modern ? 'cmi.score.' : 'cmi.core.score.';
          set(prefix + 'raw', Math.round(total ? points / total * 100 : 0)); set(prefix + 'min', 0); set(prefix + 'max', 100);
          if (modern) api.Commit(''); else api.LMSCommit('');
          break;
        }
        if (owner.parent === owner) break;
        owner = owner.parent;
      }
    } catch (_) { /* Sandboxed Editor previews do not expose an LMS. */ }
    root.replaceChildren(); const main = node('main', 'assessment', undefined, root);
    const summary = node('section', 'summary', undefined, main); const box = node('div', '', undefined, summary);
    node('div', 'eyebrow', 'AVALIAÇÃO CONCLUÍDA', box); node('h1', '', data.title, box);
    node('div', 'score', `${Math.round(total ? points / total * 100 : 0)}%`, box);
    node('p', '', `${points} de ${total} pontos · ${submitted.size} de ${questions.length} respondidas`, box);
    button('Revisar respostas', '', () => { index = 0; render(); }, box);
  }
  function advance() {
    if (index < questions.length - 1) navigate(index + 1); else finish();
  }
  function safeUrl(raw) {
    try { const u = new URL(raw, data.assetBase || document.baseURI); return ['https:', 'http:', 'blob:'].includes(u.protocol) || /^data:(image\/|video\/|application\/)/i.test(raw) ? u.href : ''; } catch (_) { return ''; }
  }
  function media(q, stage) {
    const m = q.media; const url = m && safeUrl(m.url);
    if (!url) { node('div', 'asset-empty', q.category || 'Avaliação de aprendizagem', stage); return; }
    if (m.kind === 'image') { const img = node('img', '', undefined, stage); img.src = url; img.alt = m.name || 'Material de apoio'; }
    else if (m.kind === 'video' && m.source === 'external') {
      let embed;
      try { embed = resolveVideoLink(m.url); } catch (_) { node('p', '', 'Link de vídeo inválido. Edite a questão e informe um link do YouTube, Vimeo ou Bunny Stream.', stage); return; }
      const box = node('div', 'external-video', undefined, stage);
      box.style.cssText = 'width:100%;height:100%;min-height:220px;position:relative;background:#000;overflow:hidden;border-radius:8px';
      const frame = node('iframe', '', undefined, box);
      // Match normal Editor video insertion: some Bunny libraries accept
      // direct playback but reject an external Referer with a 403 player.
      // Set policy before src so the first navigation uses the right headers.
      frame.referrerPolicy = embed.provider === 'Bunny Stream' ? 'no-referrer' : 'strict-origin-when-cross-origin';
      frame.src = embed.url; frame.title = m.name || `Vídeo · ${embed.provider}`;
      frame.style.cssText = 'position:absolute;inset:0;width:100%;height:100%;display:block;border:0';
      frame.allow = 'autoplay; encrypted-media; picture-in-picture; fullscreen'; frame.allowFullscreen = true;
    }
    else if (m.kind === 'video') { const video = node('video', '', undefined, stage); video.src = url; video.controls = true; }
    else {
      if (/\.pdf(?:[?#]|$)/i.test(m.name || m.url) || /^data:application\/pdf/i.test(url)) {
        const frame = node('iframe', '', undefined, stage); frame.src = url; frame.title = m.name || 'PDF de apoio';
      } else {
        const doc = node('div', 'document', undefined, stage); node('b', '', m.name || 'Documento de apoio', doc);
        node('p', '', 'Abra o documento no aplicativo compatível do seu dispositivo.', doc);
        const link = node('a', '', 'Abrir / baixar documento', doc); link.href = url; link.target = '_blank'; link.rel = 'noopener'; link.download = m.name || 'documento';
      }
    }
  }
  function cardImage(item, parent) {
    const url = item.media?.kind === 'image' && safeUrl(item.media.url);
    if (!url) return;
    const img = node('img', 'card-image', undefined, parent);
    img.src = url; img.alt = item.media.name || item.text; img.draggable = false;
  }
  function enlarge(q) {
    const overlay = node('div', 'image-overlay', undefined, root);
    overlay.setAttribute('role', 'dialog'); overlay.setAttribute('aria-modal', 'true');
    overlay.setAttribute('aria-label', 'Imagem ampliada');
    const close = () => { overlay.remove(); document.removeEventListener('keydown', onKey); };
    const onKey = event => { if (event.key === 'Escape') close(); };
    const closeButton = button('Fechar imagem ×', 'image-close', close, overlay);
    const img = node('img', '', undefined, overlay); img.src = safeUrl(q.media.url); img.alt = q.media.name || q.title;
    overlay.onclick = event => { if (event.target === overlay) close(); };
    document.addEventListener('keydown', onKey); closeButton.focus();
  }
  function render() {
    root.replaceChildren(); const main = node('main', 'assessment', undefined, root);
    if (!questions.length) { node('div', 'summary', 'Nenhuma questão selecionada.', main); return; }
    const q = questions[index], a = value(q), locked = submitted.has(q.id);
    const visualChoices = ['single_choice', 'multiple_choice'].includes(q.type) && !q.media && q.options.some(option => option.media?.kind === 'image');
    const top = node('header', 'top', undefined, main); const groups = new Map();
    questions.forEach((item, i) => { const category = item.category || 'Geral'; if (!groups.has(category)) groups.set(category, []); groups.get(category).push(i); });
    const nav = node('nav', 'categories', undefined, top); nav.setAttribute('aria-label', 'Categorias e questões');
    groups.forEach((indices, category) => {
      const group = node('div', '', undefined, nav); node('div', 'cat', category, group); const nums = node('div', 'numbers', undefined, group);
      indices.forEach(i => { const b = button(String(i + 1), `num ${i === index ? 'active' : ''} ${submitted.has(questions[i].id) ? 'done' : ''}`, () => navigate(i), nums, data.allowSkip === false && i > index && !locked); b.setAttribute('aria-label', `Questão ${i + 1}: ${questions[i].title}`); });
    });
    node('span', '', `${submitted.size} de ${questions.length} respondidas`, top);
    button('Finalizar', 'skip', finish, top, data.allowSkip === false && submitted.size !== questions.length);
    const shell = node('section', 'shell', undefined, main); const work = node('section', 'work', undefined, shell);
    const head = node('div', 'media-head', undefined, work); node('span', '', q.media?.name || q.title, head); node('span', 'badge', q.category, head);
    if (q.media?.kind === 'image') button('⤢ Ampliar', 'image-expand', () => enlarge(q), head);
    const stage = node('div', 'stage', undefined, work);
    const panel = node('section', 'panel', undefined, shell); const body = node('div', 'panel-body', undefined, panel);
    node('span', 'tag', labels[q.type], body); node('div', 'eyebrow', `QUESTÃO ${index + 1} DE ${questions.length}`, body);
    node('h1', '', q.title, body); node('p', 'prompt', q.prompt, body);
    node('p', 'instructions', q.instructions || (q.type === 'categorization' ? 'Arraste um cartão ou clique nele e depois no destino.' : 'Responda e confirme para avançar.'), body);
    if (q.type === 'categorization') {
      const zones = node('div', 'dropzones', undefined, stage); const tray = node('div', 'tray', undefined, body);
      const assign = (id, target) => { if (locked || !q.items.some(x => x.id === id)) return; a[id] = target; selectedCard = null; render(); };
      const card = (item, parent) => { const b = button(item.text, `card ${selectedCard === item.id ? 'selected' : ''}`, () => { selectedCard = item.id; render(); }, parent, locked); cardImage(item, b); b.draggable = !locked; b.ondragstart = ev => ev.dataTransfer.setData('text/plain', item.id); };
      q.targets.forEach((target, i) => {
        const zone = node('div', 'zone', undefined, zones); zone.style.setProperty('--zone', ['#64b5ff', '#ffc543', '#50d6cc', '#ff8a9a'][i % 4]);
        button(target.label, 'option', () => assign(selectedCard, target.id), zone, locked);
        zone.ondragover = ev => ev.preventDefault(); zone.ondrop = ev => { ev.preventDefault(); assign(ev.dataTransfer.getData('text/plain'), target.id); };
        q.items.filter(item => a[item.id] === target.id).forEach(item => card(item, zone));
      });
      q.items.filter(item => !a[item.id]).forEach(item => card(item, tray));
      if (q.media) { const support = node('div', 'assessment-support', undefined, body); media(q, support); }
    } else {
      if (!visualChoices) media(q, stage);
      const choices = visualChoices ? node('div', 'visual-choices', undefined, stage) : body;
      if (visualChoices) node('p', 'instructions', q.type === 'single_choice' ? 'Clique na imagem que responde à pergunta.' : 'Selecione todas as imagens corretas.', body);
      if (q.type === 'ordering') {
        a.forEach((id, i) => {
          const item = q.items.find(x => x.id === id); const row = node('div', 'order', undefined, body);
          row.draggable = !locked;
          row.ondragstart = ev => ev.dataTransfer.setData('text/plain', id);
          row.ondragover = ev => ev.preventDefault();
          row.ondrop = ev => {
            ev.preventDefault(); if (locked) return;
            const source = a.indexOf(ev.dataTransfer.getData('text/plain'));
            if (source < 0 || source === i) return;
            a.splice(i, 0, a.splice(source, 1)[0]); render();
          };
          node('div', 'option', `${i + 1}. ${item.text}`, row);
          const move = delta => { const j = i + delta; if (locked || j < 0 || j >= a.length) return; [a[i], a[j]] = [a[j], a[i]]; render(); };
          button('↑', '', () => move(-1), row, locked || i === 0); button('↓', '', () => move(1), row, locked || i === a.length - 1);
        });
      } else q.options.forEach((option, i) => {
        const selected = a.includes(option.id);
        const review = locked ? option.isCorrect ? ' answer-correct' : selected ? ' answer-incorrect' : '' : '';
        const b = button(visualChoices ? undefined : `${String.fromCharCode(65 + i)}. ${option.text}`, `option ${visualChoices ? 'visual-choice' : ''} ${selected ? 'selected' : ''}${review}`, () => {
          answers.set(q.id, q.type === 'single_choice' ? [option.id] : a.includes(option.id) ? a.filter(id => id !== option.id) : [...a, option.id]); render();
        }, choices, locked); cardImage(option, b);
        if (visualChoices) {
          node('span', 'visual-caption', option.text || `Alternativa ${String.fromCharCode(65 + i)}`, b);
          node('span', 'visual-marker', locked && option.isCorrect ? '✓ Correta' : locked && selected ? '× Incorreta' : selected ? '✓ Selecionada' : String.fromCharCode(65 + i), b);
        }
        b.setAttribute('aria-pressed', String(selected));
      });
    }
    if (locked) node('div', `feedback ${correct(q, submitted.get(q.id)) ? 'ok' : 'no'}`, `${correct(q, submitted.get(q.id)) ? 'Resposta correta. ' : 'Resposta incorreta. '}${q.explanation || ''}`, body);
    const footer = node('footer', 'footer', undefined, panel);
    button(locked ? 'Próxima questão →' : '✓ Confirmar resposta', 'confirm', () => {
      if (!locked) submitted.set(q.id, JSON.parse(JSON.stringify(a))); advance();
    }, footer, !locked && !ready(q));
    if (data.allowSkip !== false && !locked) button('Pular', 'skip', advance, footer);
  }
  render();
}
