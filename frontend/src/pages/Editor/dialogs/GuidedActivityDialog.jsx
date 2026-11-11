import React,{useEffect,useState} from 'react';
import axios from 'axios';
import {Dialog,DialogContent,DialogHeader,DialogTitle,DialogFooter} from '../../../components/ui/dialog';
import {Button} from '../../../components/ui/button';
import {Input} from '../../../components/ui/input';
import {Textarea} from '../../../components/ui/textarea';
import {getApiUrl} from '../../../utils/apiUrl';
import {authHeaders} from '../../../contexts/AuthContext';
import {QuestionForm} from '../../../components/assessment/AssessmentBuilder';

export default function GuidedActivityDialog({target,projectId,onClose,onApply,uploadMedia}){
 const [spec,setSpec]=useState(null),[advanced,setAdvanced]=useState(''),[error,setError]=useState(''),[busy,setBusy]=useState(false),[jsonValid,setJsonValid]=useState(true);
 useEffect(()=>{const value=target?.element?.guidedActivity;setSpec(value?JSON.parse(JSON.stringify(value)):null);setAdvanced(value?JSON.stringify(value,null,2):'');setError('');setJsonValid(true);},[target]);
 const update=(key,value)=>{setError('');setSpec(s=>({...s,[key]:value}));};
 const save=async()=>{setBusy(true);setError('');try{const {data}=await axios.post(`${getApiUrl()}/api/agent/guided/render`,{projectId,elementId:target.element.id,spec},{headers:authHeaders(),withCredentials:true});await onApply(data);onClose();}catch(e){setError(e.response?.data?.detail||e.message||'Não foi possível aplicar.');}finally{setBusy(false);}};
 return <Dialog open={!!target} onOpenChange={open=>{if(!open&&!busy)onClose();}}><DialogContent className="max-w-4xl max-h-[90vh] flex flex-col"><DialogHeader><DialogTitle>Editar recurso do percurso</DialogTitle></DialogHeader>
 {spec&&<div className="min-h-0 flex-1 overflow-auto space-y-4">
  <p className="text-sm text-muted-foreground">Edita a cópia deste slide sem gerar conteúdo nem consumir créditos de IA. As imagens existentes são preservadas; o Banco não é alterado. Depois, salve o curso e reexporte para distribuir a nova versão.</p>
  {error&&<p role="alert" className="text-sm text-red-500">{String(error)}</p>}
  <label className="block text-sm">Título<Input value={spec.title} onChange={e=>update('title',e.target.value)}/></label>
  <label className="block text-sm">Orientação<Textarea value={spec.instructions} onChange={e=>update('instructions',e.target.value)}/></label>
  {spec.questions?.map((q,i)=><details key={q.id} className="rounded-lg border p-3"><summary className="cursor-pointer font-semibold">Questão {i+1} · {q.title}</summary>
    <QuestionForm value={{...q,items:q.items||[],targets:q.targets||[],correctOrder:q.correctOrder||[]}} onUpload={uploadMedia} projectId={projectId} saveHint="Aplique ao slide e salve o curso." onChange={next=>{setError('');setSpec(current=>({...current,questions:current.questions.map(v=>v.id===q.id?{...v,...(typeof next==='function'?next(v):next),id:v.id,unitId:v.unitId}:v)}));}}/>
  </details>)}
  {spec.deliverables?.map((d,i)=><fieldset key={i} className="rounded-lg border p-3 space-y-2"><legend>Entrega {i+1}</legend>{['title','prompt','criterion'].map(key=><label key={key} className="block text-sm">{{title:'Título',prompt:'Pedido',criterion:'Critério de autoverificação'}[key]}<Textarea value={d[key]} onChange={e=>update('deliverables',spec.deliverables.map((v,j)=>i===j?{...v,[key]:e.target.value}:v))}/></label>)}</fieldset>)}
  {spec.kind==='practice'&&<details><summary className="cursor-pointer">Editar cartões e respostas da prática (dados estruturados)</summary><p className="text-sm text-muted-foreground">Altere textos, etapas e respostas no JSON; não inclua HTML, scripts nem fórmulas. Os dados serão validados antes de aplicar.</p><Textarea aria-label="Dados da prática" className="min-h-72 font-mono text-sm" value={advanced} onChange={e=>{setAdvanced(e.target.value);try{const value=JSON.parse(e.target.value);setSpec(s=>({...value,id:s.id,kind:s.kind,title:s.title,instructions:s.instructions}));setJsonValid(true);setError('');}catch(_){setJsonValid(false);setError('Revise o JSON antes de aplicar.');}}}/></details>}
 </div>}
 <DialogFooter><Button variant="outline" disabled={busy} onClick={onClose}>Cancelar</Button><Button disabled={busy||!jsonValid} onClick={save}>{busy?'Validando…':'Aplicar ao slide'}</Button></DialogFooter></DialogContent></Dialog>;
}
