import React,{useState} from 'react';
import {Button} from './ui/button';
import {authHeaders} from '../contexts/AuthContext';
import {getApiUrl} from '../utils/apiUrl';

export default function FilmGuidedSetup({busy,onPrepare,inputClass}){
 const [source,setSource]=useState('theme'),[theme,setTheme]=useState(''),[audience,setAudience]=useState('Adultos em treinamento'),[goal,setGoal]=useState('');
 const [duration,setDuration]=useState(60),[style,setStyle]=useState('3d'),[doc,setDoc]=useState(null),[reviewed,setReviewed]=useState(false),[reading,setReading]=useState(false),[error,setError]=useState('');
 async function upload(file){
  setDoc(null);setReviewed(false);setError('');if(!file)return;
  if(!/\.(pdf|pptx|docx)$/i.test(file.name)){setError('Use PDF, PowerPoint (.pptx) ou Word (.docx). Para PPT/DOC antigos, salve uma cópia como PPTX/DOCX.');return;}
  if(file.size>20*1024*1024){setError('O limite é 20 MB por documento. Divida arquivos maiores.');return;}
  setReading(true);
  try{
   const form=new FormData();form.append('file',file);
   const res=await fetch(getApiUrl()+'/api/films/extract-document',{method:'POST',headers:authHeaders(),body:form});
   const data=await res.json();if(!res.ok)throw new Error(typeof data.detail==='string'?data.detail:'Não foi possível ler o documento.');
   setDoc({...data,name:file.name});
  }catch(e){setError(e.message);}finally{setReading(false);}
 }
 const valid=audience.trim().length>=3&&goal.trim().length>=3&&(source==='theme'?theme.trim().length>=3:doc?.text?.trim().length>=20&&reviewed);
 function prepare(){
  const base=theme.trim() || doc.name.replace(/\.[^.]+$/,'');const title=base.length>=3?base:'Filme educativo: '+base;
  onPrepare({title:title.slice(0,160),topic:`Tema: ${title}\nPúblico: ${audience}\nObjetivo de aprendizagem: ${goal}\nDuração: ${duration} segundos. História educativa em PT-BR com até dois personagens originais e narração externa. Declare tópicos que não couberem.`,
   scenes:duration/10,style,sourceText:source==='document'?doc.text:'',sourceName:source==='document'?doc.name.slice(0,180):'',sourceWarning:source==='document'?doc.warning:''});
 }
 return <section className="rounded-xl border border-cyan-800 bg-cyan-950/20 p-4 space-y-4" aria-label="Preparação guiada do filme">
  <div><h3 className="font-semibold text-cyan-200">1. O que o filme vai ensinar?</h3><p className="text-sm text-slate-300 mt-1">A IA transforma o conteúdo em uma história. Você revisa as cenas e o orçamento antes das mídias.</p></div>
  <div className="flex gap-2" aria-label="Origem do conteúdo"><Button variant={source==='theme'?'default':'outline'} disabled={busy||reading} onClick={()=>setSource('theme')}>Por tema</Button><Button variant={source==='document'?'default':'outline'} disabled={busy||reading} onClick={()=>setSource('document')}>Por documento</Button></div>
  <label className="block text-sm">{source==='theme'?'Tema do filme':'Título ou tema (opcional)'}<input aria-label="Tema do filme guiado" className={inputClass} maxLength={160} value={theme} disabled={busy} onChange={e=>setTheme(e.target.value)} placeholder="Ex.: Trabalho em equipe na prática"/></label>
  {source==='document'&&<div className="rounded border border-slate-600 p-3 space-y-2">
   <label className="block text-sm">Enviar material de referência<input aria-label="Documento do filme" type="file" accept=".pdf,.docx,.pptx,.doc,.ppt" disabled={busy||reading} onChange={e=>upload(e.target.files?.[0])} className="block w-full mt-2 text-xs"/></label>
   <p className="text-xs text-slate-300">PDF, Word DOCX ou PowerPoint PPTX · até 20 MB e 100.000 caracteres. PPT/DOC antigos: salve como PPTX/DOCX. Extração de texto, sem OCR nem importação das imagens originais.</p>
   {reading&&<p role="status">Lendo o documento, sem gerar mídias…</p>}
   {doc&&<><p className="text-sm text-teal-200">{doc.name} · {doc.units} unidade(s) · {doc.text.length.toLocaleString('pt-BR')} caracteres</p><p className="text-xs text-amber-200">{doc.warning}</p>
    <details><summary className="cursor-pointer text-sm">Conferir e editar o texto extraído</summary><textarea aria-label="Texto extraído do documento do filme" className={inputClass+' min-h-[180px]'} maxLength={100000} value={doc.text} disabled={busy} onChange={e=>{setDoc({...doc,text:e.target.value});setReviewed(false);}}/></details>
    <label className="flex gap-2 text-sm"><input type="checkbox" aria-label="Confirmar revisão do documento" checked={reviewed} disabled={busy} onChange={e=>setReviewed(e.target.checked)}/>Revisei o texto e os avisos de leitura do documento.</label></>}
  </div>}
  {error&&<p role="alert" className="text-sm text-amber-200">{error}</p>}
  <div className="grid sm:grid-cols-2 gap-3"><label className="text-sm">Público<input aria-label="Público do filme" className={inputClass} value={audience} maxLength={300} disabled={busy} onChange={e=>setAudience(e.target.value)}/></label><label className="text-sm">O aluno deve aprender a…<input aria-label="Objetivo do filme" className={inputClass} value={goal} maxLength={1000} disabled={busy} onChange={e=>setGoal(e.target.value)} placeholder="Ex.: dividir tarefas e pedir ajuda"/></label>
   <label className="text-sm">Duração<select aria-label="Duração do filme guiado" className={inputClass} value={duration} disabled={busy} onChange={e=>setDuration(Number(e.target.value))}>{[30,60,90,120,180].map(s=><option key={s} value={s}>{s<60?s+' segundos':s/60+' minuto(s)'}</option>)}</select></label><label className="text-sm">Visual<select aria-label="Estilo do filme guiado" className={inputClass} value={style} disabled={busy} onChange={e=>setStyle(e.target.value)}><option value="3d">Animação 3D</option><option value="2d">Desenho 2D</option></select></label></div>
  <p className="text-xs text-amber-200">Preparar o storyboard usa créditos de texto OpenAI. Não gera imagens, voz, vídeo ou música. Material extenso será priorizado conforme o objetivo; confira a cobertura e as omissões na revisão. Não envie material sem autorização.</p>
  <Button data-testid="film-guided-prepare" disabled={busy||reading||!valid} onClick={prepare}>{busy?'Preparando…':'Preparar storyboard com IA — créditos de texto'}</Button>
 </section>;
}
