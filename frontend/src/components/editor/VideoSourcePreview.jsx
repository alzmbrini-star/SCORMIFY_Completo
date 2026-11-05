import React, {useEffect, useMemo, useRef} from 'react';
import {videoQuizProviderRuntime} from '../../utils/videoQuizProviders';

// Uses the same provider adapter as the exported activity, without questions,
// grading, storage or changes to the author's draft.
export default function VideoSourcePreview({source,onDuration}) {
  const frame=useRef(null),callback=useRef(onDuration);callback.current=onDuration;
  useEffect(()=>{
    const receive=e=>{if(e.source===frame.current?.contentWindow&&e.data?.type==='video-quiz-source-duration'&&Number.isFinite(e.data.duration)&&e.data.duration>0&&e.data.duration<=86400)callback.current(e.data.duration);};
    window.addEventListener('message',receive);return()=>window.removeEventListener('message',receive);
  },[]);
  const doc=useMemo(()=>{
    const config=JSON.stringify(source).replace(/</g,'\\u003c');
    return '<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><style>*{box-sizing:border-box}html,body{margin:0;height:100%;background:#0d1728;color:white;font:14px system-ui}body{display:flex;flex-direction:column}video{width:100%;flex:1;min-height:0}.controls{display:flex;gap:8px;padding:6px}button{background:#22587c;color:white;border:1px solid #79aec5;padding:7px;border-radius:6px}input{flex:1;min-width:0}</style></head><body><video id="video"></video><div class="controls"><button id="play">Reproduzir</button><input id="seek" type="range" min="0" max="0" step="0.1" value="0" aria-label="Posição do vídeo"></div><script id="video-quiz-data" type="application/json">'+config+'</script><script>('+videoQuizProviderRuntime.toString()+')();</script><script>(function(){var v=document.getElementById("video"),b=document.getElementById("play"),s=document.getElementById("seek");v.addEventListener("loadedmetadata",function(){s.max=v.duration;parent.postMessage({type:"video-quiz-source-duration",duration:v.duration},"*");});v.addEventListener("timeupdate",function(){s.value=v.currentTime;});v.addEventListener("play",function(){b.textContent="Pausar";});v.addEventListener("pause",function(){b.textContent="Reproduzir";});b.onclick=function(){if(v.paused)v.play().catch(function(){});else v.pause();};s.oninput=function(){v.currentTime=Number(s.value);};})();</script></body></html>';
  },[source.src,source.provider]); // eslint-disable-line react-hooks/exhaustive-deps
  return <iframe ref={frame} title="Prévia do vídeo externo" srcDoc={doc} sandbox="allow-scripts allow-same-origin" allow="autoplay; fullscreen; encrypted-media; picture-in-picture" className="w-full h-64 border-0 rounded" />;
}
