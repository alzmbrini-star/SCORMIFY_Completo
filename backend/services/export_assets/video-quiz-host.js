/* Bridge for opaque-origin/data: frames in Single Page exports. */
(function () {
  'use strict';
  window.addEventListener('message', function (event) {
    var msg = event.data;
    if (!msg || msg.type !== 'scormify-video-quiz' || !/^[a-f0-9]{20}$/.test(msg.key || '')) return;
    var frame = Array.from(document.querySelectorAll('iframe[data-video-quiz-key]')).find(function (f) { return f.contentWindow === event.source && f.dataset.videoQuizKey === msg.key; });
    if (!frame) return;
    var api = window.SCORM && window.SCORM.api, all = {}, key = 'scormify-video-quiz:' + msg.key;
    try { if (api) all = JSON.parse(api.LMSGetValue('cmi.suspend_data') || '{}'); } catch (_) {}
    if (msg.action === 'restore') {
      var saved = all.videoQuizzes && all.videoQuizzes[msg.key];
      try { if (!api) saved = JSON.parse(localStorage.getItem(key) || 'null'); } catch (_) {}
      frame.contentWindow.postMessage({type: 'scormify-video-quiz-resume', key: msg.key, state: saved}, '*');
    }
    if (msg.action === 'save' && msg.state && Number.isFinite(msg.state.t) && msg.state.t >= 0 && msg.state.t <= 86400 && Array.isArray(msg.state.p) && msg.state.p.length <= 12 && msg.state.p.every(function(p) { return Array.isArray(p) && p.length === 3 && Number.isInteger(p[0]) && p[0] >= 0 && p[0] <= 10 && ['', 'correct', 'assisted'].includes(p[1]) && [0, 1].includes(p[2]); })) {
      try { localStorage.setItem(key, JSON.stringify(msg.state)); } catch (_) {}
      if (api) { all.videoQuizzes = all.videoQuizzes || {}; all.videoQuizzes[msg.key] = msg.state; var text = JSON.stringify(all); if (new TextEncoder().encode(text).length <= 3800) { api.LMSSetValue('cmi.suspend_data', text); api.LMSCommit(''); } }
    }
    if (msg.action === 'complete' && window.SP) window.SP.markClicked(frame.closest('.sp-interactive'));
  });
})();
