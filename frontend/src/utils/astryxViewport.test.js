import {upgradeAstryxViewport,isAgentAstryxLesson} from './astryxViewport';
import {astryxViewportCss,astryxViewportRuntime} from './astryxViewportRuntime';
test('display upgrade is scoped idempotent and preserves authored content',()=>{
 const raw='<html><head></head><body><main data-astryx-lesson="1"><p>Texto &amp; conteúdo</p><script>original()</script></main></body></html>';
 const fixed=upgradeAstryxViewport(raw);expect(fixed).toContain('<p>Texto &amp; conteúdo</p><script>original()</script>');expect(fixed).toContain('id="astryx-viewport-v2"');expect(upgradeAstryxViewport(fixed)).toBe(fixed);
 expect(upgradeAstryxViewport('<body>Quiz</body>')).toBe('<body>Quiz</body>');
 const encoded='__B64__:'+btoa(unescape(encodeURIComponent(raw)));expect(isAgentAstryxLesson(encoded)).toBe(true);
 const upgraded=upgradeAstryxViewport(encoded);expect(isAgentAstryxLesson(upgraded)).toBe(true);expect(upgradeAstryxViewport(upgraded)).toBe(upgraded);
});
test('old display runtime is replaced, leaving authored scripts untouched',()=>{
 const raw='<body><main data-astryx-lesson="1">Texto</main><script>original()</script><script id="astryx-viewport-v1">oldViewport()</script></body>';
 const fixed=upgradeAstryxViewport(raw);expect(fixed).not.toContain('oldViewport()');expect(fixed).toContain('<script>original()</script>');expect(fixed).toContain('id="astryx-viewport-v2"');
});
test('runtime moves original nodes into an accessible reading panel, not recreating them',()=>{
 document.body.innerHTML='<div data-astryx-theme="neutral"><div class="ax-agent"><main data-astryx-lesson="1"><p class="ax-kicker">Módulo</p><div class="ax-grid"><section><h1>Título</h1><div class="ax-copy"><button>Original</button><p>Texto</p></div></section><div class="astryx-card"><figure><img alt="Original"></figure></div></div></main></div></div>';
 const button=document.querySelector('button');let clicked=0;button.onclick=()=>clicked++;
 astryxViewportRuntime(astryxViewportCss);if(document.readyState==='loading')document.dispatchEvent(new Event('DOMContentLoaded'));
 expect(document.querySelector('.ax-reading').contains(button)).toBe(true);button.click();expect(clicked).toBe(1);
 expect(document.querySelector('.ax-reading').tabIndex).toBe(0);expect(document.querySelector('.astryx-card img').alt).toBe('Original');
 astryxViewportRuntime(astryxViewportCss);expect(document.querySelectorAll('.ax-reading').length).toBe(1);
});
