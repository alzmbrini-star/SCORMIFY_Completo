import React, {useEffect, useRef, useState} from 'react';
import {Button} from './ui/button';
import {Input} from './ui/input';

export default function GammaDesignPicker({api, value, onChange, disabled}) {
  const [mode, setMode] = useState('auto');
  const [query, setQuery] = useState('');
  const [type, setType] = useState('');
  const [items, setItems] = useState([]);
  const [cursor, setCursor] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
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
  return <fieldset className="border rounded p-3 space-y-3" disabled={disabled}>
    <legend className="px-1 font-semibold">Aparência da apresentação</legend>
    <label className="block text-sm">Como definir o visual?
      <select aria-label="Modo visual Gamma" className="w-full mt-1 p-2 rounded border bg-background" value={mode} onChange={e => changeMode(e.target.value)}>
        <option value="auto">Automático — orientar pela descrição</option>
        <option value="theme">Escolher tema — cores e fontes</option>
        <option value="template">Escolher modelo — base visual e composição</option>
      </select>
    </label>
    <p className="text-xs text-muted-foreground">Tema define cores e fontes. Modelo usa uma apresentação-base com seu próprio visual. O Gamma aceita um OU outro, não ambos. A seleção vale somente para novas gerações.</p>
    {mode !== 'auto' && <>
      <div className="flex flex-wrap gap-2">
        <Input aria-label="Buscar visual Gamma" className="flex-1 min-w-40" placeholder={theme ? 'Buscar tema por nome' : 'Buscar modelo'} value={query} onChange={e => setQuery(e.target.value)} onKeyDown={e => {if (e.key === 'Enter') {e.preventDefault(); load(mode, query, type);}}}/>
        {theme && <select aria-label="Origem dos temas Gamma" className="p-2 rounded border bg-background" value={type} onChange={e => {setType(e.target.value); setItems([]); setCursor(null); load(mode, query, e.target.value);}}>
          <option value="">Todos os temas</option><option value="standard">Padrão Gamma</option><option value="custom">Personalizados da conta</option>
        </select>}
        <Button type="button" variant="outline" disabled={busy} onClick={() => load(mode, query, type)}>Buscar</Button>
      </div>
      <p className="text-xs text-muted-foreground">Opções da conta Gamma vinculada à chave do servidor. Consultar esta lista não inicia geração. As palavras de cores são descrições fornecidas pelo Gamma, não uma prévia exata de cada slide.</p>
      {value && <p role="status" className="text-sm font-semibold">Selecionado: {value.name}</p>}
      {busy && <p role="status">Consultando opções no Gamma…</p>}
      {error && <p role="alert" className="text-amber-500">{error} Você pode tentar Buscar novamente ou escolher Automático.</p>}
      {!busy && !error && items.length === 0 && <p>Nenhuma opção encontrada. Tente outro nome ou filtro.</p>}
      <div className="max-h-64 overflow-y-auto grid gap-2 sm:grid-cols-2" role="group" aria-label={theme ? 'Temas Gamma disponíveis' : 'Modelos Gamma disponíveis'}>
        {items.map(item => <div key={`${item.source}:${item.id}`} className={`border rounded p-3 space-y-1 ${value?.id === item.id ? 'ring-2 ring-primary' : ''}`}>
          <button type="button" className="text-left w-full font-semibold" aria-pressed={value?.id === item.id} onClick={() => onChange({...item, kind: mode})}>{item.name}</button>
          <p className="text-xs text-muted-foreground">{{standard:'Padrão Gamma', custom:'Personalizado da conta', official:'Modelo oficial Gamma', workspace:'Modelo da conta'}[item.source] || 'Gamma'}</p>
          {item.colors?.length > 0 && <p className="text-xs">Cores: {item.colors.join(' · ')}</p>}
          {item.tones?.length > 0 && <p className="text-xs">Estilo: {item.tones.join(' · ')}</p>}
          {item.url && <a className="underline text-xs" href={item.url} target="_blank" rel="noopener noreferrer">Ver modelo no Gamma</a>}
        </div>)}
      </div>
      {cursor && <Button type="button" variant="outline" disabled={busy} onClick={() => load(mode, loadedSearch.current.query, loadedSearch.current.type, cursor)}>Carregar mais temas</Button>}
      {!theme && <p className="text-xs text-muted-foreground">A busca mostra até 25 modelos da conta e 25 oficiais. Refine o nome para localizar outros. Modelos indisponíveis podem ser recusados pelo Gamma, sem substituição silenciosa.</p>}
      {!value && <p className="text-sm">Selecione uma opção para habilitar a geração.</p>}
    </>}
  </fieldset>;
}
