import React, { useCallback, useEffect, useState } from 'react';
import { authHeaders } from '../contexts/AuthContext';
import { getApiUrl } from '../utils/apiUrl';

const API = getApiUrl();
const stateName = value => ({running:'Em geração',accepted:'Validado para inserção',failed:'Reprovado ou interrompido'}[value] || value);

export default function SimulatorDiagnostics() {
  const [sessions,setSessions]=useState([]), [sessionId,setSessionId]=useState(''), [slideIndex,setSlideIndex]=useState('');
  const [data,setData]=useState(null), [error,setError]=useState(''), [busy,setBusy]=useState(false);
  const course=sessions.find(s=>s.id===sessionId);
  const request=useCallback(async(path,options={})=>{
    const response=await fetch(API+'/api'+path,{credentials:'include',...options,headers:authHeaders({'Content-Type':'application/json'})});
    const body=await response.json();
    if(!response.ok)throw new Error(typeof body.detail==='string'?body.detail:'Não foi possível consultar o diagnóstico.');
    return body;
  },[]);
  useEffect(()=>{
    let active=true;
    request('/agent/simulator-diagnostics/sessions').then(items=>{if(active)setSessions(items);}).catch(e=>{if(active)setError(e.message);});
    return ()=>{active=false;};
  },[request]);
  const refresh=useCallback(async()=>{
    if(!sessionId)return;
    try{const result=await request('/agent/sessions/'+sessionId+'/simulator-diagnostics');setData(result);setError('');}
    catch(e){setError(e.message);}
  },[request,sessionId]);
  useEffect(()=>{setData(null);setSlideIndex('');refresh();},[refresh]);
  useEffect(()=>{
    if(data?.run?.status!=='running')return;
    const interval=setInterval(refresh,4000);return ()=>clearInterval(interval);
  },[data?.run?.status,refresh]);
  async function retry(){
    if(slideIndex==='')return;
    setBusy(true);setError('');
    try{await request('/agent/sessions/'+sessionId+'/simulator-diagnostics/retry',{method:'POST',body:JSON.stringify({slideIndex:Number(slideIndex)})});await refresh();}
    catch(e){setError(e.message);}finally{setBusy(false);}
  }
  async function download(){
    try{
      const full=await request('/agent/sessions/'+sessionId+'/simulator-diagnostics?full=1');
      const url=URL.createObjectURL(new Blob([JSON.stringify(full,null,2)],{type:'application/json'}));
      const link=document.createElement('a');link.href=url;link.download='scormify-simulator-diagnostic.json';link.click();
      setTimeout(()=>URL.revokeObjectURL(url),10000);
    }catch(e){setError(e.message);}
  }
  return <main className="min-h-screen bg-slate-950 text-slate-100 p-6"><div className="max-w-5xl mx-auto space-y-5">
    <h1 className="text-2xl font-bold">Diagnóstico de simuladores do Agente</h1>
    <p>Teste apenas um simulador, sem alterar a estrutura ou iniciar o Storyboard inteiro. Uma nova tentativa pode consumir créditos de IA. O resultado só é reaproveitado após aprovação automática, com pedido e contexto idênticos.</p>
    <p className="text-slate-300">Esta tela pode ficar aberta em outra aba. A aba original do Agente não precisa ser recarregada. O diagnóstico é privado, retido por sete dias e não executa o HTML reprovado.</p>
    {error && <p role="alert" className="bg-red-950 text-red-100 p-4 rounded">{error}</p>}
    <label className="block">Curso / sessão<select aria-label="Curso / sessão" className="block w-full mt-2 bg-slate-800 p-3 rounded" value={sessionId} onChange={e=>setSessionId(e.target.value)}><option value="">Selecione um curso</option>{sessions.map(s=><option key={s.id} value={s.id}>{s.title} · {s.id.slice(0,8)}</option>)}</select></label>
    {course && <>
      {course.error && <p className="bg-slate-800 p-4 rounded">Último erro do Storyboard: {course.error}</p>}
      <label className="block">Simulador<select aria-label="Simulador" className="block w-full mt-2 bg-slate-800 p-3 rounded" value={slideIndex} onChange={e=>setSlideIndex(e.target.value)}><option value="">Selecione um simulador</option>{course.simulators.map(s=><option key={s.index} value={s.index}>{s.title}</option>)}</select></label>
      <div className="flex flex-wrap gap-3">
        <button className="bg-emerald-700 p-3 rounded disabled:opacity-50" disabled={busy || data?.run?.status==='running' || slideIndex===''} onClick={retry}>Gerar somente este simulador com diagnóstico</button>
        <button className="bg-slate-700 p-3 rounded" onClick={refresh}>Atualizar diagnóstico</button>
        <button className="bg-slate-700 p-3 rounded disabled:opacity-50" disabled={!data?.records?.length} onClick={download}>Baixar diagnóstico completo (JSON)</button>
      </div>
    </>}
    {data?.run && <section role="status" className="bg-slate-800 p-4 rounded"><h2 className="font-bold">{data.run.title}: {stateName(data.run.status)}</h2>{data.run.error && <p className="whitespace-pre-wrap">{data.run.error}</p>}{data.run.status==='accepted' && <p>O resultado validado foi guardado. Volte à aba original e retome o Storyboard para reaproveitá-lo. A validação pode usar motor testado e dados verificados ou revisão automática de código; não equivale a uma verificação visual no navegador.</p>}</section>}
    {data?.records?.map(record=><section key={record.generationKey} className="border border-slate-600 p-4 rounded space-y-3">
      <h2 className="font-bold">{record.activityTitle} — {stateName(record.status)}</h2>
      {record.attempts.map((attempt,i)=><details key={i} className="bg-slate-900 p-3 rounded"><summary>Tentativa {i+1}: {attempt.error || 'Documento validado'}</summary>{attempt.issues.map((issue,j)=><div key={j} className="border-t border-slate-600 mt-3 pt-3"><p>{issue.issue}</p><p>Contexto: {issue.context || 'Não informado pelo revisor'}</p><p>Correção sugerida: {issue.action || 'Não informada pelo revisor'}</p></div>)}</details>)}
    </section>)}
  </div></main>;
}
