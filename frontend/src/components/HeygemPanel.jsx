import React, { useEffect, useRef, useState } from 'react';
import { getApiUrl } from '../utils/apiUrl';
import { authHeaders } from '../contexts/AuthContext';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Textarea } from './ui/textarea';

const API=getApiUrl();
export async function heygemRequest(path,body) {
  const res=await fetch(`${API}/api/heygem${path}`,{method:body?'POST':'GET',
    headers:authHeaders(body?{'Content-Type':'application/json'}:{}),...(body?{body:JSON.stringify(body)}:{})});
  const data=await res.json();
  if(!res.ok)throw new Error(typeof data.detail==='string'?data.detail:'Não foi possível consultar o HeyGem.');
  return data;
}
export function HeygemPanel({onUseVideo,initialScript='',title='Avatar HeyGem'}) {
  const [config,setConfig]=useState(null),[avatars,setAvatars]=useState([]),[items,setItems]=useState([]);
  const [avatar,setAvatar]=useState(''),[voice,setVoice]=useState(''),[script,setScript]=useState(initialScript.slice(0,1000));
  const [consent,setConsent]=useState(false),[job,setJob]=useState(null),[busy,setBusy]=useState(false),[error,setError]=useState('');
  const requestId=useRef(null),mounted=useRef(true);
  const load=async()=>{
    setError('');
    try {
      const c=await heygemRequest('/config');if(!mounted.current)return;setConfig(c);
      const list=await heygemRequest('/videos');if(mounted.current)setItems(list.videos||[]);
      if(c.configured){const a=await heygemRequest('/avatars');if(mounted.current)setAvatars(a.avatars||[]);}
    }catch(e){if(mounted.current)setError(e.message);}
  };
  useEffect(()=>{mounted.current=true;load();return()=>{mounted.current=false;};},[]); // eslint-disable-line react-hooks/exhaustive-deps
  const refresh=async id=>{
    try{const next=await heygemRequest('/jobs/'+id);if(mounted.current){setJob(next);setItems(old=>[next,...old.filter(i=>i.video_id!==id)]);}}
    catch(e){if(mounted.current)setError(e.message);}
  };
  useEffect(()=>{
    if(!job||['completed','failed'].includes(job.status))return;
    const timer=setTimeout(()=>refresh(job.video_id),8000);return()=>clearTimeout(timer);
  },[job]); // eslint-disable-line react-hooks/exhaustive-deps
  const generate=async()=>{
    if(busy)return;setBusy(true);setError('');
    const fingerprint=JSON.stringify([avatar,voice,script]);
    if(job?.status==='failed'||!requestId.current||requestId.current.fingerprint!==fingerprint)requestId.current={fingerprint,id:crypto.randomUUID()};
    try{const next=await heygemRequest('/jobs',{avatar_id:avatar,voice_id:voice,script,title,consent,request_id:requestId.current.id});
      if(mounted.current){setJob(next);setItems(old=>[next,...old.filter(i=>i.video_id!==next.video_id)]);}}
    catch(e){if(mounted.current)setError(e.message);}finally{if(mounted.current)setBusy(false);}
  };
  const active=busy||job&&!['completed','failed'].includes(job.status);
  const names={preparing:'Preparando áudio PT-BR',submitting:'Enviando ao servidor GPU',processing:'Processando no HeyGem',
    unknown:'Envio ainda não confirmado — atualize a mesma tarefa',completed:'Concluído e armazenado',failed:'Falhou'};
  const handleUseVideo=row=>onUseVideo(row.video_url.startsWith('/')?API+row.video_url:row.video_url,row);
  return <section className="space-y-3 text-sm" data-testid="heygem-panel">
    <p>HeyGem / Duix.Avatar — provedor independente do HeyGen. Esta fase usa vídeo-base autorizado cadastrado no servidor GPU e voz ElevenLabs em português brasileiro.</p>
    {!config?<p role="status">Consultando configuração...</p>:<p role="status" className="rounded border p-3">{config.message} {!config.ttsReady&&' A voz requer ElevenLabs configurado.'}</p>}
    {error&&<p role="alert" className="rounded border border-red-500 p-3 text-red-300">{error}</p>}
    <Button type="button" variant="outline" onClick={load}>Atualizar configuração e biblioteca HeyGem</Button>
    <label className="block">Avatar HeyGem
      <select aria-label="Avatar HeyGem" className="mt-1 w-full rounded border border-slate-500 bg-slate-900 p-2 text-white"
        value={avatar} disabled={active||!config?.configured} onChange={e=>setAvatar(e.target.value)}>
        <option value="">Selecione um avatar cadastrado</option>{avatars.map(a=><option key={a.id} value={a.id}>{a.name}</option>)}
      </select>
    </label>
    <label className="block">ID da voz ElevenLabs — PT-BR<Input value={voice} disabled={active} maxLength={100} onChange={e=>setVoice(e.target.value)} placeholder="ID de voz da conta ElevenLabs configurada" /></label>
    <label className="block">Roteiro falado em português brasileiro<Textarea value={script} disabled={active} maxLength={1000} rows={5} onChange={e=>setScript(e.target.value)} /></label>
    <p>{script.length}/1000 caracteres. Consome créditos ElevenLabs e processamento GPU; não usa créditos HeyGen. Fundo transparente não garantido nesta fase.</p>
    <label className="flex gap-2"><input type="checkbox" checked={consent} disabled={active} onChange={e=>setConsent(e.target.checked)} />Tenho autorização para usar a imagem e a voz selecionadas.</label>
    <Button type="button" onClick={generate} disabled={active||!config?.configured||!config?.ttsReady||!avatar||!voice.trim()||!script.trim()||!consent} data-testid="heygem-generate">{active?'Acompanhar tarefa abaixo':job?.status==='failed'?'Nova tentativa HeyGem (usa créditos)':'Gerar vídeo HeyGem'}</Button>
    {job&&<div role="status" className="rounded border p-3"><strong>{names[job.status]||job.status}</strong>{job.error&&<p>{job.error}</p>}
      <Button type="button" variant="outline" onClick={()=>refresh(job.video_id)}>Atualizar tarefa existente</Button>
      <p className="text-xs">Fechar a janela não insere o vídeo no slide. Reabra a biblioteca para acompanhar. Atualizar não gera outro vídeo.</p>
    </div>}
    <h3 className="font-semibold">Biblioteca HeyGem — meus vídeos</h3>
    {!items.length&&<p>Nenhum vídeo HeyGem gerado por este usuário.</p>}
    <div className="max-h-80 space-y-3 overflow-y-auto">{items.map(row=><article key={row.video_id} className="rounded border border-slate-600 p-3">
      <strong>{row.title}</strong><p>{names[row.status]||row.status}</p>
      {row.status==='completed'&&row.video_url?<><video src={row.video_url.startsWith('/')?API+row.video_url:row.video_url} controls preload="metadata" className="my-2 max-h-56 w-full" />
        <Button type="button" onClick={()=>handleUseVideo(row)}>Usar este vídeo HeyGem</Button></>:<Button type="button" variant="outline" onClick={()=>refresh(row.video_id)}>Atualizar</Button>}
    </article>)}</div>
    <p className="text-xs">Depois de inserir no Editor, use Perguntas durante o vídeo para criar pausas e revisar os tempos. Esta fase não cria pausas automaticamente. Gere e revise o vídeo antes de confirmar a Mídia no Agente.</p>
  </section>;
}
