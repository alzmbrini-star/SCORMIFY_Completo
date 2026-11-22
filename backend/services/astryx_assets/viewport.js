export const astryxViewportCss = String.raw`
html.ax-viewport-document,body.ax-viewport-document{height:100%!important;min-height:0!important;max-height:100%!important;overflow:hidden!important}
body.ax-viewport-document>[data-astryx-theme],body.ax-viewport-document>[data-astryx-theme]>.ax-agent{height:100%!important;min-height:0!important;overflow:hidden!important}
.ax-agent .ax-page.ax-viewport{height:100%!important;min-height:0!important;max-height:100%!important;display:flex!important;flex-direction:column;overflow:hidden!important;padding:clamp(12px,3vh,32px) clamp(20px,4vw,64px)!important;box-sizing:border-box}
.ax-viewport>.ax-kicker{flex-shrink:0;margin:0 0 12px!important;max-height:18%;overflow:auto}
.ax-viewport>.ax-grid{flex:1;min-height:0!important;height:auto!important;max-height:100%;align-items:stretch!important;grid-auto-rows:minmax(0,1fr);overflow:hidden}
.ax-viewport-text{display:flex!important;flex-direction:column;min-height:0!important;max-height:100%;overflow:hidden!important}
.ax-viewport-text>h1,.ax-viewport-text>h2{flex-shrink:0;font-size:clamp(24px,3vw,42px)!important;line-height:1.15!important;max-height:44%;overflow:auto;margin:0 0 10px!important;overflow-wrap:break-word}
.ax-viewport-text>.ax-rule{flex-shrink:0;margin:6px 0 12px!important}
.ax-reading{flex:1;min-height:0!important;overflow:auto!important;overscroll-behavior:contain;scrollbar-gutter:stable;padding-right:10px;overflow-wrap:break-word}
.ax-reading:focus-visible{outline:3px solid var(--ax-accent,#315ad1);outline-offset:-3px}
.ax-viewport>.ax-viewport-text{flex:1}
.ax-viewport>.ax-grid>.astryx-card{display:flex;flex-direction:column;min-height:0!important;height:100%;max-height:100%;align-self:stretch;overflow:hidden!important;background:transparent!important;border:0!important;box-shadow:none!important;padding:0!important}
.ax-viewport>.ax-grid>.astryx-card>figure{display:flex;flex-direction:column;align-items:center;justify-content:center;flex:1;min-height:0;height:100%;margin:0;background:transparent}
.ax-viewport>.ax-grid>.astryx-card img{display:block;flex:1 1 0;min-height:0;width:100%!important;height:100%!important;max-height:100%!important;object-fit:contain!important}
.ax-viewport>.ax-grid>.astryx-card figcaption{flex-shrink:0;max-height:25%;overflow:auto}
.ax-picture{flex:none;max-width:100%;max-height:100%;overflow:hidden;box-shadow:0 6px 18px #0002}
.ax-viewport>.ax-grid>.astryx-card .ax-picture img{width:100%!important;height:100%!important;max-height:none!important;margin:0!important;border-radius:0!important;object-fit:contain!important}
@media(max-width:700px){.ax-agent .ax-page.ax-viewport{padding:12px 16px!important}.ax-viewport>.ax-grid{grid-template-columns:minmax(0,1fr)!important;grid-template-rows:minmax(0,1fr) minmax(0,.45fr);gap:12px!important}.ax-viewport-text>h1,.ax-viewport-text>h2{font-size:clamp(22px,6vw,30px)!important}.ax-viewport>.ax-kicker{font-size:12px;margin-bottom:8px!important}}
`;

export function astryxViewportRuntime(cssText) {
  function mount() {
    var main=document.querySelector('.ax-agent main[data-astryx-lesson]');
    if(!main||main.classList.contains('ax-viewport'))return;
    if(!document.getElementById('astryx-viewport-style')){
      var style=document.createElement('style');style.id='astryx-viewport-style';
      style.textContent=cssText||'';document.head.appendChild(style);
    }
    document.documentElement.classList.add('ax-viewport-document');
    document.body.classList.add('ax-viewport-document');main.classList.add('ax-viewport');
    var grid=Array.from(main.children).find(function(n){return n.classList.contains('ax-grid');});
    var text=grid&&grid.querySelector(':scope>section');
    if(!text){
      text=document.createElement('section');main.appendChild(text);
      Array.from(main.childNodes).forEach(function(n){
        if(n!==text&&!(n.nodeType===1&&n.classList.contains('ax-kicker')))text.appendChild(n);
      });
    }
    text.classList.add('ax-viewport-text');
    var reading=document.createElement('div');reading.className='ax-reading';
    reading.tabIndex=0;reading.setAttribute('role','region');reading.setAttribute('aria-label','Conteúdo do slide — use as setas para rolar');
    Array.from(text.children).forEach(function(n){if(n.classList.contains('ax-copy'))reading.appendChild(n);});
    // Source figures appended after generation also stay in the reading flow.
    if(grid)Array.from(main.children).forEach(function(n){if(n!==grid&&n.classList.contains('ax-copy'))reading.appendChild(n);});
    if(reading.childNodes.length)text.appendChild(reading);
    Array.from(text.children).forEach(function(n){if(/^H[12]$/.test(n.tagName))n.tabIndex=0;});
    var figure=grid&&grid.querySelector(':scope>.astryx-card>figure');
    var image=figure&&figure.querySelector('img');
    if(image){
      var picture=document.createElement('div');picture.className='ax-picture';
      picture.style.borderRadius=getComputedStyle(figure.parentElement).borderRadius;
      image.parentNode.insertBefore(picture,image);picture.appendChild(image);
      function fit(){
        if(!image.naturalWidth||!image.naturalHeight)return;
        var caption=figure.querySelector('figcaption'),extra=0;
        if(caption&&getComputedStyle(caption).display!=='none'){
          var cs=getComputedStyle(caption);extra=caption.offsetHeight+(parseFloat(cs.marginTop)||0)+(parseFloat(cs.marginBottom)||0);
        }
        var width=figure.clientWidth,height=Math.max(0,figure.clientHeight-extra);
        var scale=Math.min(width/image.naturalWidth,height/image.naturalHeight);
        if(!scale)return;
        var w=(image.naturalWidth*scale).toFixed(2)+'px',h=(image.naturalHeight*scale).toFixed(2)+'px';
        if(picture.style.width!==w)picture.style.width=w;if(picture.style.height!==h)picture.style.height=h;
      }
      image.addEventListener('load',fit);window.addEventListener('resize',fit);
      if(typeof ResizeObserver!=='undefined')new ResizeObserver(fit).observe(figure);
      fit();
    }
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',mount,{once:true});else mount();
}

