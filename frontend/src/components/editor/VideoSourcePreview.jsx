import React, {useEffect, useRef, useState} from 'react';
import {videoQuizProviderRuntime} from '../../utils/videoQuizProviders';

// Direct SDK preview in a scoped mount. No author HTML/additional srcdoc.
export default function VideoSourcePreview({source,onDuration}) {
  const scope=useRef(null),media=useRef(null),callback=useRef(onDuration);
  const [duration,setDuration]=useState(0),[time,setTime]=useState(0),[paused,setPaused]=useState(true);
  callback.current=onDuration;
  useEffect(()=>{
    const root=scope.current,v=document.createElement('video');v.id='video';root.appendChild(v);media.current=v;
    setDuration(0);setTime(0);setPaused(true);
    const metadata=()=>{if(Number.isFinite(v.duration)&&v.duration>0){setDuration(v.duration);callback.current(v.duration);}};
    const tick=()=>setTime(v.currentTime),play=()=>setPaused(false),pause=()=>setPaused(true);
    v.addEventListener('loadedmetadata',metadata);v.addEventListener('timeupdate',tick);v.addEventListener('play',play);v.addEventListener('pause',pause);
    const dispose=videoQuizProviderRuntime(root,source);
    return()=>{dispose?.();v.removeEventListener('loadedmetadata',metadata);v.removeEventListener('timeupdate',tick);v.removeEventListener('play',play);v.removeEventListener('pause',pause);root.replaceChildren();media.current=null;};
  },[source.src,source.provider]); // eslint-disable-line react-hooks/exhaustive-deps
  return <div aria-label="Prévia do vídeo externo" className="rounded overflow-hidden bg-slate-950">
    <div ref={scope} className="h-56 flex flex-col" />
    <div className="flex items-center gap-2 p-2"><button type="button" className="rounded border px-3 py-1" disabled={!duration} onClick={()=>{const v=media.current;if(v?.paused)v.play().catch(()=>{});else v?.pause();}}>{paused?'Reproduzir':'Pausar'}</button><input aria-label="Posição da prévia" type="range" className="flex-1 min-w-0" min="0" max={duration} step="0.1" value={time} onChange={e=>{if(media.current)media.current.currentTime=Number(e.target.value);}} /><span className="text-xs">{time.toFixed(1)}s</span></div>
  </div>;
}
