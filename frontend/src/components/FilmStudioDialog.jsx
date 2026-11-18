import React,{useEffect,useRef,useState} from 'react';
import {Dialog,DialogContent,DialogHeader,DialogTitle,DialogDescription} from './ui/dialog';
import {Button} from './ui/button';
import {getApiUrl} from '../utils/apiUrl';
import {authHeaders} from '../contexts/AuthContext';

const API=getApiUrl();
const labels={draft:'Rascunho',planning:'Preparando storyboard',storyboard_approved:'Storyboard aprovado',budget_approved:'Orçamento aprovado',generating:'Produzindo mídias',failed:'Produção interrompida',unknown:'Envio não confirmado',completed:'Concluído'};
async function request(path,method='GET',body) {
 const res=await fetch(API+'/api'+path,{method,headers:authHeaders(body?{'Content-Type':'application/json'}:{}),...(body?{body:JSON.stringify(body)}:{})});
 const data=await res.json();if(!res.ok)throw new Error(typeof data.detail==='string'?data.detail:'Revise os campos e tente novamente. Nenhuma mídia foi liberada por esta resposta.');return data;
}

export default function FilmStudioDialog({open,onOpenChange,sourceProjectId=null,sourceTitle=''}) {
 const [film,setFilm]=useState(null),[history,setHistory]=useState([]),[voices,setVoices]=useState([]),[config,setConfig]=useState(null);
 const [title,setTitle]=useState(''),[topic,setTopic]=useState(''),[count,setCount]=useState(6);
 const [dirty,setDirty]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState('');
 const [storyConsent,setStoryConsent]=useState(false),[budgetConsent,setBudgetConsent]=useState(false),[ceiling,setCeiling]=useState('');
 const inFlight=useRef(false),createId=useRef(null);
 const accept=data=>{setFilm(data);setDirty(false);setStoryConsent(false);setBudgetConsent(false);setCeiling(String(data.quote?.suggestedCeilingUsd || ''));};
 const act=async action=>{
  if(inFlight.current)return;inFlight.current=true;setBusy(true);setError('');
  try {const data=await action();if(data?.board)accept(data);return data;}
  catch(e){setError(e.message);}finally{inFlight.current=false;setBusy(false);}
 };
 const refresh=()=>act(()=>request('/films/'+film.id));
 const loadHistory=()=>request('/films'+(sourceProjectId?'?sourceProjectId='+encodeURIComponent(sourceProjectId):'')).then(data=>setHistory(data.films || []));
 useEffect(()=>{
  if(!open)return;
  let active=true;
  request('/films/config').then(d=>{if(active)setConfig(d);}).catch(e=>{if(active)setError(e.message);});
  loadHistory().catch(e=>{if(active)setError(e.message);});
  return()=>{active=false;};
  // History is project-scoped; opening the studio never generates or approves anything.
  // eslint-disable-next-line react-hooks/exhaustive-deps
 },[open,sourceProjectId]);
 useEffect(()=>{
  if(!open || !film || !['generating','planning'].includes(film.status))return;
  let active=true;const timer=setInterval(()=>request('/films/'+film.id).then(data=>{if(active)setFilm(data);}).catch(()=>{}),5000);
  return()=>{active=false;clearInterval(timer);};
 },[open,film?.id,film?.status]);
 const board=film?.board;
 const locked=busy || ['generating','planning','unknown','completed'].includes(film?.status);
 const change=values=>{setFilm(prev=>({...prev,board:{...prev.board,...values}}));setDirty(true);setStoryConsent(false);setBudgetConsent(false);};
 const sceneChange=(index,values)=>change({scenes:board.scenes.map((s,i)=>i===index?{...s,...values}:s)});
 const charChange=(index,values)=>change({characters:board.characters.map((c,i)=>i===index?{...c,...values}:c)});
 const save=()=>act(()=>request('/films/'+film.id,'PUT',{revision:film.revision,board}));
 const voiceOptions=<><option value="">Selecione uma voz brasileira</option>{voices.filter(v=>v.brazilian || board?.allowOtherVoices).map(v=><option key={v.id} value={v.id}>{v.name}{v.brazilian?' · PT-BR':''}</option>)}</>;
 const inputClass='w-full rounded border border-slate-600 bg-slate-950 text-slate-100 px-3 py-2 text-sm mt-1';
 return <Dialog open={open} onOpenChange={onOpenChange}><DialogContent className="max-w-6xl max-h-[92vh] overflow-y-auto bg-slate-900 text-slate-100 border-slate-700" data-testid="film-studio">
  <DialogHeader><DialogTitle>Filme educativo em desenho animado</DialogTitle><DialogDescription className="text-slate-300">História com personagens, narração PT-BR e trilha instrumental. Produção em projeto separado: slides, perguntas e interações do curso de origem não são alterados.</DialogDescription></DialogHeader>
  <div className="flex gap-2 text-xs flex-wrap" aria-label="Etapas do filme">{['1 · Storyboard','2 · Aprovar roteiro','3 · Aprovar orçamento','4 · Gerar mídias'].map(s=><span key={s} className="px-3 py-2 bg-cyan-950 border border-cyan-800 rounded">{s}</span>)}</div>
  {error&&<p role="alert" className="rounded border border-amber-700 bg-amber-950 p-3 text-amber-100">{error}</p>}
  {config&&(!config.runway || !config.narration || !config.mediaTools)&&<p className="text-sm text-amber-200">Você pode preparar e revisar o roteiro. Para gerar mídias, é necessário Runway, ElevenLabs, vozes PT-BR, FFmpeg/FFprobe e permissão de narração da empresa configurados no servidor.</p>}
  {!film ? <div className="grid md:grid-cols-2 gap-5"><section className="rounded border border-slate-700 p-4 space-y-3">
   <h3 className="font-semibold">Novo filme{sourceTitle?' para '+sourceTitle:''}</h3>
   <label className="block text-sm">Título<input aria-label="Título do filme" className={inputClass} value={title} maxLength={160} onChange={e=>setTitle(e.target.value)}/></label>
   <label className="block text-sm">Conteúdo, público e objetivo educativo<textarea aria-label="Conteúdo do filme" className={inputClass+' min-h-[160px]'} value={topic} maxLength={12000} onChange={e=>setTopic(e.target.value)} placeholder="Cole o conteúdo que a história deve ensinar. Os slides em imagem não são relidos automaticamente."/></label>
   <label className="block text-sm">Quantidade de cenas de 10 segundos<input type="number" aria-label="Quantidade de cenas do filme" className={inputClass} min={3} max={18} value={count} onChange={e=>setCount(Number(e.target.value))}/></label>
   <p className="text-xs text-slate-300">De 30 segundos a 3 minutos. Criar rascunho não usa IA nem gera mídias; a sugestão de roteiro com IA é opcional e usa créditos de texto.</p>
   <Button data-testid="film-create-draft" disabled={busy || title.trim().length<3 || topic.trim().length<20 || count<3 || count>18} onClick={()=>act(async()=>{
    createId.current=createId.current || crypto.randomUUID();
    const data=await request('/films','POST',{title,topic,scenes:count,sourceProjectId,requestId:createId.current});createId.current=null;return data;
   })}>Criar rascunho vazio — sem geração de mídias</Button>
  </section><section className="rounded border border-slate-700 p-4"><h3 className="font-semibold mb-3">Meus filmes e rascunhos</h3>
   <Button variant="outline" disabled={busy} onClick={()=>act(loadHistory)}>Atualizar lista</Button>
   {!history.length&&<p className="text-sm text-slate-400 mt-3">Nenhum filme neste contexto.</p>}
   {history.map(row=><button type="button" key={row.id} className="w-full text-left border border-slate-700 p-3 mt-2 rounded hover:bg-slate-800" disabled={busy} onClick={()=>act(()=>request('/films/'+row.id))}><strong>{row.board?.title}</strong><span className="block text-xs text-slate-400">{labels[row.status] || row.status}</span></button>)}
  </section></div> : <>
   <div className="flex justify-between gap-2 items-center flex-wrap"><p role="status" className="text-cyan-200">{labels[film.status] || film.status}{dirty?' · Alterações locais ainda não salvas':''}{film.progress?' · '+film.progress:''}</p>
    <div className="flex gap-2"><Button variant="outline" disabled={busy || dirty} onClick={refresh}>Atualizar status</Button><Button variant="outline" disabled={busy || dirty} onClick={()=>{setFilm(null);loadHistory().catch(e=>setError(e.message));}}>Meus filmes</Button></div>
   </div>
   {film.error&&<p role="alert" className="p-3 rounded bg-amber-950 text-amber-100">{film.error}</p>}
   {['generating','planning'].includes(film.status)&&<Button variant="outline" disabled={busy} onClick={()=>act(()=>request('/films/'+film.id+'/recover-interrupted','POST',{}))}>Conferir execução interrompida (após 10 min sem atividade)</Button>}
   <div className="grid lg:grid-cols-[1fr_330px] gap-5"><section className="space-y-4 min-w-0">
    <fieldset disabled={locked} className="rounded border border-slate-700 p-4 space-y-3">
     <legend className="px-2 text-cyan-200 font-semibold">Storyboard editável</legend>
     <label className="block text-sm">Título<input aria-label="Editar título do filme" className={inputClass} value={board.title} maxLength={160} onChange={e=>change({title:e.target.value})}/></label>
     <label className="block text-sm">Conteúdo de referência<textarea aria-label="Editar conteúdo do filme" className={inputClass} value={board.topic} maxLength={12000} onChange={e=>change({topic:e.target.value})}/></label>
     <div className="grid sm:grid-cols-2 gap-3"><label className="text-sm">Estilo<select aria-label="Estilo do filme" className={inputClass} value={board.style} onChange={e=>change({style:e.target.value})}><option value="2d">Desenho animado 2D</option><option value="3d">Animação 3D</option></select></label>
      <label className="text-sm">Modelo de vídeo<select aria-label="Modelo do filme" className={inputClass} value={board.model} onChange={e=>change({model:e.target.value})}><option value="gen4_turbo">Runway Gen-4 Turbo · US$ 0,05/s</option><option value="gen4.5">Runway Gen-4.5 · US$ 0,12/s</option></select></label></div>
     <p className="text-xs text-slate-300">Personagens e quadros usam referências para reduzir variações, mas a continuidade exige revisão. As vozes são sobrepostas; não há sincronização labial automática.</p>
     <Button variant="outline" disabled={locked || dirty || Object.keys(film.operations || {}).length>0} onClick={()=>act(()=>request('/films/'+film.id+'/suggest-storyboard','POST',{revision:film.revision}))}>Sugerir storyboard com IA — usa créditos de texto</Button>
     <div className="grid sm:grid-cols-2 gap-3">{board.characters.map((c,i)=><div key={i} className="border border-slate-700 rounded p-3"><label className="text-xs">Personagem {i+1}<input aria-label={`Nome do personagem ${i+1}`} className={inputClass} value={c.name} maxLength={80} onChange={e=>charChange(i,{name:e.target.value})}/></label><textarea aria-label={`Descrição do personagem ${i+1}`} className={inputClass} value={c.description} maxLength={400} onChange={e=>charChange(i,{description:e.target.value})}/><label className="text-xs">Voz própria (opcional; vazia usa narrador)<input aria-label={`Voz do personagem ${i+1}`} className={inputClass} value={c.voiceId} maxLength={100} onChange={e=>charChange(i,{voiceId:e.target.value})}/></label></div>)}</div>
     <Button variant="outline" disabled={busy} onClick={()=>act(async()=>{const data=await request('/runway/voices');setVoices(data.voices || []);})}>Carregar vozes ElevenLabs — sem síntese</Button>
     <label className="block text-sm">Voz do narrador<select aria-label="Selecionar voz do narrador" className={inputClass} value={board.narratorVoice} onChange={e=>change({narratorVoice:e.target.value})}>{voiceOptions}</select></label>
     <label className="block text-sm">ID da voz (para narrador ou para copiar nos personagens)<input aria-label="ID da voz do narrador" className={inputClass} value={board.narratorVoice} maxLength={100} onChange={e=>change({narratorVoice:e.target.value})}/></label>
     <label className="flex gap-2 text-xs"><input type="checkbox" checked={board.allowOtherVoices} onChange={e=>change({allowOtherVoices:e.target.checked})}/>Permitir voz multilíngue sem identificação de sotaque brasileiro. Revise a pronúncia.</label>
     {board.scenes.map((s,i)=><details key={i} open={i===0} className="border border-slate-600 rounded p-3"><summary className="cursor-pointer font-semibold">Cena {i+1} · {s.title} · {s.duration}s</summary>
      <label className="block text-xs mt-2">Título<input aria-label={`Título da cena ${i+1}`} className={inputClass} value={s.title} maxLength={100} onChange={e=>sceneChange(i,{title:e.target.value})}/></label>
      <label className="block text-xs mt-2">Ação e cenário<textarea aria-label={`Ação da cena ${i+1}`} className={inputClass} value={s.visual} maxLength={600} onChange={e=>sceneChange(i,{visual:e.target.value})}/></label>
      <label className="block text-xs mt-2">Fala exata em PT-BR<textarea aria-label={`Fala da cena ${i+1}`} className={inputClass} value={s.narration} maxLength={s.duration===5?55:110} onChange={e=>sceneChange(i,{narration:e.target.value})}/></label>
      <div className="grid sm:grid-cols-2 gap-3"><label className="text-xs">Quem fala<select aria-label={`Quem fala na cena ${i+1}`} className={inputClass} value={s.speaker} onChange={e=>sceneChange(i,{speaker:e.target.value})}><option value="narrator">Narrador</option>{board.characters.map((c,j)=><option key={j} value={'character'+(j+1)}>{c.name}</option>)}</select></label>
       <label className="text-xs">Duração<select aria-label={`Duração da cena ${i+1}`} className={inputClass} value={s.duration} onChange={e=>sceneChange(i,{duration:Number(e.target.value)})}><option value={5}>5 segundos</option><option value={10}>10 segundos</option></select></label></div>
      <p className="text-xs text-slate-400 mt-2">A fala será medida antes de gerar o vídeo da cena. Se não couber, a produção será interrompida para revisão, sem congelar o último quadro.</p>
      {film.operations?.['frame_'+i]?.url&&<img className="w-full mt-2 rounded" src={API+film.operations['frame_'+i].url} alt={`Quadro da cena ${i+1}`}/>}
     </details>)}
     <label className="flex gap-2 text-sm"><input type="checkbox" checked={board.music} onChange={e=>change({music:e.target.checked})}/>Trilha instrumental única, com volume reduzido durante as falas</label>
     {board.music&&<><textarea aria-label="Estilo da trilha do filme" className={inputClass} value={board.musicPrompt} maxLength={800} onChange={e=>change({musicPrompt:e.target.value})}/><label className="block text-xs">Volume da trilha: {board.musicVolume}%<input aria-label="Volume da trilha do filme" type="range" min={0} max={35} value={board.musicVolume} onChange={e=>change({musicVolume:Number(e.target.value)})}/></label></>}
     <Button disabled={locked || !dirty} onClick={save}>Salvar revisão — invalida aprovações anteriores</Button>
    </fieldset>
   </section><aside className="space-y-4 min-w-0">
    <section className="rounded border border-teal-700 bg-teal-950/40 p-4 space-y-3"><h3 className="font-semibold text-teal-200">1. Aprovação do storyboard</h3>
     <label className="flex gap-2 text-sm"><input aria-label="Confirmar revisão do storyboard" type="checkbox" checked={storyConsent} disabled={locked || dirty} onChange={e=>setStoryConsent(e.target.checked)}/>Revisei conteúdo, personagens, falas e duração das cenas.</label>
     <Button data-testid="film-approve-storyboard" disabled={locked || dirty || !storyConsent} onClick={()=>act(()=>request('/films/'+film.id+'/approve-storyboard','POST',{revision:film.revision}))}>Aprovar storyboard</Button>
     {film.storyboardApproval===film.revision&&!dirty&&<p className="text-xs text-teal-200">Versão salva aprovada.</p>}
    </section>
    <section className="rounded border border-amber-700 bg-amber-950/30 p-4 space-y-3"><h3 className="font-semibold text-amber-200">2. Orçamento antes das mídias</h3>
     {film.quote&&!dirty?<><p className="text-sm">{film.quote.duration}s · tabela {film.quote.ratesVersion}</p>
      {film.quote.items.map(item=><div key={item.label} className="text-xs flex justify-between gap-2"><span>{item.label}<small className="block text-slate-400">{item.quantity} {item.unit}</small></span><strong>US$ {item.usd.toFixed(2)}</strong></div>)}
      <p className="font-bold">Estimativa restante: US$ {film.quote.estimatedUsd.toFixed(2)}</p><p className="text-xs text-slate-300">{film.quote.disclaimer}</p>
      <label className="block text-sm">Limite autorizado (USD)<input aria-label="Limite do orçamento do filme" className={inputClass} type="number" min={film.quote.estimatedUsd} max={1000} step="0.01" value={ceiling} onChange={e=>setCeiling(e.target.value)}/></label>
      <label className="flex gap-2 text-xs"><input aria-label="Confirmar orçamento do filme" type="checkbox" checked={budgetConsent} disabled={locked} onChange={e=>setBudgetConsent(e.target.checked)}/>Li a estimativa e autorizo as chamadas planejadas desta versão, até o limite estimado informado.</label>
      <Button data-testid="film-approve-budget" disabled={locked || !budgetConsent || !Number.isFinite(Number(ceiling)) || Number(ceiling)<film.quote.estimatedUsd} onClick={()=>act(()=>request('/films/'+film.id+'/approve-budget','POST',{revision:film.revision,quoteId:film.quote.id,ceilingUsd:Number(ceiling),consent:budgetConsent}))}>Aprovar orçamento — ainda não gera mídias</Button>
     </>:<p className="text-sm text-slate-300">Salve as alterações e aprove o storyboard para calcular o orçamento. Mídias prontas compatíveis serão reaproveitadas.</p>}
    </section>
    <section className="rounded border border-cyan-700 p-4 space-y-3"><h3 className="font-semibold">3. Produção autorizada</h3><p className="text-xs text-slate-300">As duas aprovações são exigidas no servidor. Editar o roteiro invalida ambas. Não há novas tentativas pagas automáticas. Fechar esta janela não cancela a produção: acompanhe pelo histórico de filmes.</p>
     <Button data-testid="film-generate" disabled={locked || dirty || film.status!=='budget_approved' || !config?.runway || !config?.narration || !config?.mediaTools} onClick={()=>act(()=>request('/films/'+film.id+'/generate','POST',{revision:film.revision}))}>Gerar mídias e montar filme</Button>
    </section>
    {film.status==='completed'&&<section className="rounded bg-teal-950 p-4 space-y-3"><h3 className="font-semibold">Filme pronto para revisão</h3><video src={API+film.videoUrl} controls preload="metadata" className="w-full rounded"/>
     <a className="block underline" href={API+film.videoUrl} target="_blank" rel="noreferrer">Abrir MP4</a><a className="block underline" href={API+film.subtitlesUrl} target="_blank" rel="noreferrer">Baixar legendas SRT</a>
     <a className="block underline" href={'/editor/'+film.projectId} target="_blank" rel="noreferrer">Revisar projeto independente no Editor</a><p className="text-xs">Também disponível na Biblioteca de Vídeos. Para usar no curso original, adicione pela biblioteca após revisar.</p>
    </section>}
   </aside></div>
  </>}
 </DialogContent></Dialog>;
}
