function videoQuizFeedbackLayoutRuntime() {
  'use strict';
  var panel = document.getElementById('panel');
  if (!panel || !document.getElementById('video-quiz-data') || document.getElementById('video-quiz-feedback-style')) return;
  // Move the actual live regions: their listeners, IDs and answer state stay
  // intact. Only the right panel may grow/scroll when a message appears.
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
videoQuizFeedbackLayoutRuntime();
