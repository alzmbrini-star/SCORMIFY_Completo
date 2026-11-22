import {astryxViewportCss,astryxViewportRuntime} from './astryxViewportRuntime';
export function isAgentAstryxLesson(source) {
  if(typeof source!=='string')return false;
  if(source.startsWith('__B64__:')){try{source=atob(source.slice(8));}catch(_){return false;}}
  return /data-astryx-lesson=["']/.test(source);
}
export function upgradeAstryxViewport(source) {
  if(typeof source!=='string')return source;
  if(source.startsWith('__B64__:')){
    try{
      const raw=decodeURIComponent(Array.from(atob(source.slice(8)),c=>'%'+c.charCodeAt(0).toString(16).padStart(2,'0')).join(''));
      const fixed=upgradeAstryxViewport(raw);
      return fixed===raw?source:'__B64__:'+btoa(unescape(encodeURIComponent(fixed)));
    }catch(_){return source;}
  }
  if(!/data-astryx-lesson=["']/.test(source)||source.includes('id="astryx-viewport-v2"'))return source;
  source=source.replace(/<script id="astryx-viewport-v1">[\s\S]*?<\/script>/gi,'');
  const snippet='<script id="astryx-viewport-v2">('+astryxViewportRuntime.toString()+')('+JSON.stringify(astryxViewportCss)+');</script>';
  return /<\/body\s*>/i.test(source)?source.replace(/<\/body\s*>/i,m=>snippet+m):source+snippet;
}
