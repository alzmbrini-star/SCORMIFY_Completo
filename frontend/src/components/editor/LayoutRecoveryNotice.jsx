import React, {useState} from 'react';
import axios from 'axios';
import {toast} from 'sonner';
import {getApiUrl} from '../../utils/apiUrl';
import {authHeaders} from '../../contexts/AuthContext';
import {Button} from '../ui/button';
import {parseLayoutReference} from '../../utils/layoutReference';

export function hasMissingLayout(project) {
  const positive=v=>typeof v==='number'&&Number.isFinite(v)&&v>0;
  return (project?.course?.slides||[]).some(s=>!s.id||!positive(s.width)||!positive(s.height)||(s.elements||[]).some(e=>!e.id||!positive(e.width)||!positive(e.height)));
}

export function activityLayoutIncomplete(project) {
  return (project?.course?.slides || []).some(slide => {
    const elements=slide.elements || [], element=elements[0];
    if(elements.length!==1 || element?.type!=='html' || !/<script\b[^>]*\bid=["'](?:video-quiz-data|assessment-data)["']/i.test(element.htmlContent || '')) return false;
    const positive=value => typeof value==='number' && Number.isFinite(value) && value>0;
    return !slide.id || !element.id || !positive(slide.width) || !positive(slide.height) || !positive(element.width) || !positive(element.height)
      || (element.width===100 && element.height===100 && !element.videoQuizConfig && !element.assessmentConfig);
  });
}

export default function LayoutRecoveryNotice({project, onRecovered}) {
  const [busy,setBusy]=useState(false), [error,setError]=useState('');
  if(!activityLayoutIncomplete(project)&&!hasMissingLayout(project)) return null;
  async function recover(referenceCourse) {
    setBusy(true);setError('');
    try {
      const body={expectedUpdatedAt:project.updatedAt ?? null};
      if(referenceCourse)body.referenceCourse=referenceCourse;
      const {data}=await axios.post(`${getApiUrl()}/api/projects/${project.id}/recover-activity-layout`,body,{headers:authHeaders(),timeout:120000});
      if(!data.recoveredSlides.length){setError(data.message||'Nenhum elemento compatível; curso preservado.');return;}
      await onRecovered(project.id);
      toast.success(`Enquadramento restaurado em ${data.recoveredSlides.length} slide(s). Conteúdo preservado.`);
      if(data.skippedSlides?.length)setError(`Slides não correspondentes preservados sem alteração: ${data.skippedSlides.join(', ')}.`);
    } catch(e) {setError(typeof e.response?.data?.detail==='string'?e.response.data.detail:'Não foi possível confirmar a restauração. O conteúdo não foi substituído. Reabra o curso para conferir antes de tentar novamente.');}
    finally {setBusy(false);}
  }
  return <aside role="status" className="shrink-0 border-b border-amber-500 bg-amber-950 text-amber-100 px-4 py-2 text-sm flex flex-wrap items-center gap-3">
    <span className="flex-1">Os dados de enquadramento de algumas atividades estão incompletos. O conteúdo ainda está presente. A restauração guarda uma cópia de segurança e ajusta apenas os metadados de posição, tamanho e identificação.</span>
    {activityLayoutIncomplete(project)&&<Button onClick={()=>recover()} disabled={busy} variant="outline">{busy?'Restaurando enquadramento…':'Restaurar enquadramento'}</Button>}
    <label>Restaurar de HTML anterior <input aria-label="HTML anterior para recuperar enquadramento" type="file" accept=".html,.htm" disabled={busy} onChange={async e=>{
      const file=e.target.files?.[0];if(!file)return;
      try{if(file.size>50*1024*1024)throw new Error('Use um HTML de referência de até 50 MB.');await recover(parseLayoutReference(await file.text()));}
      catch(err){setError(err.message||'Não foi possível ler a referência.');}
      finally{e.target.value='';}
    }}/></label>
    {error && <p role="alert" className="w-full">{error}</p>}
  </aside>;
}
