function videoQuizMobileControlsRuntime() {
  'use strict';
  if (!document.getElementById('video-quiz-data') || document.getElementById('video-quiz-mobile-controls-style')) return;
  var style = document.createElement('style');
  style.id = 'video-quiz-mobile-controls-style';
  style.textContent = `
@media(max-width:650px){
  body{gap:8px}
  header{display:grid;grid-template-columns:minmax(0,1fr) auto auto;align-items:center;gap:6px;padding:6px 8px!important}
  header h1{flex-basis:auto;font-size:18px;line-height:1.2;margin:0;overflow-wrap:anywhere}
  header #font,header #contrast{min-height:44px;padding:6px 8px;font-size:14px}
  main{grid-template-rows:auto minmax(180px,1fr);min-height:0}
  .avatar{padding:6px;min-height:0}
  .avatar #video,.avatar #hosted-video{flex:none!important;aspect-ratio:16/9;width:100%;height:auto;min-height:0;max-height:44svh;object-fit:contain}
  .avatar #hosted-video iframe{min-height:0!important}
  .avatar .controls{display:flex;flex-wrap:nowrap;align-items:center;gap:6px;height:52px;min-height:52px;flex:0 0 52px;padding:4px 6px!important}
  .controls #play,.controls #restart-video-quiz{position:relative;flex:0 0 44px;width:44px;height:44px;min-width:44px;min-height:44px;padding:0!important;font-size:0!important;overflow:hidden}
  .controls #play::before,.controls #restart-video-quiz::before{content:'';display:block;width:22px;height:22px;margin:auto;background:center/contain no-repeat}
  .controls #play::before{background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath fill='white' d='M8 5v14l11-7z'/%3E%3C/svg%3E")}
  .controls #play[data-transport-state=playing]::before{background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath fill='white' d='M6 5h4v14H6zm8 0h4v14h-4z'/%3E%3C/svg%3E")}
  .controls #play[data-transport-state=loading]::before{background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath fill='none' stroke='white' stroke-width='2' d='M20 12a8 8 0 1 1-8-8'/%3E%3C/svg%3E");animation:vq-control-spin 1s linear infinite}
  .controls #restart-video-quiz::before{background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath fill='none' stroke='white' stroke-width='2' stroke-linecap='round' stroke-linejoin='round' d='M3 10a9 9 0 1 1 0 5M3 4v6h6'/%3E%3C/svg%3E")}
  .controls #seek{flex:1 1 0;min-width:24px;width:0;height:44px;margin:0;touch-action:pan-y}
  .controls #clock{flex:0 0 auto;white-space:nowrap;font:13px/1.2 ui-monospace,monospace;font-variant-numeric:tabular-nums}
  body.large header h1{font-size:20px}
}
@media(max-width:650px) and (orientation:landscape){
  main{grid-template-columns:minmax(0,1.4fr) minmax(0,1fr);grid-template-rows:minmax(180px,1fr)}
  .avatar #video,.avatar #hosted-video{flex:1!important;min-height:0;max-height:none;aspect-ratio:auto;height:100%}
}
@keyframes vq-control-spin{to{transform:rotate(360deg)}}
@media(prefers-reduced-motion:reduce){.controls #play[data-transport-state=loading]::before{animation:none}}
`;
  document.head.appendChild(style);
  function sync() {
    ['play','restart-video-quiz'].forEach(function(id) {
      var button = document.getElementById(id);
      if (!button) return;
      var label = button.textContent.trim();
      button.setAttribute('aria-label', label);
      button.setAttribute('title', label);
      if (id === 'play') button.dataset.transportState = button.getAttribute('aria-busy') === 'true' ? 'loading' : label === 'Pausar' ? 'playing' : 'paused';
    });
  }
  sync();
  var controls = document.querySelector('.controls');
  if (controls) {
    var observer = new MutationObserver(sync);
    observer.observe(controls, {subtree:true,childList:true,characterData:true,attributes:true,attributeFilter:['aria-busy']});
    window.addEventListener('pagehide',function(){observer.disconnect();},{once:true});
  }
}
videoQuizMobileControlsRuntime();
