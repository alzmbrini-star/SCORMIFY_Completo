import {EDITORIAL_CARDS} from './editorialTextColors';

// Read-only bridge for the existing sandboxed canvas iframe. No new sandbox
// privileges, model/state changes, network, or generated script execution.
export function editorialColorProbeRuntime(cards) {
  let requestId=null,observer=null,timer=null;
  function visible(node){const s=getComputedStyle(node);return s.display!=='none'&&s.visibility!=='hidden'&&node.getClientRects().length>0;}
  function hex(value){const match=value.match(/^rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)(?:\s*,\s*([\d.]+))?\s*\)$/);if(!match||match[4]!==undefined&&Number(match[4])!==1)return null;return '#'+match.slice(1,4).map(n=>Number(n).toString(16).padStart(2,'0')).join('');}
  function background(node){
    for(let n=node;n;n=n.parentElement){const s=getComputedStyle(n);if(s.backgroundImage!=='none')return null;const c=hex(s.backgroundColor);if(c)return c;if(s.backgroundColor!=='transparent'&&!/rgba\([^)]*,\s*0\s*\)/.test(s.backgroundColor))return null;}
    return null;
  }
  function sample(nodes,bg=false){const values=new Set();let complex=false;nodes.slice(0,200).forEach(n=>{const c=bg?background(n):hex(getComputedStyle(n).color);if(c)values.add(c);else complex=true;});return {count:nodes.length,colors:[...values].slice(0,12),complex};}
  function publish(){
    timer=null;if(!requestId)return;
    const cardNodes=[...document.querySelectorAll(cards)].filter(visible);
    const titles=[...document.querySelectorAll('h1,h2,h3,h4,h5,h6')].filter(visible);
    const texts=[...document.querySelectorAll('p,span,label,small,td,th,figcaption,summary,div')].filter(n=>!n.closest(cards)&&!n.closest('h1,h2,h3,h4,h5,h6')&&[...n.childNodes].some(c=>c.nodeType===3&&c.textContent.trim())&&visible(n));
    parent.postMessage({type:'scormify-editorial-color-snapshot',requestId,groups:{title:sample(titles),text:sample(texts),card:sample(cardNodes),cardBackground:sample(cardNodes,true)}},'*');
  }
  function schedule(){if(timer===null)timer=setTimeout(publish,250);}
  addEventListener('message',event=>{
    const m=event.data;if(event.source!==parent||!m||m.type!=='scormify-editorial-color-request'||typeof m.requestId!=='string')return;
    if(m.action==='stop'){requestId=null;if(observer)observer.disconnect();clearTimeout(timer);timer=null;return;}
    requestId=m.requestId.slice(0,100);
    if(!observer)observer=new MutationObserver(schedule);
    observer.observe(document.documentElement,{childList:true,subtree:true,attributes:true,attributeFilter:['style','class','hidden']});
    publish();
  });
  addEventListener('pagehide',()=>{if(observer)observer.disconnect();clearTimeout(timer);});
}

export function withEditorialColorProbe(html) {
  if(typeof html!=='string'||html.includes('id="scormify-editorial-color-probe"'))return html;
  const script='<script id="scormify-editorial-color-probe">('+editorialColorProbeRuntime.toString()+')('+JSON.stringify(EDITORIAL_CARDS)+');</script>';
  return /<\/body>/i.test(html)?html.replace(/<\/body>/i,script+'</body>'):html+script;
}

export function readEditorialColorSnapshot(event,frame,requestId) {
  const m=event.data;
  if(!frame||event.source!==frame.contentWindow||m?.type!=='scormify-editorial-color-snapshot'||m.requestId!==requestId)return null;
  const groups={};
  for(const key of ['title','text','card','cardBackground']){
    const g=m.groups?.[key];
    if(!g||!Number.isInteger(g.count)||g.count<0||!Array.isArray(g.colors)||g.colors.length>12||g.colors.some(c=>!/^#[0-9a-f]{6}$/i.test(c))||typeof g.complex!=='boolean')return null;
    groups[key]={count:g.count,colors:g.colors,complex:g.complex};
  }
  return groups;
}
