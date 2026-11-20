import React, {useEffect, useRef, useState} from 'react';
import {Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription} from './ui/dialog';
import {Button} from './ui/button';
import {getApiUrl} from '../utils/apiUrl';
import {authHeaders} from '../contexts/AuthContext';
import {resolveAssetUrls} from '../utils/htmlUtils';

const defaults={style:'clean',palette:'blue',customAccent:'',captions:false};
async function request(path, body, signal) {
  const r=await fetch(getApiUrl()+'/api/'+path,{method:body?'POST':'GET',signal,
    headers:authHeaders(body?{'Content-Type':'application/json'}:{}),...(body?{body:JSON.stringify(body)}:{})});
  const data=await r.json();if(!r.ok)throw Error(typeof data.detail==='string'?data.detail:'Não foi possível preparar o visual. Confira os campos e tente novamente.');return data;
}
export function AstryxAppearanceButton(props) {
  const [open,setOpen]=useState(false);
  return <><Button type="button" variant="outline" onClick={()=>setOpen(true)}>Estilos, cores e legendas Astryx</Button>
    {open&&<AstryxAppearanceDialog {...props} onClose={()=>setOpen(false)}/>}</>;
}
export default function AstryxAppearanceDialog({projectId,value,onChange,onClose,onSaved,title}) {
  const [options,setOptions]=useState({...defaults,...value}),[catalog,setCatalog]=useState(null),[preview,setPreview]=useState(null),
    [busy,setBusy]=useState(false),[error,setError]=useState(''),[index,setIndex]=useState(0),[mobile,setMobile]=useState(false);
  const alive=useRef(true);
  useEffect(()=>{const controller=new AbortController();alive.current=true;
    request(projectId?'projects/'+encodeURIComponent(projectId)+'/astryx-appearance':'design-prototypes/astryx/appearance-options',null,controller.signal)
      .then(data=>{if(!alive.current)return;setCatalog(data);if(projectId)setOptions({...defaults,...data.appearance});})
      .catch(e=>{if(e.name!=='AbortError')setError(e.message);});
    return()=>{alive.current=false;controller.abort();};
  },[projectId]);
  const edit=(key,v)=>{setOptions(old=>({...old,[key]:v}));setPreview(null);setError('');};
  const prepare=async()=>{setBusy(true);setError('');setPreview(null);
    try {let data;
      if(projectId)data=await request('projects/'+encodeURIComponent(projectId)+'/astryx-appearance/preview',{appearance:options});
      else {
        const p=await request('design-prototypes/astryx/preview',{title:title||'Prévia do design Astryx',appearance:options});
        data={slides:p.course.slides.map((s,i)=>({slide:i+1,title:s.title,html:s.elements[0].htmlContent}))};
      }
      if(alive.current){setPreview(data);setIndex(0);}
    }catch(e){if(alive.current)setError(e.message);}finally{if(alive.current)setBusy(false);}
  };
  const apply=async()=>{if(!preview?.slides?.length)return;setBusy(true);setError('');
    try {
      if(projectId){await request('projects/'+encodeURIComponent(projectId)+'/astryx-appearance/apply',{appearance:options,fingerprint:preview.fingerprint});await onSaved?.();}
      else onChange?.(options);
      onClose();
    }catch(e){if(alive.current)setError(e.message);}finally{if(alive.current)setBusy(false);}
  };
  const current=preview?.slides?.[index];
  return <Dialog open onOpenChange={v=>{if(!v&&!busy)onClose();}}><DialogContent className="!max-w-6xl w-[96vw] max-h-[94vh] overflow-y-auto">
    <DialogHeader><DialogTitle>Astryx — estilos, cores e legendas</DialogTitle><DialogDescription>Prévia sem salvar e sem créditos de IA. Legendas ficam desativadas por padrão; descrições de acessibilidade são preservadas.</DialogDescription></DialogHeader>
    <div className="grid lg:grid-cols-[280px_minmax(0,1fr)] gap-5">
      <fieldset disabled={busy||!catalog} className="space-y-4 min-w-0"><legend className="font-semibold">Aparência</legend>
        <div className="grid grid-cols-2 gap-2" aria-label="Estilos Astryx">{catalog?.styles.map(s=><button type="button" key={s.id} aria-pressed={options.style===s.id} onClick={()=>edit('style',s.id)} className={'text-left p-3 border rounded-lg '+(options.style===s.id?'border-cyan-400 bg-cyan-950':'border-slate-600')}><strong>{s.name}</strong><span className="block text-xs mt-1">{s.description}</span></button>)}</div>
        <label className="block">Paleta<select className="block w-full bg-slate-950 border rounded p-2" value={options.palette} onChange={e=>edit('palette',e.target.value)}>{catalog?.palettes.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</select></label>
        <div className="flex gap-2" aria-label="Amostras de cores">{catalog?.palettes.map(p=><button type="button" key={p.id} title={p.name} aria-label={'Paleta '+p.name} aria-pressed={options.palette===p.id} onClick={()=>edit('palette',p.id)} className={'w-8 h-8 rounded-full border-2 '+(options.palette===p.id?'border-white':'border-transparent')} style={{background:p.accent}}/>)}</div>
        <label className="block text-sm">Cor de destaque personalizada (opcional)<input aria-label="Cor personalizada Astryx" placeholder="#315AD1" maxLength={7} value={options.customAccent} onChange={e=>edit('customAccent',e.target.value)} className="block w-full bg-slate-950 border rounded p-2"/></label>
        <p className="text-xs">Cores muito claras são escurecidas na prévia para manter contraste. Deixe vazio para usar a paleta.</p>
        <label className="flex gap-2 items-start"><input type="checkbox" checked={options.captions} onChange={e=>edit('captions',e.target.checked)}/>Mostrar legendas abaixo das imagens</label>
        <p className="text-xs">Ocultar a legenda não remove o texto alternativo da imagem nem apaga a legenda armazenada.</p>
        <Button type="button" onClick={prepare} disabled={!catalog||busy}>{busy?'Preparando…':'Preparar prévia — sem salvar'}</Button>
      </fieldset>
      <section className="min-w-0 space-y-3" aria-label="Prévia do estilo Astryx">
        <div className="flex flex-wrap gap-2"><Button variant="outline" aria-pressed={!mobile} onClick={()=>setMobile(false)}>Computador</Button><Button variant="outline" aria-pressed={mobile} onClick={()=>setMobile(true)}>Celular · 390 px</Button></div>
        {current&&<label className="block text-sm">Tela da prévia<select aria-label="Tela da prévia Astryx" className="block w-full bg-slate-950 border p-2 rounded" value={index} onChange={e=>setIndex(Number(e.target.value))}>{preview.slides.map((s,i)=><option key={i} value={i}>Slide {s.slide}: {s.title}</option>)}</select></label>}
        {current?<div className="overflow-auto bg-slate-800 p-2 rounded"><iframe title="Prévia de aparência Astryx" sandbox="allow-scripts" srcDoc={resolveAssetUrls(current.html)} style={{width:mobile?390:'100%',maxWidth:'100%',height:mobile?700:580,border:0,background:'white'}}/></div>:<p className="p-6 border rounded">Escolha o estilo e prepare a prévia. {projectId?'Somente telas Astryx compatíveis serão estilizadas.':'Exemplos de capa, conteúdo e atividade demonstram o design; não geram conteúdo do curso.'}</p>}
        {preview&&!preview.slides.length&&<p role="status">Este curso não tem telas Astryx compatíveis. Gamma, PPT e atividades não serão convertidos.</p>}
        <p className="text-sm">{projectId?'Ao aplicar, só o curso aberto recebe o visual, com cópia de segurança e proteção contra edições simultâneas. Slides, perguntas, gabaritos, notas e interações são preservados. Reexporte HTML/SCORM para atualizar os arquivos.':'Usar esta aparência guarda a escolha na configuração, sem gerar ou alterar cursos. Os custos de conteúdo e mídia permanecem os usuais.'}</p>
      </section>
    </div>
    {error&&<p role="alert" className="text-red-400">{error}</p>}
    <div className="flex flex-wrap justify-end gap-2"><Button variant="outline" disabled={busy} onClick={onClose}>Cancelar sem aplicar</Button><Button disabled={busy||!preview?.slides?.length} onClick={apply}>{projectId?'Aplicar visual somente neste curso':'Usar esta aparência'}</Button></div>
  </DialogContent></Dialog>;
}
