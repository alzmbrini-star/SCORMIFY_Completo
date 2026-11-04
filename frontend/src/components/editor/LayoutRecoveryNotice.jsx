import React, {useState} from 'react';
import axios from 'axios';
import {toast} from 'sonner';
import {getApiUrl} from '../../utils/apiUrl';
import {authHeaders} from '../../contexts/AuthContext';
import {Button} from '../ui/button';

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
  if(!activityLayoutIncomplete(project)) return null;
  async function recover() {
    setBusy(true);setError('');
    try {
      const {data}=await axios.post(`${getApiUrl()}/api/projects/${project.id}/recover-activity-layout`,{expectedUpdatedAt:project.updatedAt ?? null},{headers:authHeaders(),timeout:120000});
      await onRecovered(project.id);
      toast.success(`Enquadramento restaurado em ${data.recoveredSlides.length} slide(s). Conteúdo preservado.`);
    } catch(e) {setError(typeof e.response?.data?.detail==='string'?e.response.data.detail:'Não foi possível confirmar a restauração. O conteúdo não foi substituído. Reabra o curso para conferir antes de tentar novamente.');}
    finally {setBusy(false);}
  }
  return <aside role="status" className="shrink-0 border-b border-amber-500 bg-amber-950 text-amber-100 px-4 py-2 text-sm flex flex-wrap items-center gap-3">
    <span className="flex-1">Os dados de enquadramento de algumas atividades estão incompletos. O conteúdo ainda está presente. A restauração guarda uma cópia de segurança e ajusta apenas os metadados de posição, tamanho e identificação.</span>
    <Button onClick={recover} disabled={busy} variant="outline">{busy?'Restaurando enquadramento…':'Restaurar enquadramento'}</Button>
    {error && <p role="alert" className="w-full">{error}</p>}
  </aside>;
}
