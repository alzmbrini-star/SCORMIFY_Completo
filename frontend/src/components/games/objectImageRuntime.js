// Trusted presentation only: follow the existing SVG transforms, never its rules.
export function objectImageRuntime() {
  function mount() {
    var source=document.getElementById('scormify-simulator-plan')||document.getElementById('scormify-visualization-plan'),data;
    try{data=JSON.parse(source.textContent);}catch(_){return;}
    var scene=data.visual||data,rows=scene.illustrations||[],ns='http://www.w3.org/2000/svg';
    if(data.artworkNotice){var warning=document.createElement('p');warning.setAttribute('role','status');warning.textContent=data.artworkNotice;var aside=document.querySelector('aside');if(aside)aside.appendChild(warning);}
    rows.slice(0,4).forEach(function(row){
      if(!row||!/^[a-z][a-z0-9_]{0,31}$/.test(row.node)||typeof row.src!=='string'||row.src.length>334000||!/^data:image\/png;base64,[A-Za-z0-9+/=]+$/.test(row.src))return;
      var base=scene.nodes.find(function(n){return n.id===row.node;}),a=base&&base.attrs;
      var target=document.querySelector('[data-visual-node="'+row.node+'"]');
      if(!target&&base){var group=Array.from(document.querySelectorAll('#scene > g[role="button"]')).find(function(g){return g.getAttribute('aria-label')===base.label;});target=group&&group.firstElementChild;}
      if(!target)return;
      var image=document.createElementNS(ns,'image');
      if(!a)return;
      var box;
      if(base.type==='circle'||base.type==='ellipse'){var rx=a.r||a.rx,ry=a.r||a.ry;box=[a.x-rx,a.y-ry,rx*2,ry*2];}
      else if(base.type==='rect')box=[a.x||0,a.y||0,a.width,a.height];
      else if(base.type==='polygon'){var xs=a.points.map(function(p){return p[0];}),ys=a.points.map(function(p){return p[1];});box=[Math.min.apply(Math,xs),Math.min.apply(Math,ys),Math.max.apply(Math,xs)-Math.min.apply(Math,xs),Math.max.apply(Math,ys)-Math.min.apply(Math,ys)];}
      if(!box)return;
      image.setAttribute('preserveAspectRatio','xMidYMid meet');image.setAttribute('pointer-events','none');image.setAttribute('aria-hidden','true');
      function sync(){
        var x=Number(target.getAttribute(base.type==='circle'||base.type==='ellipse'?'cx':'x')),y=Number(target.getAttribute(base.type==='circle'||base.type==='ellipse'?'cy':'y'));
        image.setAttribute('x',box[0]+(Number.isFinite(x)?x-(a.x||0):0));image.setAttribute('y',box[1]+(Number.isFinite(y)?y-(a.y||0):0));
        image.setAttribute('width',box[2]);image.setAttribute('height',box[3]);image.setAttribute('transform',target.getAttribute('transform')||'');
        image.style.display=target.style.display;image.setAttribute('opacity',target.getAttribute('opacity')||'1');
      }
      var observer=new MutationObserver(sync);
      var oldFillOpacity=target.style.fillOpacity,oldStrokeOpacity=target.style.strokeOpacity;
      // Keep the original hit target, keyboard focus and tooltip alive.
      image.addEventListener('load',function(){target.style.fillOpacity='0';target.style.strokeOpacity='0';sync();observer.observe(target,{attributes:true,attributeFilter:['transform','x','y','cx','cy','opacity','style']});},{once:true});
      image.addEventListener('error',function(){observer.disconnect();target.style.fillOpacity=oldFillOpacity;target.style.strokeOpacity=oldStrokeOpacity;image.remove();},{once:true});
      target.after(image);sync();image.setAttribute('href',row.src);
      window.addEventListener('pagehide',function(){observer.disconnect();},{once:true});
    });
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',mount,{once:true});else mount();
}
