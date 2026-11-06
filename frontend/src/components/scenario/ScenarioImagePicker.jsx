import React,{useEffect,useState} from 'react';
import {Dialog,DialogContent,DialogHeader,DialogTitle} from '../ui/dialog';
import {Input} from '../ui/input';
import {getApiUrl} from '../../utils/apiUrl';
import {authHeaders} from '../../contexts/AuthContext';

export default function ScenarioImagePicker({open,onClose,onSelect}){
 const [images,setImages]=useState([]),[search,setSearch]=useState(''),[error,setError]=useState(''),[loading,setLoading]=useState(false);
 useEffect(()=>{if(!open)return;const controller=new AbortController();setLoading(true);setError('');fetch(getApiUrl()+'/api/gallery/images',{headers:authHeaders(),credentials:'include',signal:controller.signal}).then(r=>{if(!r.ok)throw new Error();return r.json();}).then(d=>setImages(d.images||[])).catch(e=>{if(e.name!=='AbortError')setError('Não foi possível carregar a biblioteca. Tente novamente.');}).finally(()=>{if(!controller.signal.aborted)setLoading(false);});return()=>controller.abort();},[open]);
 const list=images.filter(i=>(i.keywords+' '+i.projectName).toLocaleLowerCase().includes(search.toLocaleLowerCase()));
 return <Dialog open={open} onOpenChange={v=>{if(!v)onClose();}}><DialogContent className="sm:max-w-3xl"><DialogHeader><DialogTitle>Imagem da cena · Biblioteca</DialogTitle></DialogHeader>
  <Input aria-label="Buscar imagem da cena" placeholder="Buscar por tema ou projeto…" value={search} onChange={e=>setSearch(e.target.value)}/>
  {loading?<p role="status">Carregando biblioteca…</p>:error?<p role="alert">{error}</p>:<div className="grid grid-cols-2 sm:grid-cols-3 gap-3 max-h-[55vh] overflow-auto">{list.map(i=><button type="button" className="border rounded-lg overflow-hidden text-left hover:border-teal-500" key={i.id} onClick={()=>{onSelect(i);onClose();}}><img src={i.imageUrl?.startsWith('/')?getApiUrl()+i.imageUrl:i.imageUrl} alt={i.keywords||'Imagem da biblioteca'} className="w-full aspect-video object-cover"/><span className="block p-2 text-xs line-clamp-2">{i.keywords||i.projectName||'Selecionar imagem'}</span></button>)}{!list.length&&<p>Nenhuma imagem encontrada.</p>}</div>}
 </DialogContent></Dialog>;
}
