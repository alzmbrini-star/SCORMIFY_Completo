import React,{useEffect,useRef,useState} from 'react';
import {Dialog,DialogContent,DialogHeader,DialogTitle,DialogDescription} from './ui/dialog';
import {Button} from './ui/button';
import {getApiUrl} from '../utils/apiUrl';
import {authHeaders} from '../contexts/AuthContext';

const API=getApiUrl();
const initial={title:'',mode:'instrumental',theme:'',style:'Inspiradora, leve e acolhedora',duration:60,lyrics:''};
const labels={quoted:'Orçamento calculado',approved:'Orçamento aprovado',generating:'Gerando música',ready:'Pronta para ouvir',unknown:'Geração não confirmada'};
const money=(n,currency='BRL')=>new Intl.NumberFormat('pt-BR',{style:'currency',currency}).format(n);
export async function musicRequest(path,method='GET',body){
 const res=await fetch(API+'/api'+path,{method,headers:authHeaders(body?{'Content-Type':'application/json'}:{}),...(body?{body:JSON.stringify(body)}:{})});
 const data=await res.json();if(!res.ok)throw new Error(typeof data.detail==='string'?data.detail:'Revise os campos e tente novamente.');return data;
}

export default function MusicStudioDialog({open,onOpenChange,sourceProjectId=null,onUseAudio}){
 const [spec,setSpec]=useState(initial),[job,setJob]=useState(null),[history,setHistory]=useState([]),[config,setConfig]=useState(null);
 const [busy,setBusy]=useState(false),[error,setError]=useState(''),[consent,setConsent]=useState(false),[limit,setLimit]=useState('');
 const [preview,setPreview]=useState('');
 const guard=useRef(false),requestId=useRef(null),blobRef=useRef(null),previewRef=useRef('');
 const clearPreview=()=>{if(previewRef.current)URL.revokeObjectURL(previewRef.current);previewRef.current='';blobRef.current=null;setPreview('');};
 const accept=data=>{setJob(data);setConsent(false);setLimit((data.approval?.ceilingBrl??Math.ceil(data.quote.estimatedBrl*120)/100).toFixed(2));};
 const act=async fn=>{if(guard.current)return;guard.current=true;setBusy(true);setError('');try{return await fn();}catch(e){setError(e.message);}finally{guard.current=false;setBusy(false);}};
 useEffect(()=>{
  if(!open)return;let active=true;
  musicRequest('/music/config').then(d=>{if(active)setConfig(d);}).catch(e=>{if(active)setError(e.message);});
  musicRequest('/music').then(d=>{if(active)setHistory(d.music||[]);}).catch(e=>{if(active)setError(e.message);});
  return()=>{active=false;};
 },[open]);
 useEffect(()=>{
  if(!open||job?.status!=='generating')return;let active=true;
  const timer=setInterval(()=>musicRequest('/music/'+job.id).then(d=>{if(active)setJob(d);}).catch(e=>{if(active)setError('Consulta interrompida. Atualize o status; não clique em gerar novamente.');}),5000);
  return()=>{active=false;clearInterval(timer);};
 },[open,job?.id,job?.status]);
 useEffect(()=>{if(!open)clearPreview();return()=>{};},[open]); // no auto playback
 useEffect(()=>()=>{if(previewRef.current)URL.revokeObjectURL(previewRef.current);},[]);
 const change=values=>{setSpec(old=>({...old,...values}));setJob(null);requestId.current=null;setConsent(false);clearPreview();};
 const estimate=()=>act(async()=>{
  if(job){requestId.current=null;setJob(null);setConsent(false);clearPreview();}
  if(!requestId.current)requestId.current=crypto.randomUUID();
  accept(await musicRequest('/music/quotes','POST',{spec,sourceProjectId,requestId:requestId.current}));
 });
 async function loadAudio(){
  if(blobRef.current)return blobRef.current;
  const res=await fetch(API+job.audioUrl,{headers:authHeaders()});
  if(!res.ok)throw new Error('Não foi possível carregar o áudio salvo. Nenhuma nova música foi solicitada.');
  const blob=await res.blob();blobRef.current=blob;previewRef.current=URL.createObjectURL(blob);setPreview(previewRef.current);return blob;
 }
 const field='w-full rounded border border-slate-600 bg-slate-900 p-2 text-white';
 const valid=spec.title.trim().length>=3&&spec.theme.trim().length>=10&&spec.style.trim().length>=3;
 const q=job?.quote;
 const active=job?.status==='generating';
 return <Dialog open={open} onOpenChange={onOpenChange}><DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto bg-slate-950 text-white border-slate-700">
  <DialogHeader><DialogTitle>Gerador de músicas · ElevenLabs</DialogTitle><DialogDescription className="text-slate-300">Trilhas instrumentais e músicas educativas em PT-BR, de 15 segundos a 5 minutos. Biblioteca independente: nenhum curso é alterado automaticamente.</DialogDescription></DialogHeader>
  {error&&<p role="alert" className="rounded bg-red-950 p-3 text-red-100">{error}</p>}
  {config&&!config.configured&&<p role="alert">Configure ELEVENLABS_API_KEY no servidor. O plano e a chave precisam permitir Eleven Music.</p>}
  <fieldset disabled={busy||active} className="space-y-3 min-w-0">
   <label className="block">Título<input aria-label="Título da música" maxLength={160} className={field} value={spec.title} onChange={e=>change({title:e.target.value})}/></label>
   <div className="grid gap-3 sm:grid-cols-2">
    <label>Tipo<select aria-label="Tipo de música" className={field} value={spec.mode} onChange={e=>change({mode:e.target.value,lyrics:''})}><option value="instrumental">Trilha instrumental — sem voz</option><option value="educational">Música educativa cantada · PT-BR</option></select></label>
    <label>Duração<select aria-label="Duração da música" className={field} value={spec.duration} onChange={e=>change({duration:Number(e.target.value)})}>{[15,30,60,90,120,180,240,300].map(n=><option key={n} value={n}>{n} segundos</option>)}</select></label>
   </div>
   <label className="block">Tema e objetivos<textarea aria-label="Tema da música" rows={3} maxLength={800} className={field} value={spec.theme} onChange={e=>change({theme:e.target.value})} placeholder="Ex.: colaboração no trabalho, comunicação e respeito às diferenças."/></label>
   <label className="block">Estilo e clima<input aria-label="Estilo da música" maxLength={400} className={field} value={spec.style} onChange={e=>change({style:e.target.value})}/></label>
   {spec.mode==='educational'&&<label className="block">Letra original em português (opcional)<textarea aria-label="Letra da música" rows={5} maxLength={2500} className={field} value={spec.lyrics} onChange={e=>change({lyrics:e.target.value})}/><small>Sem letra, o Eleven Music compõe a partir do tema. Com letra, revise se ela cabe na duração. Vocais são sintetizados pelo modelo musical, não por uma voz da biblioteca ElevenLabs.</small></label>}
   <p className="text-xs text-slate-300">Use conteúdo original ou autorizado, sem pedir imitação de artistas ou músicas existentes. Confira a licença comercial do plano antes de entregar a clientes. Revise a letra, pronúncia e duração do resultado.</p>
   <Button disabled={!valid||!config?.configured} onClick={estimate} data-testid="music-estimate">Calcular orçamento em reais — sem gerar</Button>
  </fieldset>
  {q&&<section className="rounded border border-amber-600 p-4 space-y-3" data-testid="music-budget">
   <h3 className="font-semibold">Orçamento de uma geração · {labels[job.status]}</h3>
   <p className="text-xl font-bold">Estimativa: {money(q.estimatedBrl)}</p><p className="text-sm">Referência: {money(q.estimatedUsd,'USD')} · {q.duration}s · {money(q.rateUsdMinute,'USD')}/minuto</p>
   <p className="text-sm">Cotação: US$ 1 = R$ {q.exchange.rate.toLocaleString('pt-BR',{minimumFractionDigits:4})} · data {q.exchange.asOfDate.split('-').reverse().join('/')}. Banco Central, dólar venda. {q.exchange.stale&&q.exchange.notice}</p>
   <p className="text-xs">{q.disclaimer} Validade: {new Date(q.expiresAt).toLocaleString('pt-BR')}.</p>
   <label className="block">Limite autorizado (R$)<input aria-label="Limite do orçamento da música" type="number" min={q.estimatedBrl} max="10000" step="0.01" disabled={busy||!['quoted','approved'].includes(job.status)} className={field} value={limit} onChange={e=>{setLimit(e.target.value);setConsent(false);}}/></label>
   <label className="flex gap-2 text-sm"><input aria-label="Confirmar orçamento da música" type="checkbox" checked={consent} disabled={busy||!['quoted','approved'].includes(job.status)} onChange={e=>setConsent(e.target.checked)}/>Li a estimativa e a cotação, tenho autorização sobre o conteúdo e aprovo uma geração até este limite de referência em reais, ciente de que a cobrança em dólares pode variar.</label>
   <Button disabled={busy||!consent||!Number.isFinite(Number(limit))||Number(limit)<q.estimatedBrl||Number(limit)>10000||!['quoted','approved'].includes(job.status)} onClick={()=>act(async()=>accept(await musicRequest('/music/'+job.id+'/approve','POST',{quoteId:q.id,ceilingBrl:Number(limit),consent:true})))} data-testid="music-approve">Aprovar orçamento — ainda não gera música</Button>
   <Button disabled={busy||job.status!=='approved'||Number(limit)!==job.approval?.ceilingBrl} onClick={()=>act(async()=>setJob(await musicRequest('/music/'+job.id+'/generate','POST',{quoteId:q.id})))} data-testid="music-generate">Gerar música aprovada — usa créditos</Button>
  </section>}
  {job&&<div className="space-y-3"><p role="status">{labels[job.status]}{active&&' · Pode levar alguns minutos. Fechar esta janela não cancela a solicitação.'}</p>{job.notice&&<p role="alert" className="text-amber-200">{job.notice}</p>}
   <Button variant="outline" disabled={busy} onClick={()=>act(async()=>setJob(await musicRequest('/music/'+job.id)))}>Atualizar status — sem gerar novamente</Button>
   {job.status==='ready'&&<><Button disabled={busy} onClick={()=>act(loadAudio)}>Carregar áudio para ouvir</Button>{preview&&<><audio src={preview} controls preload="metadata" className="w-full"/><a className="block underline" href={preview} download="scormify-musica.mp3">Baixar MP3</a></>}
    {onUseAudio&&<Button disabled={busy} onClick={()=>act(async()=>{const blob=await loadAudio();await onUseAudio(new File([blob],'scormify-musica.mp3',{type:'audio/mpeg'}));onOpenChange(false);})}>Escolher onde inserir no Editor</Button>}
   </>}
  </div>}
  <section className="border-t border-slate-700 pt-3 space-y-2"><h3 className="font-semibold">Minhas músicas e orçamentos</h3><Button variant="outline" disabled={busy} onClick={()=>act(async()=>setHistory((await musicRequest('/music')).music||[]))}>Atualizar biblioteca</Button>
   {history.map(row=><Button key={row.id} variant="outline" disabled={busy||active} className="block w-full whitespace-normal text-left h-auto" onClick={()=>act(async()=>{clearPreview();const data=await musicRequest('/music/'+row.id);setSpec(data.spec);requestId.current=null;accept(data);})}>{row.spec.title} · {labels[row.status]}</Button>)}
  </section>
 </DialogContent></Dialog>;
}
