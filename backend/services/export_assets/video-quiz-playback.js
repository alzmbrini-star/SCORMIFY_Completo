function videoQuizPlaybackRuntime() {
  'use strict';
  var video = document.getElementById('video'), button = document.getElementById('play');
  if (!video || !button || !document.getElementById('video-quiz-data') || video.dataset.playbackStatus === 'v1') return;
  video.dataset.playbackStatus = 'v1';
  var status = document.createElement('p');
  status.id = 'video-load-status';
  status.setAttribute('role', 'status');
  status.setAttribute('aria-live', 'polite');
  status.style.cssText = 'margin:5px 0 0;font-size:.875em;color:#c8dcee;flex-shrink:0';
  status.hidden = true;
  var controls = button.closest('.controls');
  (controls || button).insertAdjacentElement('afterend', status);
  var timer = null, waiting = false, lastTime = video.currentTime;
  function clearTimer() { if (timer !== null) clearTimeout(timer); timer = null; }
  function idle() {
    waiting = false; clearTimer(); status.hidden = true; status.textContent = '';
    button.textContent = video.paused || video.ended ? 'Reproduzir' : 'Pausar';
    button.setAttribute('aria-busy', 'false');
    video.removeAttribute('aria-busy');
  }
  function loading() {
    if (video.paused || video.ended) { idle(); return; }
    if (waiting) return;
    waiting = true; button.textContent = 'Carregando vídeo…';
    button.setAttribute('aria-busy', 'true'); video.setAttribute('aria-busy', 'true');
    status.hidden = false; status.textContent = 'Aguardando os dados do vídeo. A reprodução continuará assim que carregar. Clique novamente para pausar.';
    clearTimer();
    timer = setTimeout(function () {
      timer = null;
      if (waiting && !video.paused) status.textContent = 'O carregamento está demorando. Verifique sua conexão; o vídeo continuará quando os dados chegarem. Você pode pausar e tentar novamente.';
    }, 12000);
  }
  video.addEventListener('play', loading);
  video.addEventListener('waiting', loading);
  video.addEventListener('stalled', loading);
  video.addEventListener('seeking', loading);
  video.addEventListener('playing', idle);
  video.addEventListener('pause', idle);
  video.addEventListener('ended', idle);
  video.addEventListener('error', function () {
    idle();
    status.hidden = false;
    status.textContent = 'Não foi possível carregar o vídeo. Verifique a conexão e se o link ainda está disponível.';
  });
  video.addEventListener('timeupdate', function () {
    if (video.currentTime > lastTime && !video.paused && !video.seeking && video.readyState >= 3) idle();
    lastTime = video.currentTime;
  });
  window.addEventListener('pagehide', clearTimer);
  // Restore the real media state, including previews that initialized paused.
  idle();
}
videoQuizPlaybackRuntime();
