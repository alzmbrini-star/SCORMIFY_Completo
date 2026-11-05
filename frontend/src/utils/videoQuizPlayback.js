// Presentation-only upgrade: never changes questions, answers or LMS status.
export function videoQuizPlaybackRuntime() {
  'use strict';
  var video = document.getElementById('video'), button = document.getElementById('play');
  if (!video || !button || !document.getElementById('video-quiz-data') || video.dataset.playbackStatus === 'v2') return;
  video.dataset.playbackStatus = 'v2';
  var settings = {};
  try { settings = JSON.parse(document.getElementById('video-quiz-data').textContent); } catch (_) {}
  if (settings.preserveTransparency !== false) {
    var alphaStyle = document.createElement('style');
    alphaStyle.id = 'video-quiz-alpha-style';
    alphaStyle.textContent = 'html,body{background:transparent!important}.avatar,#video{background:transparent!important}.avatar{border-color:#7895ac80}header,.controls,footer{background:rgba(13,23,40,.94);border-radius:8px;padding:6px 10px}#video-load-status{background:rgba(13,23,40,.94);padding:5px 8px;border-radius:6px}';
    document.head.appendChild(alphaStyle);
    video.dataset.preserveTransparency = 'true';
  }
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

export function videoQuizFeedbackLayoutRuntime() {
  'use strict';
  var panel = document.getElementById('panel');
  if (!panel || !document.getElementById('video-quiz-data') || document.getElementById('video-quiz-feedback-style')) return;
  var feedback = document.getElementById('feedback');
  var message = document.getElementById('message');
  if (feedback) {
    if (message && message.parentNode === panel) message.insertAdjacentElement('afterend', feedback);
    else panel.appendChild(feedback);
  }
  var loading = document.getElementById('video-load-status');
  if (loading) panel.appendChild(loading);
  var style = document.createElement('style');
  style.id = 'video-quiz-feedback-style';
  style.textContent = '#panel #feedback{max-height:none;overflow:visible;overflow-wrap:anywhere;margin:10px 0;padding:12px}#panel #video-load-status{overflow-wrap:anywhere;margin:10px 0}#panel #message{overflow-wrap:anywhere}';
  document.head.appendChild(style);
}

export function upgradeVideoQuizPlayback(html) {
  if (typeof html !== 'string' || !/id=["']video-quiz-data["']/.test(html)) return html;
  if (!html.includes('id="video-quiz-playback-v2"')) {
  html = html.replace(/<script\b[^>]*\bid=["']video-quiz-playback-v1["'][^>]*>[\s\S]*?<\/script>/gi, '');
  const snippet = '<script id="video-quiz-playback-v2">(' + videoQuizPlaybackRuntime.toString() + ')();</script>';
  html = /<\/body>/i.test(html) ? html.replace(/<\/body>/i, snippet + '</body>') : html + snippet;
  }
  if (!html.includes('id="video-quiz-feedback-v1"')) {
    const layout = '<script id="video-quiz-feedback-v1">(' + videoQuizFeedbackLayoutRuntime.toString() + ')();</script>';
    html = /<\/body>/i.test(html) ? html.replace(/<\/body>/i, layout + '</body>') : html + layout;
  }
  return html;
}
