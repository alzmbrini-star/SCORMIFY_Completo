import React,{useEffect,useRef,useState} from 'react';
import {useNavigate} from 'react-router-dom';
import {authHeaders} from '../contexts/AuthContext';
import {getApiUrl} from '../utils/apiUrl';
import {Dialog,DialogContent,DialogHeader,DialogTitle,DialogDescription} from './ui/dialog';
import {Button} from './ui/button';

const labels=['Capa','Conteúdo com imagem','Atividade'];
export default function AstryxPrototypeDialog({open,onOpenChange,sourceProjectId}){
 const navigate=useNavigate(),[data,setData]=useState(null),[preview,setPreview]=useState(null),
 [tab,setTab]=useState(0),[mobile,setMobile]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState('');
 const requestId=useRef(null),alive=useRef(false);
 const api=async(path,body,download=false)=>{
  const res=await fetch(`${getApiUrl()}/api/design-prototypes/astryx/${path}`,{
   method:body?'POST':'GET',headers:{...authHeaders(),...(body?{'Content-Type':'application/json'}:{})},...(body?{body:JSON.stringify(body)}:{})});
  if(!res.ok){let detail;try{detail=(await res.json()).detail;}catch{detail=null;}
   throw Error(typeof detail==='string'?detail:Array.isArray(detail)?detail.map(d=>d.msg).join(' '):'Não foi possível preparar o protótipo. Tente novamente.');}
  return download?res.blob():res.json();
 };
 useEffect(()=>{if(!open)return;alive.current=true;setError('');setBusy(true);setPreview(null);setData(null);requestId.current=crypto.randomUUID();
  api('defaults').then(d=>{if(alive.current)setData(d);}).catch(e=>{if(alive.current)setError(e.message);}).finally(()=>{if(alive.current)setBusy(false);});
  return()=>{alive.current=false;};
 // Initialization intentionally only runs on open; no project data is sent.
 // eslint-disable-next-line react-hooks/exhaustive-deps
 },[open]);
 const edit=(key,value)=>{setData(d=>({...d,[key]:value}));setPreview(null);requestId.current=crypto.randomUUID();setError('');};
 const run=async(action)=>{if(busy)return;setBusy(true);setError('');try{await action();}catch(e){setError(e.message);}finally{setBusy(false);}};
 const download=kind=>run(async()=>{const blob=await api(`export/${kind}`,data,true),url=URL.createObjectURL(blob),a=document.createElement('a');
  a.href=url;a.download=`Prototipo_Astryx.${kind==='html'?'html':'zip'}`;a.click();setTimeout(()=>URL.revokeObjectURL(url),30000);});
 const field=(key,label,maxLength,multiline=false)=><label className="block text-sm space-y-1" key={key}>{label}
  {multiline?<textarea className="w-full rounded border border-slate-600 bg-slate-950 p-2 min-h-24" value={data[key]} maxLength={maxLength} disabled={busy} onChange={e=>edit(key,e.target.value)}/>
   :<input className="w-full rounded border border-slate-600 bg-slate-950 p-2" value={data[key]} maxLength={maxLength} disabled={busy} onChange={e=>edit(key,e.target.value)}/>}</label>;
 return <Dialog open={open} onOpenChange={value=>{if(!busy)onOpenChange(value);}}><DialogContent className="!max-w-6xl w-[96vw] max-h-[94vh] overflow-y-auto bg-slate-900 text-slate-100">
  <DialogHeader><DialogTitle>Astryx — laboratório de slides</DialogTitle><DialogDescription className="text-slate-300">Protótipo opcional · 3 slides independentes · sem créditos de IA · nenhum curso existente será alterado.</DialogDescription></DialogHeader>
  <p className="text-sm rounded-lg p-3 bg-blue-950 text-blue-100">Edite o conteúdo, prepare a prévia e teste os arquivos. Criar novo projeto não aplica o tema ao curso aberto. Não redesenha imagens de Gamma/PPT nem substitui os modos atuais.</p>
  {error&&<p role="alert" className="text-red-200 p-3 border border-red-700 rounded">{error}</p>}
  {!data?<p role="status">{busy?'Carregando modelos…':'Feche e abra novamente para tentar carregar os modelos.'}</p>:<>
   <div className="grid lg:grid-cols-[320px_minmax(0,1fr)] gap-5">
    <fieldset disabled={busy} className="space-y-4 min-w-0">
     <legend className="font-semibold mb-3">Conteúdo do protótipo</legend>
     {field('title','Título da capa',160)}{field('subtitle','Apresentação',300)}{field('heading','Título do conteúdo',180)}{field('body','Conteúdo (um parágrafo por linha)',4000,true)}
     <label className="block text-sm space-y-1">Imagem PNG, JPEG ou WebP (até 2 MB)
      <input aria-label="Imagem do protótipo" type="file" accept="image/png,image/jpeg,image/webp" className="block w-full text-xs" onChange={async e=>{
       const f=e.target.files?.[0];if(!f)return;if(f.size>2*1024*1024){setError('Use uma imagem de até 2 MB.');e.target.value='';return;}
       try{const uri=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=()=>reject(Error('Não foi possível ler a imagem.'));reader.readAsDataURL(f);});edit('image',uri);}catch(err){setError(err.message);}
      }}/></label>
     {data.image&&<Button type="button" variant="outline" onClick={()=>edit('image','')}>Usar ilustração de exemplo</Button>}
     {field('imageAlt','Descrição da imagem',300)}
     <label className="block text-sm">Cor de destaque<select aria-label="Cor do protótipo" value={data.accent} onChange={e=>edit('accent',e.target.value)} className="block w-full p-2 bg-slate-950 border rounded border-slate-600"><option value="blue">Azul</option><option value="teal">Verde-petróleo</option><option value="violet">Violeta</option></select></label>
     {field('question','Pergunta da atividade',600,true)}
     {data.options.map((value,i)=><label key={i} className="block text-sm">Alternativa {i+1}<input aria-label={`Alternativa ${i+1}`} value={value} maxLength={400} className="block w-full p-2 bg-slate-950 border rounded border-slate-600" onChange={e=>edit('options',data.options.map((v,j)=>j===i?e.target.value:v))}/></label>)}
     <label className="block text-sm">Resposta correta<select aria-label="Resposta correta" value={data.correct} onChange={e=>edit('correct',Number(e.target.value))} className="block w-full p-2 bg-slate-950 border rounded border-slate-600">{data.options.map((_,i)=><option key={i} value={i}>{i+1}</option>)}</select></label>
     {field('feedback','Feedback explicativo',900,true)}
     <p className="text-xs text-slate-300">Atividade de autoestudo sem nota no LMS. Quiz tradicional e Avaliação interativa continuam disponíveis, sem conversão.</p>
     <Button type="button" disabled={busy} onClick={()=>run(async()=>setPreview(await api('preview',data)))} className="w-full">{busy?'Preparando…':'Preparar prévia — sem salvar'}</Button>
    </fieldset>
    <section className="min-w-0 space-y-3" aria-label="Prévia Astryx">
     <div className="flex flex-wrap gap-2">{labels.map((label,i)=><Button key={label} type="button" variant={tab===i?'default':'outline'} aria-pressed={tab===i} onClick={()=>setTab(i)}>{label}</Button>)}</div>
     <div className="flex gap-2"><Button type="button" variant="outline" aria-pressed={!mobile} onClick={()=>setMobile(false)}>Computador</Button><Button type="button" variant="outline" aria-pressed={mobile} onClick={()=>setMobile(true)}>Celular · 390 px</Button></div>
     <div className="bg-slate-950 rounded-xl border border-slate-700 p-2 flex justify-center">
      {preview?<iframe title={`Astryx: ${labels[tab]}`} sandbox="allow-scripts" srcDoc={preview.course.slides[tab].elements[0].htmlContent} className="border-0 bg-white rounded-lg" style={{width:mobile?'390px':'100%',maxWidth:'100%',height:mobile?'720px':'640px'}}/>:<p className="p-10 text-slate-300">Prepare a prévia para conferir os três modelos. Alterar um campo exige preparar uma nova prévia.</p>}
     </div>
     <div className="flex flex-wrap gap-2"><Button disabled={busy||!preview} variant="outline" onClick={()=>download('html')}>Baixar HTML de teste</Button><Button disabled={busy||!preview} variant="outline" onClick={()=>download('scorm')}>Baixar SCORM 1.2 de teste</Button></div>
     <p className="text-xs text-slate-300">Os arquivos usam os exportadores do SCORMIFY, com estilos e imagem incorporados. Não usam CDN Astryx. A atividade não envia nota ao LMS. Revise os textos e a imagem antes de distribuir.</p>
     <Button disabled={busy||!preview} data-testid="astryx-create" onClick={()=>run(async()=>{const result=await api('create',{content:data,requestId:requestId.current,...(sourceProjectId?{sourceProjectId}:{})});onOpenChange(false);navigate(`/editor/${result.projectId}`);})}>Criar novo projeto com estes 3 slides</Button>
    </section>
   </div>
  </>}
 </DialogContent></Dialog>;
}
