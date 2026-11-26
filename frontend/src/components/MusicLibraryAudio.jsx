import React,{useEffect,useRef,useState} from 'react';
import {Button} from './ui/button';
import {getApiUrl} from '../utils/apiUrl';
import {authHeaders} from '../contexts/AuthContext';

export default function MusicLibraryAudio({item,onUseAudio}){
 const [src,setSrc]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState('');
 const blob=useRef(null),url=useRef(''),inFlight=useRef(false);
 useEffect(()=>()=>{if(url.current)URL.revokeObjectURL(url.current);},[]);
 const act=async use=>{
  if(inFlight.current)return;inFlight.current=true;setBusy(true);setError('');
  try{
   if(!blob.current){
    const res=await fetch(getApiUrl()+item.audio_url,{headers:authHeaders()});
    if(!res.ok)throw new Error('Não foi possível carregar o áudio salvo. Nenhuma geração foi solicitada.');
    blob.current=await res.blob();url.current=URL.createObjectURL(blob.current);setSrc(url.current);
   }
   if(use&&onUseAudio)await onUseAudio(new File([blob.current],'scormify-musica.mp3',{type:'audio/mpeg'}));
  }catch(e){setError(e.message);}finally{inFlight.current=false;setBusy(false);}
 };
 return <div className="space-y-2 border-t p-3" onClick={e=>e.stopPropagation()}>
  {error&&<p role="alert" className="text-sm text-red-500">{error}</p>}
  <div className="flex gap-2 flex-wrap"><Button size="sm" variant="outline" disabled={busy} onClick={()=>act(false)}>Ouvir áudio</Button>
   {src&&<a href={src} download="scormify-musica.mp3" className="text-sm underline p-2">Baixar MP3</a>}
   {onUseAudio&&<Button size="sm" disabled={busy} onClick={()=>act(true)}>Inserir áudio…</Button>}
  </div>
  {src&&<audio src={src} controls preload="metadata" className="w-full"/>}
 </div>;
}
