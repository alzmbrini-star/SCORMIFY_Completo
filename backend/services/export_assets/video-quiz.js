(function () {
  'use strict';
  const config = JSON.parse(document.getElementById('video-quiz-data').textContent);
  const $ = id => document.getElementById(id), video = $('video');
  if (config.timingReviewRequired === true) {
    // Author draft: watch the original speech, but never run/grade guessed pauses.
    video.src = config.src; video.controls = true;
    $('title').textContent = config.title;
    $('question').textContent = 'Tempos de pausa aguardam revisão do autor';
    $('progress').textContent = 'As perguntas e o roteiro foram preservados; esta atividade ainda não está liberada.';
    $('message').textContent = config.timingReviewMessage;
    $('play').disabled = true; $('seek').disabled = true;
    document.querySelector('footer').textContent = 'Rascunho: revise as pausas em Perguntas durante o vídeo no Editor antes de distribuir ou exportar para os alunos.';
    ['font', 'contrast'].forEach((id, i) => { $(id).onclick = () => { const on = document.body.classList.toggle(i ? 'high' : 'large'); $(id).setAttribute('aria-pressed', String(on)); }; });
    return;
  }
  const progress = config.checkpoints.map(() => ({attempts: 0, resolved: '', released: false}));
  let active = -1, ready = false, saving = false, lastSave = -1, finished = false, acceptResume = true;
  let pauseFrame = null;
  function stopPauseMonitor() {
    if (pauseFrame !== null) window.cancelAnimationFrame(pauseFrame);
    pauseFrame = null;
  }
  function monitorPause() {
    pauseFrame = null;
    if (video.paused || video.ended || !ready) return;
    enforce();
    if (!video.paused && active < 0) pauseFrame = window.requestAnimationFrame(monitorPause);
  }
  function startPauseMonitor() {
    stopPauseMonitor();
    // Native media timeupdate can lag hundreds of milliseconds. Read the actual
    // media clock each display frame, rather than pausing after the next phrase.
    if (typeof window.requestAnimationFrame === 'function') pauseFrame = window.requestAnimationFrame(monitorPause);
  }
  const graded = config.graded === true;
  const restart = document.createElement('button'); restart.id = 'restart-video-quiz'; restart.type = 'button'; restart.hidden = true;
  restart.textContent = graded ? 'Nova tentativa (vale nota)' : 'Rever vídeo e perguntas';
  $('play').closest('.controls').appendChild(restart);
  const footer = document.querySelector('footer');
  if (footer) footer.textContent = graded ? 'Atividade avaliativa: acertos dentro do limite de tentativas valem nota. A explicação após esgotar as tentativas não pontua.' : 'Atividade sem nota: você pode rever o vídeo e responder novamente usando “Rever vídeo e perguntas”.';
  const storeKey = 'scormify-video-quiz:' + config.key;
  function api() {
    try { let win = window; for (let n = 0; n < 8; n++) { if (win.API) return win.API; if (win === win.parent) break; win = win.parent; } } catch (_) { /* sandboxed author preview */ }
    return null;
  }
  function load() {
    try { const lms = api(); const all = lms ? JSON.parse(lms.LMSGetValue('cmi.suspend_data') || '{}') : null; if (lms) return all && all.videoQuizzes && all.videoQuizzes[config.key] || null; return JSON.parse(localStorage.getItem(storeKey) || 'null'); } catch (_) { return null; }
  }
  function save() {
    if (saving) return; saving = true;
    const state = {p: progress.map(p => [p.attempts, p.resolved, p.released ? 1 : 0]), t: Math.floor(video.currentTime || 0), d: finished ? 1 : 0};
    try { localStorage.setItem(storeKey, JSON.stringify(state)); } catch (_) { /* storage may be disabled */ }
    try { const lms = api(); if (lms) { const all = JSON.parse(lms.LMSGetValue('cmi.suspend_data') || '{}'); all.videoQuizzes = all.videoQuizzes || {}; all.videoQuizzes[config.key] = state; const text = JSON.stringify(all); if (new TextEncoder().encode(text).length <= 3800) { lms.LMSSetValue('cmi.suspend_data', text); lms.LMSCommit(''); } } } catch (_) { /* Never overwrite non-JSON LMS resume or lesson_status. */ }
    window.parent.postMessage({type: 'scormify-video-quiz', action: 'save', key: config.key, state: state}, '*');
    saving = false;
  }
  function notify(type) { window.parent.postMessage({type: 'scormify-video-quiz', action: type, key: config.key}, '*'); }
  function reportResult() {
    if (!graded || !finished || !progress.every(p => p.released)) return;
    const correct = progress.filter(p => p.resolved === 'correct').length;
    window.parent.postMessage({type:'scormify-video-quiz',action:'result',key:config.key,correct,total:progress.length,score:Math.round(100*correct/progress.length)},'*');
  }
  function restore(saved) {
    if (!saved || !Array.isArray(saved.p) || saved.p.length !== progress.length) return;
    saved.p.forEach((p, i) => { if (Array.isArray(p) && Number.isInteger(p[0]) && p[0] >= 0 && p[0] <= config.checkpoints[i].maxAttempts && ['', 'correct', 'assisted'].includes(p[1])) Object.assign(progress[i], {attempts:p[0],resolved:p[1],released:!!p[2]&&!!p[1]}); });
    finished = saved.d === 1 && progress.every(p => p.released);
    if (Number.isFinite(saved.t)) video.currentTime = Math.max(0, Math.min(saved.t, video.duration));
    restart.hidden = graded && !finished;
    reportResult();
  }
  function time(cp) { return cp.relative ? cp.at * video.duration : cp.at; }
  function nextDue(position) { return config.checkpoints.findIndex((cp, i) => !progress[i].released && time(cp) <= position + 0.04); }
  function say(text) { $('feedback').hidden = !text; $('feedback').textContent = text; }
  function show(index) {
    if (active === index) return;
    active = index; video.pause(); notify('pause');
    const cp = config.checkpoints[index], state = progress[index];
    $('question').textContent = cp.question; $('progress').textContent = 'Pergunta ' + (index+1) + ' de ' + progress.length + ' · até ' + cp.maxAttempts + ' tentativas';
    $('options').replaceChildren();
    const legend = document.createElement('legend'); legend.textContent = 'Selecione uma alternativa'; $('options').appendChild(legend);
    cp.options.forEach((text, i) => { const label = document.createElement('label'); label.className = 'option'; const input = document.createElement('input'); input.type = 'radio'; input.name = 'answer'; input.value = String(i); input.disabled = !!state.resolved; const span = document.createElement('span'); span.textContent = text; label.append(input, span); $('options').appendChild(label); });
    $('options').hidden = false; $('answer').hidden = !!state.resolved; $('continue').hidden = !state.resolved;
    $('message').textContent = state.resolved ? 'Leia a explicação abaixo do personagem e continue.' : 'Responda para liberar este trecho do vídeo.';
    say(state.resolved ? cp.explanation : ''); $('question').focus();
  }
  function enforce() {
    if (!ready) return;
    const due = nextDue(video.currentTime);
    if (due >= 0) { const boundary = time(config.checkpoints[due]); if (Math.abs(video.currentTime - boundary) > .15) video.currentTime = boundary; show(due); video.pause(); }
  }
  async function play() { enforce(); if (active >= 0) return; try { await video.play(); notify('pause'); } catch (_) { $('message').textContent = 'Clique em Reproduzir para iniciar o vídeo.'; } }
  $('title').textContent = config.title;
  // Assign the URL through a DOM property: never interpret author text as HTML.
  video.src = config.src;
  video.addEventListener('loadedmetadata', () => {
    if (!Number.isFinite(video.duration) || config.checkpoints.some(cp => time(cp) >= video.duration)) { $('message').textContent = 'Existe uma pausa fora da duração do vídeo. O autor precisa revisar os tempos nas propriedades.'; $('play').disabled = true; return; }
    $('seek').max = String(video.duration); ready = true;
    restore(load()); restart.hidden = graded && !finished;
    $('progress').textContent = progress.length + ' pausas com perguntas. Use Reproduzir para começar.'; enforce();
    if (!video.paused) startPauseMonitor();
    notify('restore');
  });
  window.addEventListener('message', event => {
    if (!ready || !acceptResume || event.source !== window.parent || event.data?.type !== 'scormify-video-quiz-resume' || event.data.key !== config.key || progress.some(p => p.attempts || p.released) || video.currentTime > 0.1) return;
    const saved = event.data.state;
    if (!saved || !Array.isArray(saved.p) || saved.p.length !== progress.length) return;
    restore(saved);
    active = -1;
    enforce();
  });
  video.addEventListener('error', () => { $('message').textContent = 'Não foi possível carregar o vídeo. Verifique o link, a conexão e a disponibilidade do arquivo.'; });
  video.addEventListener('timeupdate', () => { enforce(); $('seek').value = String(video.currentTime); $('clock').textContent = Math.floor(video.currentTime/60) + ':' + String(Math.floor(video.currentTime%60)).padStart(2, '0'); const tick = Math.floor(video.currentTime / 5); if (tick !== lastSave) { lastSave = tick; save(); } });
  video.addEventListener('seeking', enforce);
  video.addEventListener('play', () => { enforce(); $('play').textContent = 'Pausar'; startPauseMonitor(); });
  video.addEventListener('pause', () => { stopPauseMonitor(); $('play').textContent = 'Reproduzir'; save(); });
  video.addEventListener('ended', stopPauseMonitor);
  video.addEventListener('ended', () => { enforce(); if (active < 0 && progress.every(p => p.released)) { finished = true; restart.hidden = false; $('question').textContent = 'Vídeo concluído'; const correct=progress.filter(p=>p.resolved==='correct').length; $('message').textContent = graded ? 'Sua nota: '+Math.round(100*correct/progress.length)+'% ('+correct+' de '+progress.length+'). Uma nova tentativa avaliativa precisa ser iniciada pelo botão próprio.' : 'Atividade sem nota concluída. Você pode rever o vídeo e responder às perguntas novamente.'; reportResult(); notify('complete'); save(); } });
  restart.onclick = () => {
    if (!ready || graded && !finished) return;
    video.pause(); acceptResume = false; finished = false; active = -1; lastSave = -1;
    progress.forEach(p => Object.assign(p,{attempts:0,resolved:'',released:false}));
    $('options').replaceChildren(); $('options').hidden = true; $('answer').hidden = true; $('continue').hidden = true;
    $('question').textContent='Assista ao vídeo'; $('message').textContent=graded?'Nova tentativa avaliativa iniciada.':'Revisão sem nota: as perguntas aparecerão novamente.'; say('');
    video.currentTime=0; $('seek').value='0'; $('clock').textContent='0:00';
    restart.hidden=graded; if(graded)notify('retry'); save(); play();
  };
  $('play').onclick = () => video.paused ? play() : video.pause();
  $('seek').oninput = () => { if (ready) { const requested = Number($('seek').value), due = nextDue(requested); video.currentTime = due < 0 ? requested : time(config.checkpoints[due]); enforce(); } };
  $('answer').onclick = () => {
    if (active < 0 || progress[active].resolved) return;
    const selected = document.querySelector('input[name="answer"]:checked');
    if (!selected) { $('message').textContent = 'Selecione uma alternativa antes de confirmar.'; return; }
    const cp = config.checkpoints[active], state = progress[active], correct = Number(selected.value) === cp.correctIndex;
    state.attempts++;
    if (correct || state.attempts >= cp.maxAttempts) {
      state.resolved = correct ? 'correct' : 'assisted';
      $('answer').hidden = true; $('continue').hidden = false;
      document.querySelectorAll('input[name="answer"]').forEach(n => { n.disabled = true; });
      $('message').textContent = correct ? 'Resposta correta! Você pode continuar.' : 'Tentativas concluídas. Leia a explicação para continuar aprendendo.';
      say(cp.explanation + (!correct ? '\nResposta correta: ' + cp.options[cp.correctIndex] : ''));
      $('continue').focus();
    } else { $('message').textContent = 'Ainda não. Tente outra alternativa. Restam ' + (cp.maxAttempts - state.attempts) + ' tentativas.'; say('Relembre o trecho apresentado e compare as alternativas.'); }
    save();
  };
  $('continue').onclick = () => { if (active < 0 || !progress[active].resolved) return; progress[active].released = true; active = -1; $('options').hidden = true; $('continue').hidden = true; $('question').textContent = 'Continue assistindo'; $('message').textContent = ''; say(''); save(); play(); };
  ['font', 'contrast'].forEach((id, i) => { $(id).onclick = () => { const on = document.body.classList.toggle(i ? 'high' : 'large'); $(id).setAttribute('aria-pressed', String(on)); }; });
  document.addEventListener('visibilitychange', () => { if (document.hidden) { video.pause(); save(); } });
  window.addEventListener('pagehide', () => { stopPauseMonitor(); video.pause(); save(); });
})();
