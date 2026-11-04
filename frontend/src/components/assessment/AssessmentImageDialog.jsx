import React, { useEffect, useRef, useState } from 'react';
import { Loader2, Sparkles } from 'lucide-react';
import { authHeaders } from '../../contexts/AuthContext';
import { getApiUrl } from '../../utils/apiUrl';
import { Button } from '../ui/button';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '../ui/dialog';
import { Textarea } from '../ui/textarea';
import { generateAssessment } from './assessmentGeneration';

export default function AssessmentImageDialog({ target, projectId, onClose, onApply }) {
  const [prompt,setPrompt]=useState(''),[media,setMedia]=useState(null),[busy,setBusy]=useState(false),[error,setError]=useState(''),[progress,setProgress]=useState('');
  const mounted=useRef(true);
  useEffect(()=>{mounted.current=true;return ()=>{mounted.current=false;};},[]);
  useEffect(()=>{setPrompt(target?.description || '');setMedia(null);setError('');},[target]);
  const generate=async()=>{
    setBusy(true);setError('');
    try {
      const result=await generateAssessment(getApiUrl(),{projectId,prompt,context:target.context,title:target.label,category:target.category},authHeaders({'Content-Type':'application/json'}),
        {startPath:'/images/jobs',initialMessage:'Gerando e salvando a imagem na galeria…',storageKey:`scormify-assessment-image:${projectId}:${target.key}`,onProgress:value=>{if(mounted.current)setProgress(value);}});
      if(!result.media?.url)throw new Error('O serviço não retornou uma imagem persistida.');
      if(mounted.current)setMedia(result.media);
    } catch(failure){if(mounted.current)setError(failure.message);}
    finally{if(mounted.current){setBusy(false);setProgress('');}}
  };
  return <Dialog open={!!target} onOpenChange={open=>{if(!open&&!busy)onClose();}}><DialogContent className="max-w-xl max-h-[90vh] overflow-auto" onEscapeKeyDown={e=>{if(busy)e.preventDefault();}}>
    <DialogHeader><DialogTitle>Gerar imagem com IA · {target?.label}</DialogTitle><DialogDescription>A imagem será salva na galeria reutilizável e nos arquivos persistentes do projeto. A geração consome créditos da IA configurada. Nenhum anexo será substituído antes de você confirmar.</DialogDescription></DialogHeader>
    <label className="text-sm font-medium" htmlFor="assessment-image-description">Descreva a imagem</label>
    <Textarea id="assessment-image-description" value={prompt} maxLength={2000} disabled={busy} onChange={e=>{setPrompt(e.target.value);setMedia(null);}} className="min-h-28" />
    {busy&&<p role="status" className="text-sm">{progress || 'Gerando e salvando a imagem…'}</p>}
    {error&&<p role="alert" className="text-sm text-red-500">{error}</p>}
    {media&&<figure><img src={`${getApiUrl()}${media.url}`} alt={media.name} className="max-h-64 w-full rounded border object-contain" /><figcaption className="text-xs text-muted-foreground">Salva na galeria. Confira o resultado antes de usar.</figcaption></figure>}
    <DialogFooter><Button type="button" variant="outline" disabled={busy} onClick={onClose}>Cancelar</Button><Button type="button" disabled={busy||!prompt.trim()} onClick={generate}>{busy?<Loader2 className="mr-2 h-4 w-4 animate-spin"/>:<Sparkles className="mr-2 h-4 w-4"/>}{media?'Gerar outra imagem':'Gerar imagem'}</Button><Button type="button" disabled={busy||!media} onClick={()=>onApply(media)}>Usar esta imagem</Button></DialogFooter>
    <p className="text-xs text-muted-foreground">Depois de usar, salve a questão no Banco. Avaliações já inseridas no slide guardam uma cópia: insira uma avaliação atualizada para refletir a alteração.</p>
  </DialogContent></Dialog>;
}
