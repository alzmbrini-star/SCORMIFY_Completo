import React, { useEffect, useId, useMemo, useState } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from './ui/dialog';
import { Button } from './ui/button';
import { getApiUrl } from '../utils/apiUrl';
import { authHeaders } from '../contexts/AuthContext';
import { componentLibraryFilter } from '../utils/componentLibraryFilter';

export function sceneModel(html) {
  try {
    const doc = new DOMParser().parseFromString(html, 'text/html');
    const nodes = doc.querySelectorAll('script#scormify-simulator-plan');
    if (nodes.length !== 1) return null;
    const model = JSON.parse(nodes[0].textContent);
    const valid = model && typeof model.title === 'string' && typeof model.mission === 'string'
      && Array.isArray(model.variables) && model.variables.length <= 10 && model.variables.every(v => v && typeof v.id === 'string' && typeof v.label === 'string' && Number.isFinite(v.min) && Number.isFinite(v.max))
      && Array.isArray(model.actions) && model.actions.length <= 18 && model.actions.every(a => a && typeof a.id === 'string' && typeof a.label === 'string' && typeof a.feedback === 'string') && model.maxSteps;
    return valid ? model : null;
  } catch (_) { return null; }
}

export function draftProject(model) {
  const saved = model.visualProject;
  const safe = saved && typeof saved.title === 'string' && typeof saved.description === 'string'
    && Array.isArray(saved.instances) && saved.instances.length <= 6 && saved.instances.every(r => r && typeof r.id === 'string' && typeof r.label === 'string' && r.position && r.inputs && r.actions && Object.values(r.inputs).every(v => v && Array.isArray(v.range)))
    && saved.teaching && typeof saved.teaching.focus === 'string' && typeof saved.teaching.readScene === 'string' && Array.isArray(saved.teaching.links) && saved.teaching.links.every(l => l && typeof l.instance === 'string' && typeof l.input === 'string' && typeof l.whatChanges === 'string' && typeof l.whyItMatters === 'string');
  return safe ? saved : { version: 1, catalogVersion: 2, renderer: 'svg-v1', style: 'studio',
    title: model.title.slice(0, 100), description: model.subtitle || model.mission,
    instances: [], teaching: { focus: model.mission.slice(0, 220), readScene: 'Observe como suas decisões modificam o cenário.', links: [] } };
}

// Links are explicit author descriptions; never modify effects, units or rules.
export function syncLinks(project) {
  const available = project.instances.flatMap(row => Object.entries(row.inputs)
    .filter(([, input]) => input.var).map(([input]) => ({ instance: row.id, input })));
  const retained = project.teaching.links.filter(link => available.some(a => a.instance === link.instance && a.input === link.input));
  const links = [...retained];
  available.forEach(a => { if (links.length < 4 && !links.some(l => l.instance === a.instance && l.input === a.input)) links.push({ ...a, whatChanges: '', whyItMatters: '' }); });
  return { ...project, teaching: { ...project.teaching, links } };
}

export default function ComponentSceneReview({ html, onApply, disabled = false, sessionId, slideIndex, elementIndex }) {
  const model = useMemo(() => sceneModel(html), [html]);
  const [open, setOpen] = useState(false);
  return model ? <>
    <Button variant="outline" disabled={disabled} onClick={() => setOpen(true)}>Revisar projeto visual</Button>
    {open && <Review key={html} model={model} onClose={() => setOpen(false)} onApply={onApply}
      sessionId={sessionId} slideIndex={slideIndex} elementIndex={elementIndex} />}
  </> : null;
}

function Review({ model, onClose, onApply, sessionId, slideIndex, elementIndex }) {
  const [catalog, setCatalog] = useState(null), [project, setProject] = useState(() => draftProject(model));
  const [selection, setSelection] = useState(''), [preview, setPreview] = useState(''), [error, setError] = useState(''), [busy, setBusy] = useState(false);
  const [view, setView] = useState('project');
  const [showAllComponents, setShowAllComponents] = useState(false);
  const library = useMemo(() => componentLibraryFilter(catalog, model, project, showAllComponents), [catalog, model, project, showAllComponents]);
  useEffect(() => { if (selection && !library.entries.some(([id]) => id === selection)) setSelection(''); }, [library, selection]);
  const uid = useId();
  useEffect(() => {
    const controller = new AbortController();
    fetch(`${getApiUrl()}/api/generate-html/jobs/components/catalog`, { headers: authHeaders(), signal: controller.signal })
      .then(async r => { if (!r.ok) throw new Error('Não foi possível carregar a biblioteca.'); return r.json(); })
      .then(setCatalog).catch(e => { if (e.name !== 'AbortError') setError(e.message); });
    return () => controller.abort();
  }, []);
  const edit = next => { setProject(next); setPreview(''); setError(''); };
  const rowEdit = (index, patch) => edit(syncLinks({ ...project, instances: project.instances.map((r, i) => i === index ? { ...r, ...patch } : r) }));
  const add = () => {
    const definition = catalog.components[selection];
    if (!definition || !library.entries.some(([id]) => id === selection) || project.instances.length >= 6) return;
    let n = 1; while (project.instances.some(r => r.id === `piece${n}`)) n++;
    edit({ ...project, catalogVersion: catalog.version, instances: [...project.instances, { id: `piece${n}`, component: selection, version: definition.version,
      label: definition.description.slice(0, 80), position: { x: 20, y: 20 }, inputs: Object.fromEntries(definition.inputs.map(p => [p, { value: 50, range: [0, 100] }])), actions: {},
      ...(definition.variants ? { variant: definition.variants[0] } : {}) }] });
  };
  const request = async save => {
    setBusy(true); setError('');
    try {
      const target = save && sessionId ? `/components/sessions/${encodeURIComponent(sessionId)}` : '/components/preview';
      const response = await fetch(`${getApiUrl()}/api/generate-html/jobs${target}`, {
        method: 'POST', headers: authHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ sourceSimulator: JSON.stringify(model), visualProject: project,
          ...(save && sessionId ? { slideIndex, elementIndex } : {}) }) });
      const result = await response.json();
      if (!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail : 'Projeto inválido. Revise os campos e tente novamente.');
      if (save) { onApply(result.html); onClose(); } else { setPreview(result.html); setView('preview'); }
    } catch (e) { setError(e.message || 'Falha na conexão. O simulador anterior foi preservado.'); }
    finally { setBusy(false); }
  };
  const field = (label, value, change, maxLength = 180) => <label className="block text-sm">{label}<input className="block w-full p-2 border rounded bg-background" value={value} maxLength={maxLength} onChange={e => change(e.target.value)} /></label>;
  return <Dialog open onOpenChange={value => { if (!value && !busy) onClose(); }}>
    <DialogContent className="sm:max-w-6xl max-h-[92vh] overflow-y-auto">
      <DialogHeader><DialogTitle>Projeto visual do simulador</DialogTitle><DialogDescription>Revise, componha as peças e aprove a apresentação antes de aplicá-la.</DialogDescription></DialogHeader>
      <p className="text-sm">{model.title} · Objetivo: {model.mission}</p>
      <p className="text-sm text-muted-foreground">As peças representam os indicadores existentes. Regras, ações, aprovação e métricas não são alteradas. Sem geração paga nesta revisão.</p>
      <details><summary>Revisar decisões e consequências</summary><ul className="text-sm space-y-2">{model.actions.map(a => <li key={a.id}><strong>{a.label}: </strong>{a.feedback}</li>)}</ul></details>
      <nav aria-label="Etapas do projeto visual" className="flex flex-wrap gap-2">{[['project','Objetivo e relações'],['pieces','Cenário e peças'],['preview','Prévia e aprovação']].map(([id,label]) => <Button key={id} variant={view === id ? 'default' : 'outline'} aria-pressed={view === id} disabled={busy} onClick={() => setView(id)}>{label}</Button>)}</nav>
      <fieldset disabled={busy || !catalog} className="space-y-4">
        <div hidden={view !== 'project'}><div className="grid md:grid-cols-2 gap-3">
          {field('Título da cena', project.title, title => edit({ ...project, title }), 100)}
          <label className="text-sm">Acabamento<select className="block w-full p-2 border rounded bg-background" value={project.style} onChange={e => edit({ ...project, style: e.target.value })}><option value="studio">Ilustrado claro</option><option value="blueprint">Técnico escuro</option></select></label>
          {field('Descrição do cenário', project.description, description => edit({ ...project, description }), 600)}
          {field('Foco didático', project.teaching.focus, focus => edit({ ...project, teaching: { ...project.teaching, focus } }), 220)}
        </div></div>
        <div hidden={view !== 'pieces'} className="space-y-4">
        <p className="text-sm">Escolha cenário, personagens e objetos. A ordem define as camadas: o último aparece à frente. A cena usa uma área de 800 × 450.</p>
        <label className="block text-sm" htmlFor={`${uid}-piece`}>Biblioteca de componentes</label>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={showAllComponents} onChange={e => setShowAllComponents(e.target.checked)} />Mostrar biblioteca completa</label>
        <p className="text-xs text-muted-foreground" role="status">Exibindo {library.entries.length} de {library.total} componentes. {library.basis === 'used' ? 'Somente os tipos de peças já usados neste simulador. Peças removidas nesta revisão continuam disponíveis para adicionar novamente.' : library.basis === 'context' ? 'Sugestões relacionadas ao conteúdo deste simulador; ainda não fazem parte da cena.' : library.basis === 'none' ? 'Nenhuma peça da biblioteca foi identificada para este simulador. O desenho personalizado continua preservado; marque a opção acima para procurar outra peça.' : 'Biblioteca completa exibida por sua escolha.'}</p>
        <div className="flex gap-2"><select id={`${uid}-piece`} className="w-full min-w-0 p-2 border rounded bg-background" value={selection} onChange={e => setSelection(e.target.value)}>
          <option value="">{library.entries.length ? 'Selecione uma peça…' : 'Nenhuma peça neste filtro'}</option>{library.entries.map(([id, def]) => <option key={id} value={id}>{def.description}</option>)}
        </select><Button type="button" onClick={add} disabled={!selection || project.instances.length >= 6}>Adicionar peça</Button></div>
        <p className="text-sm text-amber-500">Não encontrou uma peça adequada? Não substitua por um objeto sem relação com o tema. Novos componentes e vídeos de transição ainda exigem uma etapa de produção; não são gerados por este seletor.</p>
        {project.instances.map((row, index) => {
          const def = catalog?.components[row.component];
          return <details className="border rounded p-3 space-y-3" key={row.id} aria-label={`Peça ${index + 1}`}>
            <summary className="cursor-pointer font-semibold">{index + 1}. {row.label}</summary>
            <div className="flex flex-wrap gap-2 items-center">
              <Button type="button" variant="outline" disabled={index === 0} onClick={() => { const rows = [...project.instances]; [rows[index - 1], rows[index]] = [rows[index], rows[index - 1]]; edit({ ...project, instances: rows }); }}>Recuar camada</Button>
              <Button type="button" variant="outline" onClick={() => edit(syncLinks({ ...project, instances: project.instances.filter((_, i) => i !== index) }))}>Remover peça</Button></div>
            <div className="grid md:grid-cols-3 gap-3">{field('Nome acessível da peça', row.label, label => rowEdit(index, { label }), 80)}
              {['x', 'y'].map((axis, i) => <label className="text-sm" key={axis}>Posição {axis.toUpperCase()}<input type="number" min="20" max={(i ? 430 : 780) - (def?.size[i] || 0)} className="block w-full p-2 border rounded bg-background" value={row.position[axis]} onChange={e => rowEdit(index, { position: { ...row.position, [axis]: Number(e.target.value) } })} /></label>)}
              {def?.variants && <label className="text-sm">Personagem<select className="block w-full p-2 border rounded bg-background" value={row.variant || def.variants[0]} onChange={e => rowEdit(index, { variant: e.target.value })}>{def.variants.map(v => <option key={v}>{v}</option>)}</select></label>}
            </div>
            {Object.entries(row.inputs).map(([port, input]) => <div key={port} className="grid md:grid-cols-2 gap-2">
              <label className="text-sm">{port} — indicador<select className="block w-full p-2 border rounded bg-background" value={input.var || ''} onChange={e => { const v = model.variables.find(v => v.id === e.target.value); rowEdit(index, { inputs: { ...row.inputs, [port]: v ? { var: v.id, range: [v.min, v.max] } : { value: 50, range: [0, 100] } } }); }}><option value="">Constante visual (0–100)</option>{model.variables.map(v => <option key={v.id} value={v.id}>{v.label} ({v.min}–{v.max} {v.unit})</option>)}</select></label>
              {!input.var ? <label className="text-sm">Valor constante ({input.range.join('–')})<input className="block w-full p-2 border rounded bg-background" type="number" min={input.range[0]} max={input.range[1]} value={input.value} onChange={e => rowEdit(index, { inputs: { ...row.inputs, [port]: { value: Number(e.target.value), range: input.range } } })} /></label> : <p className="text-sm self-end">Projeção visual: {input.range.join(' → ')}. Escolha somente um indicador que represente esta característica.</p>}
            </div>)}
            {(def?.actions || []).map(slot => <label className="block text-sm" key={slot}>Ação ao clicar: {slot}<select className="block w-full p-2 border rounded bg-background" value={row.actions[slot] || ''} onChange={e => { const actions = { ...row.actions }; if (e.target.value) actions[slot] = e.target.value; else delete actions[slot]; rowEdit(index, { actions }); }}><option value="">Sem ação na peça</option>{model.actions.map(a => <option key={a.id} value={a.id}>{a.label}</option>)}</select></label>)}
          </details>;
        })}
        </div>
        <div hidden={view !== 'project'} className="space-y-4">
        {field('Como o aluno deve ler a cena', project.teaching.readScene, readScene => edit({ ...project, teaching: { ...project.teaching, readScene } }), 700)}
        <p className="text-sm">Relacione pelo menos duas variáveis distintas a mudanças visuais perceptíveis. A validação usa os estados alcançáveis do motor; não certifica a fidelidade científica do desenho.</p>
        {project.teaching.links.map((link, index) => <details key={index} className="border rounded p-3"><summary className="cursor-pointer font-semibold">Relação {index + 1}: {project.instances.find(r => r.id === link.instance)?.label} / {link.input}</summary><div className="grid md:grid-cols-2 gap-3 mt-3">
          <label className="text-sm md:col-span-2">Característica observada<select className="block w-full p-2 border rounded bg-background" value={`${link.instance}/${link.input}`} onChange={e => { const [instance, input] = e.target.value.split('/'); edit({ ...project, teaching: { ...project.teaching, links: project.teaching.links.map((l, n) => n === index ? { instance, input, whatChanges: '', whyItMatters: '' } : l) } }); }}>
            {project.instances.flatMap(row => Object.entries(row.inputs).filter(([,input]) => input.var).map(([port]) => <option key={`${row.id}/${port}`} value={`${row.id}/${port}`}>{row.label} / {port}</option>))}
          </select></label>
          {['whatChanges', 'whyItMatters'].map((key, i) => <React.Fragment key={key}>{field(i ? 'Por que isso importa para aprender?' : 'O que muda visualmente?', link[key], value => edit({ ...project, teaching: { ...project.teaching, links: project.teaching.links.map((l, n) => n === index ? { ...l, [key]: value } : l) } }), i ? 240 : 180)}</React.Fragment>)}
        </div></details>)}
        </div>
      </fieldset>
      <Button type="button" disabled={busy || !catalog} onClick={() => request(false)}>Validar e preparar prévia</Button>
      {busy && <p role="status">Validando o projeto…</p>}
      {error && <p role="alert" className="text-red-500">{error} Seu rascunho visual continua aberto. Se a conexão falhou ao salvar no Agente, reabra o storyboard para confirmar o estado antes de repetir.</p>}
      {view === 'preview' && (preview ? <iframe title="Prévia do projeto visual" srcDoc={preview} sandbox="allow-scripts" className="w-full aspect-video border rounded bg-white" /> : <p>Prepare uma prévia validada para experimentar as ações e aprovar o resultado.</p>)}
      <div className="flex justify-end gap-2"><Button variant="outline" disabled={busy} onClick={onClose}>Cancelar</Button><Button disabled={!preview || busy} onClick={() => request(true)}>{sessionId ? 'Aplicar e salvar no storyboard' : 'Aplicar à prévia do Editor'}</Button></div>
    </DialogContent>
  </Dialog>;
}
