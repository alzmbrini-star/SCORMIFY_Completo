import React, { useEffect, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Bot, X, Maximize2, Minimize2, Minus, Plus, Send, ExternalLink, Trash2, Loader2 } from 'lucide-react';
import { useAuth, authHeaders } from '../contexts/AuthContext';
import { getApiUrl } from '../utils/apiUrl';
import './CreatorTutor.css';

const API = getApiUrl();
const welcome = {role:'assistant', text:'Olá! Sou o Tutor do Criador. Posso orientar você no Agente, no Editor e na Administração, conforme seu perfil. Escolha um guia rápido ou escreva sua dúvida. Não altero nem salvo seus cursos.', links:[], mode:'guide'};
const quickIds=['start','agent','assessment','video','export','simulators','simulator-access','approvals','admin-overview','batch-export','batch-export-access','users','admin-game-bank','student-tutor','admin-tutor-dashboard','admin-reports','companies','costs','admin-integrations','admin-migration','admin-cleanup'];
const settingsKey=id=>`scormify-creator-tutor-reading-v1:${id}`;
function preferences(id) {
  try {const p=JSON.parse(localStorage.getItem(settingsKey(id))||'{}');return {font:[16,18,20,22,24,26,28].includes(p.font)?p.font:18, palette:['dark','light','contrast'].includes(p.palette)?p.palette:'dark'};}
  catch {return {font:18,palette:'dark'};}
}

export default function CreatorTutor() {
  const {user,isAuthenticated,loading:authLoading}=useAuth();
  const location=useLocation();
  const navigate=useNavigate();
  const owner=user?.user_id;
  const [open,setOpen]=useState(false),[expanded,setExpanded]=useState(false);
  const [messages,setMessages]=useState([welcome]),[topics,setTopics]=useState([]),[guideError,setGuideError]=useState('');
  const [question,setQuestion]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState('');
  const [reading,setReading]=useState({font:18,palette:'dark'});
  const dialog=useRef(null),input=useRef(null),launcher=useRef(null),end=useRef(null),request=useRef(null),activeOwner=useRef(owner),wasOpen=useRef(false);
  const path=location.pathname;
  activeOwner.current=owner;
  const visible=isAuthenticated&&!authLoading&&!['/login','/change-password'].includes(path);

  useEffect(()=>{
    request.current?.abort();setOpen(false);setExpanded(false);setMessages([welcome]);setQuestion('');setTopics([]);setBusy(false);setError('');
    setReading(preferences(owner));
    return ()=>request.current?.abort();
  },[owner]);
  useEffect(()=>{if(owner){try{localStorage.setItem(settingsKey(owner),JSON.stringify(reading));}catch{/* preferences are optional */}}},[reading,owner]);
  useEffect(()=>{
    if(!open||!visible)return;
    const controller=new AbortController();setGuideError('');
    fetch(`${API}/api/creator-tutor/guide?path=${encodeURIComponent(path)}`,{credentials:'include',headers:authHeaders(),signal:controller.signal})
      .then(async r=>{if(!r.ok)throw new Error('Não foi possível carregar os guias.');return r.json();})
      .then(data=>setTopics(Array.isArray(data.topics)?data.topics:[]))
      .catch(e=>{if(e.name!=='AbortError')setGuideError('Guias temporariamente indisponíveis. Você ainda pode tentar enviar sua pergunta.');});
    return ()=>controller.abort();
  },[open,visible,path]);
  useEffect(()=>{
    if(open&&expanded){if(dialog.current&&!dialog.current.open)dialog.current.showModal();}
    else if(dialog.current?.open)dialog.current.close();
    if(open)input.current?.focus();
    else if(wasOpen.current)launcher.current?.focus();
    wasOpen.current=open;
  },[open,expanded]);
  useEffect(()=>{if(open)end.current?.scrollIntoView({block:'nearest'});},[messages,busy,open,expanded]);
  const close=()=>{setOpen(false);setExpanded(false);launcher.current?.focus();};
  const changeFont=delta=>setReading(p=>({...p,font:Math.max(16,Math.min(28,p.font+delta))}));
  const openGuide=topic=>{
    setError('');setMessages(previous=>[...previous,{role:'user',text:topic.title},{role:'assistant',text:topic.steps.map((s,i)=>`${i+1}. ${s}`).join('\n\n'),links:[topic.link],mode:'guide'}]);
  };
  const send=async event=>{
    event.preventDefault();const text=question.trim();if(!text||busy)return;
    const current=owner;const controller=new AbortController();request.current=controller;
    const history=messages.filter((m,i)=>i>0).slice(-8).map(m=>({role:m.role,content:m.text.slice(0,1500)}));
    setMessages(previous=>[...previous,{role:'user',text}]);setQuestion('');setBusy(true);setError('');
    const timeout=setTimeout(()=>controller.abort(),55000);
    try {
      const response=await fetch(`${API}/api/creator-tutor/chat`,{method:'POST',credentials:'include',headers:authHeaders({'Content-Type':'application/json'}),signal:controller.signal,body:JSON.stringify({message:text,path,history})});
      const data=await response.json();
      if(!response.ok)throw new Error(typeof data.detail==='string'?data.detail:'Não foi possível obter a resposta.');
      if(typeof data.answer!=='string'||!data.answer.trim())throw new Error('O Tutor retornou uma resposta vazia.');
      if(activeOwner.current===current)setMessages(previous=>[...previous,{role:'assistant',text:data.answer,links:Array.isArray(data.links)?data.links:[],mode:data.mode}]);
    } catch(e) {if(activeOwner.current===current){setError(e.name==='AbortError'?'A resposta demorou mais que o esperado. Tente novamente ou use um guia rápido.':e.message);setQuestion(text);}}
    finally {clearTimeout(timeout);if(activeOwner.current===current)setBusy(false);}
  };
  // Only locally verified product destinations are clickable. The server also
  // derives links from its guide, never from raw model-generated URLs.
  const safeLink=href=>typeof href==='string'&&/^\/(?:\?help=(?:new-project|import))?$|^\/agent$|^\/admin\?tab=(?:users|companies|game_questions|tutor|tutor_dashboard|cost_report|integrations_health|batch_export|reports|data_migration|plates_cleanup)$|^\/editor\/[A-Za-z0-9_-]{1,100}(?:\?help=(?:export|video|assessment|games|html|text-colors|template|preview|image|tts|scenario|whiteboard|pdf))?$/.test(href);
  const follow=(event,href)=>{
    if(path.startsWith('/editor/')&&href.split('?')[0]!==path)return; // new tab preserves the open course
    event.preventDefault();navigate(href);close();
  };
  const content=()=> <>
    <header className="ct-header">
      <div className="ct-heading"><Bot aria-hidden="true" size={23}/><div><h2 id="creator-tutor-title">Tutor do Criador</h2><p>Ajuda para usar o SCORMIFY</p></div></div>
      <div className="ct-tools"><button type="button" aria-label={expanded?'Reduzir painel do Tutor':'Ampliar Tutor no centro da tela'} onClick={()=>setExpanded(v=>!v)}>{expanded?<Minimize2 size={20}/>:<Maximize2 size={20}/>}</button><button type="button" aria-label="Recolher Tutor" onClick={close}><X size={21}/></button></div>
    </header>
    <div className="ct-reading" aria-label="Opções de leitura">
      <button type="button" aria-label="Diminuir fonte do Tutor" disabled={reading.font===16} onClick={()=>changeFont(-2)}><Minus size={16}/> A</button>
      <output aria-label="Tamanho da fonte">{reading.font}px</output>
      <button type="button" aria-label="Aumentar fonte do Tutor" disabled={reading.font===28} onClick={()=>changeFont(2)}>A <Plus size={16}/></button>
      <label>Contraste<select aria-label="Contraste do Tutor" value={reading.palette} onChange={e=>setReading(p=>({...p,palette:e.target.value}))}><option value="dark">Escuro</option><option value="light">Claro</option><option value="contrast">Alto contraste</option></select></label>
      <button type="button" className="ct-clear" aria-label="Limpar conversa do Tutor" disabled={busy} onClick={()=>{setMessages([welcome]);setError('');setQuestion('');}}><Trash2 size={18}/></button>
    </div>
    <div className="ct-messages" role="log" aria-label="Conversa com o Tutor" aria-live="polite" aria-relevant="additions text">
      {messages.map((message,index)=><article className={`ct-message ct-${message.role}`} key={index}>
        <p className="ct-who">{message.role==='user'?'Você':message.mode==='ai'?'Tutor · IA':'Tutor · Guia do produto'}</p>
        <div className="ct-message-text">{message.text}</div>
        {!!message.links?.length&&<nav aria-label="Locais citados na resposta" className="ct-links">{message.links.filter(l=>l&&safeLink(l.href)&&typeof l.label==='string').map((l,i)=><a key={i} href={l.href} target={path.startsWith('/editor/')&&l.href.split('?')[0]!==path?'_blank':undefined} rel="noopener noreferrer" onClick={e=>follow(e,l.href)}>{l.label}<ExternalLink size={16} aria-hidden="true"/></a>)}</nav>}
      </article>)}
      {busy&&<p className="ct-status" role="status"><Loader2 className="ct-spin" size={18}/> O Tutor está preparando a resposta…</p>}
      {error&&<p className="ct-error" role="alert">{error}</p>}
      <div ref={end}/>
    </div>
    <details className="ct-guides" open={messages.length===1}><summary>Guias rápidos · sem geração de IA</summary>
      {guideError&&<p role="status">{guideError}</p>}
      <div>{topics.filter(t=>quickIds.includes(t.id)).map(t=><button type="button" key={t.id} disabled={busy} onClick={()=>openGuide(t)}>{t.title}</button>)}</div>
    </details>
    <form className="ct-compose" onSubmit={send}>
      <label className="ct-sr" htmlFor="creator-tutor-question">Sua pergunta sobre o SCORMIFY</label>
      <textarea id="creator-tutor-question" ref={input} value={question} maxLength={2000} rows={2} placeholder="Como faço para…?" onChange={e=>setQuestion(e.target.value)} onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.nativeEvent.isComposing){e.preventDefault();if(!busy&&question.trim())send(e);}}}/>
      <button type="submit" disabled={busy||!question.trim()} aria-label="Enviar pergunta ao Tutor"><Send size={20}/></button>
      <p>Não envie senhas ou chaves. Perguntas usam a IA configurada; confira a orientação antes de agir.</p>
    </form>
  </>;
  if(!visible)return null;
  return <div className={`creator-tutor ct-${reading.palette}`} style={{'--ct-font':`${reading.font}px`}} data-testid="creator-tutor">
    <button ref={launcher} type="button" className="ct-launcher" aria-label={open?'Recolher Tutor do Criador':'Abrir Tutor do Criador'} aria-expanded={open} aria-controls={expanded?'creator-tutor-modal':'creator-tutor-panel'} onClick={()=>open?close():setOpen(true)} data-testid="creator-tutor-launcher"><Bot size={25}/><span>Tutor IA</span></button>
    {open&&!expanded&&<section id="creator-tutor-panel" className="ct-panel" aria-labelledby="creator-tutor-title" onKeyDown={e=>{if(e.key==='Escape'){e.stopPropagation();close();}}} data-testid="creator-tutor-panel">{content()}</section>}
    <dialog id="creator-tutor-modal" ref={dialog} className="ct-modal" aria-labelledby="creator-tutor-title" onCancel={e=>{e.preventDefault();close();}} data-testid="creator-tutor-modal">{open&&expanded&&content()}</dialog>
  </div>;
}
