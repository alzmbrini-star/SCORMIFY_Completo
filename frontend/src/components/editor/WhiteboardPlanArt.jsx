import { useEffect, useState } from 'react';
import { getApiUrl } from '../../utils/apiUrl';
import { authHeaders } from '../../contexts/AuthContext';
import { Button } from '../ui/button';
import { Input } from '../ui/input';

export function WhiteboardIconPreview({ op }) {
  const [strokes,setStrokes]=useState([]);
  useEffect(()=>{
    const controller=new AbortController();setStrokes([]);
    fetch(`${getApiUrl()}/api/whiteboard/icons/${encodeURIComponent(op.name)}`,{headers:authHeaders(),credentials:'include',signal:controller.signal})
      .then(r=>{if(!r.ok)throw new Error();return r.json();}).then(data=>setStrokes(data.strokes||[])).catch(()=>{});
    return ()=>controller.abort();
  },[op.name]);
  const size=op.size||220,color=op.color||'#1f2937';
  const path=s=>'M '+s.map(p=>p.join(',')).join(' L ');
  return <g transform={`translate(${op.x-size/2} ${op.y-size/2}) scale(${size/24})`} aria-label={op.name}>
    {strokes.length? <>
      {op.fill&&strokes.filter(s=>s.length>3&&Math.hypot(s[0][0]-s[s.length-1][0],s[0][1]-s[s.length-1][1])<.1).map((s,i)=><path key={`f${i}`} d={path(s)+' Z'} fill={op.fill} fillOpacity={(op.fill_opacity??85)/100}/>)}
      {strokes.map((s,i)=><path key={i} d={path(s)} fill="none" stroke={color} strokeWidth={(op.width||5)*24/size} strokeLinecap="round" strokeLinejoin="round"/>)}
    </>:<text x="12" y="12" fontSize="2" textAnchor="middle" fill={color}>{op.name}</text>}
  </g>;
}

const normalize=s=>String(s||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();
const hex=v=>/^#[0-9a-f]{6}$/i.test(v||'')?v:'#1f2937';
export default function WhiteboardPlanArt({plan,onChange,disabled}) {
  const [catalog,setCatalog]=useState({names:[],aliases:{}}),[search,setSearch]=useState(''),[chosen,setChosen]=useState(''),[error,setError]=useState('');
  useEffect(()=>{
    const controller=new AbortController();
    fetch(`${getApiUrl()}/api/whiteboard/icons`,{headers:authHeaders(),credentials:'include',signal:controller.signal})
      .then(r=>{if(!r.ok)throw new Error();return r.json();}).then(setCatalog).catch(e=>{if(e.name!=='AbortError')setError('Catálogo temporariamente indisponível. O plano existente foi preservado.');});
    return ()=>controller.abort();
  },[]);
  const matches=(catalog.names||[]).filter(name=>normalize(name).includes(normalize(search))||Object.entries(catalog.aliases||{}).some(([alias,value])=>value===name&&normalize(alias).includes(normalize(search)))).slice(0,60);
  const patch=(index,values)=>onChange(previous=>({...previous,quality:undefined,ops:previous.ops.map((op,i)=>i===index?{...op,...values}:op)}));
  return <details className="rounded border border-slate-600 p-3 text-sm" data-testid="whiteboard-art-controls"><summary className="cursor-pointer font-medium">Desenhos, cores e preenchimentos</summary>
    <p className="my-2 text-xs text-muted-foreground">Ajustes manuais não usam IA. Preenchimentos aparecem depois do contorno, sem cobrir textos. Nos desenhos do catálogo, apenas regiões fechadas são coloridas.</p>
    <div className="grid gap-2 sm:grid-cols-[1fr_1fr_auto]">
      <Input aria-label="Buscar desenhos do Whiteboard" placeholder="Buscar: árvore, casa, coração…" value={search} onChange={e=>{setSearch(e.target.value);setChosen('');}} disabled={disabled}/>
      <select aria-label="Desenho do catálogo" className="min-w-0 rounded border bg-background px-2" value={chosen} onChange={e=>setChosen(e.target.value)} disabled={disabled}><option value="">{matches.length?'Selecione um desenho':'Nenhum desenho encontrado'}</option>{matches.map(name=><option key={name}>{name}</option>)}</select>
      <Button type="button" size="sm" variant="outline" disabled={disabled||!chosen||plan.ops.length>=12} onClick={()=>onChange(previous=>({...previous,quality:undefined,ops:[...previous.ops,{id:`icon_${Date.now()}`,type:'icon',name:chosen,x:960,y:540,size:240,color:'#1f2937',width:6}]}))}>Adicionar desenho</Button>
    </div>{error&&<p role="status" className="mt-2 text-xs text-amber-400">{error}</p>}
    <p className="mt-1 text-xs text-muted-foreground">{catalog.names.length} desenhos disponíveis · até 12 operações por plano. Ajuste a posição para evitar sobreposição.</p>
    <div className="mt-3 space-y-3">{plan.ops.map((op,i)=><fieldset key={op.id||i} disabled={disabled} className="rounded border border-slate-700 p-2"><legend className="px-1 text-xs">{i+1}. {op.text||op.name||op.type}</legend><div className="flex flex-wrap items-center gap-3">
      <label className="text-xs">Traço <input aria-label={`Cor do traço ${i+1}`} type="color" value={hex(op.color)} onChange={e=>patch(i,{color:e.target.value})}/></label>
      {['circle','rectangle','polygon','icon'].includes(op.type)&&<><label className="flex items-center gap-1 text-xs"><input type="checkbox" checked={!!op.fill} onChange={e=>patch(i,{fill:e.target.checked?'#bfdbfe':null})}/>Preencher {i+1}</label>{op.fill&&<><input aria-label={`Cor de preenchimento ${i+1}`} type="color" value={hex(op.fill)} onChange={e=>patch(i,{fill:e.target.value})}/><label className="text-xs">Opacidade <input aria-label={`Opacidade do preenchimento ${i+1}`} type="range" min="10" max="100" value={op.fill_opacity??85} onChange={e=>patch(i,{fill_opacity:Number(e.target.value)})}/></label></>}</>}
      {op.type==='icon'&&['x','y','size'].map(key=><label className="text-xs" key={key}>{key==='size'?'Tamanho':key.toUpperCase()} <input aria-label={`${key} do desenho ${i+1}`} className="w-20 rounded border bg-background p-1" type="number" min={key==='size'?80:0} max={key==='size'?500:key==='x'?1920:1080} value={op[key]} onChange={e=>patch(i,{[key]:Math.max(key==='size'?80:0,Math.min(key==='size'?500:key==='x'?1920:1080,Number(e.target.value)||0))})}/></label>)}
    </div></fieldset>)}</div>
  </details>;
}
