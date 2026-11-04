/* Bridge for opaque-origin/data: frames in Single Page exports. */
(function () {
  'use strict';
  var registrations = new WeakMap(), configs = new WeakMap();
  function configFor(element) {
    if (!element || typeof element !== 'object') return null;
    if (element.videoQuizConfig) return element.videoQuizConfig;
    if (configs.has(element)) return configs.get(element);
    var config = null, raw = element.htmlContent || '';
    try {
      if (raw.indexOf('__B64__:') === 0) raw = new TextDecoder().decode(Uint8Array.from(atob(raw.slice(8)), function(c){return c.charCodeAt(0);}));
      var match = /<script\b[^>]*\bid=["']video-quiz-data["'][^>]*>([\s\S]*?)<\/script>/i.exec(raw);
      if (match) config = JSON.parse(match[1]);
    } catch (_) {}
    configs.set(element,config); return config;
  }
  window.VideoQuizHost = {
    configFor:configFor,
    bindFrame:function(frame,element,onResult,onRetry) {
      var config=configFor(element); if(!config)return;
      frame.dataset.videoQuizKey=config.key;
      registrations.set(frame,{config:config,onResult:onResult,onRetry:onRetry});
    }
  };
  window.addEventListener('message', function (event) {
    var msg = event.data;
    if (!msg || msg.type !== 'scormify-video-quiz' || !/^[a-f0-9]{20}$/.test(msg.key || '')) return;
    var frame = Array.from(document.querySelectorAll('iframe[data-video-quiz-key]')).find(function (f) { return f.contentWindow === event.source && f.dataset.videoQuizKey === msg.key; });
    if (!frame) return;
    var entry=registrations.get(frame), config=entry?entry.config:{graded:frame.dataset.videoQuizGraded==='true',checkpoints:new Array(Number(frame.dataset.videoQuizTotal)||0)};
    var api = window.SCORM && window.SCORM.api || window.ScormAPI && typeof window.ScormAPI.getAPI==='function' && window.ScormAPI.getAPI(), all = {}, key = 'scormify-video-quiz:' + msg.key;
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
    if (msg.action === 'result' && config.graded===true && msg.total===config.checkpoints.length && msg.total>0 && Number.isInteger(msg.correct) && msg.correct>=0 && msg.correct<=msg.total && msg.score===Math.round(100*msg.correct/msg.total)) {
      frame.dataset.videoQuizResultReceived='true';
      if(entry&&entry.onResult)entry.onResult(msg.score);
      if(window.SP&&window.SP.recordVideoQuizResult)window.SP.recordVideoQuizResult(msg.key,msg.correct,msg.total);
    }
    if (msg.action === 'retry' && config.graded===true) {
      delete frame.dataset.videoQuizResultReceived;
      if(entry&&entry.onRetry)entry.onRetry();
      if(window.SP&&window.SP.retryVideoQuiz)window.SP.retryVideoQuiz(msg.key);
    }
    if (msg.action === 'complete' && window.SP && (config.graded!==true || frame.dataset.videoQuizResultReceived==='true')) window.SP.markClicked(frame.closest('.sp-interactive'));
  });
})();
