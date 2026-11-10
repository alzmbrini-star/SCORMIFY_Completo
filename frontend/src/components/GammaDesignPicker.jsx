import React, {useEffect, useRef, useState} from 'react';
import {Button} from './ui/button';
import {Input} from './ui/input';

// Approximate swatches from descriptive keywords, NOT provider theme hex values.
export function indicativePalette(item) {
  const colors = {gold:'#d4a72c',golden:'#d4a72c',yellow:'#facc15',orange:'#fb923c',red:'#ef4444',pink:'#f472b6',purple:'#a78bfa',violet:'#8b5cf6',blue:'#60a5fa',navy:'#1e3a8a',cyan:'#22d3ee',teal:'#2dd4bf',green:'#4ade80',white:'#f8fafc',light:'#e2e8f0',black:'#101827',dark:'#1e293b',gray:'#94a3b8',grey:'#94a3b8',brown:'#92400e',beige:'#e7d4b5',cream:'#fff1d6',metallic:'#cbd5e1',silver:'#cbd5e1'};
  const result = [];
  (item.colors || []).forEach(keyword => String(keyword).toLowerCase().split(/[^a-z]+/).forEach(word => {if (colors[word] && !result.includes(colors[word])) result.push(colors[word]);}));
  return result.length ? result.slice(0,5) : ['#94a3b8','#cbd5e1','#f1f5f9'];
}

export default function GammaDesignPicker({api, value, onChange, disabled}) {
  const [mode, setMode] = useState('auto');
  const [query, setQuery] = useState('');
  const [type, setType] = useState('');
  const [items, setItems] = useState([]);
  const [cursor, setCursor] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [page, setPage] = useState(0);
  const sequence = useRef(0);
  const loadedSearch = useRef({query: '', type: ''});
  async function load(kind, search = '', filter = '', after = '') {
    const request = ++sequence.current;
    setBusy(true); setError('');
    try {
      const params = new URLSearchParams({kind: kind === 'theme' ? 'themes' : 'templates', query: search, themeType: filter, after});
      const result = await api(`/designs?${params}`);
      if (sequence.current !== request) return;
      if (!after) loadedSearch.current = {query: search, type: filter};
      if (!after) setPage(0);
      setItems(previous => after ? [...previous, ...result.items] : result.items);
      setCursor(result.nextCursor || null);
    } catch (e) { if (sequence.current === request) setError(e.message); }
    finally { if (sequence.current === request) setBusy(false); }
  }
  useEffect(() => () => { sequence.current += 1; }, []);
  function changeMode(next) {
    sequence.current += 1; setMode(next); setItems([]); setQuery(''); setType(''); setCursor(null); setError(''); setBusy(false); onChange(null, next !== 'auto');
    if (next !== 'auto') load(next);
  }
  const theme = mode === 'theme';
  const pages = Math.max(1, Math.ceil(items.length/6)), current = Math.min(page,pages-1);
  return <fieldset className="gamma-design" disabled={disabled}>
    <legend>Aparência da apresentação</legend>
    <div className="gamma-design-mode"><label>Como definir o visual?
      <select aria-label="Modo visual Gamma" value={mode} onChange={e => changeMode(e.target.value)}>
        <option value="auto">Automático — orientar pela descrição</option>
        <option value="theme">Escolher tema — cores e fontes</option>
        <option value="template">Escolher modelo — base visual e composição</option>
      </select>
    </label><p>Tema: cores e fontes. Modelo: composição com visual próprio. Escolha um OU outro.</p></div>
    {mode==='auto'&&<div className="gamma-info mt-4">O Gamma define a aparência a partir da sua descrição. Prefere escolher as cores e o estilo? Selecione um tema acima.</div>}
    {mode !== 'auto' && <>
      <div className="gamma-design-search">
        <Input aria-label="Buscar visual Gamma" className="flex-1 min-w-40" placeholder={theme ? 'Buscar tema por nome' : 'Buscar modelo'} value={query} onChange={e => setQuery(e.target.value)} onKeyDown={e => {if (e.key === 'Enter') {e.preventDefault(); load(mode, query, type);}}}/>
        {theme && <select aria-label="Origem dos temas Gamma" className="p-2 rounded border bg-background" value={type} onChange={e => {setType(e.target.value); setItems([]); setCursor(null); load(mode, query, e.target.value);}}>
          <option value="">Todos os temas</option><option value="standard">Padrão Gamma</option><option value="custom">Personalizados da conta</option>
        </select>}
        <Button type="button" variant="outline" disabled={busy} onClick={() => load(mode, query, type)}>Buscar</Button>
      </div>
      <p className="gamma-palette-note">Paletas indicativas: cores aproximadas a partir das descrições do Gamma, não uma prévia exata. Consultar opções não inicia geração.</p>
      {value && <p role="status" className="gamma-design-selected"><span>✓ Selecionado: <strong>{value.name}</strong></span><span>Pronto para gerar</span></p>}
      {busy && <p role="status">Consultando opções no Gamma…</p>}
      {error && <p role="alert" className="text-amber-500">{error} Você pode tentar Buscar novamente ou escolher Automático.</p>}
      {!busy && !error && items.length === 0 && <p>Nenhuma opção encontrada. Tente outro nome ou filtro.</p>}
      <div className="gamma-design-grid" role="group" aria-label={theme ? 'Temas Gamma disponíveis' : 'Modelos Gamma disponíveis'}>
        {items.slice(current*6,current*6+6).map(item => <div key={`${item.source}:${item.id}`} className={`gamma-design-card ${value?.id===item.id?'selected':''} ${/dark|black/.test(String(item.colors?.[0]||item.name).toLowerCase())?'dark':''}`}>
          <button type="button" aria-label={item.name} aria-pressed={value?.id === item.id} onClick={() => onChange({...item, kind: mode})}>
          <div className="gamma-palette" aria-hidden="true">{indicativePalette(item).map(color=><i key={color} style={{backgroundColor:color}}/>)}</div>
          <div className="gamma-design-card-content"><strong>{item.name}</strong>
          <small>{{standard:'Padrão Gamma', custom:'Personalizado da conta', official:'Modelo oficial Gamma', workspace:'Modelo da conta'}[item.source] || 'Gamma'}</small>
          <p>{item.colors?.length>0?item.colors.slice(0,4).join(' · '):'Paleta não informada pelo Gamma'}{item.tones?.length>0?' / '+item.tones.slice(0,2).join(' · '):''}</p>
          {value?.id===item.id&&<span className="gamma-chosen">✓ Selecionado</span>}</div></button>
          {item.url && <a className="underline text-xs" href={item.url} target="_blank" rel="noopener noreferrer">Ver modelo no Gamma</a>}
        </div>)}
      </div>
      {items.length>0&&<div className="gamma-design-pagination"><button type="button" aria-label="Visuais anteriores" disabled={current===0} onClick={()=>setPage(current-1)}>← Anterior</button><span>{current+1} / {pages} · {items.length} opções carregadas</span><button type="button" aria-label="Próximos visuais" disabled={current===pages-1} onClick={()=>setPage(current+1)}>Próximos →</button></div>}
      {cursor && <Button className="gamma-design-load" type="button" variant="outline" disabled={busy} onClick={() => load(mode, loadedSearch.current.query, loadedSearch.current.type, cursor)}>Carregar mais temas</Button>}
      <details className="gamma-help mt-3"><summary>Sobre os temas e modelos</summary><p>Opções da conta Gamma vinculada à chave do servidor. A seleção vale somente para novas gerações. As cores são aproximações ilustrativas. {theme?'Temas personalizados precisam existir na conta Gamma.':'A busca mostra até 25 modelos da conta e 25 oficiais. Refine o nome para localizar outros. Modelos indisponíveis podem ser recusados pelo Gamma, sem substituição silenciosa.'}</p></details>
    </>}
  </fieldset>;
}
