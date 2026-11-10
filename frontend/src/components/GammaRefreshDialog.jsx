import React, {useEffect, useRef, useState} from 'react';
import {authHeaders} from '../contexts/AuthContext';
import {getApiUrl} from '../utils/apiUrl';
import {Button} from './ui/button';
import {Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription} from './ui/dialog';

const API = getApiUrl();
async function request(path, body) {
  const response = await fetch(`${API}/api${path}`, {method: body ? 'POST' : 'GET',
    headers: authHeaders({'Content-Type':'application/json'}), ...(body ? {body:JSON.stringify(body)} : {})});
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Não foi possível atualizar o Gamma.');
  return data;
}
const url = value => value?.startsWith('/') ? `${API}${value}` : value;

export default function GammaRefreshDialog({project, saveCourse, onApplied}) {
  const [open, setOpen] = useState(false), [job, setJob] = useState(null);
  const [busy, setBusy] = useState(false), [error, setError] = useState(''), [confirmed, setConfirmed] = useState(false);
  const [mapping, setMapping] = useState({}), [notice, setNotice] = useState('');
  const requestId = useRef(null), inFlight = useRef(false);
  const pid = project?.id;
  const active = job && ['pending','submitting','preparing'].includes(job.status);
  useEffect(() => {setJob(null);setMapping({});setError('');setNotice('');requestId.current=null;}, [pid]);
  useEffect(() => {
    if (!open || job) return undefined;
    let cancelled=false, ident;
    try {ident=sessionStorage.getItem(`gamma-refresh:${pid}`);} catch (_) {return undefined;}
    if (ident) request(`/projects/${pid}/gamma-refresh/${encodeURIComponent(ident)}`).then(next=>{if(!cancelled)setJob(next);}).catch(e=>{if(!cancelled)setError(e.message);});
    return ()=>{cancelled=true;};
  }, [open, pid]);
  useEffect(() => {
    if (!open || !active) return undefined;
    let cancelled = false, timer;
    async function poll() {
      try {
        const next = await request(`/projects/${pid}/gamma-refresh/${job.id}`);
        if (!cancelled) {setJob(next);setError(next.error || '');}
      } catch (e) {if (!cancelled) setError(e.message);}
      if (!cancelled) timer = setTimeout(poll, 5000);
    }
    timer = setTimeout(poll, 3000);
    return () => {cancelled=true;clearTimeout(timer);};
  }, [open, active, job?.id, pid]);
  if (project?.source !== 'gamma' || !project?.gammaJobId) return null;
  const prepare = async () => {
    if (inFlight.current) return;
    inFlight.current=true;setBusy(true);setError('');setNotice('');setConfirmed(false);setMapping({});
    requestId.current = requestId.current || crypto.randomUUID();
    try {
      // Save only before preparation. Saving again before apply would overwrite
      // the checked server revision or cause stale local content to win.
      await saveCourse();
      const next = await request(`/projects/${pid}/gamma-refresh`, {requestId:requestId.current});
      setJob(next);setError(next.error || '');
      try {sessionStorage.setItem(`gamma-refresh:${pid}`, next.id);} catch (_) {/* API job remains safe without browser storage. */}
    } catch (e) {setError(e.message);}
    finally {inFlight.current=false;setBusy(false);}
  };
  const apply = async () => {
    if (inFlight.current || !confirmed) return;
    inFlight.current=true;setBusy(true);setError('');
    try {
      const mappings = Object.entries(mapping).filter(([,index])=>index!=='').map(([slideId,index])=>({slideId,sourceIndex:Number(index)}));
      const result = await request(`/projects/${pid}/gamma-refresh/${job.id}/apply`, {mappings});
      setJob(previous=>({...previous,status:'applied'}));
      setNotice(`${result.appliedSlides || mappings.length} slide(s) atualizado(s). Perguntas e interações preservadas. Confira o alinhamento e exporte novamente HTML/SCORM.`);
      await onApplied(pid);
    } catch (e) {setError(e.message);}
    finally {inFlight.current=false;setBusy(false);}
  };
  const selected = Object.values(mapping).filter(value=>value!=='').length;
  return <>
    <Button variant="outline" onClick={()=>setOpen(true)} data-testid="gamma-refresh-open">Atualizar do Gamma</Button>
    <Dialog open={open} onOpenChange={next=>{if(!busy)setOpen(next);}}>
      <DialogContent className="w-[95vw] max-w-5xl max-h-[90vh] flex flex-col" onInteractOutside={event=>{if(busy)event.preventDefault();}}>
        <DialogHeader><DialogTitle>Atualizar imagens-base do Gamma</DialogTitle><DialogDescription>
          Busca a versão atual da apresentação original. Não recria o curso nem remove perguntas, interações, áudio ou objetos do Editor.
        </DialogDescription></DialogHeader>
        <div className="overflow-y-auto min-h-0 flex-1 space-y-4 pr-2">
          <p className="rounded-lg border border-cyan-700 bg-cyan-950/40 p-3 text-sm text-cyan-100">
            Primeiro, suas edições são salvas. Depois, você revisa e escolhe as substituições. Não há geração por IA; disponibilidade e eventuais limites de exportação dependem da conta Gamma.
          </p>
          <p className="text-sm">Se você reordenou, incluiu ou removeu slides no Gamma, confira cada correspondência manualmente. Nenhum slide será incluído, excluído ou reordenado automaticamente. O enquadramento e o tempo do Editor são mantidos; revise sobreposições se o novo layout mudou.</p>
          {error && <p role="alert" className="rounded border border-red-700 bg-red-950 p-3 text-red-100">{error}</p>}
          {notice && <p role="status" className="rounded border border-emerald-600 bg-emerald-950 p-3 text-emerald-100">{notice}</p>}
          {active && <p role="status">Preparando a exportação e persistindo imagens… Pode fechar esta janela e reabrir nesta sessão. O curso ainda não foi alterado.</p>}
          {job?.status==='ready' && <>
            <p className="font-medium">{job.images.length} imagens recebidas · {selected} selecionadas para aplicar</p>
            <div className="flex flex-wrap gap-2"><Button variant="outline" className="whitespace-normal h-auto min-h-10 py-2" onClick={()=>{setMapping(Object.fromEntries(job.bases.filter(base=>job.images.some(image=>image.index===base.index)).map(base=>[base.slideId,String(base.index)])));setConfirmed(false);}}>Selecionar posições de origem — conferir antes de aplicar</Button><Button variant="outline" onClick={()=>{setMapping({});setConfirmed(false);}}>Limpar seleção</Button></div>
            <div className="grid gap-4 md:grid-cols-2">
              {job.bases.map(base=>{
                const index = mapping[base.slideId] ?? '';
                const image = job.images.find(item=>item.index===Number(index));
                return <section key={base.slideId} className="rounded-xl border border-slate-600 bg-slate-900 p-3 space-y-2">
                  <h3 className="font-semibold">Slide {base.position+1} · {base.title}</h3>
                  <div className="grid grid-cols-2 gap-2"><div><p className="text-xs mb-1">Atual no SCORMIFY</p><img className="w-full aspect-video object-contain bg-slate-800 rounded" src={url(base.src)} alt={`Imagem atual: ${base.title}`}/></div>
                    <div><p className="text-xs mb-1">Substituição escolhida</p>{index!=='' && image ? <img className="w-full aspect-video object-contain bg-slate-800 rounded" src={url(image.src)} alt={`Gamma slide ${image.index+1}`}/> : <p className="text-sm p-4">Manter imagem atual</p>}</div></div>
                  <label className="block text-sm">Imagem do Gamma para o slide {base.position+1}
                    <select className="block w-full mt-1 p-2 rounded border border-slate-500 bg-slate-950 text-white" aria-label={`Imagem Gamma para slide ${base.position+1}`} value={index} onChange={event=>{setMapping(previous=>({...previous,[base.slideId]:event.target.value}));setConfirmed(false);}}>
                      <option value="">Manter imagem atual</option>{job.images.map(item=><option key={item.index} value={item.index}>Gamma · slide {item.index+1}{item.index===base.index?' (posição de origem)':''}</option>)}
                    </select>
                  </label>
                  {index!=='' && image && base.width && base.height && Math.abs(image.width/image.height-base.width/base.height)>.03 && <p className="text-amber-300 text-sm">A proporção mudou. O tamanho no Editor será preservado; confira o enquadramento.</p>}
                </section>;
              })}
            </div>
            <label className="flex gap-2 items-start rounded border border-amber-700 bg-amber-950/40 p-3 text-sm"><input type="checkbox" checked={confirmed} onChange={event=>setConfirmed(event.target.checked)}/>Conferi as correspondências e quero substituir somente as imagens selecionadas, mantendo as interações existentes.</label>
          </>}
        </div>
        <div className="flex flex-wrap justify-end gap-2 border-t pt-3">
          <Button variant="outline" disabled={busy} onClick={()=>setOpen(false)}>Fechar</Button>
          {!active && <Button variant="outline" disabled={busy} onClick={()=>{if(job?.status==='ready'||job?.status==='applied'||job?.status==='failed')requestId.current=null;prepare();}}>{busy?'Aguarde…':job?'Preparar nova atualização':'Buscar versão atual no Gamma'}</Button>}
          {job?.status==='ready' && <Button disabled={busy||!confirmed||!selected} onClick={apply}>Aplicar em {selected} slide(s)</Button>}
        </div>
      </DialogContent>
    </Dialog>
  </>;
}
